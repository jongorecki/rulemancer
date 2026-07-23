"""Generation: turn retrieved rules into a cited answer.

Days 6-9. Retrieves the top-k chunks with pure vector (the Phase C decision:
hybrid didn't help, vector's top-10 is the best simple candidate set), hands
them to Claude, and gets back a structured Answer -- cited, and honest when
the rules don't cover the question (the low-confidence / groundedness guard).

Reads ANTHROPIC_API_KEY from the environment (.env). Model is pinned for
reproducible answer evals -- see DECISIONS.md.
"""

import logging

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from rulesagent.contracts import Answer, Card, CardFace, Retrieved
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.crossrefs import expand_crossrefs
from rulesagent.retrieve.hybrid import rrf_fuse
from rulesagent.retrieve.rewrite import rewrite_query
from rulesagent.tools.ruling_retrieval import ruling_id, select_rulings, select_rulings_union
from rulesagent.tools.scryfall import ATTRIBUTION, get_card, parse_card_refs

load_dotenv()

logger = logging.getLogger(__name__)

GEN_MODEL = "claude-sonnet-5"  # pinned; one-line swap to A/B other models
TOP_K = 15  # pure-vector top-15 (raised from 10: near-miss rules like a
# multiplayer clause at rank ~13 were just outside the old window)

PROMPT_VERSION = 3
# Bump on EVERY change to SYSTEM or the Answer schema, and note what changed.
# Stamped into the public-demo query log so feedback stays interpretable
# across deploys (plan-limitations-and-deploy.md L8).
#   v1: through the 31/31 grade + trust-the-ruling + transcript-in-message.
#   v2: L8 batch -- tldr, suggested_followups, cite-rulings-by-label.
#   v3: docs/plan-prompt-tuning.md Sec 1 (Jon-approved 2026-07-22) -- six
#   bullets targeting F1 full-card-names, F2 mana-symbol semantics, F4
#   multiplayer defaults (replaces the old bullet), F5 timing-assumption
#   disclosure, F7 card-text-overrides-rules, and F3/F6 direct-answer-first.

# Plan #3a: the winning rewriter config from evals/run_eval.py's 2x2 grid
# (rewrite count x rewriter model, see docs/plan-3a-query-rewriting.md).
# Kept as module constants -- not inlined below -- so picking a different
# cell later is a one-line change here rather than a code change.
REWRITE_MODEL = "claude-haiku-4-5"
REWRITE_N = 1
REWRITE_FUSION_DEPTH = 100  # candidates pulled per rewrite before RRF fusion
# when REWRITE_N > 1 -- matches evals/run_eval.py's DEPTH, so production
# retrieval is fused at the same depth the eval actually measured, not a
# smaller ad hoc one.

SYSTEM = (
    "You are a Magic: The Gathering rules expert. Answer the user's question "
    "using ONLY the numbered rules provided in the context below. Rules are "
    "labeled with their number in brackets, e.g. [104.3a].\n"
    # 1a (F1 card-role confusion) -- new first bullet, before the old [1].
    "- Always refer to a card by its exact full name, every time you mention "
    "it in your reasoning and in the answer text -- never by a role word "
    "(\"the attacker,\" \"the blocker,\" \"the creature,\" \"it\") once two or "
    "more named cards are in the question. If you find yourself about to "
    "write a role word for a card, stop and substitute its full name "
    "instead.\n"
    "- Cite the exact rule numbers you relied on in the citations field. Every "
    "rule number you reference anywhere in the answer text MUST also appear in "
    "the citations field, and whenever answered is true the citations field MUST "
    "be non-empty -- that field is what makes the answer verifiable, so an "
    "answer that relies on rules can never leave it blank. If you genuinely "
    "cannot ground the answer in any provided rule, set answered to false "
    "instead of answering without citations.\n"
    "- If the provided rules don't contain enough to answer, set answered to "
    "false and say what's missing -- do NOT fill the gap with outside "
    "knowledge or guesses.\n"
    "- Define any key term the question hinges on (e.g. what 'phasing' means) "
    "so the answer stands on its own.\n"
    # 1b (F2 mana-symbol semantics) -- new, right after the define-key-term
    # bullet.
    "- Mana symbols are not interchangeable. {N} (a plain number) means N "
    "generic mana, payable with any color or with colorless mana. {C} means "
    "colorless mana specifically -- it is NOT generic and NOT interchangeable "
    "with {N}. {G}/{U}/{B}/{R}/{W} mean mana of that one color specifically. "
    "When a cost-reduction or cost-increase effect says it reduces or "
    "increases \"the mana cost\" or \"the generic mana\" of a spell, only the "
    "generic portion changes -- any colored or colorless symbols in the cost "
    "are unaffected. When you state a resulting total cost, break it out by "
    "symbol rather than only giving a lump number.\n"
    "- Name the specific zones, steps, or objects involved rather than "
    "referring to them vaguely (e.g. the command zone and exile are separate "
    "zones).\n"
    # 1c (F4 multiplayer defaults) -- REPLACES the old "If the provided rules
    # cover multiplayer or Commander cases..." bullet.
    "- Unless the question specifies exactly two players, don't assume a "
    "two-player game. If the provided context includes any rule about "
    "multiplayer play (choosing a defending player, \"each opponent,\" turn "
    "order among more than two players, etc.), say how the answer differs, if "
    "at all, between two players and more than two. If the context contains "
    "ONLY two-player-framed rules, say plainly that your answer is for the "
    "two-player case and that a multiplayer table may follow different rules "
    "-- do not invent multiplayer rules that weren't provided.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it.\n"
    # 1d (F5 unstated timing/ordering assumptions) -- new, right after the
    # accurate-and-to-the-point bullet.
    "- If the order or timing of events in the question is ambiguous (for "
    "example, exactly when damage was marked relative to a spell being cast "
    "or resolving), say plainly which timing you're assuming, then add one "
    "short sentence on how the answer would change under a different timing. "
    "Never resolve an ambiguous timing question as if only one order were "
    "possible without saying so.\n"
    "- You may also be given specific cards' oracle text and rulings, "
    "labeled \"Card data\" below the rules context. Treat that as additional "
    "ground truth alongside the rules -- if you rely on a card, cite it by "
    "name in the citations field, the same way you cite rule numbers.\n"
    # 1e (F7 card-text-overrides-rules) -- new, right after the card-data
    # bullet.
    "- A card's own printed rules text always wins over a general rule it "
    "contradicts. If a card's text says something that conflicts with how a "
    "general rule would otherwise apply, follow the card's text and say so "
    "explicitly (name the specific text and note that card text overrides "
    "the general rule) rather than applying the general rule as if the card "
    "were silent.\n"
    "- A provided ruling is itself authoritative, self-sufficient grounding. If "
    "a ruling directly states what happens in the interaction, rely on it and "
    "answer -- do NOT decline or hedge just because the underlying numbered rule "
    "isn't also in the context. (You still must not invent rules or rulings that "
    "weren't provided.)\n"
    "- Card rulings in the context are labeled like \"[Card Name ruling #4]\". "
    "When you rely on a ruling, put that exact label in the citations field, "
    "the same way you cite rule numbers.\n"
    # 1f (F3 intent misses + F6 answer clarity, merged) -- new, right after
    # the ruling-label bullet and before tldr.
    "- Open the text field with a direct, unmistakable answer to the "
    "question -- the first sentence or two should say plainly what happens, "
    "not lead with caveats or setup. Put reasoning, assumptions, and "
    "secondary discussion after that direct answer, never before it. If the "
    "question can reasonably be read two ways (for example, \"who gets "
    "priority\" could mean right after a spell is cast or right after it "
    "resolves), answer the reading actually asked first and explicitly, then "
    "briefly cover the other reading if it's a likely point of confusion -- "
    "don't let a second reading delay or bury the direct answer to the "
    "first.\n"
    "- Fill the tldr field with one or two plain sentences that directly answer "
    "the question for a player in a hurry -- no rule numbers, no hedging "
    "boilerplate. If answered is false, the tldr plainly says the provided "
    "rules don't settle it.\n"
    "- Fill suggested_followups with two or three short natural next questions "
    "a curious player might ask after reading this answer, each under about "
    "twelve words."
)


def _format_context(retrieved: list[Retrieved]) -> str:
    return "\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)


def build_prompt(question: str, retrieved: list[Retrieved], cards: list[Card],
                 convo_ctx: str | None = None,
                 rewrite_queries: list[str] | None = None) -> tuple[str, str]:
    """Assemble the exact (system, user) prompt pair the generator is called
    with. Extracted from RulesAgent.answer() (plan-openrouter-models.md) so
    the OpenRouter A/B arms generate from the byte-identical prompt the
    pinned Anthropic path sees -- tests/fixtures/prompt_identity.json guards
    that this stays true. `convo_ctx` is the condensed transcript (None =
    single-turn); `rewrite_queries` is the show_rewrite transparency block
    (None = off, the shipped default)."""
    context = _format_context(retrieved)
    user = f"Rules context:\n{context}"
    if cards:
        # Card data goes in AFTER the rules context, per Jon's call in
        # the plan -- it enriches generation, it never touches
        # retrieval or the (unchanged) rewrite step.
        user += f"\n\nCard data:\n{_format_cards(cards)}"
    user += f"\n\nQuestion: {question}"
    if rewrite_queries is not None:
        # Jon's idea: let the generator see BOTH the user's own words and
        # the reinterpretation retrieval actually searched on, so the
        # stronger model can notice when they've drifted apart. A
        # transparency/faithfulness lever, not a recall one -- see the
        # show_rewrite flag notes in RulesAgent.__init__.
        searched = "\n".join(f"- {q}" for q in rewrite_queries)
        user += (
            f"\n\nFor context: to search the rules, that question was "
            f"reinterpreted as:\n{searched}\n"
            "Answer the question the user actually asked. If the "
            "reinterpretation drifted from their intent, or the rules "
            "retrieved answer a broader or narrower question than they "
            "asked, say so plainly rather than answering the "
            "reinterpretation."
        )
    system = SYSTEM
    if convo_ctx is not None:
        system = SYSTEM + (
            "\n- This conversation has earlier turns, provided as a "
            "transcript at the top of the message. Read the final question "
            "in their context -- it may refine or correct an earlier one -- "
            "but ground the answer ONLY in the rules and card data provided."
        )
        user = f"Conversation so far (for context only):\n{convo_ctx}\n\n{user}"
    return system, user


def _degenerate(a: Answer) -> bool:
    """A parseable draw that is nonetheless a non-answer: declined, cited
    nothing, and said almost nothing. Deliberately narrow so an HONEST decline
    -- answered=false with a real explanation of what's missing (200+ chars
    across the eval history) -- never matches. The 80-char bound clears the
    observed degenerate specimens (0 and ~70 chars, 2026-07-22) with margin."""
    if not a.answered:
        return not a.citations and len(a.text.strip()) < 80
    # answered=True but no actual content: q029 (2026-07-21, L1 gate 4) drew
    # answered:true with fully blank text. Deliberately blank-only (not a
    # length threshold) so a legitimately short answered=True answer never
    # matches -- that's the only shape observed.
    return not a.text.strip()


def _face_block(f: CardFace, label: str = "") -> str:
    """One face rendered as a header line (name, cost, type, P/T or loyalty or
    defense, color indicator) followed by its oracle text."""
    header = label + f.name
    if f.mana_cost:
        header += f" {f.mana_cost}"
    attrs = []
    if f.type_line:
        attrs.append(f.type_line)
    if f.power != "" or f.toughness != "":
        attrs.append(f"{f.power}/{f.toughness}")
    if f.loyalty:
        attrs.append(f"loyalty {f.loyalty}")
    if f.defense:
        attrs.append(f"defense {f.defense}")
    if f.color_indicator:
        attrs.append("color indicator " + "/".join(f.color_indicator))
    if attrs:
        header += " -- " + " -- ".join(attrs)
    return header + (f"\n{f.oracle_text}" if f.oracle_text else "")


def _format_cards(cards: list[Card]) -> str:
    # Enrich with every printed, rules-relevant field, layout-first: a
    # single-faced card folds its card-level meta (mana value, color identity,
    # layout) onto its one header line; a multi-face card leads with the layout
    # + meta, then renders EACH face so the generator sees each face's own cost
    # and type (docs/plan-card-enrichment-fields.md).
    parts = []
    for c in cards:
        meta = []
        if c.layout and c.layout != "normal":
            meta.append(c.layout)
        meta.append(f"MV {c.mana_value:g}")
        if c.color_identity:
            meta.append("color identity " + "/".join(c.color_identity))
        meta_str = ", ".join(meta)

        lines = []
        if len(c.faces) > 1:
            lines.append(f"{c.name}  ({meta_str})")
            for i, f in enumerate(c.faces, 1):
                lines.append(_face_block(f, label=f"Face {i}: "))
        else:
            f = c.faces[0] if c.faces else CardFace(
                name=c.name, oracle_text=c.oracle_text,
                type_line=c.type_line, mana_cost=c.mana_cost,
            )
            first, _, rest = _face_block(f).partition("\n")
            lines.append(f"{first}  ({meta_str})")
            if rest:
                lines.append(rest)

        if c.rulings:
            lines.append("Rulings:")
            lines.extend(f"- {r}" for r in c.rulings)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


class RulesAgent:
    def __init__(self, store: VectorStore, client: anthropic.Anthropic | None = None,
                 model: str = GEN_MODEL, k: int = TOP_K, rewrite: bool = True,
                 show_rewrite: bool = False, card_no_refresh: bool = False,
                 ruling_select: bool = True, rewrite_version: str = "v2",
                 ruling_query_mode: str = "raw"):
        self.store = store
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.k = k
        self.rewrite = rewrite
        self.show_rewrite = show_rewrite
        self.card_no_refresh = card_no_refresh
        self.ruling_select = ruling_select
        # Selectable rewriter prompt version (docs/plan-prompt-tuning.md Sec
        # 2, Task 1 in docs/plan-v3-execution-tasks.md), threaded straight
        # into every rewrite_query() call below -- "v1" (byte-identical to
        # the pre-v2 rewriter prompt) or "v2" (default; adds the mana-symbol
        # and multiplayer-phrasing bullets). The prompt-v3 A/B's condition B
        # runs gen-v3 + rewrite-v1 on purpose, so this must stay overridable
        # per agent instance, not hardcoded to the new default.
        self.rewrite_version = rewrite_version
        if ruling_query_mode not in ("raw", "union"):
            raise ValueError(f"ruling_query_mode must be 'raw' or 'union', got {ruling_query_mode!r}")
        # Part B ruling-query union toggle (docs/plan-l1-crossref-expansion.md
        # Part B; exposed for real generation here -- previously only
        # runnable as a measurement-only report via evals/run_openrouter_arm
        # .py's `--ruling-query union`, which never touched RulesAgent or a
        # generated answer). "raw" (default, unchanged): select_rulings()
        # scores each card's rulings against the bare question only. "union":
        # select_rulings_union() scores against the question UNIONED with the
        # rewriter's own rewrite phrasing(s), so a ruling can clear the
        # relevance floor via whichever angle actually matches it. Needs
        # `rewrite=True` to have any rewrites to union with; falls back to a
        # one-query union (just the question) when rewrite=False, which is
        # still a valid select_rulings_union() call.
        self.ruling_query_mode = ruling_query_mode
        # Cross-ref expansion (L1, docs/plan-l1-crossref-expansion.md): id ->
        # Chunk, built ONCE here from the store's own chunks so expand_crossrefs
        # can resolve a "see rule X" mention without re-parsing the CR. Same
        # dict api/main.py used to build itself in its lifespan -- the agent is
        # now its one owner, and the API reads agent.chunk_map instead.
        # getattr-guarded: a store double that only implements .search() (e.g.
        # tests/test_prompt_identity.py's _FrozenStore) has no .chunks, and
        # should degrade to an empty map -- expand_crossrefs then resolves
        # nothing and appends nothing, an inert no-op -- rather than crash.
        self.chunk_map = {c.source_id: c for c in getattr(store, "chunks", [])}
        # Per-card ruling mini-RAG (plan-rulings-on-demand.md): when True (the
        # default), a referenced card's rulings are relevance-filtered against
        # the question instead of dumped wholesale. False restores the old
        # dump-all behavior, so the answer eval can A/B the two.
        self.last_ruling_selection: dict | None = None
        # {card name -> [ruling_id, ...]} chosen on the last answer() call (None
        # if ruling_select is off). Read by the rulings-recall eval, mirroring
        # last_rewritten.
        self.last_cards: list | None = None
        self.last_retrieved: list | None = None
        # Also recorded per answer() call, for the API to build an enriched
        # response: the resolved cards used (each already carrying its
        # mini-RAG-selected rulings) and the retrieved rule chunks. Not part of
        # the Answer contract -- read right after answer(), same pattern as
        # last_rewritten / last_ruling_selection.
        # Passed straight through to get_card()'s no_refresh -- eval-
        # reproducibility freeze mode (plan #3b): use any cached card entry
        # regardless of its TTL age, so a card eval re-run is byte-
        # identical instead of drifting if Scryfall adds a ruling mid-eval.
        # Default False: the live/interactive path wants TTL freshness.
        # show_rewrite (EXPERIMENTAL, default OFF): hand the generator the
        # rewrite alongside the user's original wording (see answer() below) so
        # it can flag when retrieval drifted from intent. Default off because
        # an early spot-check showed the extra instruction can make the model
        # cite rules in prose while leaving the structured `citations` field
        # empty -- which breaks the exact field the groundedness eval reads. A
        # flag, not hardcoded, so the answer eval can A/B it (--show-rewrite)
        # and only adopt it if it earns its keep. No effect when rewrite=False.
        # rewrite=True is the shipped default (plan #3a, Jon's "Decided:
        # always-on"): rewriting measurably helps retrieval and the honest
        # cost -- one extra LLM call plus ~1-2s of latency per question -- is
        # small enough to always pay rather than gate behind an overfit
        # confidence threshold. See docs/plan-3a-query-rewriting.md.
        self.last_rewritten = None
        # Set by answer() on every call when rewrite=True (None otherwise).
        # Not part of the Answer contract -- callers that need the rewrites
        # used or the clarification for a given answer (e.g.
        # evals/run_answer_eval.py, recording them alongside the answer)
        # read it right after calling answer() rather than answer() growing
        # a second return value.
        self.last_crossref: dict | None = None
        # Set by answer() on every call: {"refs_found": [...], "appended":
        # [...], "skipped": [...]} from expand_crossrefs -- so a label-like
        # ref that resolved to no chunk (e.g. 701.5 "Cast") is an observable
        # miss, not a silent one. Same pattern as last_rewritten.
        self.last_unresolved_refs: list[dict] | None = None
        # Set by answer() on every call (c012 observability, docs/plan-q029-
        # empty-answer-guard.md Plan B): [{"ref": ..., "reason": "not_found" |
        # "error"}, ...] for every `[bracket]` token that failed to resolve to
        # a Card, either a confirmed Scryfall miss or a fetch exception (the
        # latter previously crashed the whole request). Same lifecycle/
        # pattern as last_crossref -- read right after answer() by the API.

    def answer(self, question: str, history: list[dict] | None = None) -> Answer:
        """`history` (optional): prior conversation turns, oldest first, each
        {"role": "user"|"assistant", "content": text}. history=None is the
        single-turn path and behaves exactly as before the parameter existed
        (same prompt string, same caches) -- the evals run single-turn, so
        their numbers are untouched by conversation support."""
        history = history or []
        self.last_rewritten = None
        # Parse `[Card Name]` / `[oracle-id]` tokens BEFORE anything else
        # touches the question. `question` from here on is bracket-stripped
        # ("[Dovescape]" -> "Dovescape") -- what the rewriter sees, what the
        # generator sees as the question -- so the rewriter and the
        # no-brackets path are untouched: a question with no tokens comes
        # back unchanged and `cards` stays [].
        question, card_refs = parse_card_refs(question)
        # Cards referenced in EARLIER user turns stay in play: a follow-up
        # ("what if it's in the graveyard?") rarely repeats the [bracket], but
        # the card's data is still what grounds the answer. Union, oldest
        # first, deduped case-insensitively; the Scryfall cache makes the
        # repeat lookups free.
        seen: set[str] = set()
        all_refs: list[str] = []
        for turn in history:
            if turn.get("role") == "user":
                _, hist_refs = parse_card_refs(turn.get("content", ""))
                all_refs.extend(hist_refs)
        all_refs.extend(card_refs)
        all_refs = [r for r in all_refs if not (r.lower() in seen or seen.add(r.lower()))]
        # Unresolvable tokens (typo'd past fuzzy match, made-up name) are
        # silently dropped rather than erroring the whole answer -- the
        # rules-only answer still has a shot at being useful. Not specified
        # by the plan either way; this is the call made here. c012
        # observability (docs/plan-q029-empty-answer-guard.md Plan B): both
        # failure shapes -- a confirmed miss (get_card -> None) and a
        # transient fetch error (get_card raises) -- are now recorded on
        # last_unresolved_refs and logged, instead of vanishing (or, for a
        # raise, crashing the whole request) with zero trace. Broad
        # `except Exception` on purpose: it's the audit trail for any fetch
        # failure, not just the ones we've anticipated.
        resolved, unresolved = [], []
        for ref in all_refs:
            try:
                c = get_card(ref, no_refresh=self.card_no_refresh)
            except Exception as e:
                logger.warning("card ref failed to resolve (fetch error): %r: %r", ref, e)
                unresolved.append({"ref": ref, "reason": "error"})
                continue
            if c is None:
                logger.warning("card ref failed to resolve (not found): %r", ref)
                unresolved.append({"ref": ref, "reason": "not_found"})
                continue
            resolved.append(c)
        cards = resolved
        self.last_unresolved_refs = unresolved

        # Condensed transcript for the rewriter: a follow-up like "what about
        # while it's phased out?" only rewrites into a useful standalone search
        # query if the rewriter can see what "it" was. Last 6 turns, each
        # clipped -- enough to resolve references without bloating the call.
        convo_ctx = None
        if history:
            lines = []
            for turn in history[-6:]:
                who = "User" if turn.get("role") == "user" else "Assistant"
                text = (turn.get("content") or "").strip()
                if len(text) > 500:
                    text = text[:500] + " …"
                lines.append(f"{who}: {text}")
            convo_ctx = "\n".join(lines)

        # Rewrite is computed here, BEFORE ruling selection, so a
        # ruling_query_mode="union" selection below can union the rewrite's
        # own phrasing(s) into what it scores rulings against (docs/plan-l1-
        # crossref-expansion.md Part B). This is a pure reorder from the
        # original post-ruling-selection position -- the retrieval search
        # itself still runs at the same point in the pipeline as before
        # (right after ruling selection, unchanged), so for the default
        # ruling_query_mode="raw" path this has no effect on retrieval
        # results or the assembled prompt (guarded by
        # tests/test_prompt_identity.py).
        rewritten = None
        if self.rewrite:
            rewritten = rewrite_query(question, REWRITE_MODEL, REWRITE_N, self.client,
                                      context=convo_ctx, version=self.rewrite_version)
            self.last_rewritten = rewritten

        self.last_ruling_selection = None
        if self.ruling_select:
            # Ruling mini-RAG: replace each card's full ruling list with only
            # the ones relevant to the (stripped, pre-rewrite) question. A card
            # with no relevant ruling contributes none -- rulings withheld, the
            # rules-RAG + oracle text stand alone.
            selection, picked = {}, []
            for card in cards:
                if self.ruling_query_mode == "union":
                    # Part B: union the raw question with the rewrite's own
                    # phrasing(s) so a ruling can clear the relevance floor
                    # via whichever angle actually matches it. Falls back to
                    # a one-query union (just the question) when rewrite is
                    # off / produced nothing -- still a valid
                    # select_rulings_union() call. Deduplicated (order-
                    # preserving) per select_rulings_union()'s own docstring
                    # ("queries should be passed already-deduplicated") -- a
                    # single-query rewrite (REWRITE_N=1) commonly equals the
                    # raw question verbatim or falls back to it on error, and
                    # a duplicate query would just waste one redundant embed
                    # call rather than change the result.
                    all_queries = [question] + (rewritten.queries if rewritten is not None else [])
                    union_queries = list(dict.fromkeys(all_queries))
                    sel = select_rulings_union(card, union_queries)
                else:
                    sel = select_rulings(card, question)
                selection[card.name] = [ruling_id(card, i) for i, _ in sel]
                # Label each ruling with its ORIGINAL Scryfall index so the
                # model can cite it precisely ("[Name ruling #4]") and the
                # cited label maps back to the gold oracle_id#index (L8).
                picked.append(card.model_copy(update={"rulings": [
                    f"[{card.name} ruling #{i}] {card.rulings[i]}" for i, _ in sel]}))
            cards, self.last_ruling_selection = picked, selection
        else:
            # Dump-all A/B path gets the same labels, so the cite-by-label
            # convention holds in both configs.
            cards = [c.model_copy(update={"rulings": [
                f"[{c.name} ruling #{i}] {r}" for i, r in enumerate(c.rulings)]})
                for c in cards]
        self.last_cards = cards

        if self.rewrite:
            if len(rewritten.queries) == 1:
                # Nothing to fuse with one rewrite -- search it directly.
                retrieved = self.store.search(rewritten.queries[0], self.k)
            else:
                rankings = [self.store.search(q, REWRITE_FUSION_DEPTH) for q in rewritten.queries]
                retrieved = rrf_fuse(rankings)[: self.k]
                # Deliberately NOT fusing the original question back in here
                # -- the plan's spike measured that hurting every arm it was
                # tried on. See evals/run_eval.py's `+orig` variant.
        else:
            retrieved = self.store.search(question, self.k)
        # Cross-ref expansion (L1): a pure post-ranking step -- runs AFTER
        # retrieval/rewrite/fusion have already produced the organic top-k,
        # so it can't move any rank the retrieval eval measures. No LLM call,
        # no recursion (one hop only), no prompt-shape change: appended
        # chunks are just more `[id] text` blocks after the organic ones.
        crossref_debug: dict = {}
        retrieved = expand_crossrefs(retrieved, self.chunk_map, debug=crossref_debug)
        self.last_crossref = crossref_debug
        self.last_retrieved = retrieved
        # Empty/invalid structured output happens INTERMITTENTLY on
        # claude-sonnet-5 (c018 came back empty on two eval runs, then answered
        # cleanly on retry -- diagnosed at ~600 thinking + ~1600 output tokens,
        # nowhere near the 16384 cap, so it is NOT budget/thinking exhaustion).
        # So keep max_tokens at 16384 and RETRY once before degrading. Raising
        # the cap is not the fix and actively backfires: max_tokens=32768 trips
        # the SDK's non-streaming 10-minute-timeout guard and errors the call.
        # Multi-turn (docs/plan-multiturn-stability.md): the conversation goes
        # into the final user message as a condensed TRANSCRIPT block -- the
        # same clipped form the rewriter consumes -- NOT as real prose
        # assistant messages. Injecting prose turns measurably destabilized
        # structured output (~50% degenerate answered=false draws on the
        # Grist/Animate Dead thread, 2026-07-22) -- plausibly because a
        # transcript of prose assistant replies contradicts the JSON reply
        # format, or because history citing rules absent from the current
        # context trips the grounding guard. With the transcript inlined, the
        # message list is single-turn-shaped in every case. Gated on `history`
        # so the single-turn path -- and therefore every eval number -- stays
        # byte-identical.
        system, user = build_prompt(
            question, retrieved, cards,
            convo_ctx=convo_ctx,
            rewrite_queries=(self.last_rewritten.queries
                             if self.show_rewrite and self.last_rewritten is not None
                             else None),
        )
        msgs: list[dict] = [{"role": "user", "content": user}]
        parsed, response = None, None
        weak = None  # best parseable-but-degenerate draw, kept as a fallback
        for _attempt in range(2):
            try:
                response = self.client.messages.parse(
                    model=self.model,
                    max_tokens=16384,
                    system=system,
                    messages=msgs,
                    output_format=Answer,
                )
                parsed = response.parsed_output
            except ValidationError:
                # messages.parse RAISES on empty content rather than returning
                # parsed_output=None -- treat both the same: retry, then degrade.
                parsed = None
            if parsed is not None and _degenerate(parsed):
                # Parsed fine but it's a degenerate non-answer (answered=false,
                # no citations, ~empty text) -- the weak-draw class the old
                # retry couldn't see because it only caught parse FAILURES.
                # Retry once, same budget as the parse-failure retry; keep the
                # longer draw in case both come back degenerate. An honest
                # decline explains what's missing (200+ chars in the eval
                # history) so it doesn't match _degenerate and is never
                # retried away.
                if weak is None or len(parsed.text) > len(weak.text):
                    weak = parsed
                parsed = None
            if parsed is not None:
                break
        if parsed is None and weak is not None and not weak.answered:
            # Only an honest answered=false decline is ever reused as a
            # fallback -- a still-blank answered=true `weak` (q029, L1 gate 4)
            # falls through to the honest non-answer Answer below instead of
            # ever being returned as if it were real content.
            parsed = weak
        if parsed is None:
            # Both attempts came back empty/invalid -- honest non-answer, not a
            # crash. Rare after the retry; a persistent failure is worth seeing.
            stop = response.stop_reason if response is not None else "error"
            return Answer(
                text="(no structured answer: the model returned empty output "
                f"twice, stop_reason={stop} -- try again)",
                tldr="Something went wrong generating this answer -- try again.",
                citations=[],
                answered=False,
                suggested_followups=[],
            )
        if cards:
            # Minimal approach consistent with the Answer contract (no new
            # field): append the Fan Content Policy attribution to the
            # prose whenever Scryfall card data was in the prompt at all,
            # rather than trying to detect post hoc whether the model
            # "relied on" it -- the citations field already covers which
            # specific rules/cards it leaned on.
            parsed.text = f"{parsed.text}\n\n{ATTRIBUTION}"
        return parsed

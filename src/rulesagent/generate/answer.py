"""Generation: turn retrieved rules into a cited answer.

Days 6-9. Retrieves the top-k chunks with pure vector (the Phase C decision:
hybrid didn't help, vector's top-10 is the best simple candidate set), hands
them to Claude, and gets back a structured Answer -- cited, and honest when
the rules don't cover the question (the low-confidence / groundedness guard).

Reads ANTHROPIC_API_KEY from the environment (.env). Model is pinned for
reproducible answer evals -- see DECISIONS.md.
"""

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from rulesagent.contracts import Answer, Card, CardFace, Retrieved
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.hybrid import rrf_fuse
from rulesagent.retrieve.rewrite import rewrite_query
from rulesagent.tools.ruling_retrieval import ruling_id, select_rulings
from rulesagent.tools.scryfall import ATTRIBUTION, get_card, parse_card_refs

load_dotenv()

GEN_MODEL = "claude-sonnet-5"  # pinned; one-line swap to A/B other models
TOP_K = 15  # pure-vector top-15 (raised from 10: near-miss rules like a
# multiplayer clause at rank ~13 were just outside the old window)

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
    "- Name the specific zones, steps, or objects involved rather than "
    "referring to them vaguely (e.g. the command zone and exile are separate "
    "zones).\n"
    "- If the provided rules cover multiplayer or Commander cases, address "
    "them too, not just the two-player case.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it.\n"
    "- You may also be given specific cards' oracle text and rulings, "
    "labeled \"Card data\" below the rules context. Treat that as additional "
    "ground truth alongside the rules -- if you rely on a card, cite it by "
    "name in the citations field, the same way you cite rule numbers.\n"
    "- A provided ruling is itself authoritative, self-sufficient grounding. If "
    "a ruling directly states what happens in the interaction, rely on it and "
    "answer -- do NOT decline or hedge just because the underlying numbered rule "
    "isn't also in the context. (You still must not invent rules or rulings that "
    "weren't provided.)"
)


def _format_context(retrieved: list[Retrieved]) -> str:
    return "\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)


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
                 ruling_select: bool = True):
        self.store = store
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.k = k
        self.rewrite = rewrite
        self.show_rewrite = show_rewrite
        self.card_no_refresh = card_no_refresh
        self.ruling_select = ruling_select
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
        cards = [c for ref in all_refs if (c := get_card(ref, no_refresh=self.card_no_refresh)) is not None]
        # Unresolvable tokens (typo'd past fuzzy match, made-up name) are
        # silently dropped rather than erroring the whole answer -- the
        # rules-only answer still has a shot at being useful. Not specified
        # by the plan either way; this is the call made here.
        self.last_ruling_selection = None
        if self.ruling_select:
            # Ruling mini-RAG: replace each card's full ruling list with only
            # the ones relevant to the (stripped, pre-rewrite) question. A card
            # with no relevant ruling contributes none -- rulings withheld, the
            # rules-RAG + oracle text stand alone.
            selection, picked = {}, []
            for card in cards:
                sel = select_rulings(card, question)
                selection[card.name] = [ruling_id(card, i) for i, _ in sel]
                picked.append(card.model_copy(update={"rulings": [card.rulings[i] for i, _ in sel]}))
            cards, self.last_ruling_selection = picked, selection
        self.last_cards = cards
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
        if self.rewrite:
            rewritten = rewrite_query(question, REWRITE_MODEL, REWRITE_N, self.client,
                                      context=convo_ctx)
            self.last_rewritten = rewritten
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
        self.last_retrieved = retrieved
        context = _format_context(retrieved)
        user = f"Rules context:\n{context}"
        if cards:
            # Card data goes in AFTER the rules context, per Jon's call in
            # the plan -- it enriches generation, it never touches
            # retrieval or the (unchanged) rewrite step above.
            user += f"\n\nCard data:\n{_format_cards(cards)}"
        user += f"\n\nQuestion: {question}"
        if self.show_rewrite and self.last_rewritten is not None:
            # Jon's idea: let the generator see BOTH the user's own words and
            # the reinterpretation retrieval actually searched on, so the
            # stronger model can notice when they've drifted apart. The
            # generator has always answered the ORIGINAL question (the
            # `Question:` line above is `question`, never a rewrite) -- what
            # this adds is the ability to SAY the retrieved rules answer a
            # differently-scoped question than the one asked, instead of
            # silently answering whatever was retrieved.
            #
            # This cannot recover a chunk that retrieval never surfaced -- a
            # missed rule is missed regardless of how well intent is
            # understood. It's a transparency/faithfulness lever, not a
            # recall one, so it's graded on the ANSWER eval, not recall@k.
            searched = "\n".join(f"- {q}" for q in self.last_rewritten.queries)
            user += (
                f"\n\nFor context: to search the rules, that question was "
                f"reinterpreted as:\n{searched}\n"
                "Answer the question the user actually asked. If the "
                "reinterpretation drifted from their intent, or the rules "
                "retrieved answer a broader or narrower question than they "
                "asked, say so plainly rather than answering the "
                "reinterpretation."
            )
        # Empty/invalid structured output happens INTERMITTENTLY on
        # claude-sonnet-5 (c018 came back empty on two eval runs, then answered
        # cleanly on retry -- diagnosed at ~600 thinking + ~1600 output tokens,
        # nowhere near the 16384 cap, so it is NOT budget/thinking exhaustion).
        # So keep max_tokens at 16384 and RETRY once before degrading. Raising
        # the cap is not the fix and actively backfires: max_tokens=32768 trips
        # the SDK's non-streaming 10-minute-timeout guard and errors the call.
        # Multi-turn: prior turns become real conversation messages ahead of
        # the final user message (which alone carries the rules/card context),
        # and the system prompt gains a context-reading line. Both are gated on
        # `history` so the single-turn path -- and therefore every eval number
        # -- stays byte-identical.
        system = SYSTEM
        msgs: list[dict] = [{"role": "user", "content": user}]
        if history:
            system = SYSTEM + (
                "\n- This conversation has earlier turns. Read the final "
                "question in their context -- it may refine or correct an "
                "earlier one -- but ground the answer ONLY in the rules and "
                "card data provided in the final message."
            )
            msgs = [{"role": t["role"], "content": t["content"]} for t in history] + msgs
        parsed, response = None, None
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
            if parsed is not None:
                break
        if parsed is None:
            # Both attempts came back empty/invalid -- honest non-answer, not a
            # crash. Rare after the retry; a persistent failure is worth seeing.
            stop = response.stop_reason if response is not None else "error"
            return Answer(
                text="(no structured answer: the model returned empty output "
                f"twice, stop_reason={stop} -- try again)",
                citations=[],
                answered=False,
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

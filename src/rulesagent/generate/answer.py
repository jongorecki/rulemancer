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

from rulesagent.contracts import Answer, Card, Retrieved
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.hybrid import rrf_fuse
from rulesagent.retrieve.rewrite import rewrite_query
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
    "name in the citations field, the same way you cite rule numbers."
)


def _format_context(retrieved: list[Retrieved]) -> str:
    return "\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)


def _format_cards(cards: list[Card]) -> str:
    parts = []
    for c in cards:
        block = f"{c.name}\n{c.oracle_text}"
        if c.rulings:
            rulings = "\n".join(f"- {r}" for r in c.rulings)
            block += f"\nRulings:\n{rulings}"
        parts.append(block)
    return "\n\n".join(parts)


class RulesAgent:
    def __init__(self, store: VectorStore, client: anthropic.Anthropic | None = None,
                 model: str = GEN_MODEL, k: int = TOP_K, rewrite: bool = True,
                 show_rewrite: bool = False, card_no_refresh: bool = False):
        self.store = store
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.k = k
        self.rewrite = rewrite
        self.show_rewrite = show_rewrite
        self.card_no_refresh = card_no_refresh
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

    def answer(self, question: str) -> Answer:
        self.last_rewritten = None
        # Parse `[Card Name]` / `[oracle-id]` tokens BEFORE anything else
        # touches the question. `question` from here on is bracket-stripped
        # ("[Dovescape]" -> "Dovescape") -- what the rewriter sees, what the
        # generator sees as the question -- so the rewriter and the
        # no-brackets path are untouched: a question with no tokens comes
        # back unchanged and `cards` stays [].
        question, card_refs = parse_card_refs(question)
        cards = [c for ref in card_refs if (c := get_card(ref, no_refresh=self.card_no_refresh)) is not None]
        # Unresolvable tokens (typo'd past fuzzy match, made-up name) are
        # silently dropped rather than erroring the whole answer -- the
        # rules-only answer still has a shot at being useful. Not specified
        # by the plan either way; this is the call made here.
        if self.rewrite:
            rewritten = rewrite_query(question, REWRITE_MODEL, REWRITE_N, self.client)
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
        # 8192: claude-sonnet-5 runs adaptive thinking by default, and thinking
        # tokens draw from max_tokens. 4096 was enough for the 31 rules-only
        # questions, but card questions carry far more context (oracle text +
        # all rulings) and are harder interactions, so thinking ran longer and
        # ate the whole budget -- leaving EMPTY structured output. Doubling the
        # budget gives thinking room AND leaves space for the answer.
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM,
                messages=[{"role": "user", "content": user}],
                output_format=Answer,
            )
            parsed = response.parsed_output
        except ValidationError:
            # Safety net: if the model still returns empty/invalid content
            # (thinking consumed the whole budget), messages.parse RAISES a
            # ValidationError rather than returning parsed_output=None -- so
            # the None-guard below never fires and the crash propagates. Catch
            # it and degrade to an honest non-answer instead of taking the
            # whole pipeline down. Raising max_tokens above should make this
            # rare; this keeps a truncation from ever being fatal.
            return Answer(
                text="(no structured answer: the model returned empty output, "
                "likely truncated -- try again or raise max_tokens)",
                citations=[],
                answered=False,
            )
        if parsed is None:
            # incomplete/blocked output -- treat as an honest non-answer
            return Answer(
                text=f"(no structured answer; stop_reason={response.stop_reason})",
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

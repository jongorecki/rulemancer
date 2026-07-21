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

from rulesagent.contracts import Answer, Retrieved
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.hybrid import rrf_fuse
from rulesagent.retrieve.rewrite import rewrite_query

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
    "- Cite the exact rule numbers you relied on in the citations field.\n"
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
    "act on it."
)


def _format_context(retrieved: list[Retrieved]) -> str:
    return "\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)


class RulesAgent:
    def __init__(self, store: VectorStore, client: anthropic.Anthropic | None = None,
                 model: str = GEN_MODEL, k: int = TOP_K, rewrite: bool = True,
                 show_rewrite: bool = True):
        self.store = store
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.k = k
        self.rewrite = rewrite
        self.show_rewrite = show_rewrite
        # show_rewrite: hand the generator the rewrite alongside the user's
        # original wording (see answer() below). A flag rather than a
        # hardcoded behavior so it can be A/B'd on the answer eval --
        # --show-rewrite / --no-show-rewrite in evals/run_answer_eval.py --
        # instead of being assumed to help. No effect when rewrite=False.
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
        user = f"Rules context:\n{context}\n\nQuestion: {question}"
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
        # 4096: claude-sonnet-5 runs adaptive thinking by default, and thinking
        # tokens draw from max_tokens -- too small a budget gets eaten by
        # thinking and truncates the structured answer to nothing.
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_format=Answer,
        )
        parsed = response.parsed_output
        if parsed is None:
            # incomplete/blocked output -- treat as an honest non-answer
            return Answer(
                text=f"(no structured answer; stop_reason={response.stop_reason})",
                citations=[],
                answered=False,
            )
        return parsed

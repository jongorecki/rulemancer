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

load_dotenv()

GEN_MODEL = "claude-sonnet-5"  # pinned; one-line swap to A/B other models
TOP_K = 10  # pure-vector top-10 feeds the generator (Phase C: 81% recall@10)

SYSTEM = (
    "You are a Magic: The Gathering rules expert. Answer the user's question "
    "using ONLY the numbered rules provided in the context below. Rules are "
    "labeled with their number in brackets, e.g. [104.3a].\n"
    "- Cite the exact rule numbers you relied on in the citations field.\n"
    "- If the provided rules don't contain enough to answer, set answered to "
    "false and say what's missing -- do NOT fill the gap with outside "
    "knowledge or guesses.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it."
)


def _format_context(retrieved: list[Retrieved]) -> str:
    return "\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)


class RulesAgent:
    def __init__(self, store: VectorStore, client: anthropic.Anthropic | None = None,
                 model: str = GEN_MODEL, k: int = TOP_K):
        self.store = store
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.k = k

    def answer(self, question: str) -> Answer:
        retrieved = self.store.search(question, self.k)
        context = _format_context(retrieved)
        user = f"Rules context:\n{context}\n\nQuestion: {question}"
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_format=Answer,
        )
        return response.parsed_output

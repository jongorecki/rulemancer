"""BM25 keyword index over Chunks. Phase A of retrieval -- pure Python, no
API key, no cost. See DESIGN.md's retrieval table (BM25 / vector / hybrid /
+rerank); this is the first column.
"""

import re

from rank_bm25 import BM25Okapi

from rulesagent.contracts import Chunk, Retrieved

_TOKEN_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    """Lowercase + \\w+ tokens. Deliberately simple for Phase A -- if MTG's
    symbol jargon ({T}, +1/+1) turns out to matter, we'll see it in the
    retrieval failures and specialize then, rather than guessing now."""
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._bm25 = BM25Okapi([tokenize(c.text) for c in chunks])

    def search(self, query: str, k: int = 10) -> list[Retrieved]:
        scores = self._bm25.get_scores(tokenize(query))
        # top-k by score, highest first
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [Retrieved(chunk=self.chunks[i], score=float(scores[i])) for i in ranked]

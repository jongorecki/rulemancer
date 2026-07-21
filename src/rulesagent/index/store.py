"""NumPy-array vector store -- the pinned-stack choice, no vector database.

At ~3,600 chunks a brute-force cosine search over one (N, 1024) matrix is a
single matrix-vector product: milliseconds. Standing up a vector DB here would
be answering a scale problem we don't have. The eval harness times this so the
"brute force is fast enough" claim is measured, not asserted.

Embeddings are computed once and pickled (they cost API calls); every later
run loads from disk. Self-contained: the pickle holds the chunks alongside the
matrix, so a loaded store needs nothing else to answer a query.
"""

import pickle
from pathlib import Path

import numpy as np

from rulesagent.contracts import Chunk, Retrieved
from rulesagent.index.embed import embed_documents, embed_query


class VectorStore:
    def __init__(self, model: str, chunks: list[Chunk], embeddings: np.ndarray):
        self.model = model
        self.chunks = chunks
        self.embeddings = embeddings  # (N, dim), L2-normalized

    @classmethod
    def build(cls, chunks: list[Chunk], model: str) -> "VectorStore":
        embeddings = embed_documents([c.text for c in chunks], model)
        return cls(model, chunks, embeddings)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {"model": self.model, "chunks": self.chunks, "embeddings": self.embeddings},
                f,
            )

    @classmethod
    def load(cls, path: str | Path) -> "VectorStore":
        with open(path, "rb") as f:
            data = pickle.load(f)
        return cls(data["model"], data["chunks"], data["embeddings"])

    def search_vec(self, qvec: np.ndarray, k: int = 10) -> list[Retrieved]:
        """Search with an already-embedded, normalized query vector. Splitting
        this out lets the eval pass CACHED query vectors for reproducibility --
        Voyage returns slightly different query embeddings on repeated calls,
        which would otherwise wobble ranks at the top-k boundary."""
        # both sides are L2-normalized, so the dot product IS cosine similarity
        scores = self.embeddings @ qvec  # (N,)
        ranked = np.argsort(-scores)[:k]
        return [Retrieved(chunk=self.chunks[i], score=float(scores[i])) for i in ranked]

    def search(self, query: str, k: int = 10) -> list[Retrieved]:
        return self.search_vec(embed_query(query, self.model), k)

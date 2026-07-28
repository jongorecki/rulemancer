"""NumPy-array vector store -- the pinned-stack choice, no vector database.

At ~3,600 chunks a brute-force cosine search over one (N, 1024) matrix is a
single matrix-vector product: milliseconds. Standing up a vector DB here would
be answering a scale problem we don't have. The eval harness times this so the
"brute force is fast enough" claim is measured, not asserted.

Embeddings are computed once and pickled (they cost API calls); every later
run loads from disk. Self-contained: the pickle holds the chunks alongside the
matrix, so a loaded store needs nothing else to answer a query.
"""

import hashlib
import json
import pickle
from pathlib import Path

import numpy as np

from rulesagent.cache import KVCache
from rulesagent.contracts import Chunk, Retrieved
from rulesagent.index.embed import embed_documents, embed_query

# Query-embedding cache (task-caching-report.md Change 2). Same KVCache /
# per-key-hash pattern src/rulesagent/tools/ruling_retrieval.py already uses
# for ruling embeddings -- one table in the shared data/cache.db, keyed by
# embedding model + a hash of the exact query text.
#
# This is a LATENCY optimization, not a cost one -- be accurate about that
# distinction in comments and anywhere this gets reported. embed_query()
# costs about $0.000005/call, roughly a ten-thousandth of one generation call
# (~$0.0485), so caching it saves essentially no money. What it saves is one
# API round trip -- typically ~100-300ms -- on every search() call after the
# first time a given (model, query) pair is seen.
_query_emb_cache = KVCache("query_emb")


def _query_emb_key(model: str, query: str) -> str:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"{model}#{digest}"


def _cached_embed_query(query: str, model: str) -> np.ndarray:
    """embed_query(), fronted by _query_emb_cache. A cache HIT returns the
    exact vector recorded from the first real call for this (model, query)
    pair, so it does not reintroduce the wobble search_vec()'s docstring
    warns about (Voyage returning slightly different embeddings for the
    same query on repeated live calls) -- it just avoids paying for that
    call more than once per distinct query."""
    key = _query_emb_key(model, query)
    raw = _query_emb_cache.get(key)
    if raw is not None:
        return np.array(json.loads(raw), dtype=np.float32)
    vec = embed_query(query, model)
    _query_emb_cache.put(key, json.dumps(vec.tolist()).encode("utf-8"))
    return vec


class VectorStore:
    def __init__(self, model: str, chunks: list[Chunk], embeddings: np.ndarray):
        self.model = model
        self.chunks = chunks
        self.embeddings = embeddings  # (N, dim), L2-normalized

    @classmethod
    def build(cls, chunks: list[Chunk], model: str) -> "VectorStore":
        embeddings = embed_documents([c.embed_text for c in chunks], model)
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
        return self.search_vec(_cached_embed_query(query, self.model), k)

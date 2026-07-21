"""Hybrid retrieval -- fuse a BM25 ranking and a vector ranking into one.

Two fusion methods, because BM25 and cosine scores live on incomparable
scales (BM25 sums are unbounded; cosine is ~0-1), so you can't just add them:

- Reciprocal Rank Fusion (rrf_fuse): ignore raw scores entirely, combine on
  RANK position. score(chunk) = sum over lists of 1/(k_rrf + rank). No
  normalization, no weight to tune. The robust default.
- Weighted score fusion (weighted_fuse): min-max normalize each list's scores
  to 0-1, then blend with per-retriever weights. More expressive (can lean
  toward the stronger retriever) at the cost of a weight to tune and a
  normalization that can wobble per query.

Both take a list of rankings (each a list[Retrieved], best-first) and return a
single fused list[Retrieved], best-first. A chunk missing from a list simply
contributes nothing from that retriever -- so appearing in both is rewarded.
"""

from collections import defaultdict

from rulesagent.contracts import Chunk, Retrieved


def rrf_fuse(rankings: list[list[Retrieved]], k_rrf: int = 60) -> list[Retrieved]:
    scores: dict[str, float] = defaultdict(float)
    chunks: dict[str, Chunk] = {}
    for ranking in rankings:
        for rank, r in enumerate(ranking, start=1):
            scores[r.chunk.source_id] += 1.0 / (k_rrf + rank)
            chunks[r.chunk.source_id] = r.chunk
    order = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [Retrieved(chunk=chunks[cid], score=scores[cid]) for cid in order]


def weighted_fuse(rankings: list[list[Retrieved]], weights: list[float]) -> list[Retrieved]:
    combined: dict[str, float] = defaultdict(float)
    chunks: dict[str, Chunk] = {}
    for ranking, w in zip(rankings, weights):
        if not ranking:
            continue
        raw = [r.score for r in ranking]
        lo, hi = min(raw), max(raw)
        span = (hi - lo) or 1.0
        for r in ranking:
            combined[r.chunk.source_id] += w * ((r.score - lo) / span)
            chunks[r.chunk.source_id] = r.chunk
    order = sorted(combined, key=lambda cid: combined[cid], reverse=True)
    return [Retrieved(chunk=chunks[cid], score=combined[cid]) for cid in order]


class Hybrid:
    """Production hybrid retriever: wraps base retrievers (each exposing
    .search(query, k)) and fuses their results. Used once we plug a single
    retriever into the agent; the eval harness fuses inline for efficiency.
    """

    def __init__(self, bases, method: str = "rrf", weights=None, k_rrf: int = 60, depth: int = 100):
        self.bases = bases
        self.method = method
        self.weights = weights
        self.k_rrf = k_rrf
        self.depth = depth

    def search(self, query: str, k: int = 10) -> list[Retrieved]:
        rankings = [b.search(query, self.depth) for b in self.bases]
        if self.method == "rrf":
            fused = rrf_fuse(rankings, self.k_rrf)
        elif self.method == "weighted":
            fused = weighted_fuse(rankings, self.weights)
        else:
            raise ValueError(f"unknown fusion method: {self.method}")
        return fused[:k]

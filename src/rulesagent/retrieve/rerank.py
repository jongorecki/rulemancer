"""Reranking -- stage two. A first-stage retriever returns a candidate pool;
the reranker (a cross-encoder) rereads the query against each candidate's full
text TOGETHER (not via pre-computed vectors) and reorders them. That joint read
is why it can fix "the right chunk was in the pool but not the top 5."

Voyage's rerank API. Reads VOYAGE_API_KEY from the environment.
"""

import voyageai
from dotenv import load_dotenv

from rulesagent.contracts import Retrieved

load_dotenv()

_client = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client()
    return _client


def rerank(query: str, candidates: list[Retrieved], model: str, top_k: int | None = None) -> list[Retrieved]:
    """Reorder `candidates` by the reranker's relevance score, best-first.
    Returns up to top_k Retrieved (all of them if top_k is None), carrying the
    reranker's relevance score."""
    if not candidates:
        return []
    docs = [c.chunk.text for c in candidates]
    result = _get_client().rerank(query, docs, model=model, top_k=top_k or len(candidates))
    return [
        Retrieved(chunk=candidates[r.index].chunk, score=r.relevance_score)
        for r in result.results
    ]

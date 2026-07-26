"""Maximal Marginal Relevance: pick k results that are relevant AND distinct.

Why this exists (docs/spec-retrieval-diversity.md): the v3 relabel showed
retrieval is healthy at finding *one* relevant rule and close to non-functional
at getting two or three DISTINCT ones into the window -- `groups` recall@15 is
10.1%, `all` is 0.0%. Cosine similarity is the direct cause: near-duplicate
rules (613.3 / 613.7a / 613.8a) score almost identically and eat the window
together, crowding out the second rule a multi-rule question needs.

MMR selects greedily, trading relevance against redundancy:

    lambda * rel[i]  -  (1 - lambda) * max_{j in selected} cos(i, j)

lambda = 1.0 is pure relevance (and so reproduces the input ranking), lambda = 0
is pure diversity. This is a pure function -- no I/O, no API, no global state --
so it costs nothing to run and is trivially testable with toy vectors.
"""

import numpy as np

from rulesagent.contracts import Retrieved


def _normalize_relevance(scores: np.ndarray) -> np.ndarray:
    """Min-max the pool's scores into [0, 1].

    Load-bearing, not cosmetic. RRF scores sit around 1/61 while cosine
    similarities sit around 0.3-0.8, so mixing them raw would make `lambda`
    mean something completely different on a hybrid arm than on a vector arm --
    the sweep would then be measuring that scale mismatch rather than the
    diversity trade-off it exists to measure.

    Degenerate pool (every score identical) -> all zeros, which carries no
    relevance signal and leaves selection to the diversity term and the
    input-order tie-break. That is the honest answer: a pool whose scores are
    all equal genuinely does not rank.
    """
    lo, hi = float(scores.min()), float(scores.max())
    if hi <= lo:
        return np.zeros_like(scores)
    return (scores - lo) / (hi - lo)


def mmr_select(
    candidates: list[Retrieved],
    vecs: np.ndarray,
    k: int,
    lambda_: float,
) -> list[Retrieved]:
    """Select up to `k` of `candidates` by MMR, most-relevant-first.

    `vecs` is (M, dim), row-aligned with `candidates`, and MUST be L2-normalised
    -- `VectorStore.embeddings` already guarantees that, so a dot product IS
    cosine similarity and no renormalising is needed here.

    Returns the selected `Retrieved` objects UNCHANGED (original scores intact),
    so downstream scoring (`hit_at` and friends, which read
    `chunk.source_id`) behaves identically to any other ranking.

    Determinism: `np.argmax` returns the FIRST maximal index, so ties break by
    input order and repeated calls on the same input are byte-identical. This
    matters because the whole eval is built on frozen query vectors to keep
    run-to-run numbers comparable; a tie-break that wobbled would undo that.

    At `lambda_ = 1.0` the diversity term drops out entirely and the result is
    the pool ordered by descending score -- i.e. the input ranking's top-k, for
    the sorted input that every real retriever produces. tests/test_mmr.py
    asserts exactly that, and it is the self-test worth trusting: if it fails,
    the relevance term is wrong and every other number this produces is noise.
    """
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError(f"lambda_ must be in [0, 1], got {lambda_}")
    m = len(candidates)
    if m == 0:
        return []
    if vecs.shape[0] != m:
        raise ValueError(f"vecs has {vecs.shape[0]} rows for {m} candidates")
    k = min(k, m)

    rel = _normalize_relevance(np.array([c.score for c in candidates], dtype=float))
    sim = vecs @ vecs.T  # (M, M) cosine, both sides already L2-normalised

    chosen = np.zeros(m, dtype=bool)
    # max similarity of each candidate to anything selected so far. -inf until
    # the first pick, so the first selection is driven by relevance alone --
    # which is what MMR specifies, not an approximation of it.
    max_sim = np.full(m, -np.inf)
    order: list[int] = []

    for _ in range(k):
        if order:
            obj = lambda_ * rel - (1.0 - lambda_) * max_sim
        else:
            obj = lambda_ * rel
        obj = np.where(chosen, -np.inf, obj)
        pick = int(np.argmax(obj))
        order.append(pick)
        chosen[pick] = True
        max_sim = np.maximum(max_sim, sim[pick])

    return [candidates[i] for i in order]

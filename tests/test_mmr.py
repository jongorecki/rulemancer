"""Tests for MMR selection (docs/spec-retrieval-diversity.md).

The load-bearing one is `test_lambda_one_reproduces_input_ranking`: at
lambda = 1.0 the diversity term drops out, so MMR MUST return the input
ranking's top-k unchanged. If that fails, the relevance term is wrong and every
number the diversity experiment produces is noise.
"""

import numpy as np
import pytest

from rulesagent.contracts import Chunk, Retrieved
from rulesagent.retrieve.mmr import mmr_select


def _r(source_id: str, score: float) -> Retrieved:
    return Retrieved(
        chunk=Chunk(
            source_id=source_id,
            kind="rule",
            section="Game Concepts",
            text=f"text of {source_id}",
            embed_text=f"embed of {source_id}",
        ),
        score=score,
    )


def _unit(rows: list[list[float]]) -> np.ndarray:
    """L2-normalise toy vectors -- mmr_select's contract requires unit rows."""
    a = np.array(rows, dtype=float)
    return a / np.linalg.norm(a, axis=1, keepdims=True)


def test_lambda_one_reproduces_input_ranking():
    """THE self-test. Pure relevance must not reorder a sorted ranking."""
    cands = [_r(f"r{i}", 1.0 - i * 0.1) for i in range(6)]
    vecs = _unit([[1, 0], [1, 0.01], [1, 0.02], [0, 1], [0, 1], [1, 0]])
    out = mmr_select(cands, vecs, k=4, lambda_=1.0)
    assert [x.chunk.source_id for x in out] == ["r0", "r1", "r2", "r3"]


def test_lambda_one_full_pool_is_identity():
    cands = [_r(f"r{i}", 1.0 - i * 0.1) for i in range(5)]
    vecs = _unit([[1, 0]] * 5)
    out = mmr_select(cands, vecs, k=5, lambda_=1.0)
    assert [x.chunk.source_id for x in out] == [f"r{i}" for i in range(5)]


def test_diversity_promotes_the_distinct_candidate():
    """Three near-identical vectors and one distinct one: with diversity on,
    the distinct candidate is taken second even though it ranks last on score.
    This is precisely the 613.3/613.7a/613.8a failure mode the experiment
    exists to attack."""
    cands = [_r("dup0", 1.0), _r("dup1", 0.99), _r("dup2", 0.98), _r("far", 0.10)]
    vecs = _unit([[1, 0], [1, 0.01], [1, 0.02], [0, 1]])

    greedy = mmr_select(cands, vecs, k=2, lambda_=1.0)
    assert [x.chunk.source_id for x in greedy] == ["dup0", "dup1"]

    diverse = mmr_select(cands, vecs, k=2, lambda_=0.5)
    assert [x.chunk.source_id for x in diverse] == ["dup0", "far"]


def test_lambda_zero_is_pure_diversity():
    cands = [_r("dup0", 1.0), _r("dup1", 0.99), _r("far", 0.10)]
    vecs = _unit([[1, 0], [1, 0.01], [0, 1]])
    out = mmr_select(cands, vecs, k=2, lambda_=0.0)
    assert [x.chunk.source_id for x in out] == ["dup0", "far"]


def test_scores_and_chunks_pass_through_unchanged():
    cands = [_r("a", 0.9), _r("b", 0.4)]
    vecs = _unit([[1, 0], [0, 1]])
    out = mmr_select(cands, vecs, k=2, lambda_=0.5)
    assert {(x.chunk.source_id, x.score) for x in out} == {("a", 0.9), ("b", 0.4)}


def test_k_larger_than_pool_returns_whole_pool():
    cands = [_r("a", 0.9), _r("b", 0.4)]
    vecs = _unit([[1, 0], [0, 1]])
    out = mmr_select(cands, vecs, k=50, lambda_=0.5)
    assert len(out) == 2


def test_empty_pool():
    assert mmr_select([], np.zeros((0, 2)), k=5, lambda_=0.5) == []


def test_deterministic_across_calls():
    cands = [_r(f"r{i}", 1.0 - i * 0.05) for i in range(10)]
    rng = np.random.default_rng(0)
    vecs = _unit(rng.normal(size=(10, 8)).tolist())
    a = mmr_select(cands, vecs, k=5, lambda_=0.5)
    b = mmr_select(cands, vecs, k=5, lambda_=0.5)
    assert [x.chunk.source_id for x in a] == [x.chunk.source_id for x in b]


def test_ties_break_by_input_order():
    """All scores and all vectors identical -> nothing distinguishes the
    candidates, so the input order must survive."""
    cands = [_r(f"r{i}", 0.5) for i in range(4)]
    vecs = _unit([[1, 0]] * 4)
    out = mmr_select(cands, vecs, k=3, lambda_=0.5)
    assert [x.chunk.source_id for x in out] == ["r0", "r1", "r2"]


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_rejects_lambda_out_of_range(bad):
    with pytest.raises(ValueError):
        mmr_select([_r("a", 1.0)], _unit([[1, 0]]), k=1, lambda_=bad)


def test_rejects_misaligned_vecs():
    with pytest.raises(ValueError):
        mmr_select([_r("a", 1.0), _r("b", 0.5)], _unit([[1, 0]]), k=1, lambda_=0.5)

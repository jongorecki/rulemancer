"""Tests for the graded retrieval coverage metric (docs/spec-coverage-metric.md).

Covers:
  - coverage_at() / coverage_from_ids() (evals/run_eval.py): the flat formula,
    including the degenerate cases the spec calls out by name -- empty gold
    (excluded, not scored as 0), single-rule gold, and a match:"any"
    multi-rule row where coverage and hit_at() disagree.
  - The apostrophe-normalization trap hit_at() already guards against
    (normalize_source_id on both sides) applies identically to coverage.
  - evals/backfill_coverage.py's pure helpers: hit_bool_from_ids() is checked
    for exact equivalence with the untouched hit_at(), and resolve_gold_groups
    / score_row / build_worklist are exercised directly.

Does NOT touch hit_at()/gold_groups() -- only imports and calls them, to
prove the new code agrees with the old, unchanged code.
"""
from __future__ import annotations

from rulesagent.contracts import Chunk, EvalQuestion, Retrieved

import run_eval
import backfill_coverage as bc


def mk_chunk(source_id: str, kind: str = "rule") -> Chunk:
    return Chunk(source_id=source_id, kind=kind, section="Test", text="",
                 embed_text="")


def mk_ranking(source_ids: list[str]) -> list[Retrieved]:
    return [Retrieved(chunk=mk_chunk(sid), score=1.0) for sid in source_ids]


# --------------------------------------------------------------------------
# coverage_from_ids -- the plain-id formula (the one the backfill runs on)
# --------------------------------------------------------------------------

def test_coverage_from_ids_full_and_partial():
    assert run_eval.coverage_from_ids(["104.3a"], ["104.3a"]) == 1.0
    assert run_eval.coverage_from_ids(["104.3a"], ["999.9z"]) == 0.0
    # 2 of 4 gold ids present -> exactly 0.5, not rounded, not boolean.
    assert run_eval.coverage_from_ids(
        ["a", "b", "c", "d"], ["a", "b", "x", "y"]
    ) == 0.5


def test_coverage_from_ids_empty_gold_is_none_not_zero():
    """Empty-gold rows (10.9% of the full 1,409-question corpus, 153 rows --
    confirmed directly against evals/rulesguru_full_v2.jsonl) must be excluded
    from any mean, never scored as 0. Scoring them 0 would make retrieval look
    worse than it is on more than a tenth of the corpus for a property of the
    QUESTION, not of retrieval."""
    assert run_eval.coverage_from_ids([], ["104.3a"]) is None
    assert run_eval.coverage_from_ids([], []) is None


def test_empty_gold_excluded_from_mean_not_scored_as_zero():
    """The convention in practice: filter Nones out before averaging. A naive
    `sum(values)/len(values)` with None-as-0 would drag every arm's mean down
    by exactly its empty-gold share; filtering first (what backfill_coverage
    and run_eval's n_scored both do) leaves the mean measuring only rows that
    could ever hit."""
    raw = [
        run_eval.coverage_from_ids(["a"], ["a"]),       # 1.0
        run_eval.coverage_from_ids([], ["a"]),          # None (empty gold)
        run_eval.coverage_from_ids(["a", "b"], ["a"]),  # 0.5
    ]
    scored = [c for c in raw if c is not None]
    assert scored == [1.0, 0.5]
    assert sum(scored) / len(scored) == 0.75  # not 0.5 (which None-as-0 would give)


def test_coverage_from_ids_single_rule_gold():
    """Single-rule gold: coverage can only be 0.0 or 1.0 -- it degenerates to
    exactly what hit_at() would say, for BOTH any and all (the two modes are
    indistinguishable at gold size 1)."""
    assert run_eval.coverage_from_ids(["104.3a"], ["104.3a", "other"]) == 1.0
    assert run_eval.coverage_from_ids(["104.3a"], ["other"]) == 0.0


def test_coverage_from_ids_apostrophe_normalization_both_sides():
    """The three curly-apostrophe glossary ids (City's Blessing etc.) must
    still match an ASCII-apostrophe gold id -- same trap hit_at() guards
    against via normalize_source_id() on both sides."""
    curly = "City’s Blessing"
    ascii_ = "City's Blessing"
    assert run_eval.coverage_from_ids([ascii_], [curly]) == 1.0
    assert run_eval.coverage_from_ids([curly], [ascii_]) == 1.0


# --------------------------------------------------------------------------
# coverage_at -- the Retrieved-ranking formula, and its relationship to
# hit_at() by match mode (spec section 1)
# --------------------------------------------------------------------------

def test_coverage_at_matches_coverage_from_ids():
    q = EvalQuestion(id="t1", question="q", gold=["a", "b", "c"], match="any")
    ranking = mk_ranking(["a", "x", "y"])
    at_result = run_eval.coverage_at(q, ranking, k=3)
    ids_result = run_eval.coverage_from_ids(q.gold, ["a", "x", "y"])
    assert at_result == ids_result == 1 / 3


def test_coverage_at_empty_gold_is_none():
    q = EvalQuestion(id="t2", question="q", gold=[], match="any")
    assert run_eval.coverage_at(q, mk_ranking(["a"]), k=5) is None


def test_coverage_at_respects_k_cutoff():
    q = EvalQuestion(id="t3", question="q", gold=["a", "b"], match="all")
    ranking = mk_ranking(["a", "b", "c"])
    assert run_eval.coverage_at(q, ranking, k=1) == 0.5   # only "a" in window
    assert run_eval.coverage_at(q, ranking, k=2) == 1.0   # both in window


def test_all_mode_hit_at_iff_coverage_is_exactly_one():
    """Spec section 1: for match:"all", hit_at()==True iff coverage==1.0,
    exactly -- coverage is a strict generalization, same pass/fail line."""
    q = EvalQuestion(id="t4", question="q", gold=["a", "b", "c"], match="all")

    full = mk_ranking(["a", "b", "c"])
    assert run_eval.hit_at(q, full, k=10) is True
    assert run_eval.coverage_at(q, full, k=10) == 1.0

    partial = mk_ranking(["a", "b"])  # missing "c"
    assert run_eval.hit_at(q, partial, k=10) is False
    cov = run_eval.coverage_at(q, partial, k=10)
    assert cov == 2 / 3
    assert cov < 1.0


def test_any_mode_multirule_row_where_coverage_and_hit_at_disagree():
    """THE degenerate case the task calls out by name: a match:"any" row with
    multiple gold ids where retrieval finds exactly one. hit_at() scores a
    complete pass (any() needs just one); coverage reports the true fraction.
    This is the exact failure mode docs/spec-coverage-metric.md's rg4023
    example targets, reproduced at a smaller scale."""
    q = EvalQuestion(id="rgFAKE", question="q",
                      gold=["a", "b", "c", "d"], match="any")
    ranking = mk_ranking(["a", "unrelated1", "unrelated2"])

    assert run_eval.hit_at(q, ranking, k=10) is True        # boolean: full pass
    cov = run_eval.coverage_at(q, ranking, k=10)
    assert cov == 0.25                                       # graded: 1 of 4
    assert cov != 1.0


def test_groups_mode_can_score_below_hit_at():
    """Spec section 1: for match:"groups", coverage can be a strictly harder
    ceiling than hit_at() on a legitimate OR-group -- hit_at() only needs one
    member per group; coverage needs the whole flat union."""
    q = EvalQuestion(
        id="rg93fake", question="q",
        gold=["608.2c", "702.120a", "118.9d", "601.2b", "608.2g"],
        match="groups",
        gold_groups=[["608.2c"], ["702.120a"], ["118.9d", "601.2b", "608.2g"]],
    )
    # Satisfies every group via one alternative each: 608.2c, 702.120a, 118.9d.
    ranking = mk_ranking(["608.2c", "702.120a", "118.9d"])
    assert run_eval.hit_at(q, ranking, k=10) is True
    cov = run_eval.coverage_at(q, ranking, k=10)
    assert cov == 3 / 5   # unused alternates 601.2b/608.2g count against it
    assert cov < 1.0


# --------------------------------------------------------------------------
# backfill_coverage.py -- id-only hit-boolean must agree with hit_at()
# --------------------------------------------------------------------------

def test_hit_bool_from_ids_matches_hit_at_any():
    q = EvalQuestion(id="a1", question="q", gold=["a", "b", "c"], match="any")
    for retrieved in (["a"], ["z"], ["a", "b"], []):
        ranking = mk_ranking(retrieved)
        expected = run_eval.hit_at(q, ranking, k=10)
        actual = bc.hit_bool_from_ids(run_eval.gold_groups(q), retrieved)
        assert actual == expected, retrieved


def test_hit_bool_from_ids_matches_hit_at_all():
    q = EvalQuestion(id="a2", question="q", gold=["a", "b", "c"], match="all")
    for retrieved in (["a", "b", "c"], ["a", "b"], [], ["a", "b", "c", "d"]):
        ranking = mk_ranking(retrieved)
        expected = run_eval.hit_at(q, ranking, k=10)
        actual = bc.hit_bool_from_ids(run_eval.gold_groups(q), retrieved)
        assert actual == expected, retrieved


def test_hit_bool_from_ids_matches_hit_at_groups():
    q = EvalQuestion(
        id="a3", question="q", gold=["a", "b", "c", "d"], match="groups",
        gold_groups=[["a"], ["b", "c"], ["d"]],
    )
    for retrieved in (["a", "b", "d"], ["a", "c", "d"], ["a", "d"], ["a", "b"]):
        ranking = mk_ranking(retrieved)
        expected = run_eval.hit_at(q, ranking, k=10)
        actual = bc.hit_bool_from_ids(run_eval.gold_groups(q), retrieved)
        assert actual == expected, retrieved


# --------------------------------------------------------------------------
# backfill_coverage.py -- resolve_gold_groups / score_row / build_worklist
# --------------------------------------------------------------------------

def test_resolve_gold_groups_inline_takes_priority():
    row = {"id": "x", "gold_groups": [["a"], ["b"]]}
    assert bc.resolve_gold_groups(row, "groups", {}) == [["a"], ["b"]]


def test_resolve_gold_groups_falls_back_to_v3_join():
    row = {"id": "rg93"}
    v3 = {"rg93": [["608.2c"], ["702.120a"]]}
    assert bc.resolve_gold_groups(row, "groups", v3) == [["608.2c"], ["702.120a"]]


def test_resolve_gold_groups_unresolvable_is_none():
    row = {"id": "unknown-id"}
    assert bc.resolve_gold_groups(row, "groups", {}) is None


def test_resolve_gold_groups_unused_for_any_all():
    """any/all rows derive their groups from `gold` alone (gold_groups()
    already handles this); resolve_gold_groups is only consulted for
    match=="groups" and returns None (meaning "not needed") otherwise."""
    assert bc.resolve_gold_groups({"id": "x"}, "any", {}) is None
    assert bc.resolve_gold_groups({"id": "x"}, "all", {}) is None


def test_score_row_empty_gold_is_all_none():
    row = {"id": "empty1", "gold": [], "match": "any", "retrieved_rule_ids": ["a"]}
    r = bc.score_row("test-arm", row, {})
    assert r["coverage"] is None
    assert r["hit"] is None
    assert r["gap"] is None


def test_score_row_single_rule_gold():
    hit_row = {"id": "s1", "gold": ["104.3a"], "match": "any",
               "retrieved_rule_ids": ["104.3a", "other"]}
    r = bc.score_row("test-arm", hit_row, {})
    assert r["coverage"] == 1.0 and r["hit"] is True and r["gap"] == 0.0

    miss_row = {"id": "s2", "gold": ["104.3a"], "match": "any",
                "retrieved_rule_ids": ["other"]}
    r = bc.score_row("test-arm", miss_row, {})
    assert r["coverage"] == 0.0 and r["hit"] is False and r["gap"] == 0.0


def test_score_row_any_multirule_inflation_case():
    """The exact diagnostic case: hit_at()==True (any semantics, one hit
    suffices) with coverage well under 1 -- a positive gap, the signal the
    worklist ranks on."""
    row = {"id": "rgFAKE2", "gold": ["a", "b", "c", "d"], "match": "any",
           "retrieved_rule_ids": ["a"]}
    r = bc.score_row("test-arm", row, {})
    assert r["hit"] is True
    assert r["coverage"] == 0.25
    assert r["gap"] == 0.75


def test_score_row_groups_unresolvable_leaves_hit_and_gap_none():
    row = {"id": "no-such-id", "gold": ["a", "b"], "match": "groups",
           "retrieved_rule_ids": ["a"]}
    r = bc.score_row("test-arm", row, {})
    assert r["coverage"] == 0.5      # coverage never needs gold_groups
    assert r["hit"] is None          # but the hit boolean does, and couldn't resolve
    assert r["gap"] is None


def test_build_worklist_sorts_descending_and_filters_by_threshold():
    rows = [
        {"id": "low", "gap": 0.1},
        {"id": "high", "gap": 0.9},
        {"id": "mid", "gap": 0.5},
        {"id": "no_gap_none", "gap": None},
        {"id": "not_inflated", "gap": -0.3},  # hit=False rows: excluded, not "inflation"
        {"id": "zero", "gap": 0.0},
    ]
    ranked, above = bc.build_worklist(rows, threshold=0.5)
    assert [r["id"] for r in ranked] == ["high", "mid", "low"]  # zero/negative/None excluded
    assert [r["id"] for r in above] == ["high"]  # strictly greater than threshold


def test_gap_threshold_is_0_5_and_documented():
    """Sanity-check the constant matches what the report cites, so a future
    edit to the number doesn't silently drift from what was justified."""
    assert bc.GAP_THRESHOLD == 0.5

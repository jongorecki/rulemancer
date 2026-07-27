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
  - The prompt-supplied-ids coverage fix: a gold id that reached the model
    via the system prompt or a tool schema, but was never retrieved, must
    count as covered (rulesagent.generate.answer.prompt_supplied_rule_ids,
    threaded through coverage_at/coverage_from_ids/backfill_coverage). Also
    a drift guard: regexes the actual SYSTEM_VERSIONS/tool-schema strings in
    answer.py and asserts the curated constants match what's really there.

Does NOT touch hit_at()/gold_groups() -- only imports and calls them, to
prove the new code agrees with the old, unchanged code.
"""
from __future__ import annotations

import json
import re

from rulesagent.contracts import Chunk, EvalQuestion, Retrieved
from rulesagent.generate import answer as answer_mod

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


# --------------------------------------------------------------------------
# Measurement-bug fix: prompt-supplied ids count as covered
# --------------------------------------------------------------------------

def test_coverage_from_ids_prompt_supplied_only_counts_as_covered():
    """A gold id never retrieved, but supplied for free via the system
    prompt/a tool schema (real text/substance, not a bare reference -- see
    prompt_supplied_rule_ids' text-vs-reference standard), must count as
    covered -- that's the whole bug. 613.6 is quoted verbatim by
    RESOLVE_LAYERS_TOOL, so it's a valid prompt-supplied id to test with."""
    assert run_eval.coverage_from_ids(
        ["613.6"], [], prompt_supplied=["613.6"]
    ) == 1.0


def test_coverage_from_ids_retrieved_only_still_counts():
    """A gold id that WAS retrieved counts as covered whether or not it's
    also in prompt_supplied -- retrieval isn't penalized for redundancy."""
    assert run_eval.coverage_from_ids(
        ["613.6"], ["613.6"], prompt_supplied=[]
    ) == 1.0


def test_coverage_from_ids_both_retrieved_and_prompt_supplied():
    """A gold id in both sets still counts once, not double -- coverage is a
    fraction of distinct gold ids covered, never > 1.0."""
    assert run_eval.coverage_from_ids(
        ["613.6"], ["613.6"], prompt_supplied=["613.6"]
    ) == 1.0


def test_coverage_from_ids_neither_retrieved_nor_prompt_supplied():
    """A gold id in neither set is still a genuine miss -- the fix corrects
    false misses, it does not inflate every row to 1.0."""
    assert run_eval.coverage_from_ids(
        ["613.8a"], ["other"], prompt_supplied=["613.6"]
    ) == 0.0


def test_coverage_from_ids_default_is_backward_compatible():
    """Omitting prompt_supplied entirely (every existing call site) must be
    byte-identical to the pre-fix formula -- no positional/keyword change to
    any existing caller."""
    assert run_eval.coverage_from_ids(["104.3a"], ["104.3a"]) == 1.0
    assert run_eval.coverage_from_ids(["104.3a"], ["999.9z"]) == 0.0
    assert run_eval.coverage_from_ids(
        ["a", "b", "c", "d"], ["a", "b", "x", "y"]
    ) == 0.5
    assert run_eval.coverage_from_ids([], ["104.3a"]) is None


def test_coverage_from_ids_prompt_supplied_apostrophe_normalized():
    """prompt_supplied goes through the same normalize_source_id() path as
    retrieved_ids -- the curly/ASCII apostrophe trap applies here too."""
    curly = "City’s Blessing"
    ascii_ = "City's Blessing"
    assert run_eval.coverage_from_ids([ascii_], [], prompt_supplied=[curly]) == 1.0


def test_coverage_at_prompt_supplied_only_counts_as_covered():
    """Same fix, exercised through coverage_at (the Retrieved-ranking form)
    rather than coverage_from_ids). 613.6/613.8a are RESOLVE_LAYERS_TOOL's
    two ids that carry real rule substance (613.3/613.4a are excluded --
    bare reference only, see prompt_supplied_rule_ids)."""
    q = EvalQuestion(id="pt1", question="q", gold=["613.6", "613.8a"], match="any")
    ranking = mk_ranking(["other"])  # neither gold id retrieved
    cov_before = run_eval.coverage_at(q, ranking, k=10)
    assert cov_before == 0.0
    cov_after = run_eval.coverage_at(q, ranking, k=10, prompt_supplied=["613.6"])
    assert cov_after == 0.5  # only 613.6 is prompt-supplied; 613.8a still missing


def test_coverage_at_default_is_backward_compatible():
    """Omitting prompt_supplied on coverage_at is byte-identical to before."""
    q = EvalQuestion(id="pt2", question="q", gold=["a", "b"], match="all")
    ranking = mk_ranking(["a"])
    assert run_eval.coverage_at(q, ranking, k=10) == 0.5


def test_prompt_supplied_rule_ids_matches_the_worked_example():
    """The exact mapping, after the text-vs-substance correction: only ids
    backed by real rule content ever appear (611.3a/613.6/613.8a). Bare
    references (104.3a's citation-format example, 601.2f's citation,
    613.3/613.4a's two-word gloss) never do -- see prompt_supplied_rule_ids'
    module comment for how each was checked."""
    fn = answer_mod.prompt_supplied_rule_ids

    # system_version 3, layers off: cost tool contributes nothing (601.2f
    # is never quoted), system prompt contributes nothing (104.3a is a
    # citation-format example, not rule text) -- empty set.
    assert fn(3, False) == set()

    # system_version 3, layers on: adds RESOLVE_LAYERS_TOOL's two
    # substance-backed ids (613.6 verbatim, 613.8a paraphrased with full
    # criteria); 613.3/613.4a stay excluded (bare "(CDAs first)" gloss).
    assert fn(3, True) == {"613.6", "613.8a"}

    # v3+613 bakes 611.3a/613.6 into the system prompt VERBATIM (LAYERS_CR_
    # BULLET) -- present regardless of the layers_tool switch. With layers
    # off, 613.8a is absent (it's layers-tool-only, not in the bullet).
    assert fn("v3+613", False) == {"611.3a", "613.6"}
    # With layers on too, the tool's 613.8a joins the bullet's ids; 613.6
    # from both sources still counts once (it's a set).
    assert fn("v3+613", True) == {"611.3a", "613.6", "613.8a"}

    # Unknown system_version: no system-prompt ids, no cost-tool ids (it's
    # always empty) -- doesn't crash, doesn't over-claim.
    assert fn("nonexistent", False) == set()


def test_prompt_supplied_rule_ids_drift_guard():
    """Regexes the ACTUAL tool-schema/system-prompt strings in answer.py and
    asserts every discovered CR-rule-number-shaped candidate lands in
    EITHER the curated constant OR the explicit _REFERENCED_NOT_QUOTED
    exclusion set -- never in neither (an id nobody has classified) and
    never claimed by both (contradictory bookkeeping).

    This encodes the text-vs-reference judgment call rather than ignoring
    it: a plain "regex output == constant" assertion would fail on every
    correctly-excluded bare reference (104.3a's citation-format example,
    etc.), so instead each candidate must be accounted for by name. A
    future prompt edit that adds a new rule-number token -- quoted or bare
    -- still trips this test until someone classifies it into one bucket or
    the other.
    """
    rule_id_re = re.compile(r"\b\d{3}\.\d+[a-z]?\b")

    def discover(obj) -> set[str]:
        s = obj if isinstance(obj, str) else json.dumps(obj)
        return set(rule_id_re.findall(s))

    found_cost = discover(answer_mod.CALCULATE_COST_TOOL)
    found_layers = discover(answer_mod.RESOLVE_LAYERS_TOOL)
    found_system = {
        3: discover(answer_mod.SYSTEM_V3),
        4: discover(answer_mod.SYSTEM_V4),
        "v4nl": discover(answer_mod.SYSTEM_V4NL),
        "v3+613": discover(answer_mod.SYSTEM_V3_613),
    }

    excluded = set(answer_mod._REFERENCED_NOT_QUOTED)
    all_found: set[str] = found_cost | found_layers | set().union(*found_system.values())

    def check(label: str, found: set[str], quoted: set[str]) -> None:
        unclassified = found - quoted - excluded
        assert not unclassified, (
            f"{label}: regex found new rule-number token(s) {unclassified} "
            "not in the curated constant and not in "
            "_REFERENCED_NOT_QUOTED -- classify them (add rule text/"
            "substance to the constant, or a reason to the exclusion set) "
            "in src/rulesagent/generate/answer.py."
        )
        wrongly_excluded = quoted & excluded
        assert not wrongly_excluded, (
            f"{label}: id(s) {wrongly_excluded} are claimed as both "
            "quoted (in the curated constant) and bare-reference-only (in "
            "_REFERENCED_NOT_QUOTED) -- contradictory, fix answer.py."
        )

    check("CALCULATE_COST_TOOL", found_cost, answer_mod._COST_TOOL_PROMPT_IDS)
    check("RESOLVE_LAYERS_TOOL", found_layers, answer_mod._LAYERS_TOOL_PROMPT_IDS)
    for version, found in found_system.items():
        check(f"SYSTEM_VERSIONS[{version!r}]", found, answer_mod._SYSTEM_PROMPT_IDS[version])

    stale_exclusions = excluded - all_found
    assert not stale_exclusions, (
        f"_REFERENCED_NOT_QUOTED has stale entries {stale_exclusions} no "
        "longer found anywhere in the schema/prompt strings -- the prompt "
        "changed; remove the stale exclusion or confirm it moved elsewhere."
    )


# --------------------------------------------------------------------------
# backfill_coverage.py -- row_prompt_supplied_ids / score_row corrected
# --------------------------------------------------------------------------

def test_row_prompt_supplied_ids_prefers_recorded_field():
    row = {"prompt_supplied_rule_ids": ["104.3a"], "system_version": 4, "layers_tool": True}
    assert bc.row_prompt_supplied_ids(row) == ["104.3a"]


def test_row_prompt_supplied_ids_infers_from_system_version_and_layers_tool():
    row = {"system_version": 3, "layers_tool": True}
    ids = bc.row_prompt_supplied_ids(row)
    assert set(ids) == {"613.6", "613.8a"}


def test_row_prompt_supplied_ids_missing_system_version_is_empty():
    """Rows with neither field (e.g. h2h_gpt5mini.json's joined OpenRouter
    rows) get no prompt-supplied ids -- honestly unknown, not guessed."""
    assert bc.row_prompt_supplied_ids({"id": "x"}) == []


def test_score_row_reports_both_corrected_and_uncorrected_coverage():
    """The backfill must never silently overwrite the old number -- both
    are present on every scored row. 613.6 is RESOLVE_LAYERS_TOOL's
    verbatim-quoted id, so layers_tool=True makes it prompt-supplied."""
    row = {
        "id": "fix1", "gold": ["613.6", "other"], "match": "any",
        "retrieved_rule_ids": [], "system_version": 3, "layers_tool": True,
    }
    r = bc.score_row("test-arm", row, {})
    assert r["coverage_uncorrected"] == 0.0     # neither gold id retrieved
    assert r["coverage"] == 0.5                 # 613.6 is prompt-supplied
    assert r["coverage"] != r["coverage_uncorrected"]


def test_score_row_backward_compatible_without_config_fields():
    """A row with no system_version/layers_tool (all the existing tests'
    hand-built rows) scores identically to before this fix -- coverage ==
    coverage_uncorrected, no prompt-supplied ids assumed."""
    row = {"id": "s1", "gold": ["104.3a"], "match": "any",
           "retrieved_rule_ids": ["104.3a", "other"]}
    r = bc.score_row("test-arm", row, {})
    assert r["coverage"] == r["coverage_uncorrected"] == 1.0


# --------------------------------------------------------------------------
# Gold-size stratification (evals/backfill_coverage.py:
# stratify_by_gold_size / coverage_bucket / gold_size_stratum / VERDICT_FILES)
# --------------------------------------------------------------------------

def test_coverage_bucket_boundaries():
    assert bc.coverage_bucket(0.0) == "zero"
    assert bc.coverage_bucket(1.0) == "full"
    assert bc.coverage_bucket(0.5) == "partial"
    assert bc.coverage_bucket(0.25) == "partial"


def test_gold_size_stratum_buckets_1_2_3_and_pools_4plus():
    assert bc.gold_size_stratum(1) == "1"
    assert bc.gold_size_stratum(2) == "2"
    assert bc.gold_size_stratum(3) == "3"
    assert bc.gold_size_stratum(4) == "4+"
    assert bc.gold_size_stratum(9) == "4+"


def mk_scored(arm, id_, gold_n, coverage):
    """A minimal score_row()-shaped dict -- only the fields
    stratify_by_gold_size() actually reads."""
    return {"arm": arm, "id": id_, "gold_n": gold_n, "coverage": coverage}


def test_stratify_structural_no_partial_in_stratum_1():
    """THE structural property the whole feature exists to surface: a
    gold_n==1 row can only ever be 0/1 or 1/1 -- there is no fraction
    between. However many single-rule rows are fed in, at whatever mix of
    0.0/1.0 coverage, the "partial" bucket for stratum "1" must be empty,
    and the report must say this is structural rather than a data gap."""
    rows = ([mk_scored("a", f"z{i}", 1, 0.0) for i in range(5)]
            + [mk_scored("a", f"f{i}", 1, 1.0) for i in range(7)])
    out = bc.stratify_by_gold_size(rows, verdict_maps={})
    s1 = next(s for s in out["strata"] if s["stratum"] == "1")
    assert s1["n"] == 12
    assert s1["buckets"]["partial"]["n"] == 0
    assert s1["buckets"]["zero"]["n"] == 5
    assert s1["buckets"]["full"]["n"] == 7
    assert s1["structurally_no_partial"] is True
    # Other strata do not carry the flag -- only stratum 1 is structural.
    for s in out["strata"]:
        if s["stratum"] != "1":
            assert s["structurally_no_partial"] is False


def test_stratify_multi_gold_row_lands_in_partial():
    """A multi-gold row genuinely CAN be partial -- gold_n>=2 is where the
    bucket is meaningful at all."""
    rows = [mk_scored("a", "p1", 3, 1 / 3), mk_scored("a", "p2", 4, 0.5)]
    out = bc.stratify_by_gold_size(rows, verdict_maps={})
    s3 = next(s for s in out["strata"] if s["stratum"] == "3")
    s4 = next(s for s in out["strata"] if s["stratum"] == "4+")
    assert s3["buckets"]["partial"]["n"] == 1
    assert s4["buckets"]["partial"]["n"] == 1


def test_stratify_excludes_empty_gold_rows():
    rows = [mk_scored("a", "e1", 0, None), mk_scored("a", "r1", 1, 1.0)]
    out = bc.stratify_by_gold_size(rows, verdict_maps={})
    total_n = sum(s["n"] for s in out["strata"])
    assert total_n == 1


def test_stratify_mean_coverage_per_stratum():
    rows = [mk_scored("a", "x1", 2, 0.0), mk_scored("a", "x2", 2, 1.0)]
    out = bc.stratify_by_gold_size(rows, verdict_maps={})
    s2 = next(s for s in out["strata"] if s["stratum"] == "2")
    assert s2["n"] == 2
    assert s2["mean_coverage"] == 0.5


def test_stratify_empty_stratum_has_none_mean_and_zero_counts():
    out = bc.stratify_by_gold_size([], verdict_maps={})
    for s in out["strata"]:
        assert s["n"] == 0
        assert s["mean_coverage"] is None
        for b in bc.COVERAGE_BUCKET_ORDER:
            assert s["buckets"][b]["n"] == 0
            assert s["buckets"][b]["accuracy"] is None


# ---- the verdict join ----

def test_stratify_accuracy_join_correct_and_wrong():
    rows = [mk_scored("armA", "q1", 2, 0.0), mk_scored("armA", "q2", 2, 0.0)]
    verdict_maps = {"armA": {"q1": True, "q2": False}}
    out = bc.stratify_by_gold_size(rows, verdict_maps)
    s2 = next(s for s in out["strata"] if s["stratum"] == "2")
    zero = s2["buckets"]["zero"]
    assert zero["n"] == 2
    assert zero["n_accuracy_scored"] == 2
    assert zero["accuracy"] == 0.5


def test_stratify_accuracy_join_missing_arm_reports_unknown_not_zero():
    """An arm with no verdict file (verdict_maps[arm] is None) must not be
    silently scored as 0% accuracy or dropped -- coverage still counts,
    accuracy is None, and the arm is named so the gap is visible."""
    rows = [mk_scored("no_verdicts_arm", "q1", 2, 0.0)]
    out = bc.stratify_by_gold_size(rows, {"no_verdicts_arm": None})
    s2 = next(s for s in out["strata"] if s["stratum"] == "2")
    zero = s2["buckets"]["zero"]
    assert zero["n"] == 1                       # coverage still counted
    assert zero["accuracy"] is None              # accuracy not guessed
    assert zero["n_accuracy_scored"] == 0
    assert "no_verdicts_arm" in zero["arms_without_verdicts"]


def test_stratify_accuracy_join_mixed_arms_one_with_verdicts_one_without():
    rows = [mk_scored("has_verdicts", "q1", 3, 0.0),
            mk_scored("no_verdicts", "q2", 3, 0.0)]
    verdict_maps = {"has_verdicts": {"q1": True}, "no_verdicts": None}
    out = bc.stratify_by_gold_size(rows, verdict_maps)
    s3 = next(s for s in out["strata"] if s["stratum"] == "3")
    zero = s3["buckets"]["zero"]
    assert zero["n"] == 2
    assert zero["n_accuracy_scored"] == 1        # only the verdict-backed row
    assert zero["accuracy"] == 1.0
    assert zero["arms_without_verdicts"] == ["no_verdicts"]


def test_load_verdict_map_unknown_arm_is_none():
    assert bc.load_verdict_map("not-a-real-arm") is None


def test_load_verdict_map_reads_real_file(tmp_path):
    """load_verdict_map() against an actual verdicts_*.json on disk --
    l0_opuslow is small-ish and always present in this repo."""
    vmap = bc.load_verdict_map("l0_opuslow")
    assert vmap is not None
    assert len(vmap) > 0
    assert all(isinstance(v, bool) for v in vmap.values())


def test_shipped_arms_constant_is_six_arms():
    """Guards the constant the brief's worked numbers depend on -- a
    future edit that changes membership should have to touch this test."""
    assert len(bc.SHIPPED_ARMS) == 6
    assert len(set(bc.SHIPPED_ARMS)) == 6

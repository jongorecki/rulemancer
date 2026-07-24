"""Unit tests for the v5-grid routing logic (evals/judge_v5.py).

Covers only the PURE decision logic with stubbed judge_fn -- no network
calls, no filesystem reads of answers/ or reference files:
  - route_row(): same -> transfer, different -> None, error/unparsed ->
    None, exception passthrough never calls the judge
  - classify_stability(): the stable-flip rule (both runs "different" ->
    stable_flip; only one -> unstable_flip; judge errors and exceptions
    never counted as either)
  - bucket_qids(): c002 (gpt-5-mini) always lands in monitored_non_scoring,
    never in the scoring buckets, regardless of its own judge outcome

The real OpenRouter judge call (evals/judge_arm_pairs.call_judge, imported
unchanged by judge_v5.py) is deliberately not exercised here -- it's a
network call, not logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

from judge_v5 import (  # noqa: E402
    ARM_QIDS,
    NON_SCORING_QIDS,
    bucket_qids,
    candidate_exception,
    classify_stability,
    route_row,
)


# ---------------------------------------------------------------- candidate_exception

def test_candidate_exception_error_field_wins():
    assert candidate_exception("rate limited", "a full real answer") == "provider_error"


def test_candidate_exception_blank_answer_is_unjudgeable():
    assert candidate_exception(None, "") == "unjudgeable_empty_answer"
    assert candidate_exception(None, "   ") == "unjudgeable_empty_answer"
    assert candidate_exception(None, None) == "unjudgeable_empty_answer"


def test_candidate_exception_real_answer_is_never_excluded():
    assert candidate_exception(None, "a full real answer") is None


def test_candidate_exception_does_not_key_off_answered_flag():
    """v5 grid data has rows marked answered=False that still carry a full
    answer text (the runner's own hedged/honesty flag) -- candidate_exception
    doesn't see or use that flag at all, so such rows must still be judged."""
    long_hedged_answer = "Whether both permanents can remain is unresolved here. " * 20
    assert candidate_exception(None, long_hedged_answer) is None


# ---------------------------------------------------------------- route_row

def test_route_row_same_transfers_ref_verdict():
    ref_row = {"answer": "ref answer", "verdict": "correct"}
    candidate_row = {"answer": "candidate answer", "exception": None}
    row = route_row("c012", "q?", ref_row, candidate_row, judge_fn=lambda *a: "same")
    assert row == {"id": "c012", "judge": "same", "ref_verdict": "correct",
                    "auto_verdict": "correct", "exception": None}


def test_route_row_same_transfers_wrong_too():
    """Wrong verdicts transfer too -- the judge routes, it never grades."""
    ref_row = {"answer": "ref", "verdict": "wrong"}
    candidate_row = {"answer": "cand", "exception": None}
    row = route_row("c015", "q?", ref_row, candidate_row, judge_fn=lambda *a: "same")
    assert row["auto_verdict"] == "wrong"


def test_route_row_different_routes_to_jon():
    ref_row = {"answer": "ref", "verdict": "correct"}
    candidate_row = {"answer": "cand", "exception": None}
    row = route_row("c012", "q?", ref_row, candidate_row, judge_fn=lambda *a: "different")
    assert row["judge"] == "different"
    assert row["auto_verdict"] is None
    assert row["exception"] is None


def test_route_row_judge_error_never_transfers():
    ref_row = {"answer": "ref", "verdict": "correct"}
    candidate_row = {"answer": "cand", "exception": None}
    row = route_row("c012", "q?", ref_row, candidate_row, judge_fn=lambda *a: "error")
    assert row["judge"] == "error"
    assert row["auto_verdict"] is None


def test_route_row_unparsed_never_transfers():
    ref_row = {"answer": "ref", "verdict": "correct"}
    candidate_row = {"answer": "cand", "exception": None}
    row = route_row("c012", "q?", ref_row, candidate_row, judge_fn=lambda *a: "unparsed")
    assert row["judge"] == "unparsed"
    assert row["auto_verdict"] is None


def test_route_row_exception_skips_judge_entirely():
    """A candidate row with a provider exception must never call the judge
    (there's nothing judgeable), and must pass the exception through."""
    calls = []

    def judge_fn(question, reference, candidate, rid):
        calls.append(rid)
        return "same"

    ref_row = {"answer": "ref", "verdict": "correct"}
    candidate_row = {"answer": None, "exception": "provider_error"}
    row = route_row("c012", "q?", ref_row, candidate_row, judge_fn)
    assert calls == []  # judge never called
    assert row == {"id": "c012", "judge": None, "ref_verdict": "correct",
                    "auto_verdict": None, "exception": "provider_error"}


def test_route_row_passes_reference_and_candidate_answers_to_judge():
    seen = {}

    def judge_fn(question, reference, candidate, rid):
        seen["question"] = question
        seen["reference"] = reference
        seen["candidate"] = candidate
        seen["rid"] = rid
        return "same"

    ref_row = {"answer": "the ref answer", "verdict": "partial"}
    candidate_row = {"answer": "the candidate answer", "exception": None}
    route_row("c014", "the question", ref_row, candidate_row, judge_fn)
    assert seen == {"question": "the question", "reference": "the ref answer",
                     "candidate": "the candidate answer", "rid": "c014"}


# ---------------------------------------------------------------- classify_stability (stable-flip rule)

def _row(judge=None, exception=None):
    return {"judge": judge, "exception": exception}


def test_classify_both_same_is_no_flip():
    assert classify_stability(_row("same"), _row("same")) == "no_flip"


def test_classify_both_different_is_stable_flip():
    """The stable-flip rule: a flip counts only if BOTH runs judge
    'different' against the reference."""
    assert classify_stability(_row("different"), _row("different")) == "stable_flip"


def test_classify_only_r1_different_is_unstable_flip():
    assert classify_stability(_row("different"), _row("same")) == "unstable_flip"


def test_classify_only_r2_different_is_unstable_flip():
    assert classify_stability(_row("same"), _row("different")) == "unstable_flip"


def test_classify_judge_error_in_either_run_is_judge_error():
    assert classify_stability(_row("error"), _row("same")) == "judge_error"
    assert classify_stability(_row("same"), _row("unparsed")) == "judge_error"
    assert classify_stability(_row("error"), _row("different")) == "judge_error"


def test_classify_exception_in_either_run_is_exception():
    """Exception takes priority even if the other run has a valid verdict."""
    assert classify_stability(_row(exception="provider_error"), _row("same")) == "exception"
    assert classify_stability(_row("different"), _row(exception="unjudgeable_empty_answer")) == "exception"


def test_classify_exception_beats_judge_error():
    assert classify_stability(_row(exception="provider_error"), _row("error")) == "exception"


# ---------------------------------------------------------------- bucket_qids (c002 non-scoring enforcement)

def test_bucket_qids_c002_always_non_scoring_even_when_stable_flip():
    """c002 must never enter the scoring buckets, regardless of its own
    judge outcome -- monitored, non-scoring is unconditional."""
    arm = "gpt-5-mini"
    assert "c002" in NON_SCORING_QIDS
    r1 = {qid: _row("different") for qid in ARM_QIDS[arm]}
    r2 = {qid: _row("different") for qid in ARM_QIDS[arm]}
    out = bucket_qids(arm, r1, r2)
    all_scoring_qids = {q for ids in out["scoring"].values() if isinstance(ids, list) for q in ids}
    assert "c002" not in all_scoring_qids
    assert "c002" in out["monitored_non_scoring"]["stable_flip"]


def test_bucket_qids_scoring_qids_present_for_gpt5mini():
    arm = "gpt-5-mini"
    r1 = {qid: _row("same") for qid in ARM_QIDS[arm]}
    r2 = {qid: _row("same") for qid in ARM_QIDS[arm]}
    out = bucket_qids(arm, r1, r2)
    scoring_qids = set(out["scoring"]["no_flip"])
    non_scoring_qids = set(out["monitored_non_scoring"]["no_flip"])
    assert scoring_qids == set(ARM_QIDS[arm]) - NON_SCORING_QIDS
    assert non_scoring_qids == {"c002"}


def test_bucket_qids_sonnet_has_no_non_scoring_qids():
    """sonnet's Phase-1 set (c012/c014/c015) never includes c002."""
    arm = "sonnet"
    r1 = {qid: _row("same") for qid in ARM_QIDS[arm]}
    r2 = {qid: _row("same") for qid in ARM_QIDS[arm]}
    out = bucket_qids(arm, r1, r2)
    assert sum(len(v) for v in out["monitored_non_scoring"].values()) == 0
    assert set(out["scoring"]["no_flip"]) == set(ARM_QIDS["sonnet"])


def test_bucket_qids_counts_partition_all_qids_exactly_once():
    arm = "gpt-5-mini"
    r1 = {"c002": _row("same"), "c004": _row("different"), "c011": _row("different"),
          "c012": _row("error"), "c015": _row(exception="provider_error")}
    r2 = {"c002": _row("same"), "c004": _row("different"), "c011": _row("same"),
          "c012": _row("same"), "c015": _row("same")}
    out = bucket_qids(arm, r1, r2)
    seen = []
    for bucket in out["scoring"].values():
        seen.extend(bucket)
    for bucket in out["monitored_non_scoring"].values():
        seen.extend(bucket)
    assert sorted(seen) == sorted(ARM_QIDS[arm])
    assert out["monitored_non_scoring"]["no_flip"] == ["c002"]
    assert out["scoring"]["stable_flip"] == ["c004"]
    assert out["scoring"]["unstable_flip"] == ["c011"]
    assert out["scoring"]["judge_error"] == ["c012"]
    assert out["scoring"]["exception"] == ["c015"]

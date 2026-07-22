"""Unit tests for the transitive-grading decision logic
(docs/plan-judge-transitive-grading.md, evals/judge_arm_pairs.py).

Covers only the PURE decision logic with a faked judge -- no network calls:
  - transfer rule (same + ref verdict -> transfers; different/error -> None)
  - deterministic audit sampling
  - per-arm summary counts
  - roll-up (manual wins over auto on overlapping ids)
  - audit judge-error rate + unreliable-arm flag

The real OpenRouter judge call (evals/judge_arm_pairs.call_judge) is
deliberately not exercised here -- it's a network call, not logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

from judge_arm_pairs import (  # noqa: E402
    audit_sample,
    build_judge_pairs,
    decide_transfer,
    judge_error_report,
    rollup,
    summarize,
)


# ---------------------------------------------------------------- decide_transfer

def test_decide_transfer_same_transfers_correct():
    assert decide_transfer("same", "correct") == "correct"


def test_decide_transfer_same_transfers_wrong():
    """Wrong verdicts transfer too -- the judge routes, it never grades."""
    assert decide_transfer("same", "wrong") == "wrong"


def test_decide_transfer_same_transfers_partial():
    assert decide_transfer("same", "partial") == "partial"


def test_decide_transfer_different_returns_none():
    assert decide_transfer("different", "correct") is None


def test_decide_transfer_error_returns_none():
    """A judge call that errored or came back unparsable never transfers --
    it must fall into Jon's manual queue, not silently propagate a verdict."""
    assert decide_transfer("error", "correct") is None
    assert decide_transfer("unparsed", "correct") is None


# ---------------------------------------------------------------- audit_sample

def test_audit_sample_is_deterministic():
    ids = [f"q{i:03d}" for i in range(1, 21)]
    a = audit_sample(ids, rate=0.10, seed=42)
    b = audit_sample(ids, rate=0.10, seed=42)
    assert a == b


def test_audit_sample_different_seed_can_differ():
    ids = [f"q{i:03d}" for i in range(1, 21)]
    a = audit_sample(ids, rate=0.10, seed=42)
    c = audit_sample(ids, rate=0.10, seed=1)
    # not asserting inequality (could coincide) -- just that both are valid subsets
    assert a <= set(ids) and c <= set(ids)


def test_audit_sample_rate_approx_ten_percent():
    ids = [f"q{i:03d}" for i in range(1, 21)]  # 20 ids
    a = audit_sample(ids, rate=0.10, seed=42)
    assert len(a) == 2


def test_audit_sample_empty_ids():
    assert audit_sample([], rate=0.10, seed=42) == set()


def test_audit_sample_at_least_one_when_nonempty():
    ids = ["q001", "q002", "q003"]  # 10% of 3 rounds to 0 -- must still floor to 1
    a = audit_sample(ids, rate=0.10, seed=42)
    assert len(a) == 1


# ---------------------------------------------------------------- build_judge_pairs

def test_build_judge_pairs_marks_audit_only_on_transferred():
    target_rows = [{"id": f"q{i:03d}", "question": "q", "answer": "a"} for i in range(1, 21)]
    ref_by_id = {r["id"]: {"answer": "ref"} for r in target_rows}
    ref_verdicts_by_id = {r["id"]: {"verdict": "correct"} for r in target_rows}
    # first 10 ids "same" (eligible to transfer + audit), last 10 "different"
    verdicts = {r["id"]: ("same" if i < 10 else "different") for i, r in enumerate(target_rows)}

    def judge_fn(question, reference, candidate, _id):
        return verdicts[_id]

    rows = build_judge_pairs(target_rows, ref_by_id, ref_verdicts_by_id, judge_fn)
    by_id = {r["id"]: r for r in rows}

    for r in rows:
        if r["judge"] == "different":
            assert r["audit"] is False
            assert r["auto_verdict"] is None
        else:
            assert r["judge"] == "same"
            assert r["auto_verdict"] == "correct"

    audited_ids = {r["id"] for r in rows if r["audit"]}
    assert audited_ids <= {r["id"] for r in rows if r["judge"] == "same"}
    assert len(audited_ids) == 1  # 10% of the 10 "same" ids


def test_build_judge_pairs_error_never_transfers():
    target_rows = [{"id": "q001", "question": "q", "answer": "a"}]
    ref_by_id = {"q001": {"answer": "ref"}}
    ref_verdicts_by_id = {"q001": {"verdict": "correct"}}

    def judge_fn(question, reference, candidate, _id):
        return "error"

    rows = build_judge_pairs(target_rows, ref_by_id, ref_verdicts_by_id, judge_fn)
    assert rows[0]["judge"] == "error"
    assert rows[0]["auto_verdict"] is None
    assert rows[0]["audit"] is False


# ---------------------------------------------------------------- summarize

def test_summarize_counts():
    rows = [
        {"id": "a", "judge": "same", "auto_verdict": "correct", "audit": True},
        {"id": "b", "judge": "same", "auto_verdict": "wrong", "audit": False},
        {"id": "c", "judge": "different", "auto_verdict": None, "audit": False},
        {"id": "d", "judge": "error", "auto_verdict": None, "audit": False},
        {"id": "e", "judge": "unparsed", "auto_verdict": None, "audit": False},
    ]
    s = summarize(rows)
    assert s["n"] == 5
    assert s["same"] == 2
    assert s["different"] == 1
    assert s["error"] == 2  # error + unparsed both lump into error
    assert s["auto_transferred"] == 2
    assert s["audit"] == 1
    # remaining for Jon: different + error/unparsed + audited-same = c, d, e, a = 4
    assert s["remaining_for_jon"] == 4


# ---------------------------------------------------------------- rollup

def test_rollup_manual_wins_over_auto():
    auto = [
        {"id": "q001", "verdict": "correct", "note": "auto"},
        {"id": "q002", "verdict": "wrong", "note": "auto"},
    ]
    manual = [
        {"id": "q001", "verdict": "partial", "note": "Jon disagreed"},
        {"id": "q003", "verdict": "correct", "note": "Jon graded"},
    ]
    final = rollup(manual, auto)
    by_id = {r["id"]: r for r in final}
    assert by_id["q001"]["verdict"] == "partial"  # manual wins
    assert by_id["q001"]["note"] == "Jon disagreed"
    assert by_id["q002"]["verdict"] == "wrong"  # auto-only, kept
    assert by_id["q003"]["verdict"] == "correct"  # manual-only, kept
    assert len(final) == 3


# ---------------------------------------------------------------- judge_error_report

def test_judge_error_report_under_threshold_is_reliable():
    judge_rows = [
        {"id": f"q{i:03d}", "judge": "same", "auto_verdict": "correct", "audit": True}
        for i in range(10)
    ]
    manual_by_id = {r["id"]: {"verdict": "correct"} for r in judge_rows}
    manual_by_id["q000"] = {"verdict": "wrong"}  # 1/10 disagreement = 10%, not > 10%
    report = judge_error_report(judge_rows, manual_by_id)
    assert report["audit_n"] == 10
    assert report["judge_errors"] == 1
    assert report["error_rate"] == 0.10
    assert report["unreliable"] is False


def test_judge_error_report_over_threshold_is_unreliable():
    judge_rows = [
        {"id": f"q{i:03d}", "judge": "same", "auto_verdict": "correct", "audit": True}
        for i in range(10)
    ]
    manual_by_id = {r["id"]: {"verdict": "correct"} for r in judge_rows}
    manual_by_id["q000"] = {"verdict": "wrong"}
    manual_by_id["q001"] = {"verdict": "wrong"}  # 2/10 = 20% > 10%
    report = judge_error_report(judge_rows, manual_by_id)
    assert report["judge_errors"] == 2
    assert report["unreliable"] is True


def test_judge_error_report_ignores_non_audit_rows():
    judge_rows = [
        {"id": "q001", "judge": "same", "auto_verdict": "correct", "audit": True},
        {"id": "q002", "judge": "same", "auto_verdict": "correct", "audit": False},
    ]
    manual_by_id = {"q001": {"verdict": "correct"}, "q002": {"verdict": "wrong"}}
    report = judge_error_report(judge_rows, manual_by_id)
    assert report["audit_n"] == 1
    assert report["judge_errors"] == 0


def test_judge_error_report_no_audit_rows_is_reliable_with_zero_rate():
    report = judge_error_report([], {})
    assert report["audit_n"] == 0
    assert report["error_rate"] == 0.0
    assert report["unreliable"] is False

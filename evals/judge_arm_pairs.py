"""Transitive grading (docs/plan-judge-transitive-grading.md).

Jon hand-graded the deepseek-v3.2 arm (evals/verdicts_deepseek-v3-2.json).
For every OTHER arm's answer, judge it against v3.2's answer to the SAME
question with judge_bakeoff.py's bake-off-validated OpenRouter judge
(gpt-5-mini, 95% agreement) -- its judge prompt and call protocol are reused
by calling judge_bakeoff.or_judge() directly, unchanged, so nothing here can
drift from the wording that earned that agreement figure.

  same + v3.2's verdict  -> the verdict TRANSFERS (correct AND wrong both
                            transfer -- the judge routes, it never grades).
  different / error      -> Jon's manual queue.

A deterministic ~10% sample of transferred rows is ALSO queued for Jon,
labeled audit, so the judge's agreement is checked on this data, not assumed
from the bake-off. See judge_error_report() for the audit-driven fallback:
if judge errors on >10% of an arm's audit sample, that arm's auto-verdicts
are unreliable and it falls back to full manual grading (Roll-up rule).

Run per arm (writes judge_pairs_<label>.json, verdicts_<label>.auto.json,
data/parsed/grading_<label>_diff.html):

    uv run python evals/judge_arm_pairs.py --target sonnet-v2

Needs OPENROUTER_API_KEY in .env. Out of scope (see plan doc): changing the
grading UI template, changing the judge prompt, RulesGuru-150.
"""
import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from judge_bakeoff import OPENROUTER_JUDGES, or_judge  # noqa: E402

REPO = Path(__file__).parent.parent
PARSED = REPO / "data" / "parsed"
EVALS = Path(__file__).parent
BUILD_GRADING_UI = EVALS / "build_grading_ui.py"

REF_LABEL = "deepseek-v3-2"
JUDGE_SLUG = OPENROUTER_JUDGES["gpt-5-mini"]  # openai/gpt-5-mini, pinned
AUDIT_RATE = 0.10
AUDIT_SEED = 42
MAX_RETRIES = 3
TARGETS = ["sonnet-v2", "deepseek-v4-pro", "deepseek-v4-flash", "gemini-flash-lite", "gpt-5-mini"]


# ==================================================================
# Pure decision logic -- unit tested in tests/test_transitive_grading.py
# with a faked judge. No network here.
# ==================================================================

def decide_transfer(judge_verdict: str, ref_verdict: str) -> str | None:
    """same -> ref_verdict transfers (correct AND wrong both transfer -- the
    judge routes, it never grades). Anything else (different/error/unparsed)
    -> None, so it falls into Jon's manual queue instead of silently
    propagating a guess."""
    return ref_verdict if judge_verdict == "same" else None


def audit_sample(ids: list[str], rate: float = AUDIT_RATE, seed: int = AUDIT_SEED) -> set[str]:
    """Deterministic ~rate sample of ids, seeded so re-runs mark the same
    rows (docs/plan-judge-transitive-grading.md). Floors to 1 for any
    non-empty input so small arms still get audited."""
    if not ids:
        return set()
    n = max(1, round(len(ids) * rate))
    n = min(n, len(ids))
    rng = random.Random(seed)
    return set(rng.sample(sorted(ids), n))


def build_judge_pairs(
    target_rows: list[dict],
    ref_by_id: dict,
    ref_verdicts_by_id: dict,
    judge_fn,
    audit_rate: float = AUDIT_RATE,
    audit_seed: int = AUDIT_SEED,
) -> list[dict]:
    """One row per target answer: {id, judge, ref_verdict, auto_verdict, audit}.
    judge_fn(question, reference, candidate, row_id) -> "same"|"different"|"error"|"unparsed".
    """
    rows = []
    for row in target_rows:
        rid = row["id"]
        ref_row = ref_by_id[rid]
        ref_verdict = ref_verdicts_by_id[rid]["verdict"]
        judge_verdict = judge_fn(row["question"], ref_row["answer"], row["answer"], rid)
        auto_verdict = decide_transfer(judge_verdict, ref_verdict)
        rows.append({
            "id": rid,
            "judge": judge_verdict,
            "ref_verdict": ref_verdict,
            "auto_verdict": auto_verdict,
            "audit": False,
        })

    auto_ids = [r["id"] for r in rows if r["auto_verdict"] is not None]
    audited = audit_sample(auto_ids, audit_rate, audit_seed)
    for r in rows:
        if r["id"] in audited:
            r["audit"] = True
    return rows


def summarize(rows: list[dict]) -> dict:
    """same/different/error counts, auto-transferred count, audit count, and
    rows remaining for Jon (different + error/unparsed + audited-same)."""
    same = sum(1 for r in rows if r["judge"] == "same")
    different = sum(1 for r in rows if r["judge"] == "different")
    error = sum(1 for r in rows if r["judge"] not in ("same", "different"))
    auto = sum(1 for r in rows if r["auto_verdict"] is not None)
    audit = sum(1 for r in rows if r["audit"])
    remaining = sum(1 for r in rows if r["judge"] != "same" or r["audit"])
    return {
        "n": len(rows), "same": same, "different": different, "error": error,
        "auto_transferred": auto, "audit": audit, "remaining_for_jon": remaining,
    }


def diff_and_audit_ids(judge_rows: list[dict]) -> set[str]:
    """ids that must go to Jon: judge-different/error rows plus audited
    auto-transfers."""
    return {r["id"] for r in judge_rows if r["judge"] != "same" or r["audit"]}


def build_reduced_review_rows(target_rows: list[dict], judge_rows: list[dict]) -> list[dict]:
    """Build reduced review rows for Jon's manual queue, with audit marking.

    For each row in target_rows that's in Jon's queue (different/error or audited):
    - Copy the row
    - If it's an audit row, set audit=True and prefix question with "[AUDIT] "

    Returns a list of reduced rows with audit labeling for the grading UI.
    """
    audit_by_id = {r["id"]: r["audit"] for r in judge_rows}
    jon_ids = diff_and_audit_ids(judge_rows)

    reduced = []
    for r in target_rows:
        if r["id"] in jon_ids:
            row_copy = dict(r)
            if audit_by_id.get(r["id"], False):
                row_copy["audit"] = True
                if "question" in row_copy:
                    row_copy["question"] = "[AUDIT] " + row_copy["question"]
            reduced.append(row_copy)
    return reduced


def rollup(manual: list[dict], auto: list[dict]) -> list[dict]:
    """Final per-arm verdicts = manual UNION auto; manual wins on any id
    present in both (Roll-up rule)."""
    by_id = {r["id"]: dict(r) for r in auto}
    for r in manual:
        by_id[r["id"]] = dict(r)
    return [by_id[k] for k in sorted(by_id)]


def judge_error_report(judge_rows: list[dict], manual_by_id: dict, threshold: float = 0.10) -> dict:
    """Audit rows where Jon's manual verdict disagrees with the transferred
    auto_verdict are a judge-error count. >threshold of the audit sample ->
    this arm's auto-verdicts are flagged unreliable (falls back to full
    manual per the Roll-up rule)."""
    audit_rows = [r for r in judge_rows if r["audit"]]
    errors = [
        r["id"] for r in audit_rows
        if r["id"] in manual_by_id and manual_by_id[r["id"]]["verdict"] != r["auto_verdict"]
    ]
    n = len(audit_rows)
    rate = (len(errors) / n) if n else 0.0
    return {
        "audit_n": n, "judge_errors": len(errors), "error_rate": rate,
        "unreliable": rate > threshold, "error_ids": errors,
    }


# ==================================================================
# IO / network -- not unit tested (network call), exercised by main()
# ==================================================================

def call_judge(question: str, reference: str, candidate: str, row_id: str,
               retries: int = MAX_RETRIES) -> str:
    """Wraps judge_bakeoff.or_judge() -- the validated OpenRouter call
    protocol, reused verbatim and unmodified -- with an outer retry loop
    (up to `retries` attempts) for transient failures, per task instructions.
    Leaves an honest "error" row if every attempt fails."""
    last = "error"
    for attempt in range(1, retries + 1):
        v = or_judge(JUDGE_SLUG, question, reference, candidate)
        if v not in ("error", "unparsed"):
            return v
        last = v
        if attempt < retries:
            print(f"    retry {attempt}/{retries} for {row_id} (got {v!r})", file=sys.stderr)
            time.sleep(2)
    return last


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _index_by_id(rows: list[dict]) -> dict:
    return {r["id"]: r for r in rows}


def run_arm(label: str, rebuild_html_only: bool = False) -> dict:
    target_rows = _load_json(PARSED / f"review_{label}.json")
    ref_rows = _load_json(PARSED / f"review_{REF_LABEL}.json")
    ref_verdicts = _load_json(EVALS / f"verdicts_{REF_LABEL}.json")

    ref_by_id = _index_by_id(ref_rows)
    ref_verdicts_by_id = _index_by_id(ref_verdicts)

    target_ids = {r["id"] for r in target_rows}
    ref_ids = {r["id"] for r in ref_rows}
    if target_ids != ref_ids:
        raise ValueError(
            f"{label}: id set doesn't match reference {REF_LABEL} "
            f"(only-in-target={target_ids - ref_ids}, only-in-ref={ref_ids - target_ids})"
        )
    missing_verdicts = target_ids - set(ref_verdicts_by_id)
    if missing_verdicts:
        raise ValueError(f"{label}: no human verdict for ids {missing_verdicts}")

    pairs_path = EVALS / f"judge_pairs_{label}.json"

    if rebuild_html_only:
        print(f"\n=== {label}: rebuilding HTML from existing {pairs_path.name} ===")
        judge_rows = _load_json(pairs_path)
    else:
        print(f"\n=== {label}: judging {len(target_rows)} pairs vs {REF_LABEL} "
              f"(judge={JUDGE_SLUG}) ===")

        def judge_fn(question, reference, candidate, rid):
            v = call_judge(question, reference, candidate, rid)
            print(f"  {rid}: judge={v}")
            return v

        judge_rows = build_judge_pairs(target_rows, ref_by_id, ref_verdicts_by_id, judge_fn)
        pairs_path.write_text(json.dumps(judge_rows, indent=2), encoding="utf-8")

    auto_rows = []
    for r in judge_rows:
        if r["auto_verdict"] is None:
            continue
        note = f"auto-transferred: judge=same vs {REF_LABEL} (ref_verdict={r['ref_verdict']})"
        if r["audit"]:
            note += " [AUDIT]"
        auto_rows.append({"id": r["id"], "verdict": r["auto_verdict"], "note": note})
    auto_path = EVALS / f"verdicts_{label}.auto.json"
    auto_path.write_text(json.dumps(auto_rows, indent=2), encoding="utf-8")

    reduced_rows = build_reduced_review_rows(target_rows, judge_rows)
    reduced_path = PARSED / f"review_{label}_diff.json"
    reduced_path.write_text(json.dumps(reduced_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    diff_html_path = PARSED / f"grading_{label}_diff.html"
    if reduced_rows:
        result = subprocess.run(
            [sys.executable, str(BUILD_GRADING_UI), "--in", str(reduced_path), "--out", str(diff_html_path)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"{label}: build_grading_ui.py failed (rc={result.returncode})")
        print(result.stdout.strip())
    else:
        diff_html_path.write_text("", encoding="utf-8")
        print(f"  {label}: nothing for Jon's queue -- all {len(target_rows)} auto-transferred, no audit rows")

    summary = summarize(judge_rows)
    summary["label"] = label
    summary["pairs_path"] = str(pairs_path)
    summary["auto_path"] = str(auto_path)
    summary["diff_html_path"] = str(diff_html_path)
    print(f"  {label} summary: same={summary['same']} different={summary['different']} "
          f"error={summary['error']} auto_transferred={summary['auto_transferred']} "
          f"audit={summary['audit']} remaining_for_jon={summary['remaining_for_jon']}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", required=True,
                    help="arm label, e.g. sonnet-v2 (reads data/parsed/review_<label>.json)")
    ap.add_argument("--rebuild-html-only", action="store_true",
                    help="rebuild HTML and reduced JSON from existing judge_pairs file (skip judging)")
    args = ap.parse_args()
    run_arm(args.target, rebuild_html_only=args.rebuild_html_only)
    if not args.rebuild_html_only:
        print(
            "\nAudit fallback rule: if Jon's manual grading of the AUDIT-labeled rows "
            "disagrees with the judge-transferred verdict on >10% of that arm's audit "
            "sample, this arm's auto-verdicts are unreliable and it falls back to full "
            "manual grading (see judge_error_report() / docs/plan-judge-transitive-grading.md)."
        )


if __name__ == "__main__":
    main()

"""Task 5: build Jon's grading queue for the v4 A/B -- question-grouped,
STABLE flips only (unstable flips excluded per the stable-flip rule; see
evals/judge_v4.py's docstring), same pattern evals/build_v3ab_queue.py
already uses (adapted here, not an edit to that frozen script, because its
ARMS/CONDITIONS/naming are specific to the 6-arm x 3-condition x 2-run v3
matrix and don't cover v4's 2-arm x 1-condition matrix).

Two rows per stable-flip question (one per run) so Jon grades the actual
answer text, not a summary. Uses build_grading_ui.py UNMODIFIED
(subprocess), matching the existing pattern.

Row question is prefixed "[arm/v4 rN vs derived-C:<ref_verdict>]" so Jon
sees the derived condition-C verdict being challenged.

Output: data/parsed/review_v4_queue.json + data/parsed/grading_v4_queue.html
(gitignored, regenerate don't commit -- matching data/parsed/ convention)
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402

EVALS = Path(__file__).parent
PARSED = EVALS.parent / "data" / "parsed"
BUILD_GRADING_UI = EVALS / "build_grading_ui.py"
SUMMARY_PATH = EVALS / "judge_v4_summary.json"

OUT_JSON = PARSED / "review_v4_queue.json"
OUT_HTML = PARSED / "grading_v4_queue.html"

ARMS = ["sonnet", "gpt-5-mini"]
RUNS = [1, 2]
COND = "v4"


def build() -> dict:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    rows = []
    stable_flip_index = []
    for arm in ARMS:
        entry = summary[arm]
        stable_ids = entry["stable_flip"]
        for qid in stable_ids:
            ref_verdict = entry["ref_verdict"][qid]
            review = L.review_rows_by_id(arm)[qid]
            stable_flip_index.append({
                "arm": arm, "id": qid, "ref_verdict": ref_verdict,
            })
            for run in RUNS:
                cand_rows = {r["id"]: r for r in L.load_condition_run(arm, COND, run)}
                cand = cand_rows[qid]
                rows.append({
                    "id": f"{arm}_{COND}_r{run}:{qid}",
                    "_arm": arm, "_run": run, "_qid": qid,
                    "kind": review.get("kind"),
                    "match": review.get("match"),
                    "answered": cand["answered"],
                    "question": f"[{arm}/v4 r{run} vs derived-C:{ref_verdict}] {review['question']}",
                    "answer": cand["answer"] or "(no answer -- see exception)",
                    "citations": cand["citations"],
                    "gold": review.get("gold") or [],
                    "gold_text": review.get("gold_text"),
                    "clarification": None,
                })

    rows.sort(key=lambda r: (r["_qid"], r["_arm"], r["_run"]))
    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    if rows:
        result = subprocess.run(
            [sys.executable, str(BUILD_GRADING_UI), "--in", str(OUT_JSON), "--out", str(OUT_HTML)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"build_grading_ui.py failed (rc={result.returncode})")
        print(result.stdout.strip())
    else:
        OUT_HTML.write_text("", encoding="utf-8")
        print("queue: 0 stable-flip questions -- nothing for Jon, no HTML built")

    n_questions = len({r["_qid"] + r["_arm"] for r in rows})
    print(f"queue: {n_questions} stable-flip (arm,question) pairs, "
          f"{len(rows)} rows (2 per pair) -> {OUT_HTML}")
    return {"n_pairs": n_questions, "n_rows": len(rows), "stable_flip_index": stable_flip_index}


if __name__ == "__main__":
    result = build()
    idx_path = EVALS / "v4_stable_flip_index.json"
    idx_path.write_text(json.dumps(result["stable_flip_index"], indent=2), encoding="utf-8")
    print(f"stable-flip index -> {idx_path}")

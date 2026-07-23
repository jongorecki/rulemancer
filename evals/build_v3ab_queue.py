"""Build Jon's grading queue for the prompt-v3 A/B (task-3 brief item 4).

Reads evals/judge_v3ab_summary.json (stable/unstable flips per arm x
condition, from judge_v3ab.py) and evals/retrieval_noise_tags.json, and
emits ONE combined grading queue -- question-grouped, STABLE flips only
(unstable flips are excluded per the brief's stable-flip rule; see
judge_v3ab.py's docstring).

Two rows per stable-flip question (one per run, since both runs diverged
from condition A but may have diverged differently) so Jon grades the
actual answer text he'll see, not a summary. Uses build_grading_ui.py
UNMODIFIED (subprocess), matching the shape/pattern build_combined_diff.py
already uses -- adapted here (new script, not an edit to that frozen
combiner) because its ARMS list and review_<label>_diff.json naming are
specific to the original 5-arm-vs-v3.2 bake-off and don't cover our
6-arm x 3-condition x 2-run matrix.

Row question is prefixed "[arm/cond rN vs A:<ref_verdict>]" so Jon sees the
condition-A verdict being challenged without relying on prior_verdict
lookup (which keys on unnamespaced ids and won't fire for these namespaced
rows). A "[retrieval-noise suspect]" tag is appended when the question's
retrieved rules-context differs unexpectedly between C and D (embedding
draw noise, not a B/C/D wording effect -- see retrieval_noise_v3ab.py).

Output: data/parsed/review_v3ab_queue.json + data/parsed/grading_v3ab_queue.html
(gitignored, like the rest of data/parsed/ -- regenerate, don't commit)
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
SUMMARY_PATH = EVALS / "judge_v3ab_summary.json"
NOISE_PATH = EVALS / "retrieval_noise_tags.json"

OUT_JSON = PARSED / "review_v3ab_queue.json"
OUT_HTML = PARSED / "grading_v3ab_queue.html"

# c004 is explicitly off the board for sonnet-v2 and deepseek-v4-pro
# (already resolved by Jon's pre-A/B ruling -- docs/plan-prompt-tuning.md
# §1d amendment). Kept live for every other arm.
C004_OFF_BOARD_ARMS = {"sonnet", "deepseek-v4-pro"}


def load_noise_tags() -> dict[str, str]:
    data = json.loads(NOISE_PATH.read_text(encoding="utf-8"))
    return {r["id"]: r["tag"] for r in data["rows"]}


def build() -> dict:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    noise_tags = load_noise_tags()

    rows = []
    stable_flip_index = []  # for the report: (arm, cond, qid, ref_verdict, noise_tag)
    for arm in L.ARMS:
        for cond in L.CONDITIONS:
            entry = summary[arm][cond]
            stable_ids = entry["stable_flip"]
            for qid in stable_ids:
                if qid == "c004" and arm in C004_OFF_BOARD_ARMS:
                    continue  # off the board -- never queued, never counted
                ref_verdict = entry["ref_verdict"][qid]
                review = L.review_rows_by_id(arm)[qid]
                noise = noise_tags.get(qid, "identical")
                noise_suffix = " [retrieval-noise suspect]" if noise == "retrieval_noise_suspect" else ""
                stable_flip_index.append({
                    "arm": arm, "condition": cond, "id": qid,
                    "ref_verdict": ref_verdict, "retrieval_noise_tag": noise,
                })
                for run in L.RUNS:
                    cand_rows = {r["id"]: r for r in L.load_condition_run(arm, cond, run)}
                    cand = cand_rows[qid]
                    rows.append({
                        "id": f"{arm}_{cond}_r{run}:{qid}",
                        "_arm": arm, "_condition": cond, "_run": run, "_qid": qid,
                        "kind": review.get("kind"),
                        "match": review.get("match"),
                        "answered": cand["answered"],
                        "question": f"[{arm}/{cond} r{run} vs A:{ref_verdict}]{noise_suffix} {review['question']}",
                        "answer": cand["answer"] or "(no answer -- see exception)",
                        "citations": cand["citations"],
                        "gold": review.get("gold") or [],
                        "gold_text": review.get("gold_text"),
                        "clarification": None,
                    })

    rows.sort(key=lambda r: (r["_qid"], r["_arm"], r["_condition"], r["_run"]))
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

    n_questions = len({r["_qid"] + r["_arm"] + r["_condition"] for r in rows})
    print(f"queue: {n_questions} stable-flip (arm,condition,question) triples, "
          f"{len(rows)} rows (2 per triple) -> {OUT_HTML}")
    return {"n_triples": n_questions, "n_rows": len(rows), "stable_flip_index": stable_flip_index}


if __name__ == "__main__":
    result = build()
    idx_path = EVALS / "v3ab_stable_flip_index.json"
    idx_path.write_text(json.dumps(result["stable_flip_index"], indent=2), encoding="utf-8")
    print(f"stable-flip index -> {idx_path}")

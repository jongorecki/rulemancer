"""Combine the five per-arm diff queues into ONE grading HTML for Jon.

Rows are sorted by question id (then arm), so divergent answers to the same
question sit adjacent for direct comparison. Ids are namespaced "arm:id" to
avoid collisions in the UI's autosave/export; each question is prefixed
"[arm]" (audit rows keep their existing "[AUDIT]" prefix from
judge_arm_pairs.py). build_grading_ui.py stays unmodified.

Build:  uv run python evals/build_combined_diff.py
        -> data/parsed/review_all_diff.json + data/parsed/grading_all_diff.html

Split Jon's single export back into per-arm manual files for the roll-up:
        uv run python evals/build_combined_diff.py --split <exported.json>
        -> evals/verdicts_<arm>_manual.json (one per arm present)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

EVALS = Path(__file__).parent
PARSED = EVALS.parent / "data" / "parsed"

ARMS = ["sonnet-v2", "deepseek-v4-pro", "deepseek-v4-flash",
        "gemini-flash-lite", "gpt-5-mini"]


def build() -> None:
    combined = []
    for arm in ARMS:
        rows = json.loads((PARSED / f"review_{arm}_diff.json").read_text(encoding="utf-8"))
        for r in rows:
            r["_arm"] = arm
            r["_qid"] = r["id"]
            r["id"] = f"{arm}:{r['id']}"
            r["question"] = f"[{arm}] {r['question']}"
            combined.append(r)
    combined.sort(key=lambda r: (r["_qid"], r["_arm"]))
    out_json = PARSED / "review_all_diff.json"
    out_json.write_text(json.dumps(combined, ensure_ascii=False, indent=1), encoding="utf-8")
    out_html = PARSED / "grading_all_diff.html"
    subprocess.run(
        [sys.executable, str(EVALS / "build_grading_ui.py"),
         "--in", str(out_json), "--out", str(out_html)],
        check=True,
    )
    n_audit = sum(1 for r in combined if r.get("audit"))
    print(f"combined: {len(combined)} rows ({n_audit} audit) -> {out_html}")


def split(export_path: Path) -> None:
    verdicts = json.loads(export_path.read_text(encoding="utf-8"))
    by_arm: dict[str, list] = {}
    skipped = []
    for v in verdicts:
        if ":" not in v["id"]:
            skipped.append(v["id"])
            continue
        arm, qid = v["id"].split(":", 1)
        by_arm.setdefault(arm, []).append({**v, "id": qid})
    for arm, rows in sorted(by_arm.items()):
        out = EVALS / f"verdicts_{arm}_manual.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{arm}: {len(rows)} verdicts -> {out.name}")
    if skipped:
        print(f"WARNING: {len(skipped)} un-namespaced ids skipped: {skipped}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", type=Path, default=None,
                    help="path to the single exported verdicts JSON; splits it into per-arm manual files")
    args = ap.parse_args()
    if args.split:
        split(args.split)
    else:
        build()


if __name__ == "__main__":
    main()

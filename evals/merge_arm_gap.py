"""Merge a gap re-run into a main arm file (one-shot repair tool).

The OpenRouter arm runner is single-shot with no retry, so an upstream 429
leaves an honest error row. This script splices a gap re-run (same model,
just the failed questions) back into the main arm file, and optionally
replaces the variance block with one from a clean --limit 0 --variance run.

Replacement rule: a gap row replaces its main-file counterpart only when the
main row ERRORED — a successful main-run answer is never overwritten (that
would quietly re-roll answers, which is exactly what a pinned eval must not
do). A gap row that itself errored (429 again) also replaces nothing.

Usage:
  uv run python evals/merge_arm_gap.py \
      --main evals/answers/openrouter_deepseek-deepseek-v4-flash.json \
      --gap evals/answers/gap_deepseek-v4-flash.json \
      [--variance-from evals/answers/variance_gap_deepseek-v4-flash.json]

Prints per-question replacement decisions and the recomputed summary.
Writes the main file IN PLACE (a .bak copy is written first).
"""

import argparse
import json
import shutil
from pathlib import Path


def recompute_summary(results: list[dict]) -> dict:
    return {
        "n_questions": len(results),
        "answered": sum(1 for r in results if not r.get("error") and r.get("answered")),
        "parse_failures": sum(1 for r in results if r.get("error")),
        "total_cost": sum((r.get("usage") or {}).get("cost", 0.0) for r in results),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, required=True)
    ap.add_argument("--gap", type=Path, required=True)
    ap.add_argument("--variance-from", type=Path, default=None,
                    help="take the 'variance' block from this file (a clean "
                         "--limit 0 --variance re-run)")
    args = ap.parse_args()

    main_doc = json.loads(args.main.read_text(encoding="utf-8"))
    gap_doc = json.loads(args.gap.read_text(encoding="utf-8"))
    assert main_doc["model"] == gap_doc["model"], "model mismatch — wrong files"

    gap_by_id = {r["id"]: r for r in gap_doc["results"]}
    replaced, still_failed, skipped_ok = [], [], []
    for i, row in enumerate(main_doc["results"]):
        gap_row = gap_by_id.get(row["id"])
        if gap_row is None:
            continue
        if not row.get("error"):
            skipped_ok.append(row["id"])   # main answer stands; never re-roll
            continue
        if gap_row.get("error"):
            still_failed.append(row["id"])  # 429'd again; keep the newer error
        else:
            replaced.append(row["id"])
        main_doc["results"][i] = gap_row

    if args.variance_from is not None:
        var_doc = json.loads(args.variance_from.read_text(encoding="utf-8"))
        assert var_doc["model"] == main_doc["model"], "model mismatch — wrong variance file"
        main_doc["variance"] = var_doc["variance"]

    main_doc["summary"] = recompute_summary(main_doc["results"])

    bak = args.main.with_suffix(".json.bak")
    shutil.copy2(args.main, bak)
    args.main.write_text(json.dumps(main_doc, indent=1), encoding="utf-8")

    print(f"replaced ({len(replaced)}): {', '.join(replaced) or '-'}")
    print(f"still failed ({len(still_failed)}): {', '.join(still_failed) or '-'}")
    print(f"untouched-ok in gap set ({len(skipped_ok)}): {', '.join(skipped_ok) or '-'}")
    print(f"summary: {json.dumps(main_doc['summary'])}")
    print(f"backup: {bak}")


if __name__ == "__main__":
    main()

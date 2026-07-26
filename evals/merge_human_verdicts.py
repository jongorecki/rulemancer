"""Merge a human gold-audit grading pass into an auto-judged verdict file.

WHY THIS IS A SEPARATE FILE AND NOT AN EDIT IN PLACE. The auto verdict file is
the judge's raw output, and the judge is now an experiment subject rather than a
fixed instrument: the gold audit found it marking semantically equivalent answers
as different, and re-judging found run-to-run nondeterminism. Measuring the
judge's false-negative rate needs the original verdict sitting next to the human
one, row by row. Overwriting `verdict` would destroy exactly that pairing. So
every row keeps the judge's `verdict` untouched and gains three fields:

    human_verdict   what the human grader called it (their vocabulary, verbatim)
    human_note      the grader's note, verbatim
    final_correct   the corrected truth used for the headline accuracy

and the summary carries BOTH `accuracy_auto` (what the judge scored) and
`accuracy` (after the approved overturns), so no reader has to guess which one a
number came from.

OVERTURNS ARE PASSED EXPLICITLY, NEVER DERIVED FROM THE VOCABULARY. It is
tempting to map a human verdict like "ambiguous" onto correct automatically. That
is wrong here and would have banked an unapproved point on the first use: batch 1
graded six rows `ambiguous`, but only five were approved as "both answers say the
same thing" -- the sixth (`rg5863`) is an open rules-precedence question. Which
rows get overturned is a human ruling, so it arrives as `--overturn` and is
written into the output summary as `human_overturned`.

Both known `by_level_counts` shapes are emitted, because both exist in this repo
and downstream re-scoring reads the field across historical arms:

    by_level_counts        {correct, n}      on final_correct  (corrected truth)
    by_level_counts_auto   {same, different} preserved from the judge

Usage:
    python evals/merge_human_verdicts.py \
        --auto evals/verdicts_derivability_B.json \
        --human data/parsed/gold_audit_verdicts.json \
        --out evals/verdicts_derivability_B_human.json \
        --overturn rg7215,rg549,rg1718,rg851,rg811 \
        --grader "Jon Gorecki" --date 2026-07-26
"""
from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from pathlib import Path


def _levels_of(entries):
    """Level labels in first-seen order, as strings ("0".."3", "Corner Case")."""
    seen = OrderedDict()
    for e in entries:
        seen.setdefault(str(e.get("level")), None)
    return list(seen)


def merge(auto: dict, human: list, overturn: set[str], grader: str, date: str,
          source_auto: str, source_human: str) -> dict:
    entries = auto["entries"]
    by_id = {e["id"]: e for e in entries}

    human_by_id = {h["id"]: h for h in human}
    missing = sorted(set(human_by_id) - set(by_id))
    if missing:
        raise SystemExit(f"human ids absent from the auto file: {missing}")

    # An overturn must name a row the judge actually scored "different". Flipping
    # a row that was already "same" would inflate the accuracy while looking like
    # a correction, which is the failure mode this check exists to catch.
    unknown = sorted(overturn - set(human_by_id))
    if unknown:
        raise SystemExit(f"--overturn ids absent from the human grading: {unknown}")
    not_disagreements = sorted(i for i in overturn if by_id[i].get("verdict") != "different")
    if not_disagreements:
        raise SystemExit(
            "--overturn ids the judge did not score 'different' "
            f"(nothing to overturn): {not_disagreements}"
        )

    merged = []
    for e in entries:
        row = dict(e)
        h = human_by_id.get(e["id"])
        row["human_verdict"] = h["verdict"] if h else None
        row["human_note"] = h.get("note") if h else None
        row["final_correct"] = (e.get("verdict") == "same") or (e["id"] in overturn)
        merged.append(row)

    n = len(merged)
    n_correct = sum(1 for r in merged if r["final_correct"])
    n_auto = sum(1 for r in merged if r.get("verdict") == "same")

    by_level, by_level_counts, by_level_counts_auto = {}, {}, {}
    for lvl in _levels_of(merged):
        rows = [r for r in merged if str(r.get("level")) == lvl]
        correct = sum(1 for r in rows if r["final_correct"])
        same = sum(1 for r in rows if r.get("verdict") == "same")
        by_level[lvl] = correct / len(rows)
        by_level_counts[lvl] = {"correct": correct, "n": len(rows)}
        by_level_counts_auto[lvl] = {"same": same, "different": len(rows) - same}

    summary = dict(auto.get("summary", {}))
    summary.update({
        "accuracy": n_correct / n,
        "accuracy_auto": n_auto / n,
        "by_level": by_level,
        "by_level_counts": by_level_counts,
        "by_level_counts_auto": by_level_counts_auto,
        "human_regraded": sorted(human_by_id),
        "human_overturned": sorted(overturn),
        "still_incorrect": sorted(r["id"] for r in merged if not r["final_correct"]),
        "grader": grader,
        "grading_date": date,
        "source_auto": source_auto,
        "source_human": source_human,
    })
    return {"entries": merged, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--auto", required=True, help="auto-judged verdicts JSON")
    ap.add_argument("--human", required=True, help="human grading JSON (id/verdict/note)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--overturn", default="",
                    help="comma-separated ids the human grading overturns to correct")
    ap.add_argument("--grader", default="Jon Gorecki")
    ap.add_argument("--date", required=True, help="grading date, YYYY-MM-DD")
    args = ap.parse_args()

    auto = json.loads(Path(args.auto).read_text(encoding="utf-8"))
    human = json.loads(Path(args.human).read_text(encoding="utf-8"))
    overturn = {i.strip() for i in args.overturn.split(",") if i.strip()}

    out = merge(auto, human, overturn, args.grader, args.date,
                args.auto.replace("\\", "/"), args.human.replace("\\", "/"))
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    s = out["summary"]
    print(f"wrote {args.out}")
    print(f"  auto   {s['accuracy_auto']:.1%}  ({round(s['accuracy_auto']*len(out['entries']))}/{len(out['entries'])})")
    print(f"  final  {s['accuracy']:.1%}  ({round(s['accuracy']*len(out['entries']))}/{len(out['entries'])})"
          f"   overturned {len(s['human_overturned'])}")
    for lvl, c in s["by_level_counts"].items():
        print(f"    L{lvl:<12} {c['correct']}/{c['n']}")


if __name__ == "__main__":
    main()

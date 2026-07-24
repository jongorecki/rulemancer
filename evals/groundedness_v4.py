"""Task 5: groundedness tripwire re-check over the v4 answers, reusing
evals/groundedness_v3ab.py's check_row()/citation_kind() UNCHANGED (imported,
not reimplemented) -- same rule-number/ruling-citation-vs-provided-context
check, just pointed at cond="v4" instead of B/C/D. Decision set only:
sonnet and gpt-5-mini (the two arms still in scope for v4/condition-E per
docs/plan-v4e-execution-tasks.md).

The current signed-off level (docs/plan-prompt-v4.md's read of DECISIONS.md
2026-07-24) is 7 instances / 5 distinct questions across ALL v3 arms x
conditions x runs. This script reports the v4-only count against that
level -- a spike is a discussion trigger for Jon, not an auto-no-go
(already ruled acceptable at the current level).

Output: evals/groundedness_v4.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402
from groundedness_v3ab import check_row  # noqa: E402 -- frozen, unmodified

OUT = Path(__file__).parent / "groundedness_v4.json"
ARMS = ["sonnet", "gpt-5-mini"]
RUNS = [1, 2]
COND = "v4"


def main() -> None:
    per_arm_run = {}
    all_ungrounded_qids: set[str] = set()
    all_instances = []
    n_other_total = 0

    for arm in ARMS:
        for run in RUNS:
            rows = L.load_condition_run(arm, COND, run)
            checked = [check_row(COND, r) for r in rows]
            checked = [c for c in checked if c is not None]
            n_answered_true = len(checked)
            bad = [c for c in checked if c["ungrounded"]]
            n_other_total += sum(len(c["other_citations"]) for c in checked)
            key = f"{arm}_{COND}_r{run}"
            per_arm_run[key] = {
                "arm": arm, "condition": COND, "run": run,
                "n_answered_true": n_answered_true,
                "n_rows_with_ungrounded_citation": len(bad),
                "rows": bad,
            }
            for b in bad:
                all_ungrounded_qids.add(b["id"])
                all_instances.append({"arm": arm, "run": run, **b})

    summary = {
        "note": "v4-only groundedness re-check (Task 5 item 3), sonnet + gpt-5-mini only "
                "(v4 decision set). Compare against the signed-off v3 level of 7 instances / "
                "5 distinct questions across ALL v3 arms x conditions x runs -- a spike here "
                "is a discussion trigger, not an auto-no-go (Jon already ruled the v3 level "
                "acceptable, DECISIONS.md 2026-07-24).",
        "n_other_citations_excluded_from_tripwire": n_other_total,
        "distinct_questions_with_ungrounded_citation": sorted(all_ungrounded_qids),
        "n_distinct_questions_flagged": len(all_ungrounded_qids),
        "n_instances_total": len(all_instances),
        "v3_signed_off_level": "7 instances / 5 distinct questions across ALL 6 v3 arms x B/C/D x r1/r2",
        "per_arm_condition_run": per_arm_run,
        "instances": all_instances,
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"v4 groundedness tripwire: {len(all_instances)} instances / "
          f"{len(all_ungrounded_qids)} distinct questions -> {OUT}")
    if all_instances:
        for inst in all_instances:
            print(f"  {inst['arm']} r{inst['run']} {inst['id']}: {inst['ungrounded']}")


if __name__ == "__main__":
    main()

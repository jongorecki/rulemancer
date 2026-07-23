"""Groundedness tripwire (task-3 brief item 3; docs/plan-prompt-tuning.md
§3 row 1c -- the highest-risk item in the core bundle: the multiplayer-
default bullet (§1c) explicitly forbids inventing multiplayer facts not in
the provided context, and the go/no-go criterion in §4.7 fails if this
check spikes on more than 1-2 questions across all arms).

For every B/C/D answer with answered:true, check every RULE-NUMBER or
ruling-label citation appears in that question's provided-context
bracket-label set for that condition (parsed from _prompts_<cond>.json's
user text -- see lib_v3ab.context_ids). Citations that are bare card names
or prose (not a CR-style number or a "... ruling #N" label) are reported
separately as "other_citations" and excluded from the tripwire count --
several arms cite a card by name directly under the new §1e
card-text-overrides bullet ("name the specific text"), which is legitimate
grounding (the card IS in the Card data block) but isn't a rule-number
claim, and counting it would flood this check with noise unrelated to the
actual §1c/F4 risk (a model stating a rule that sounds real but wasn't
retrieved for this question).

Condition A: its prompts were never captured (task brief), so this exact
check can't be replayed on A. Reported here: B/C/D rates only, with that
limitation stated plainly (per brief item 3's explicit fallback).

Output: evals/groundedness_v3ab.json
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402

OUT = Path(__file__).parent / "groundedness_v3ab.json"

RULING_RE = re.compile(r"ruling\s*#\d+", re.I)
RULE_NUM_RE = re.compile(r"\b\d{3}\.\d+[a-z]?\b")


def citation_kind(c: str) -> str:
    """Classify a citation string so the tripwire targets what the brief
    actually asks for: invented/unbacked RULE NUMBERS (and ruling refs) --
    not bare card-name citations. Several arms (esp. gpt-5-mini) cite a
    card's own name directly (legitimate under the §1e card-text-overrides
    bullet -- "name the specific text" -- since the card IS present in the
    Card data block by name), which isn't a rule-number claim at all and
    would otherwise flood this check with false positives unrelated to the
    §1c/F4 groundedness risk it's meant to catch."""
    if RULING_RE.search(c):
        return "ruling"
    if RULE_NUM_RE.fullmatch(c):
        return "rule_number"
    if RULE_NUM_RE.search(c):
        return "rule_number_embedded"  # e.g. "rule 607.3", "601.2f-h"
    return "other"  # card name / prose reference / glossary phrase, not a rule cite


def check_row(cond: str, row: dict) -> dict | None:
    """None if not applicable (answered != true, or an exception row).
    Otherwise {id, n_citations, ungrounded (rule/ruling only), other_citations}."""
    if row["exception"] is not None:
        return None
    if row["answered"] is not True:
        return None
    provided = L.context_ids(cond, row["id"])
    ungrounded, other = [], []
    for c in row["citations"]:
        kind = citation_kind(c)
        if kind == "other":
            other.append(c)
            continue
        if kind == "ruling":
            ok = c in provided
        else:  # rule_number or rule_number_embedded: check every embedded number
            nums = RULE_NUM_RE.findall(c)
            ok = bool(nums) and all(n in provided for n in nums)
        if not ok:
            ungrounded.append(c)
    return {
        "id": row["id"], "n_citations": len(row["citations"]),
        "ungrounded": ungrounded, "other_citations": other,
    }


def main() -> None:
    per_arm_cond = {}
    all_ungrounded_qids: set[str] = set()
    all_ungrounded_instances = []
    n_other_total = 0

    for arm in L.ARMS:
        for cond in L.CONDITIONS:
            for run in L.RUNS:
                rows = L.load_condition_run(arm, cond, run)
                checked = [check_row(cond, r) for r in rows]
                checked = [c for c in checked if c is not None]
                n_answered_true = len(checked)
                bad = [c for c in checked if c["ungrounded"]]
                n_other_total += sum(len(c["other_citations"]) for c in checked)
                key = f"{arm}_{cond}_r{run}"
                per_arm_cond[key] = {
                    "arm": arm, "condition": cond, "run": run,
                    "n_answered_true": n_answered_true,
                    "n_rows_with_ungrounded_citation": len(bad),
                    "rows": bad,
                }
                for b in bad:
                    all_ungrounded_qids.add(b["id"])
                    all_ungrounded_instances.append({"arm": arm, "condition": cond, "run": run, **b})

    # roll up per arm/condition (both runs) for the report table
    by_arm_cond = {}
    for arm in L.ARMS:
        for cond in L.CONDITIONS:
            r1 = per_arm_cond[f"{arm}_{cond}_r1"]
            r2 = per_arm_cond[f"{arm}_{cond}_r2"]
            by_arm_cond[f"{arm}_{cond}"] = {
                "n_answered_true": r1["n_answered_true"] + r2["n_answered_true"],
                "n_rows_with_ungrounded_citation": (
                    r1["n_rows_with_ungrounded_citation"] + r2["n_rows_with_ungrounded_citation"]
                ),
            }

    summary = {
        "note": "Condition A prompts were never captured -- this check cannot be "
                "replayed on A; B/C/D rates only (task-3 brief item 3 fallback). "
                "Scope: rule-number and ruling-label citations only -- bare "
                "card-name citations are tracked separately as other_citations "
                "and excluded from this count (see module docstring).",
        "n_other_citations_excluded_from_tripwire": n_other_total,
        "distinct_questions_with_ungrounded_citation_anywhere": sorted(all_ungrounded_qids),
        "n_distinct_questions_flagged": len(all_ungrounded_qids),
        "go_no_go_threshold": "no-go if > 1-2 distinct questions flagged across ALL arms (§4.7)",
        "per_arm_condition_run": per_arm_cond,
        "per_arm_condition_rollup": by_arm_cond,
        "instances": all_ungrounded_instances,
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"groundedness tripwire: {len(all_ungrounded_qids)} distinct questions flagged "
          f"across all arms/conditions/runs -> {OUT}")
    if all_ungrounded_qids:
        print(f"  flagged ids: {sorted(all_ungrounded_qids)}")
    for k, v in by_arm_cond.items():
        if v["n_rows_with_ungrounded_citation"]:
            print(f"  {k}: {v['n_rows_with_ungrounded_citation']} ungrounded rows "
                  f"/ {v['n_answered_true']} answered:true")


if __name__ == "__main__":
    main()

"""Freeze the non-layers regression sample for the layer-system tool's Slice 0
and Slice 5 arms (docs/plan-layer-system-tool.md Sec 6.1/6.2, build spec
docs/spec-slice0-harness.md Task 4).

Slice 0 compares a CONTROL arm (a system prompt carrying CR 613.6 + 611.3a)
against a BASE arm, and Slice 5 compares the layers tool on vs off. Per Jon's
Sec 8.2 ruling both are judged on win-rate AND regression, because the two
interventions carry asymmetric risk: a system-prompt bullet is a GLOBAL change
that applies to every question in the corpus, while the tool only fires when its
trigger trips (5.1% of the non-layers pool). Measuring that asymmetry needs a
non-layers sample that is identical across every arm and every rep -- hence a
frozen, committed file rather than a sample re-drawn per run.

Population:
  rows of evals/rulesguru_full.jsonl whose id is NOT in
  evals/_layers_union_slice.jsonl (the 68 CR-613-citing rows), AND which carry
  a truthy `answer_gold`.

Excluding the union ids guarantees ZERO overlap with the bucket-A win-rate set,
so a regression row can never double as a win-rate row.

RELATION TO THE CALIBRATION SCRIPT (verified 2026-07-24, not assumed):
evals/calibrate_layers_trigger.py builds its `non_layers_plain` sample from the
same non-union population with the same random.seed(613), but WITHOUT the
`answer_gold` filter -- it only asks whether the trigger regex fires, which
needs no gold. The filter here exists because the regression arm measures ANSWER
CORRECTNESS and judge_rulesguru.py skips any row without gold, so an ungraded
row would silently shrink the effective sample.

On today's corpus that filter is a NO-OP: all 1,341 non-union rows carry
`answer_gold`, so this sample's 100 ids are IDENTICAL to the calibration
script's plain sample (checked by set comparison, not by inspection). That is
a useful property, not a coincidence to rely on: it means the regression arm
runs on exactly the rows the 5.1% trigger fire-rate was measured against.

The filter is kept as a guard. If the corpus ever gains gold-less rows the two
samples WILL diverge, and this file -- not the calibration script -- is the one
the arms are measured on. Re-check the identity before restating it.

Run: `uv run python evals/build_layers_regression_sample.py`
"""

import json
import random
from pathlib import Path

EVALS_DIR = Path(__file__).parent
FULL_CORPUS_PATH = EVALS_DIR / "rulesguru_full.jsonl"
UNION_SLICE_PATH = EVALS_DIR / "_layers_union_slice.jsonl"
OUT_PATH = EVALS_DIR / "_layers_regression_sample.jsonl"

SEED = 613  # same seed as calibrate_layers_trigger.py, different population
SAMPLE_N = 100


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    full_rows = _load_jsonl(FULL_CORPUS_PATH)
    union_ids = {r["id"] for r in _load_jsonl(UNION_SLICE_PATH)}

    non_union = [r for r in full_rows if r["id"] not in union_ids]
    population = [r for r in non_union if r.get("answer_gold")]
    dropped_by_gold_filter = len(non_union) - len(population)

    if len(population) < SAMPLE_N:
        raise SystemExit(
            f"population is {len(population)} rows, need at least {SAMPLE_N}"
        )

    random.seed(SEED)
    sampled_ids = {r["id"] for r in random.sample(population, SAMPLE_N)}

    # Write in master-corpus order, not sample order, so the file is stable and
    # diffable regardless of how random.sample happened to order its draw.
    sampled = [r for r in full_rows if r["id"] in sampled_ids]

    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        for row in sampled:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"corpus rows:              {len(full_rows)}")
    print(f"union-slice ids excluded: {len(union_ids)}")
    print(f"non-union rows:           {len(non_union)}")
    print(f"dropped by gold filter:   {dropped_by_gold_filter}")
    print(f"population:               {len(population)}")
    print(f"sampled (seed={SEED}):      {len(sampled)} -> {OUT_PATH}")
    overlap = sampled_ids & union_ids
    print(f"overlap with union slice: {len(overlap)} (must be 0)")


if __name__ == "__main__":
    main()

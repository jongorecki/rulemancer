"""Freeze the row set for the retrieval-value A/B (docs/spec-retrieval-value-ab.md,
Row selection). 120 rows: 40 each from level 2, level 3, and Corner Case, drawn
from evals/rulesguru_full_v2.jsonl.

Deliberately NOT corpus-representative -- L0/L1 are 86.7%/70.0% confounded (the
model answers them without rules, so retrieval can't show an effect there), so
this draws only where retrieval could matter.

Rules for the draw (spec):
  - Stratified random WITHIN level, fixed seed (SEED = 613, this project's
    frozen-sample convention -- see build_h2h_set.py /
    build_layers_regression_sample.py), spread across the file -- NOT a
    prefix. random.Random(SEED).sample() over the full sorted eligible id
    list per level satisfies this: sample() draws without replacement from
    the whole population, so it can land anywhere, not just the head.
  - Gold-bearing rows only (skip the 153 empty-gold rows corpus-wide).
  - Exclude every row whose id is the `source_qid` of a evals/purerules.jsonl
    row -- that is the held-out set. purerules ids are pr001..pr008; the
    OVERLAP with rulesguru_full_v2 is via each purerules row's `source_qid`
    field (e.g. pr001 -> source_qid "rg5800"), since purerules rows were
    derived FROM specific rulesguru_full_v2 rows and carry a different id
    scheme of their own. Excluding by source_qid is what actually keeps the
    held-out set out of the drawn sample; a literal id-string exclusion
    would be a no-op (pr* ids never appear in rulesguru_full_v2 at all).

Zero API cost: this only reads/filters/samples existing jsonl rows written to
disk already. No retrieval, no embedding, no model call of any kind.

Run: uv run python evals/build_ab_rows.py
"""

import json
import random
from pathlib import Path

REPO = Path(__file__).parent.parent
SOURCE = REPO / "evals" / "rulesguru_full_v2.jsonl"
PURERULES = REPO / "evals" / "purerules.jsonl"
OUT = REPO / "evals" / "ab_rows.jsonl"

SEED = 613  # this project's frozen-sample seed convention
LEVELS = ("2", "3", "Corner Case")
N_PER_LEVEL = 40


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def purerules_source_qids(path: Path) -> set[str]:
    """The set of rulesguru_full_v2 ids that a purerules.jsonl row was
    derived from -- the actual held-out set to exclude (see module
    docstring: purerules' own `id` field, e.g. "pr001", never overlaps a
    rulesguru_full_v2 id, so it's `source_qid` that carries the exclusion)."""
    return {row["source_qid"] for row in load_jsonl(path)}


def draw_rows(rows: list[dict], exclude: set[str]) -> list[dict]:
    by_level: dict[str, list[dict]] = {lvl: [] for lvl in LEVELS}
    for row in rows:
        lvl = row.get("level")
        if lvl not in by_level:
            continue
        if not row.get("gold"):
            continue
        if row["id"] in exclude:
            continue
        by_level[lvl].append(row)

    drawn: list[dict] = []
    for lvl in LEVELS:
        pool = sorted(by_level[lvl], key=lambda r: r["id"])
        if len(pool) < N_PER_LEVEL:
            raise SystemExit(
                f"[ERROR] level {lvl!r} has only {len(pool)} eligible rows "
                f"(need {N_PER_LEVEL}) after excluding empty-gold and purerules"
            )
        rng = random.Random(SEED)
        sample = rng.sample(pool, N_PER_LEVEL)
        sample.sort(key=lambda r: r["id"])
        drawn.extend(sample)
        print(f"level {lvl!r}: {len(pool)} eligible -> drew {len(sample)}")
    return drawn


def main() -> None:
    rows = load_jsonl(SOURCE)
    exclude = purerules_source_qids(PURERULES)
    print(f"purerules held-out source_qids ({len(exclude)}): {sorted(exclude)}")

    drawn = draw_rows(rows, exclude)

    overlap = {r["id"] for r in drawn} & exclude
    if overlap:
        raise SystemExit(f"[ERROR] drawn set intersects purerules held-out set: {sorted(overlap)}")

    with OUT.open("w", encoding="utf-8") as f:
        for row in drawn:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = {lvl: sum(1 for r in drawn if r["level"] == lvl) for lvl in LEVELS}
    print(f"\nwrote {OUT.name}: {len(drawn)} rows -- {counts}")
    print(f"seed: {SEED}")


if __name__ == "__main__":
    main()

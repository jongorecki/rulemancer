"""Draw one fixed, level-stratified subset for the cross-judge comparison.

Every judge (gpt-5-mini, a Claude panel, and two neutral third-family judges)
must vote on the SAME rows, or a ranking difference could be a sampling
difference. Writes the id list to the repo so the draw is reproducible and
shared rather than re-rolled per judge.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evals" / "rulesguru_full_v2.jsonl"
OUT = ROOT / "evals" / "_crossjudge_subset.json"

N_TARGET = 150
SEED = 20260727

rows = [json.loads(l) for l in CORPUS.open(encoding="utf-8") if l.strip()]
by_level: dict[str, list[str]] = {}
for r in rows:
    by_level.setdefault(str(r.get("level")), []).append(r["id"])

total = len(rows)
rng = random.Random(SEED)

# proportional allocation with largest-remainder rounding, floor 5 per stratum so
# even Corner Case (69 rows corpus-wide) can move the needle
raw = {lv: len(ids) / total * N_TARGET for lv, ids in by_level.items()}
alloc = {lv: max(5, int(v)) for lv, v in raw.items()}
while sum(alloc.values()) > N_TARGET:
    lv = max(alloc, key=lambda k: alloc[k] - raw[k])
    if alloc[lv] > 5:
        alloc[lv] -= 1
    else:
        break
while sum(alloc.values()) < N_TARGET:
    lv = max(alloc, key=lambda k: raw[k] - alloc[k])
    alloc[lv] += 1

picked: list[str] = []
for lv in sorted(by_level):
    ids = sorted(by_level[lv])
    take = min(alloc[lv], len(ids))
    picked.extend(rng.sample(ids, take))

picked.sort()
OUT.write_text(json.dumps({
    "seed": SEED,
    "n": len(picked),
    "corpus": CORPUS.name,
    "allocation": {lv: alloc[lv] for lv in sorted(alloc)},
    "corpus_level_counts": {lv: len(v) for lv, v in sorted(by_level.items())},
    "ids": picked,
}, indent=1), encoding="utf-8")

print(f"corpus {total} rows")
for lv in sorted(by_level):
    share = len(by_level[lv]) / total
    got = alloc[lv]
    print(f"  level {lv:<12} corpus {len(by_level[lv]):>4} ({share*100:4.1f}%)"
          f"  -> drew {got:>3} ({got/len(picked)*100:4.1f}%)")
print(f"\nwrote {OUT.relative_to(ROOT)}: {len(picked)} ids, seed {SEED}")
print("first 8:", picked[:8])

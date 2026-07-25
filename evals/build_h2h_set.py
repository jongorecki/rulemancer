"""Build the 36-row sonnet-vs-gpt-5-mini head-to-head question set.

Purpose: decide whether the product can move off claude-sonnet-5 for cost
reasons. The held-out gap is 15 points (sonnet 72% vs gpt-5-mini 57%,
monotonic across every difficulty tier), and tools are NOT the deciding factor
-- measured 2026-07-24, the layers tool fires on only 4 of gpt-5-mini's 64
held-out misses and the cost tool on 0, so tools address ~2 points of a
15-point gap. This set therefore compares the two generators WITHOUT tools,
which is the comparison the cost decision actually turns on.

WHY BOTH MISSES AND HITS. Testing a candidate only on the incumbent's misses
guarantees a flattering result: every recovery is visible and every new
breakage is invisible. It is the same asymmetry that Sec 8.2 of
plan-layer-system-tool.md exists to prevent for the layers tool. Half this set
is rows sonnet got RIGHT, so a swap that fixes three misses while breaking
five hits shows up as the regression it is.

Source: evals/layers_slice0_verdicts_base_layers_r1.json -- the completed
Slice 0 BASE arm (bucket-A COMPUTE rows, layers tool off, 66.7%). Using that
arm means sonnet's verdict on every row here already exists and costs nothing
to compare against.

LEVEL MATCHING IS IMPERFECT AND THAT IS RECORDED, NOT HIDDEN. The 18 misses
are level 2 x10, level 3 x5, Corner Case x3. The 36 hits contain NO Corner
Case rows at all -- sonnet went 0-for-3 on Corner Case in this arm -- so the
three Corner Case misses cannot be level-matched. Levels 2 and 3 are matched
exactly; the remaining slots are filled from the hardest available level. Any
read of this set must treat the Corner Case rows as miss-only.

Run: `uv run python evals/build_h2h_set.py`
"""

import collections
import json
import random
from pathlib import Path

EVALS = Path(__file__).resolve().parent
VERDICTS = EVALS / "layers_slice0_verdicts_base_layers_r1.json"
SOURCE_ROWS = EVALS / "_layers_union_slice.jsonl"
OUT = EVALS / "_h2h_set.jsonl"
SEED = 613  # same seed convention as the other frozen eval samples


def main() -> None:
    v = json.loads(VERDICTS.read_text(encoding="utf-8"))
    misses = [e for e in v["entries"] if e["verdict"] == "different"]
    hits = [e for e in v["entries"] if e["verdict"] == "same"]

    want = collections.Counter(e.get("level") for e in misses)
    by_level: dict[str, list] = collections.defaultdict(list)
    for e in hits:
        by_level[e.get("level")].append(e)

    rng = random.Random(SEED)
    for lvl in by_level:
        rng.shuffle(by_level[lvl])

    chosen: list = []
    unmatched: dict[str, int] = {}
    for lvl, n in want.items():
        avail = by_level.get(lvl, [])
        take = min(n, len(avail))
        chosen += avail[:take]
        by_level[lvl] = avail[take:]
        if take < n:
            unmatched[lvl] = n - take

    # Fill any shortfall from the hardest levels still available, so the
    # control half stays as difficult as possible rather than drifting easy.
    order = ["Corner Case", "3", "2", "1", "0"]
    while len(chosen) < len(misses):
        for lvl in order:
            if by_level.get(lvl):
                chosen.append(by_level[lvl].pop(0))
                break
        else:
            break

    keep = {e["id"] for e in misses} | {e["id"] for e in chosen}
    rows = [
        json.loads(line)
        for line in SOURCE_ROWS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [r for r in rows if r["id"] in keep]

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for r in selected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"misses (sonnet wrong): {len(misses)}  {dict(want)}")
    print(f"hits   (sonnet right): {len(chosen)}  "
          f"{dict(collections.Counter(e.get('level') for e in chosen))}")
    if unmatched:
        print(f"COULD NOT LEVEL-MATCH: {unmatched} "
              f"(no hits exist at that level -- treat as miss-only)")
    print(f"wrote {len(selected)} rows -> {OUT}")
    assert len(selected) == len(keep), "id collision or missing source row"


if __name__ == "__main__":
    main()

"""Wait for the 16 gpt-5-mini shard runs, then merge them into one answers file.

The fair cross-model comparison: gpt-5-mini answering the byte-identical frozen
prompts opus-5 answered, so the only variable is the model. `run_openrouter_arm.py`
is serial (~52s/row), so the corpus was split across 16 parallel `--qids` shards
plus a 161-row partial from an earlier serial attempt.

Run: .venv/Scripts/python.exe evals/merge_gpt5mini_shards.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "evals" / "answers"
PROGRESS = ANSWERS / "_progress"
CORPUS = ROOT / "evals" / "rulesguru_full_v2.jsonl"
OUT = ANSWERS / "gpt5mini_fair_merged.json"

SHARDS = [ANSWERS / f"gpt5mini_sh{k}.json" for k in range(16)]
PARTIAL = ANSWERS / "gpt5mini_fair_1409.json"
TIMEOUT_S = 90 * 60
POLL_S = 30


def rows_of(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []                      # mid-write; caller retries
    rows = d.get("results", d) if isinstance(d, dict) else d
    return rows if isinstance(rows, list) else []


def shards_running() -> int:
    """How many shard progress files still say running."""
    n = 0
    for k in range(16):
        p = PROGRESS / f"gpt5mini_sh{k}.json"
        if not p.exists():
            continue
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            n += 1                     # assume alive if unreadable mid-write
            continue
        if j.get("status") == "running" and j.get("n_done", 0) < j.get("n_total", 0):
            n += 1
    return n


def main() -> int:
    waited = 0
    while waited < TIMEOUT_S:
        alive = shards_running()
        if alive == 0:
            break
        time.sleep(POLL_S)
        waited += POLL_S
    else:
        print(f"[WARN] timed out after {TIMEOUT_S}s with {shards_running()} shards "
              f"still running -- merging what exists, honestly short")

    # Reference answers must be stamped onto the rows here. `run_answer_eval.py`
    # does this itself via load_answer_gold(), but `run_openrouter_arm.py` does
    # not, and `judge_norules_control.py` reads `answer_gold` off the ANSWERS
    # file -- so without this the judge exits with "no answer_gold-carrying rows".
    corpus_rows = [json.loads(l) for l in CORPUS.open(encoding="utf-8") if l.strip()]
    want = [r["id"] for r in corpus_rows]
    gold = {r["id"]: r for r in corpus_rows}
    merged: dict[str, dict] = {}
    dupes: list[str] = []

    for src in [PARTIAL, *SHARDS]:
        got = rows_of(src)
        for r in got:
            rid = r.get("id")
            if not rid:
                continue
            if rid in merged:
                dupes.append(rid)
                continue               # first writer wins; report the collision
            merged[rid] = r
        print(f"  {src.name:32} {len(got):>5} rows")

    missing = [i for i in want if i not in merged]
    extra = [i for i in merged if i not in set(want)]

    # The two generation paths disagree on the answer field name:
    # run_answer_eval.py writes `answer`, run_openrouter_arm.py writes `text`.
    # judge_norules_control.py reads r["answer"], so normalise here rather than
    # teaching the judge about a second key -- one canonical shape reaching the
    # judge is what keeps cross-model verdicts comparable.
    renamed = 0
    stamped = 0
    for rid, row in merged.items():
        if not row.get("answer") and row.get("text"):
            row["answer"] = row["text"]
            renamed += 1
        src = gold.get(rid)
        if not src:
            continue
        for field in ("answer_gold", "gold", "match", "kind", "level", "complexity"):
            if field in src and not row.get(field):
                row[field] = src[field]
        if row.get("answer_gold"):
            stamped += 1

    ordered = [merged[i] for i in want if i in merged]
    print(f"\nstamped answer_gold on {stamped}/{len(merged)} rows "
          f"(from {CORPUS.name})")
    print(f"copied `text` -> `answer` on {renamed}/{len(merged)} rows "
          f"(openrouter arms use `text`, the judge reads `answer`)")
    no_answer = [i for i, r in merged.items()
                 if not (r.get("answer") or "").strip()]
    print(f"rows with no answer text: {len(no_answer)}"
          + (f"  e.g. {no_answer[:5]}" if no_answer else ""))
    OUT.write_text(json.dumps(ordered, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(ordered)} rows")
    print(f"  corpus size        : {len(want)}")
    print(f"  missing            : {len(missing)}"
          + (f"  e.g. {missing[:8]}" if missing else ""))
    print(f"  duplicate ids seen : {len(dupes)}"
          + (f"  e.g. {dupes[:5]}" if dupes else ""))
    print(f"  ids not in corpus  : {len(extra)}"
          + (f"  e.g. {extra[:5]}" if extra else ""))

    empties = sum(1 for r in ordered
                  if len((r.get("answer") or r.get("text") or "").strip()) < 40)
    print(f"  short/empty answers: {empties}")

    cost = 0.0
    for k in range(16):
        p = PROGRESS / f"gpt5mini_sh{k}.json"
        if p.exists():
            try:
                cost += json.loads(p.read_text(encoding="utf-8")).get(
                    "cost_so_far", 0.0) or 0.0
            except json.JSONDecodeError:
                pass
    print(f"  shard cost (OpenRouter, excl. the earlier serial attempt): ${cost:.2f}")

    if missing:
        print("\n[INCOMPLETE] not all corpus rows present -- judge this only if you "
              "intend to report accuracy on the subset that exists, and say so.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

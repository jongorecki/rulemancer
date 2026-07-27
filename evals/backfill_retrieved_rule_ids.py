"""Stamp `retrieved_rule_ids` onto answer rows from a frozen --prompts-cache.

WHY THIS EXISTS. Jon, 2026-07-26/27: `headline_full_votes3` (and the two
rules86 arms) ran with `--prompts-cache`, so retrieval happened once at
cache-build time and the answer writer never re-recorded
`retrieved_rule_ids` on the answer rows themselves (there was no live
retrieval call during generation to record it from). The metrics-history
classifier (`evals/build_metrics_history.py::classify_arm`) reads exactly
that field and, finding it absent, has no choice but to guess -- and one
prior guess called an arm "oracle" (no rules given) when the frozen prompts
in fact contained a full rules-context block on every row.

The rules the model actually saw are NOT lost -- they're sitting in the
prompt text inside the cache file, formatted by `build_prompt()`'s
"Rules context:\n[id] text\n..." block. `answer.py` already has the exact,
non-heuristic parser for that block
(`available_sources_from_prompt_text` / `_RULES_CONTEXT_ID_RE` /
`_prompt_section`), because `evals/grounding_sources.py` needed the same
reconstruction for citation scoring. This script reuses that machinery
rather than writing a second parser -- a divergent second parser is how
this repo ended up with two definitions of "not a real card" earlier
tonight (docs/HANDOFF-development.md).

This does NOT special-case any arm by name. It parses whatever prompt text
is on disk for a row and writes exactly what's there; an arm whose frozen
prompts genuinely lack a rules block will still come back empty, and the
caller is expected to treat that as signal, not paper over it.

Usage:
    .venv/Scripts/python.exe evals/backfill_retrieved_rule_ids.py \\
        evals/answers/headline_full.json evals/answers/_prompts_rulesguru_full_v2raw.json \\
        evals/answers/rules86_real.json evals/answers/_prompts_rules86_real_v2raw.json \\
        evals/answers/rules86_placebo.json evals/answers/_prompts_rules86_placebo_v2raw.json

Pass answers/cache path pairs; each pair is backfilled and written in place
(the answers file only -- the cache is read-only). Prints, per file, how
many rows got a non-empty `retrieved_rule_ids`, the mean count per row, and
two sample rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # noqa: E402

from rulesagent.generate.answer import available_sources_from_prompt_text  # noqa: E402


def _load_cache_prompts(path: Path) -> dict:
    """{qid: {"system":..., "user":...}} -- unwraps the cache file's
    "prompts" key the same way evals/grounding_sources.py::_load_cache does,
    since a --prompts-cache file is {derived_from, arm, ..., "prompts": {...}}."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("prompts", raw) if isinstance(raw, dict) else {}


def backfill(answers_path: Path, cache_path: Path) -> dict:
    """Stamp `retrieved_rule_ids` onto every row of `answers_path` that has a
    matching entry in `cache_path`, in place. Returns a summary dict."""
    rows = json.loads(answers_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list), f"{answers_path} is not a list of rows"
    prompts = _load_cache_prompts(cache_path)

    n_total = len(rows)
    n_no_cache_entry = 0
    n_stamped_nonempty = 0
    n_stamped_empty = 0
    id_counts = []
    samples = []

    for row in rows:
        qid = row.get("id")
        entry = prompts.get(qid) if qid is not None else None
        if entry is None:
            n_no_cache_entry += 1
            continue
        user_text = entry.get("user", "")
        sources = available_sources_from_prompt_text(user_text)
        ids = sorted(sources.rules_context_ids)
        row["retrieved_rule_ids"] = ids
        if ids:
            n_stamped_nonempty += 1
            id_counts.append(len(ids))
            if len(samples) < 2:
                samples.append((qid, ids))
        else:
            n_stamped_empty += 1

    answers_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    mean_ids = sum(id_counts) / len(id_counts) if id_counts else 0.0
    return {
        "file": str(answers_path),
        "n_total": n_total,
        "n_no_cache_entry": n_no_cache_entry,
        "n_stamped_nonempty": n_stamped_nonempty,
        "n_stamped_empty": n_stamped_empty,
        "mean_ids_per_row": mean_ids,
        "samples": samples,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2 or len(argv) % 2 != 0:
        print(__doc__)
        return 2
    pairs = [(Path(argv[i]), Path(argv[i + 1])) for i in range(0, len(argv), 2)]
    for answers_path, cache_path in pairs:
        summary = backfill(answers_path, cache_path)
        print(f"\n=== {summary['file']} ===")
        print(f"  rows total: {summary['n_total']}")
        print(f"  no matching cache entry: {summary['n_no_cache_entry']}")
        print(f"  stamped non-empty retrieved_rule_ids: {summary['n_stamped_nonempty']}")
        print(f"  stamped EMPTY retrieved_rule_ids: {summary['n_stamped_empty']}")
        print(f"  mean ids/row (over non-empty rows): {summary['mean_ids_per_row']:.2f}")
        for qid, ids in summary["samples"]:
            print(f"  sample {qid}: {ids[:6]}{' ...' if len(ids) > 6 else ''} (n={len(ids)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

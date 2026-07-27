"""Reusable citation-source scorer (docs/results-groundedness-guard.md).

Classifies every row's citations into cr_rule / ruling / card / glossary /
unresolved and reports per-arm rates -- CR-reliance rate, rulings/cards/
glossary rate, a standalone glossary rate, nothing-resolvable rate,
unresolved-citation rate. Works on ANY answers file on disk, not just ones
generated after this feature shipped:

- Rows generated after this feature shipped already carry `citation_sources`
  -- scored directly, no reconstruction needed (source="row").
- Older rows carry only `citations` plus (sometimes) a `prompts_cache` path
  that was recorded at generation time. If that cache file still exists on
  disk, the exact frozen prompt text the model actually saw is reloaded and
  re-classified from it (source="prompts_cache") -- this is retroactive
  scoring of real prompt text, not a guess.
- Everything else (no prompts_cache recorded for that row, or the file is
  gone) is reported as honestly unknown and excluded from the rate
  denominators -- never guessed, never silently folded into a rate as if
  it had been resolved (docs/HANDOFF-development.md: "Do NOT guess").

No Anthropic client anywhere in this module -- pure offline computation
over files already on disk, the same kind of $0 local-compute analysis
that produced the finding in docs/results-groundedness-guard.md.

Run: `.venv/Scripts/python.exe evals/grounding_sources.py FILE [FILE ...]`
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # noqa: E402

from rulesagent.generate.answer import (  # noqa: E402
    available_sources_from_prompt_text,
    citation_source_breakdown,
)

_CACHE_MEMO: dict[str, dict | None] = {}


def _load_cache(path: str | None) -> dict | None:
    """Load and memoize a --prompts-cache JSON file by path (many rows in
    the same arm share one cache file, so this avoids re-reading it once
    per row). Returns the {qid: {system, user}} mapping itself -- a cache
    file on disk is {derived_from, arm, ..., "prompts": {qid: {...}}}
    (see evals/run_openrouter_arm.py --assemble-only, the writer), so this
    unwraps the "prompts" key when present rather than handing back the
    whole metadata dict. Falls back to the dict as-is for a cache that's
    already qid-keyed at the top level. Returns None -- never raises --
    when the path is unset, missing, or unparseable; callers treat that as
    "can't reconstruct"."""
    if not path:
        return None
    if path not in _CACHE_MEMO:
        p = Path(path)
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                _CACHE_MEMO[path] = raw.get("prompts", raw) if isinstance(raw, dict) else None
            except (json.JSONDecodeError, OSError):
                _CACHE_MEMO[path] = None
        else:
            _CACHE_MEMO[path] = None
    return _CACHE_MEMO[path]


_UNKNOWN = {
    "labels": None, "cr_rule": None, "ruling": None, "card": None,
    "glossary": None, "unresolved": None, "category": "unknown",
    "cites_cr_rule": None,
}


def score_row(row: dict) -> dict:
    """A citation_source_breakdown()-shaped dict for one row, plus a
    `"source"` provenance key: "row" (already computed at generation time),
    "prompts_cache" (reconstructed from a still-present cache file), or
    "unknown" (cannot be scored -- reported honestly, never guessed)."""
    existing = row.get("citation_sources")
    if existing is not None:
        out = dict(existing)
        out["cites_cr_rule"] = row.get("cites_cr_rule")
        out["source"] = "row"
        return out

    cache = _load_cache(row.get("prompts_cache"))
    if cache is not None and row.get("id") in cache:
        user = cache[row["id"]].get("user", "")
        sources = available_sources_from_prompt_text(user)
        out = citation_source_breakdown(row.get("citations") or [], sources)
        out["source"] = "prompts_cache"
        return out

    out = dict(_UNKNOWN)
    out["source"] = "unknown"
    return out


def score_arm(rows: list[dict]) -> dict:
    """Per-arm rates over ANSWERED rows only -- docs/results-groundedness-
    guard.md's headline finding ("ZERO ungrounded answered rows") is about
    answered rows; a declined row has no citations to be grounded in by
    contract. Rows that score "unknown" are excluded from the rate
    denominators but counted and reported separately, never silently
    treated as resolved."""
    scored = []
    n_unknown = 0
    n_answered = 0
    for row in rows:
        if not row.get("answered"):
            continue
        n_answered += 1
        s = score_row(row)
        if s["source"] == "unknown":
            n_unknown += 1
        else:
            scored.append(s)

    n = len(scored)
    if n == 0:
        return {
            "n_answered": n_answered, "n_scored": 0, "n_unknown": n_unknown,
            "cr_reliance_rate": None, "rulings_only_rate": None,
            "glossary_rate": None,
            "nothing_resolvable_rate": None, "unresolved_citation_rate": None,
        }

    cr_reliant = sum(1 for s in scored if s["category"] == "cr_reliant")
    rulings_only = sum(1 for s in scored if s["category"] == "rulings_or_cards_only")
    nothing = sum(1 for s in scored if s["category"] == "nothing_resolvable")
    unresolved_rows = sum(1 for s in scored if (s["unresolved"] or 0) > 0)
    # Standalone visibility for glossary as a GROUNDED source, shown
    # alongside (never folded silently into) rulings_only_rate -- a row
    # scored "row" from before the glossary amendment simply has no
    # "glossary" key, hence the .get(): it's honestly 0 for that row, not a
    # crash. Not a canary (glossary presence is expected and fine); the only
    # two canary columns remain nothing_resolvable_rate/unresolved_citation_rate.
    glossary_rows = sum(1 for s in scored if (s.get("glossary") or 0) > 0)

    return {
        "n_answered": n_answered,
        "n_scored": n,
        "n_unknown": n_unknown,
        "cr_reliance_rate": cr_reliant / n,
        "rulings_only_rate": rulings_only / n,
        "glossary_rate": glossary_rows / n,
        "nothing_resolvable_rate": nothing / n,
        "unresolved_citation_rate": unresolved_rows / n,
    }


def score_file(path: Path) -> dict:
    """Load one answers JSON file (either shape on disk: a plain list, like
    run_answer_eval.py writes, or a {"results": [...]} dict, like
    run_openrouter_arm.py writes) and score it."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["results"] if isinstance(data, dict) and "results" in data else data
    return score_arm(rows)


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.1%}"
    return str(v)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("answers", nargs="+", type=Path, help="answers JSON file(s) to score")
    args = p.parse_args()
    for path in args.answers:
        metrics = score_file(path)
        print(f"{path}:")
        for k, v in metrics.items():
            print(f"  {k}: {_fmt(v)}")


if __name__ == "__main__":
    main()

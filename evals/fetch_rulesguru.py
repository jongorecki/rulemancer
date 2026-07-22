"""Fetch + convert RulesGuru eval questions (docs/plan-rulesguru-import.md).

RulesGuru (rulesguru.org) hosts judge-curated MTG rules questions with a
public API. Each question ships with a human-written gold answer
(`answerSimple`) and the CR rule numbers that answer cites (`citedRules`) --
exactly the two things the hand-curated `cards.jsonl` set is missing (most of
those entries have empty rules-gold, per docs/plan-card-gold-ablation.md).

Two stages, one script:

1. FETCH (skipped with --convert-only): five requests, one per level
   ("0", "1", "2", "3", "Corner Case"), count=30 each, all three
   complexities, legality="all". Raw responses merge additively into
   evals/rulesguru_raw.json, deduped by RulesGuru id -- a re-run never
   re-fetches what's already on disk, it only tops up. Rate limit is one
   request per 2 seconds; we sleep 2.5s between requests to be safe.

2. CONVERT: evals/rulesguru_raw.json -> evals/rulesguru.jsonl, one line per
   question, matching the questions.jsonl/cards.jsonl schema (contracts.py's
   EvalQuestion) plus a few extra fields the loader is required to tolerate
   (answer_gold, level, complexity, tags, url, submitter). Runs entirely
   offline from the raw file -- no network needed for --convert-only -- so
   the raw fetch and the conversion logic can be iterated on separately.

Run:
  uv run python evals/fetch_rulesguru.py                # fetch (additive) + convert
  uv run python evals/fetch_rulesguru.py --convert-only  # convert only, no network
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

REPO = Path(__file__).parent.parent
CR_PATH = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
RAW_PATH = Path(__file__).parent / "rulesguru_raw.json"
JSONL_PATH = Path(__file__).parent / "rulesguru.jsonl"

API_URL = "https://rulesguru.org/api/questions/"
LEVELS = ["0", "1", "2", "3", "Corner Case"]  # Jon's call: full spread, not hard-only
COMPLEXITIES = ["Simple", "Intermediate", "Complicated"]  # all three, every request
COUNT_PER_LEVEL = 30  # target 150 total (5 levels x 30); a target, not a contract --
# a thin level (Corner Case is likely thin at some complexities) just returns fewer.
SLEEP_S = 2.5  # rate limit is 1 req / 2s; sleep a bit longer to be safe


# --------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------

def fetch_level(level: str, count: int = COUNT_PER_LEVEL) -> list[dict]:
    settings = {
        "count": count,
        "level": [level],
        "complexity": COMPLEXITIES,
        "legality": "all",
        "from": "rulemancer-evals",
    }
    url = f"{API_URL}?json={urllib.parse.quote(json.dumps(settings))}"
    r = httpx.get(url, timeout=30.0)
    r.raise_for_status()
    return r.json()


def load_raw() -> list[dict]:
    if RAW_PATH.exists():
        return json.loads(RAW_PATH.read_text(encoding="utf-8"))
    return []


def save_raw(records: list[dict]) -> None:
    RAW_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_and_merge() -> tuple[list[dict], dict[str, int]]:
    """Fetch all five level strata and merge additively (by id) into whatever
    is already on disk. Returns (merged records, {level: count actually
    returned by the API this run}) -- the per-level counts are what
    verification reports, since dedup against a prior run can otherwise hide
    how many the API gave us just now."""
    existing = load_raw()
    by_id = {q["id"]: q for q in existing}
    per_level_returned: dict[str, int] = {}
    for i, level in enumerate(LEVELS):
        got = fetch_level(level)
        per_level_returned[level] = len(got)
        print(f"  level={level!r}: {len(got)} returned")
        for q in got:
            by_id[q["id"]] = q  # dedupe by RulesGuru id; last-fetched wins (should be identical anyway)
        if i < len(LEVELS) - 1:
            time.sleep(SLEEP_S)
    merged = list(by_id.values())
    save_raw(merged)
    return merged, per_level_returned


# --------------------------------------------------------------------------
# Convert
# --------------------------------------------------------------------------

def bracket_card_names(text: str, names: list[str]) -> str:
    """Bracket each card's first occurrence in `text`, longest names first.

    Processing longest-first and tracking claimed spans means a short name
    that's a substring of a longer one already bracketed (e.g. "Bears" sitting
    inside "Grizzly Bears") can't grab a second, overlapping bracket around
    part of the longer name -- it's simply left unbracketed, since the longer
    name already covers that mention in context. Each name gets at most one
    bracket (its first occurrence); a name with zero occurrences in the text
    is silently skipped.
    """
    claimed: list[tuple[int, int]] = []
    for name in sorted({n for n in names if n}, key=len, reverse=True):
        pattern = re.compile(re.escape(name))
        m = pattern.search(text)  # first occurrence only
        if m is None:
            continue
        s, e = m.span()
        if any(s < ce and cs < e for cs, ce in claimed):
            continue  # overlaps a longer name's already-claimed span
        claimed.append((s, e))
    claimed.sort()
    out, last = [], 0
    for s, e in claimed:
        out.append(text[last:s])
        out.append(f"[{text[s:e]}]")
        last = e
    out.append(text[last:])
    return "".join(out)


def convert_record(
    raw: dict, chunk_ids: set[str] | None = None, drift: list[dict] | None = None
) -> dict:
    """One RulesGuru raw object -> one rulesguru.jsonl record.

    `chunk_ids`/`drift` are optional so this stays a pure, network-free unit
    -- tests exercise it without ever parsing the Comprehensive Rules. When
    `chunk_ids` is given, cited rule ids that don't resolve as real chunks
    (CR version drift between RulesGuru's snapshot and ours) are logged and
    appended to `drift`, but KEPT in the record's gold -- a drifted id is
    still what RulesGuru's answer actually cites, and dropping it would hide
    the drift rather than surface it.
    """
    rg_id = raw["id"]
    names = [c.get("name", "") for c in raw.get("includedCards", []) if c.get("name")]
    question = bracket_card_names(raw.get("questionSimple", ""), names)
    # The API's "Simple" variants are documented as plain text (no HTML) --
    # assert that holds rather than silently shipping markup into an eval
    # question. Checked post-bracketing, but bracketing never introduces
    # '<', so this is equivalent to checking the raw text.
    assert "<" not in question, f"rg{rg_id}: '<' survived in question text -- not plain text as expected"

    gold = sorted(raw.get("citedRules", {}) or {})  # empty citedRules -> gold []
    if chunk_ids is not None:
        missing = [g for g in gold if g not in chunk_ids]
        if missing:
            print(f"  [DRIFT] rg{rg_id}: gold ids not found as chunks: {missing}")
            if drift is not None:
                drift.append({"id": f"rg{rg_id}", "missing": missing})

    return {
        "id": f"rg{rg_id}",
        "question": question,
        "cards": names,
        "gold": gold,
        "match": "any",
        "kind": "rulesguru",
        "answer_gold": raw.get("answerSimple", ""),
        "level": raw.get("level", ""),
        "complexity": raw.get("complexity", ""),
        "tags": raw.get("tags", []) or [],
        "url": raw.get("url", ""),
        "submitter": raw.get("submitterName", ""),
    }


def load_chunk_ids() -> set[str]:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    return {c.source_id for c in chunks}


def convert_all(raw_records: list[dict], chunk_ids: set[str]) -> tuple[list[dict], list[dict]]:
    drift: list[dict] = []
    converted = [convert_record(r, chunk_ids, drift) for r in raw_records]
    return converted, drift


def write_jsonl(records: list[dict]) -> None:
    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--convert-only",
        action="store_true",
        help="skip the network fetch; convert whatever is already in evals/rulesguru_raw.json",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.convert_only:
        raw_records = load_raw()
        if not raw_records:
            print(f"[ERROR] no raw data at {RAW_PATH.name} -- run without --convert-only first")
            return
        print(f"--convert-only: converting {len(raw_records)} cached raw records (no network)\n")
    else:
        print(f"Fetching RulesGuru questions: {len(LEVELS)} levels x count={COUNT_PER_LEVEL}\n")
        raw_records, _ = fetch_and_merge()
        print(f"\n{len(raw_records)} total raw records on disk -> {RAW_PATH}\n")

    print("Parsing Comprehensive Rules for gold-id validation...")
    chunk_ids = load_chunk_ids()
    print(f"  {len(chunk_ids)} chunk ids\n")

    converted, drift = convert_all(raw_records, chunk_ids)
    write_jsonl(converted)

    by_level: dict[str, int] = {}
    for rec in converted:
        by_level[rec["level"]] = by_level.get(rec["level"], 0) + 1
    print(f"Wrote {len(converted)} questions -> {JSONL_PATH}")
    print("  per level (final jsonl):")
    for level in LEVELS:
        print(f"    {level:<14} {by_level.get(level, 0)}")
    empty_gold = sum(1 for r in converted if not r["gold"])
    print(f"  empty-gold questions (citedRules was empty): {empty_gold}/{len(converted)}")
    print(f"  gold-id drift: {len(drift)} question(s) with a cited id not found as a chunk")
    if drift:
        for d in drift:
            print(f"    {d['id']}: {d['missing']}")


if __name__ == "__main__":
    main()

"""Fetch the FULL RulesGuru question set via sequential `previousId` paging.

This is a companion to `fetch_rulesguru.py`, not a replacement -- it reuses
that script's conversion logic (bracket_card_names / convert_record /
load_chunk_ids) so the row schema is identical. `evals/rulesguru.jsonl` (the
frozen 150) and `evals/rulesguru_raw.json` are NEVER touched by this script;
everything here writes to new `_full` files.

Why sequential paging instead of the original script's stratified random
sampling: the RulesGuru API docs (rulesguru.org/api/documentation/) describe
a `previousId` parameter -- "the returned questions will not be random.
Instead they'll be the next X questions that match the given settings that
come after the given id." Combined with `legality: "all"` and every level /
complexity in one request, this walks the ENTIRE id space in order in a
handful of large pages, instead of 15 separate random-sampled strata that
would need many repeated calls each to approach exhaustion by chance.

Verified live 2026-07-24:
  - id=1 does not exist -> starting at previousId=1 loses nothing.
  - count=500 with previousId works reliably for the full (all levels, all
    complexities, legality=all) filter.
  - count=1000 also worked; count=1500/2000 returned 404 "not enough
    questions" -- so the live pool sits somewhere under ~1500 matching
    questions. We don't need to know the exact number: paging stops itself
    when a page comes back shorter than requested, or 404s (handled by
    shrinking the count and retrying, still on the rate limit).

Run:
  uv run python evals/fetch_rulesguru_full.py                # fetch (additive) + convert
  uv run python evals/fetch_rulesguru_full.py --convert-only  # convert only, no network
"""

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from fetch_rulesguru import (  # noqa: E402
    API_URL,
    COMPLEXITIES,
    LEVELS,
    SLEEP_S,
    CR_PATH,
    convert_record,
)

REPO = Path(__file__).parent.parent
RAW_FULL_PATH = Path(__file__).parent / "rulesguru_raw_full.json"
JSONL_FULL_PATH = Path(__file__).parent / "rulesguru_full.jsonl"

PAGE_SIZE = 500  # confirmed working page size for the full (all levels/complexities) filter


# --------------------------------------------------------------------------
# Sequential fetch
# --------------------------------------------------------------------------

def fetch_page(previous_id: int, count: int) -> httpx.Response:
    settings = {
        "count": count,
        "previousId": previous_id,
        "level": LEVELS,
        "complexity": COMPLEXITIES,
        "legality": "all",
        "from": "rulemancer-evals",
    }
    url = f"{API_URL}?json={urllib.parse.quote(json.dumps(settings))}"
    return httpx.get(url, timeout=30.0)


def fetch_all_sequential() -> list[dict]:
    """Page through the whole matching pool via previousId, starting after
    id=0 (id=1 confirmed not to exist, so nothing is skipped). Stops when a
    page returns fewer than requested (last page) or the API 404s meaning
    no more remain, shrinking the page size on 404 to find the true
    remainder rather than giving up. A safety cap on iterations guards
    against an unexpected infinite loop (e.g. wraparound not detected)."""
    by_id: dict[int, dict] = {}
    previous_id = 1  # id=1 does not exist; first real id is 2
    page_size = PAGE_SIZE
    consecutive_empty = 0
    max_iterations = 50  # generous; real run needs ~3-6 pages
    for it in range(max_iterations):
        resp = fetch_page(previous_id, page_size)
        if resp.status_code == 404:
            print(f"  [404] previousId={previous_id} count={page_size}: {resp.text[:80]}")
            if page_size <= 1:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    print("  no more questions remain after two empty probes -- done")
                    break
                time.sleep(SLEEP_S)
                continue
            page_size = max(1, page_size // 4)
            time.sleep(SLEEP_S)
            continue
        resp.raise_for_status()
        got = resp.json()
        print(f"  previousId={previous_id} count={page_size}: {len(got)} returned")
        if not got:
            break
        new_ids = 0
        max_id_this_page = previous_id
        for q in got:
            if q["id"] not in by_id:
                new_ids += 1
            by_id[q["id"]] = q
            max_id_this_page = max(max_id_this_page, q["id"])
        if max_id_this_page <= previous_id:
            # wrapped around (ids not increasing) -- we've circled the whole set
            print("  ids did not advance -- wraparound detected, stopping")
            break
        previous_id = max_id_this_page
        page_size = PAGE_SIZE  # reset to full size after a successful page
        if len(got) < page_size and new_ids == 0:
            print("  short page with no new ids -- done")
            break
        time.sleep(SLEEP_S)
    else:
        print(f"  [WARN] hit max_iterations={max_iterations} safety cap -- stopping early")
    return list(by_id.values())


def load_raw_full() -> list[dict]:
    if RAW_FULL_PATH.exists():
        return json.loads(RAW_FULL_PATH.read_text(encoding="utf-8"))
    return []


def save_raw_full(records: list[dict]) -> None:
    RAW_FULL_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------
# Convert (reuses fetch_rulesguru.convert_record)
# --------------------------------------------------------------------------

def load_chunk_ids_if_available() -> set[str] | None:
    """Returns None (not a failure) if data/raw is absent in this worktree --
    gold-id validation is then skipped and reported as 'not checked here'."""
    if not CR_PATH.exists():
        print(f"  [SKIP] {CR_PATH} not present in this worktree -- gold-id validation skipped")
        return None
    from fetch_rulesguru import load_chunk_ids
    return load_chunk_ids()


def convert_all(raw_records: list[dict], chunk_ids: set[str] | None) -> tuple[list[dict], list[dict]]:
    drift: list[dict] = []
    converted = [convert_record(r, chunk_ids, drift) for r in raw_records]
    return converted, drift


def write_jsonl(records: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--convert-only", action="store_true",
                    help="skip the network fetch; convert whatever is already in evals/rulesguru_raw_full.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.convert_only:
        raw_records = load_raw_full()
        if not raw_records:
            print(f"[ERROR] no raw data at {RAW_FULL_PATH.name} -- run without --convert-only first")
            return
        print(f"--convert-only: converting {len(raw_records)} cached raw records (no network)\n")
    else:
        print("Fetching FULL RulesGuru question set via sequential previousId paging\n")
        raw_records = fetch_all_sequential()
        save_raw_full(raw_records)
        print(f"\n{len(raw_records)} distinct records -> {RAW_FULL_PATH}\n")

    print("Checking for parsed Comprehensive Rules (gold-id validation)...")
    chunk_ids = load_chunk_ids_if_available()
    if chunk_ids is not None:
        print(f"  {len(chunk_ids)} chunk ids\n")

    converted, drift = convert_all(raw_records, chunk_ids)
    write_jsonl(converted, JSONL_FULL_PATH)

    by_level: dict[str, int] = {}
    by_complexity: dict[str, int] = {}
    for rec in converted:
        by_level[rec["level"]] = by_level.get(rec["level"], 0) + 1
        by_complexity[rec["complexity"]] = by_complexity.get(rec["complexity"], 0) + 1
    print(f"Wrote {len(converted)} questions -> {JSONL_FULL_PATH}")
    print("  per level:")
    for level in LEVELS:
        print(f"    {level:<14} {by_level.get(level, 0)}")
    print("  per complexity:")
    for c in COMPLEXITIES:
        print(f"    {c:<14} {by_complexity.get(c, 0)}")
    empty_gold = sum(1 for r in converted if not r["gold"])
    print(f"  empty-gold questions (citedRules was empty): {empty_gold}/{len(converted)}")
    if chunk_ids is not None:
        print(f"  gold-id drift: {len(drift)} question(s) with a cited id not found as a chunk")
    else:
        print("  gold-id drift: not checked here (data/raw/ absent in this worktree)")


if __name__ == "__main__":
    main()

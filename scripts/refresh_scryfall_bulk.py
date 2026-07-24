"""Refresh `data/scryfall.db` from Scryfall's bulk-data files
(docs/plan-scryfall-local-bulk.md Sec 5).

Three distinct triggers, per Jon's spec (not one mechanism):
  1. Set-calendar auto-refresh -- `should_calendar_refresh()` / `in_refresh_
     window()`: a real download+swap, gated to a window around each set's
     `released_at` (-8 days through +21 days, Jon's ruling 2026-07-23),
     light cadence (proposed every 3-4 days) within an active window.
  2. Manual trigger (CLI, this script's __main__, or the admin endpoint):
     `refresh()` unconditionally, any time.
  3. Daily freshness check, metadata-only, NEVER downloads: `check_
     staleness()` compares Scryfall's live bulk-data `updated_at` against
     what this store's own `meta` table recorded at last import. Per Jon's
     ruling and the verified evidence (plan Sec 1) that Scryfall's bulk
     timestamps change ~daily regardless of content, a naive "timestamp
     changed -> download" trigger would download ~172 MB daily for nothing
     and make the staleness signal meaningless.

`refresh()` builds into a temp file next to the real store and only ever
`os.replace()`s it in at the very end (atomic on the same volume) -- any
exception before that point aborts loudly and leaves the existing store
byte-for-byte untouched (Sec 5 step 6).

Run: uv run python scripts/refresh_scryfall_bulk.py
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.tools import scryfall_store  # noqa: E402

HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}
BULK_DATA_URL = "https://api.scryfall.com/bulk-data"

# Jon's ruling (2026-07-23): "Refresh starting 8 days before each set's
# released_at through 21 days after." Grounding: prerelease is 7 days before
# release and all cards are spoiled by prerelease, so day -8 catches the
# full spoiler set with a day of margin.
CALENDAR_WINDOW_BEFORE_DAYS = 8
CALENDAR_WINDOW_AFTER_DAYS = 21
# Light in-window cadence (plan Sec 5 item 1 proposal, not separately ruled
# by Jon -- "every 3-4 days, not daily... more than the observed
# content-change rate justifies"). Tunable, like the fuzzy threshold.
CALENDAR_REFRESH_CADENCE_DAYS = 3

# Sanity gate (Sec 5 step 4): comfortably below the verified 34,786-name
# catalog count (plan Sec 1) but far above "something went badly wrong" --
# a truncated/corrupt download lands far short of this.
MIN_EXPECTED_CARDS = 25000
_SPOT_CHECK_SAMPLE = 10


# --- network seams (tests monkeypatch these two, nothing else) -------------


def _fetch_bulk_data_metadata() -> dict:
    response = httpx.get(BULK_DATA_URL, headers=HEADERS, timeout=30.0)
    response.raise_for_status()
    return response.json()


def _download_bytes(url: str) -> bytes:
    response = httpx.get(url, headers=HEADERS, timeout=300.0)
    response.raise_for_status()
    return response.content


def find_bulk_object(bulk_data_response: dict, bulk_type: str) -> dict:
    """`bulk_data_response` is the raw {"data": [...]} envelope from
    GET /bulk-data; find the object whose `type` matches (e.g.
    "oracle_cards" or "rulings")."""
    for obj in bulk_data_response.get("data", []):
        if obj.get("type") == bulk_type:
            return obj
    raise KeyError(f"no bulk-data object of type {bulk_type!r}")


# --- transform: raw Scryfall JSON -> the dict shape scryfall_store wants ---


def _face_from_scryfall(f: dict) -> dict:
    return {
        "name": f.get("name", "") or "",
        "mana_cost": f.get("mana_cost", "") or "",
        "type_line": f.get("type_line", "") or "",
        "oracle_text": f.get("oracle_text", "") or "",
        "power": f.get("power", "") or "",
        "toughness": f.get("toughness", "") or "",
        "loyalty": f.get("loyalty", "") or "",
        "defense": f.get("defense", "") or "",
        "colors": f.get("colors", []) or [],
        "color_indicator": f.get("color_indicator", []) or [],
    }


def project_card(data: dict) -> dict:
    """One raw oracle_cards JSON object -> the dict build_store() expects.
    Ported from the old (now-removed) live-fetch `_card_from_json` in
    tools/scryfall.py -- same face-joining logic (Sec 2's "what the code
    does today", now the import script's job instead of a per-request
    live-fetch's)."""
    oracle_text = data.get("oracle_text") or ""
    if not oracle_text and data.get("card_faces"):
        oracle_text = "\n//\n".join(
            face.get("oracle_text", "") for face in data["card_faces"]
        )

    if data.get("card_faces"):
        faces = [_face_from_scryfall(f) for f in data["card_faces"]]
    else:
        faces = [_face_from_scryfall(data)]

    return {
        "oracle_id": data.get("oracle_id", ""),
        "name": data.get("name", ""),
        "oracle_text": oracle_text,
        "type_line": data.get("type_line", ""),
        "mana_cost": data.get("mana_cost", ""),
        "layout": data.get("layout", "") or "",
        "mana_value": data.get("cmc", 0.0) or 0.0,
        "colors": data.get("colors", []) or [],
        "color_identity": data.get("color_identity", []) or [],
        "faces": faces,
    }


def filter_and_project(oracle_cards_raw: list[dict]) -> list[dict]:
    """lang == "en" only (plan Sec 9 non-goal: "no non-English cards --
    matches today's scope"), and drop any entry missing the fields a row
    needs to exist at all."""
    return [
        project_card(c)
        for c in oracle_cards_raw
        if c.get("lang") == "en" and c.get("oracle_id") and c.get("name")
    ]


def project_rulings(rulings_raw: list[dict]) -> dict[str, list[str]]:
    """Group ruling comments by oracle_id, preserving file order (Scryfall's
    rulings bulk file is already chronological per card) -- this is exactly
    the order `rulings.idx` needs for `ruling_id()`'s stable oracle_id#index
    expectation (Sec 7 test 7)."""
    grouped: dict[str, list[str]] = {}
    for r in rulings_raw:
        oracle_id = r.get("oracle_id")
        if not oracle_id:
            continue
        grouped.setdefault(oracle_id, []).append(r.get("comment", ""))
    return grouped


# --- sanity gate (Sec 5 step 4) --------------------------------------------


def sanity_check(conn, cards_input: list[dict]) -> tuple[bool, str]:
    """Row-count sanity (not zero, not wildly short of the real catalog)
    plus a spot-check that a sample of the cards just imported round-trip
    correctly. Returns (ok, message) -- never raises itself, so the caller
    decides what "failed" means for control flow."""
    count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    if count < MIN_EXPECTED_CARDS:
        return False, f"only {count} cards in store, expected >= {MIN_EXPECTED_CARDS}"

    sample = cards_input[:_SPOT_CHECK_SAMPLE] + cards_input[-_SPOT_CHECK_SAMPLE:]
    for c in sample:
        found = scryfall_store.lookup_oracle_id(conn, c["oracle_id"])
        if found is None:
            return False, f"spot-check failed: oracle_id {c['oracle_id']!r} not found after import"
        if found.name != c["name"]:
            return False, (
                f"spot-check failed: oracle_id {c['oracle_id']!r} name mismatch "
                f"(expected {c['name']!r}, got {found.name!r})"
            )
    return True, f"{count} cards, {len(sample)}-card spot-check passed"


def atomic_swap(tmp_path: Path, dest_path: Path) -> None:
    """`os.replace()` -- atomic on POSIX and on Windows/NTFS when both paths
    share a volume (Sec 5 step 5). `tmp_path` must live in the same
    directory as `dest_path` (see refresh() below) -- never a different
    drive or the OS temp dir."""
    import os

    os.replace(tmp_path, dest_path)


# --- orchestration: manual/CLI trigger + shared import function ------------


def refresh(dest_path: Path = scryfall_store.DEFAULT_DB) -> dict:
    """The real refresh: fetch bulk-data metadata, download oracle_cards +
    rulings, transform, build into a temp file next to `dest_path`,
    sanity-gate, atomic-swap. Any exception before the swap aborts loudly
    and leaves `dest_path` (if it already existed) completely untouched --
    the whole point of building in a temp path first (Sec 5 step 6). This
    is the ONE shared import function every trigger (CLI, admin endpoint)
    calls -- not a duplicated code path (Sec 5 item 2)."""
    tmp_path = dest_path.with_suffix(".db.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        meta_response = _fetch_bulk_data_metadata()
        oracle_obj = find_bulk_object(meta_response, "oracle_cards")
        rulings_obj = find_bulk_object(meta_response, "rulings")

        oracle_raw = json.loads(_download_bytes(oracle_obj["download_uri"]))
        rulings_raw = json.loads(_download_bytes(rulings_obj["download_uri"]))

        cards = filter_and_project(oracle_raw)
        rulings_by_oracle_id = project_rulings(rulings_raw)

        build_meta = {
            "oracle_cards_updated_at": oracle_obj.get("updated_at", ""),
            "rulings_updated_at": rulings_obj.get("updated_at", ""),
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        summary = scryfall_store.build_store(tmp_path, cards, rulings_by_oracle_id, build_meta)

        conn = scryfall_store.connect(tmp_path)
        try:
            ok, message = sanity_check(conn, cards)
        finally:
            conn.close()
        if not ok:
            raise RuntimeError(f"sanity check FAILED, aborting: {message}")

        atomic_swap(tmp_path, dest_path)
        return {**summary, "sanity_message": message}
    except BaseException:
        # Any failure before the swap: the temp file (if it got as far as
        # being created) is scrubbed, and dest_path -- if it already
        # existed -- was never touched by anything above. Re-raise so the
        # caller (CLI main(), or the admin endpoint's background task) sees
        # exactly what went wrong.
        if tmp_path.exists():
            tmp_path.unlink()
        raise


# --- daily freshness check: metadata-only, NEVER downloads (Sec 5 item 3) -


def check_staleness(conn) -> dict:
    """Cheap, metadata-only GET /bulk-data compared against this store's
    own recorded `meta` timestamps. NEVER calls `_download_bytes()` --
    verified live (plan Sec 1) that Scryfall's bulk timestamps change
    roughly daily regardless of whether any card actually changed, so a
    naive "timestamp changed -> refresh" trigger would download ~172 MB
    daily for nothing and make the signal meaningless. This exists so an
    out-of-band change (a correction issued outside any set-release window)
    doesn't go silently unnoticed between calendar windows -- it's a
    signal, not itself a trigger."""
    live = _fetch_bulk_data_metadata()
    oracle_obj = find_bulk_object(live, "oracle_cards")
    rulings_obj = find_bulk_object(live, "rulings")
    stored_oracle = scryfall_store.get_meta(conn, "oracle_cards_updated_at")
    stored_rulings = scryfall_store.get_meta(conn, "rulings_updated_at")
    return {
        "oracle_cards_stale": oracle_obj.get("updated_at") != stored_oracle,
        "rulings_stale": rulings_obj.get("updated_at") != stored_rulings,
        "live_oracle_cards_updated_at": oracle_obj.get("updated_at"),
        "live_rulings_updated_at": rulings_obj.get("updated_at"),
        "stored_oracle_cards_updated_at": stored_oracle,
        "stored_rulings_updated_at": stored_rulings,
    }


# --- set-calendar auto-refresh trigger (Sec 5 item 1) -----------------------


def in_refresh_window(
    today: date, released_at: date,
    before_days: int = CALENDAR_WINDOW_BEFORE_DAYS,
    after_days: int = CALENDAR_WINDOW_AFTER_DAYS,
) -> bool:
    """True iff `today` falls within [released_at - before_days,
    released_at + after_days], inclusive on both ends. Scryfall's /sets has
    no prerelease/spoiler-start field (plan Sec 1) -- this heuristic window
    is the whole mechanism."""
    from datetime import timedelta

    window_start = released_at - timedelta(days=before_days)
    window_end = released_at + timedelta(days=after_days)
    return window_start <= today <= window_end


def should_calendar_refresh(
    today: date, sets: list[dict], last_refresh: date | None,
    cadence_days: int = CALENDAR_REFRESH_CADENCE_DAYS,
) -> bool:
    """True iff `today` is inside ANY set's refresh window AND it's been at
    least `cadence_days` since the last refresh (a light cadence within an
    active window, not a refresh every single day of it -- Sec 5 item 1).
    `sets`: Scryfall /sets objects (only `released_at` is read; entries
    missing it are skipped, e.g. digital-only/token sets with no release
    date on record)."""
    in_any_window = any(
        in_refresh_window(today, date.fromisoformat(s["released_at"]))
        for s in sets
        if s.get("released_at")
    )
    if not in_any_window:
        return False
    if last_refresh is None:
        return True
    return (today - last_refresh).days >= cadence_days


# --- CLI ---------------------------------------------------------------------


def main() -> int:
    print(f"Refreshing {scryfall_store.DEFAULT_DB} from Scryfall bulk data...")
    try:
        summary = refresh()
    except Exception as e:
        print(f"FAIL: {e!r}")
        return 1
    print(
        f"PASS: {summary['card_count']} cards, {summary['ruling_count']} rulings, "
        f"{summary['name_collisions']} name collisions -- {summary['sanity_message']}"
    )
    print(f"data/scryfall.db size on disk: {scryfall_store.DEFAULT_DB.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

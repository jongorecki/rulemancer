# Tests for the graceful local-first / live-fallback / self-healing design
# (docs/plan-scryfall-local-bulk.md, design revision post-approval): a
# missing or empty local snapshot is NOT a hard failure -- get_card() falls
# back to a single live Scryfall fetch for that one lookup and kicks off a
# non-blocking background bulk refresh so the snapshot repairs itself. A
# POPULATED snapshot is completely unaffected -- local-only, no live call,
# no refresh trigger, ever, exactly as before this revision.
#
# Every test monkeypatches the module-level seams (`_live_get_card`,
# `trigger_background_refresh`, `_run_bulk_refresh`) rather than hitting a
# real network or spawning a real 180MB download -- no test here ever
# touches the network. Test (d) is the one exception that lets a REAL
# background thread run end to end, but with the network seams inside
# scripts/refresh_scryfall_bulk.py stubbed (same convention
# tests/test_refresh_scryfall_bulk.py already uses).

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from rulesagent.contracts import Card
from rulesagent.tools import scryfall, scryfall_store

BOLT = {
    "oracle_id": "11111111-1111-1111-1111-111111111111",
    "name": "Lightning Bolt",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "type_line": "Instant",
    "mana_cost": "{R}",
    "layout": "normal",
    "mana_value": 1.0,
    "colors": ["R"],
    "color_identity": ["R"],
    "faces": [],
}


@pytest.fixture(autouse=True)
def _reset_refresh_state():
    """Every test starts and ends with no background thread in flight --
    otherwise a slow test could leak a live thread into the next test."""
    yield
    if scryfall._refresh_thread is not None:
        scryfall._refresh_thread.join(timeout=5)
    scryfall._refresh_thread = None


def _refuse_live(ref):
    raise AssertionError(f"must not touch live fallback for ref={ref!r} -- snapshot is healthy")


def _refuse_refresh():
    raise AssertionError("must not schedule a background refresh -- snapshot is healthy")


# --- (a) missing/empty snapshot: live fallback + refresh trigger, no raise -


def test_get_card_missing_snapshot_falls_back_to_live_and_triggers_refresh(tmp_path, monkeypatch):
    missing_path = tmp_path / "never_built.db"
    monkeypatch.setattr(scryfall, "DB_PATH", missing_path)

    live_card = Card(
        name="Lightning Bolt", oracle_text="live text", type_line="Instant",
        mana_cost="{R}", oracle_id="live-fetched-oracle-id",
    )
    live_calls = []
    refresh_calls = []
    monkeypatch.setattr(scryfall, "_live_get_card", lambda ref: (live_calls.append(ref), live_card)[1])
    monkeypatch.setattr(scryfall, "trigger_background_refresh", lambda: (refresh_calls.append(1), True)[1])

    card = scryfall.get_card("Lightning Bolt")

    assert card is live_card
    assert live_calls == ["Lightning Bolt"]
    assert len(refresh_calls) == 1


def test_get_card_empty_snapshot_falls_back_to_live_and_triggers_refresh(tmp_path, monkeypatch):
    db_path = tmp_path / "scryfall.db"
    scryfall_store.build_store(db_path, [], {}, {})  # a real, built, zero-card store
    monkeypatch.setattr(scryfall, "DB_PATH", db_path)

    live_card = Card(
        name="Lightning Bolt", oracle_text="live text", type_line="Instant",
        mana_cost="{R}", oracle_id="live-fetched-oracle-id",
    )
    live_calls = []
    refresh_calls = []
    monkeypatch.setattr(scryfall, "_live_get_card", lambda ref: (live_calls.append(ref), live_card)[1])
    monkeypatch.setattr(scryfall, "trigger_background_refresh", lambda: (refresh_calls.append(1), True)[1])

    card = scryfall.get_card("Lightning Bolt")

    assert card is live_card
    assert live_calls == ["Lightning Bolt"]
    assert len(refresh_calls) == 1


def test_get_card_missing_snapshot_live_miss_returns_none_without_raising(tmp_path, monkeypatch):
    # A live fallback that itself finds nothing is still a quiet None, not
    # an exception -- the whole point of the design is "never raise."
    missing_path = tmp_path / "never_built.db"
    monkeypatch.setattr(scryfall, "DB_PATH", missing_path)
    monkeypatch.setattr(scryfall, "_live_get_card", lambda ref: None)
    monkeypatch.setattr(scryfall, "trigger_background_refresh", lambda: True)

    assert scryfall.get_card("Not A Real Card") is None


# --- (b) populated snapshot: never touches live, never schedules a refresh -


def test_get_card_populated_snapshot_never_touches_live_or_refresh(tmp_path, monkeypatch):
    db_path = tmp_path / "scryfall.db"
    scryfall_store.build_store(db_path, [BOLT], {}, {})
    monkeypatch.setattr(scryfall, "DB_PATH", db_path)
    monkeypatch.setattr(scryfall, "_live_get_card", _refuse_live)
    monkeypatch.setattr(scryfall, "trigger_background_refresh", _refuse_refresh)

    card = scryfall.get_card("Lightning Bolt")

    assert card is not None
    assert card.name == "Lightning Bolt"
    assert card.oracle_id == BOLT["oracle_id"]


# --- (c) populated snapshot missing a specific card: None, no live/refresh -


def test_get_card_populated_snapshot_missing_card_returns_none_no_live_no_refresh(tmp_path, monkeypatch):
    db_path = tmp_path / "scryfall.db"
    scryfall_store.build_store(db_path, [BOLT], {}, {})
    monkeypatch.setattr(scryfall, "DB_PATH", db_path)
    monkeypatch.setattr(scryfall, "_live_get_card", _refuse_live)
    monkeypatch.setattr(scryfall, "trigger_background_refresh", _refuse_refresh)

    card = scryfall.get_card("Definitely Not A Real Card Xyz")

    assert card is None


# --- (d) background refresh builds to temp and swaps atomically ------------
# (the download itself is mocked -- this tests the swap, via the real
# refresh_scryfall_bulk.refresh() the background thread actually calls)


def test_background_refresh_builds_to_temp_and_swaps_atomically(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import refresh_scryfall_bulk as rsb

    dest = tmp_path / "scryfall.db"
    monkeypatch.setattr(scryfall, "DB_PATH", dest)

    # Enough cards to clear refresh_scryfall_bulk's sanity-check floor.
    cards_raw = [{**BOLT, "oracle_id": f"oid-{i}", "name": f"Card {i}", "lang": "en"} for i in range(25100)]
    bulk_response = {
        "data": [
            {"type": "oracle_cards", "updated_at": "2026-07-24T00:00:00Z",
             "download_uri": "https://data.scryfall.io/oracle-cards.json"},
            {"type": "rulings", "updated_at": "2026-07-24T00:00:00Z",
             "download_uri": "https://data.scryfall.io/rulings.json"},
        ]
    }
    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", lambda: bulk_response)
    monkeypatch.setattr(
        rsb, "_download_bytes",
        lambda url: json.dumps(cards_raw if "oracle" in url else []).encode("utf-8"),
    )

    launched = scryfall.trigger_background_refresh()
    assert launched is True
    thread = scryfall._refresh_thread
    assert thread is not None
    thread.join(timeout=30)

    assert dest.exists()
    assert not dest.with_suffix(".db.tmp").exists()  # temp file cleaned up by the swap
    conn = scryfall_store.connect(dest)
    try:
        assert scryfall_store.is_populated(conn)
        card = scryfall_store.lookup_oracle_id(conn, "oid-0")
    finally:
        conn.close()
    assert card is not None
    assert card.name == "Card 0"


def test_background_refresh_never_overwrites_healthy_store_in_place(tmp_path, monkeypatch):
    # An existing, healthy store must be replaced only via the atomic swap
    # (build-to-temp-then-os.replace), never written into directly while a
    # concurrent get_card() might be reading it.
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import refresh_scryfall_bulk as rsb

    dest = tmp_path / "scryfall.db"
    scryfall_store.build_store(dest, [BOLT], {}, {"imported_at": "old"})
    original_bytes = dest.read_bytes()
    monkeypatch.setattr(scryfall, "DB_PATH", dest)

    def _boom_metadata():
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", _boom_metadata)

    launched = scryfall.trigger_background_refresh()
    assert launched is True
    thread = scryfall._refresh_thread
    assert thread is not None
    thread.join(timeout=10)

    # Failed refresh: the old store is untouched, byte-for-byte.
    assert dest.read_bytes() == original_bytes
    assert not dest.with_suffix(".db.tmp").exists()


# --- (e) two refresh triggers don't run concurrently ------------------------


def test_trigger_background_refresh_dedups_concurrent_calls(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_refresh():
        calls.append(1)
        started.set()
        release.wait(timeout=5)
        return {"card_count": 1}

    monkeypatch.setattr(scryfall, "_run_bulk_refresh", slow_refresh)

    first = scryfall.trigger_background_refresh()
    assert first is True
    thread_ref = scryfall._refresh_thread
    assert started.wait(timeout=5), "background worker never started"

    second = scryfall.trigger_background_refresh()
    assert second is False  # deduped -- a refresh is already running
    assert len(calls) == 1  # no second call was made

    release.set()
    thread_ref.join(timeout=5)

    # After the first refresh completes, the guard clears and a new trigger
    # is allowed.
    third = scryfall.trigger_background_refresh()
    assert third is True
    assert len(calls) == 2

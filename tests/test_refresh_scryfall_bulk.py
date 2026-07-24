# Tests for scripts/refresh_scryfall_bulk.py (docs/plan-scryfall-local-bulk.md
# Sec 5/7). Same import-by-path convention as tests/test_watch_runs.py for
# evals/watch_runs.py -- scripts/ isn't a package under src/.
#
# Every test stubs the two network seams (_fetch_bulk_data_metadata,
# _download_bytes) -- nothing here ever touches the real Scryfall bulk
# files or the network (task constraint: only free Scryfall bulk downloads
# are allowed at all, and only in the real e2e run, never in unit tests).

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import refresh_scryfall_bulk as rsb  # noqa: E402

from rulesagent.tools import scryfall_store  # noqa: E402

BOLT_RAW = {
    "oracle_id": "11111111-1111-1111-1111-111111111111",
    "name": "Lightning Bolt",
    "lang": "en",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "type_line": "Instant",
    "mana_cost": "{R}",
    "layout": "normal",
    "cmc": 1.0,
    "colors": ["R"],
    "color_identity": ["R"],
}

FRENCH_BOLT_RAW = {**BOLT_RAW, "lang": "fr", "oracle_id": "ff-1111"}

DFC_RAW = {
    "oracle_id": "22222222-2222-2222-2222-222222222222",
    "name": "Valki, God of Lies // Tibalt, Cosmic Impostor",
    "lang": "en",
    "oracle_text": "",
    "type_line": "Legendary Creature // Legendary Planeswalker",
    "mana_cost": "",
    "layout": "modal_dfc",
    "cmc": 1.0,
    "colors": ["B"],
    "color_identity": ["B", "R"],
    "card_faces": [
        {
            "name": "Valki, God of Lies", "mana_cost": "{B}",
            "type_line": "Legendary Creature -- God", "oracle_text": "Front face text.",
            "power": "1", "toughness": "3", "colors": ["B"],
        },
        {
            "name": "Tibalt, Cosmic Impostor", "mana_cost": "{2}{B}{B}{R}{R}",
            "type_line": "Legendary Planeswalker -- Tibalt", "oracle_text": "Back face text.",
            "loyalty": "5", "colors": ["B", "R"],
        },
    ],
}

RULINGS_RAW = [
    {"oracle_id": BOLT_RAW["oracle_id"], "comment": "Ruling one."},
    {"oracle_id": BOLT_RAW["oracle_id"], "comment": "Ruling two."},
    {"oracle_id": DFC_RAW["oracle_id"], "comment": "DFC ruling."},
]


# --- transform: project_card -------------------------------------------------


def test_project_card_single_faced():
    projected = rsb.project_card(BOLT_RAW)

    assert projected["oracle_id"] == BOLT_RAW["oracle_id"]
    assert projected["name"] == "Lightning Bolt"
    assert projected["oracle_text"] == BOLT_RAW["oracle_text"]
    assert len(projected["faces"]) == 1
    assert projected["faces"][0]["name"] == "Lightning Bolt"


def test_project_card_double_faced_joins_both_faces_no_half_dropped():
    projected = rsb.project_card(DFC_RAW)

    assert projected["oracle_text"] == "Front face text.\n//\nBack face text."
    assert len(projected["faces"]) == 2
    assert projected["faces"][0]["oracle_text"] == "Front face text."
    assert projected["faces"][1]["oracle_text"] == "Back face text."
    assert projected["faces"][1]["loyalty"] == "5"


# --- transform: filter_and_project (lang == "en") --------------------------


def test_filter_and_project_drops_non_english():
    projected = rsb.filter_and_project([BOLT_RAW, FRENCH_BOLT_RAW])

    assert len(projected) == 1
    assert projected[0]["name"] == "Lightning Bolt"


def test_filter_and_project_drops_entries_missing_oracle_id_or_name():
    no_oracle = {**BOLT_RAW, "oracle_id": ""}
    no_name = {**BOLT_RAW, "name": ""}

    projected = rsb.filter_and_project([no_oracle, no_name])

    assert projected == []


# --- transform: project_rulings ---------------------------------------------


def test_project_rulings_groups_by_oracle_id_preserving_order():
    grouped = rsb.project_rulings(RULINGS_RAW)

    assert grouped[BOLT_RAW["oracle_id"]] == ["Ruling one.", "Ruling two."]
    assert grouped[DFC_RAW["oracle_id"]] == ["DFC ruling."]


def test_project_rulings_skips_entries_with_no_oracle_id():
    grouped = rsb.project_rulings([{"comment": "orphan"}])

    assert grouped == {}


# --- sanity gate --------------------------------------------------------------


def test_sanity_check_passes_on_healthy_store(tmp_path):
    # Each entry is its OWN dict (not aliased copies of a shared object --
    # `[project_card(x)] * N` would repeat references to the SAME dict, so
    # mutating oracle_id per-index would accumulate onto one shared object
    # instead of giving each row a distinct id).
    cards = [
        {**rsb.project_card(BOLT_RAW if i % 2 == 0 else DFC_RAW), "oracle_id": f"oid-{i}"}
        for i in range(30000)
    ]
    db_path = tmp_path / "scryfall.db"
    scryfall_store.build_store(db_path, cards, {}, {})
    conn = scryfall_store.connect(db_path)
    try:
        ok, message = rsb.sanity_check(conn, cards)
    finally:
        conn.close()
    assert ok is True
    assert "30000" in message


def test_sanity_check_fails_on_too_few_cards(tmp_path):
    cards = [rsb.project_card(BOLT_RAW)]
    db_path = tmp_path / "scryfall.db"
    scryfall_store.build_store(db_path, cards, {}, {})
    conn = scryfall_store.connect(db_path)
    try:
        ok, message = rsb.sanity_check(conn, cards)
    finally:
        conn.close()
    assert ok is False
    assert "1" in message


# --- refresh() orchestration: success path ----------------------------------


def _bulk_data_response(oracle_updated="2026-07-23T09:02:00.000Z",
                         rulings_updated="2026-07-23T09:00:00.000Z"):
    return {
        "data": [
            {"type": "oracle_cards", "updated_at": oracle_updated,
             "download_uri": "https://data.scryfall.io/oracle-cards.json"},
            {"type": "rulings", "updated_at": rulings_updated,
             "download_uri": "https://data.scryfall.io/rulings.json"},
        ]
    }


def _many_cards(n=25100):
    out = []
    for i in range(n):
        out.append({**BOLT_RAW, "oracle_id": f"oracle-{i}", "name": f"Card {i}"})
    return out


def test_refresh_success_builds_and_swaps_atomically(tmp_path, monkeypatch):
    dest = tmp_path / "scryfall.db"
    cards_raw = _many_cards()

    def fake_metadata():
        return _bulk_data_response()

    def fake_download(url):
        if "oracle" in url:
            return json.dumps(cards_raw).encode("utf-8")
        return json.dumps(RULINGS_RAW).encode("utf-8")

    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", fake_metadata)
    monkeypatch.setattr(rsb, "_download_bytes", fake_download)

    summary = rsb.refresh(dest_path=dest)

    assert dest.exists()
    assert summary["card_count"] == len(cards_raw)
    assert not dest.with_suffix(".db.tmp").exists()  # tmp cleaned up by the swap

    conn = scryfall_store.connect(dest)
    try:
        assert scryfall_store.get_meta(conn, "oracle_cards_updated_at") == "2026-07-23T09:02:00.000Z"
        card = scryfall_store.lookup_oracle_id(conn, "oracle-0")
    finally:
        conn.close()
    assert card is not None
    assert card.name == "Card 0"


# --- refresh() orchestration: crash safety (Sec 5 step 6 / Sec 7 test 8) --


def test_refresh_failure_leaves_old_store_byte_identical(tmp_path, monkeypatch):
    dest = tmp_path / "scryfall.db"
    # Build a real, working "old" store first.
    old_cards = [rsb.project_card(BOLT_RAW)]
    scryfall_store.build_store(dest, old_cards, {}, {"imported_at": "old"})
    original_bytes = dest.read_bytes()

    def fake_metadata():
        return _bulk_data_response()

    def fake_download(url):
        # Deliberately too few cards -- fails the sanity gate for real,
        # not via a mocked sanity_check.
        if "oracle" in url:
            return json.dumps([BOLT_RAW]).encode("utf-8")
        return json.dumps([]).encode("utf-8")

    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", fake_metadata)
    monkeypatch.setattr(rsb, "_download_bytes", fake_download)

    with pytest.raises(RuntimeError, match="sanity check FAILED"):
        rsb.refresh(dest_path=dest)

    # Old store untouched, byte-for-byte.
    assert dest.read_bytes() == original_bytes
    # A concurrent get_card-style lookup during/after the failed attempt
    # still resolves correctly against the untouched old store.
    conn = scryfall_store.connect(dest)
    try:
        card = scryfall_store.lookup_name_exact(conn, "Lightning Bolt")
    finally:
        conn.close()
    assert card is not None
    assert card.oracle_id == BOLT_RAW["oracle_id"]
    # No leftover tmp file.
    assert not dest.with_suffix(".db.tmp").exists()


def test_refresh_download_exception_leaves_old_store_untouched(tmp_path, monkeypatch):
    dest = tmp_path / "scryfall.db"
    old_cards = [rsb.project_card(BOLT_RAW)]
    scryfall_store.build_store(dest, old_cards, {}, {})
    original_bytes = dest.read_bytes()

    def fake_metadata():
        return _bulk_data_response()

    def raising_download(url):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", fake_metadata)
    monkeypatch.setattr(rsb, "_download_bytes", raising_download)

    with pytest.raises(ConnectionError):
        rsb.refresh(dest_path=dest)

    assert dest.read_bytes() == original_bytes
    assert not dest.with_suffix(".db.tmp").exists()


def test_refresh_first_run_no_prior_store(tmp_path, monkeypatch):
    dest = tmp_path / "scryfall.db"  # does not exist yet
    cards_raw = _many_cards()

    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", lambda: _bulk_data_response())
    monkeypatch.setattr(
        rsb, "_download_bytes",
        lambda url: json.dumps(cards_raw if "oracle" in url else RULINGS_RAW).encode("utf-8"),
    )

    summary = rsb.refresh(dest_path=dest)

    assert dest.exists()
    assert summary["card_count"] == len(cards_raw)


# --- staleness check (never downloads) (Sec 5 item 3 / Sec 7 test 9) ------


def test_staleness_check_flags_stale_without_downloading(tmp_path, monkeypatch):
    dest = tmp_path / "scryfall.db"
    scryfall_store.build_store(
        dest, [], {},
        {"oracle_cards_updated_at": "2026-07-01T00:00:00Z",
         "rulings_updated_at": "2026-07-01T00:00:00Z"},
    )

    def fake_metadata():
        return _bulk_data_response(
            oracle_updated="2026-07-23T09:02:00Z", rulings_updated="2026-07-23T09:00:00Z"
        )

    def download_should_never_be_called(url):
        raise AssertionError("staleness check must never download bulk files")

    monkeypatch.setattr(rsb, "_fetch_bulk_data_metadata", fake_metadata)
    monkeypatch.setattr(rsb, "_download_bytes", download_should_never_be_called)

    conn = scryfall_store.connect(dest)
    try:
        result = rsb.check_staleness(conn)
    finally:
        conn.close()

    assert result["oracle_cards_stale"] is True
    assert result["rulings_stale"] is True


def test_staleness_check_reports_fresh_when_timestamps_match(tmp_path, monkeypatch):
    dest = tmp_path / "scryfall.db"
    scryfall_store.build_store(
        dest, [], {},
        {"oracle_cards_updated_at": "2026-07-23T09:02:00Z",
         "rulings_updated_at": "2026-07-23T09:00:00Z"},
    )
    monkeypatch.setattr(
        rsb, "_fetch_bulk_data_metadata",
        lambda: _bulk_data_response(
            oracle_updated="2026-07-23T09:02:00Z", rulings_updated="2026-07-23T09:00:00Z"
        ),
    )
    monkeypatch.setattr(
        rsb, "_download_bytes",
        lambda url: (_ for _ in ()).throw(AssertionError("must never download")),
    )

    conn = scryfall_store.connect(dest)
    try:
        result = rsb.check_staleness(conn)
    finally:
        conn.close()

    assert result["oracle_cards_stale"] is False
    assert result["rulings_stale"] is False


# --- calendar-window trigger (Jon's ruling: -8/+21 days around released_at) -


@pytest.mark.parametrize(
    "today,released_at,expected",
    [
        (date(2026, 8, 6), date(2026, 8, 14), True),   # exactly 8 days before
        (date(2026, 8, 5), date(2026, 8, 14), False),  # 9 days before -- outside
        (date(2026, 8, 14), date(2026, 8, 14), True),  # release day itself
        (date(2026, 9, 4), date(2026, 8, 14), True),   # exactly 21 days after
        (date(2026, 9, 5), date(2026, 8, 14), False),  # 22 days after -- outside
        (date(2026, 1, 1), date(2026, 8, 14), False),  # far outside
    ],
)
def test_in_refresh_window_boundaries(today, released_at, expected):
    assert rsb.in_refresh_window(today, released_at) is expected


def test_should_calendar_refresh_false_outside_any_window():
    sets = [{"released_at": "2026-08-14"}]
    assert rsb.should_calendar_refresh(date(2026, 1, 1), sets, last_refresh=None) is False


def test_should_calendar_refresh_true_first_time_in_window():
    sets = [{"released_at": "2026-08-14"}]
    assert rsb.should_calendar_refresh(date(2026, 8, 10), sets, last_refresh=None) is True


def test_should_calendar_refresh_respects_cadence_within_window():
    sets = [{"released_at": "2026-08-14"}]
    # Refreshed yesterday -- still within the window, but too soon per the
    # light in-window cadence (proposed 3-4 days, Sec 5 item 1).
    last = date(2026, 8, 11)
    assert rsb.should_calendar_refresh(date(2026, 8, 12), sets, last_refresh=last) is False
    # Enough days have passed since the last refresh.
    assert rsb.should_calendar_refresh(date(2026, 8, 15), sets, last_refresh=last) is True


def test_should_calendar_refresh_ignores_sets_with_no_released_at():
    sets = [{"released_at": None}, {"set_type": "token"}]
    assert rsb.should_calendar_refresh(date(2026, 8, 10), sets, last_refresh=None) is False

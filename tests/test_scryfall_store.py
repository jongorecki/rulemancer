# Tests for the local Scryfall bulk-data snapshot store
# (docs/plan-scryfall-local-bulk.md Sec 3/4/7). All against a small fixture
# store built in tmp_path via scryfall_store.build_store() -- never the real
# 172 MB file, matching tests/test_scryfall.py's existing no-network,
# tmp_path-isolated convention (plan Sec 7 header).

import sqlite3

import pytest

from rulesagent.tools import scryfall_store

BOLT = {
    "oracle_id": "aaaaaaaa-1111-1111-1111-111111111111",
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
BOLT_RULINGS = [
    "Lightning Bolt can target a player, a planeswalker, or a creature.",
    "Any target means the spell must have a legal target when cast.",
]

COUNTERSPELL = {
    "oracle_id": "bbbbbbbb-2222-2222-2222-222222222222",
    "name": "Counterspell",
    "oracle_text": "Counter target spell.",
    "type_line": "Instant",
    "mana_cost": "{U}{U}",
    "layout": "normal",
    "mana_value": 2.0,
    "colors": ["U"],
    "color_identity": ["U"],
    "faces": [],
}

# Two near-identical names, deliberately close enough that a fuzzy match on
# a typo of one is ambiguous against the other (test 5).
KESSIG = {
    "oracle_id": "cccccccc-3333-3333-3333-333333333333",
    "name": "Kessig Wolf",
    "oracle_text": "Kessig Wolf oracle text.",
    "type_line": "Creature -- Wolf",
    "mana_cost": "{2}{R}",
    "layout": "normal",
    "mana_value": 3.0,
    "colors": ["R"],
    "color_identity": ["R"],
    "faces": [],
}
KESSIG_TWO = {
    "oracle_id": "dddddddd-4444-4444-4444-444444444444",
    "name": "Dessig Wolf",
    "oracle_text": "Dessig Wolf oracle text.",
    "type_line": "Creature -- Wolf",
    "mana_cost": "{2}{R}",
    "layout": "normal",
    "mana_value": 3.0,
    "colors": ["R"],
    "color_identity": ["R"],
    "faces": [],
}


def _build(tmp_path, cards, rulings=None, meta=None):
    db_path = tmp_path / "scryfall.db"
    scryfall_store.build_store(db_path, cards, rulings or {}, meta or {})
    return db_path


# --- exact lookups -----------------------------------------------------------


def test_exact_oracle_id_hit(tmp_path):
    db_path = _build(tmp_path, [BOLT, COUNTERSPELL])
    conn = scryfall_store.connect(db_path)
    try:
        card = scryfall_store.lookup_oracle_id(conn, BOLT["oracle_id"])
    finally:
        conn.close()
    assert card is not None
    assert card.name == "Lightning Bolt"
    assert card.oracle_id == BOLT["oracle_id"]
    assert card.mana_cost == "{R}"


def test_exact_oracle_id_miss_returns_none(tmp_path):
    db_path = _build(tmp_path, [BOLT])
    conn = scryfall_store.connect(db_path)
    try:
        card = scryfall_store.lookup_oracle_id(conn, "00000000-0000-0000-0000-000000000000")
    finally:
        conn.close()
    assert card is None


def test_exact_name_hit_correct_casing(tmp_path):
    db_path = _build(tmp_path, [BOLT])
    conn = scryfall_store.connect(db_path)
    try:
        card = scryfall_store.lookup_name_exact(conn, "Lightning Bolt")
    finally:
        conn.close()
    assert card is not None
    assert card.oracle_id == BOLT["oracle_id"]


def test_case_normalized_exact_hit(tmp_path):
    db_path = _build(tmp_path, [BOLT])
    conn = scryfall_store.connect(db_path)
    try:
        card = scryfall_store.lookup_name_exact(conn, "lightning bolt")
    finally:
        conn.close()
    assert card is not None
    assert card.name == "Lightning Bolt"


# --- fuzzy fallback -----------------------------------------------------------


def test_fuzzy_fallback_hit_on_near_miss_typo(tmp_path):
    db_path = _build(tmp_path, [BOLT, COUNTERSPELL])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.fuzzy_lookup(conn, "Lightning Blot")
    finally:
        conn.close()
    assert card is not None
    assert card.name == "Lightning Bolt"
    assert event is not None
    assert event["reason"] == "fuzzy_match"
    assert event["matched_name"] == "Lightning Bolt"
    assert event["oracle_id"] == BOLT["oracle_id"]
    assert event["score"] >= scryfall_store.FUZZY_THRESHOLD


def test_fuzzy_fallback_refuses_ambiguous_near_tie(tmp_path):
    db_path = _build(tmp_path, [KESSIG, KESSIG_TWO])
    conn = scryfall_store.connect(db_path)
    try:
        # "Messig Wolf" is equidistant (one letter off) from both "Kessig
        # Wolf" and "Dessig Wolf" -- WRatio scores both 90.9, a dead tie --
        # so the ambiguity guard must refuse rather than guess which one
        # was meant.
        card, event = scryfall_store.fuzzy_lookup(conn, "Messig Wolf")
    finally:
        conn.close()
    assert card is None
    assert event is not None
    assert event["reason"] == "ambiguous"
    assert event["matched_name"] is None
    assert event["oracle_id"] is None
    assert set(event["candidates"]) == {"Kessig Wolf", "Dessig Wolf"}


def test_true_miss_returns_none_with_no_event(tmp_path):
    db_path = _build(tmp_path, [BOLT, COUNTERSPELL])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.fuzzy_lookup(conn, "Zzyzzogeton Xyzzy Not A Card")
    finally:
        conn.close()
    assert card is None
    assert event is None


def test_fuzzy_lookup_on_empty_store_is_a_clean_miss(tmp_path):
    db_path = _build(tmp_path, [])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.fuzzy_lookup(conn, "Anything")
    finally:
        conn.close()
    assert card is None
    assert event is None


# --- rulings join --------------------------------------------------------------


def test_rulings_join_returns_stable_index_order(tmp_path):
    db_path = _build(tmp_path, [BOLT], {BOLT["oracle_id"]: BOLT_RULINGS})
    conn = scryfall_store.connect(db_path)
    try:
        card = scryfall_store.lookup_oracle_id(conn, BOLT["oracle_id"])
    finally:
        conn.close()
    assert card.rulings == BOLT_RULINGS


def test_card_with_no_rulings_gets_empty_list(tmp_path):
    db_path = _build(tmp_path, [COUNTERSPELL], {})
    conn = scryfall_store.connect(db_path)
    try:
        card = scryfall_store.lookup_oracle_id(conn, COUNTERSPELL["oracle_id"])
    finally:
        conn.close()
    assert card.rulings == []


# --- name-collision defensiveness (not in the plan's schema, found reading
# real Scryfall data -- see the build report) -------------------------------


def test_build_store_survives_duplicate_display_names():
    """Real Scryfall data has rare true duplicate names on DIFFERENT oracle_ids
    (e.g. the two distinct "Brothers Yamazaki" creatures). The plan's schema
    puts a UNIQUE index on name_norm; a naive INSERT would crash the whole
    import on this edge case. build_store must not crash -- first-seen wins,
    deterministically, by input order."""
    import tempfile
    from pathlib import Path

    dup_a = {**BOLT, "oracle_id": "eeee-1", "name": "Brothers Yamazaki"}
    dup_b = {**COUNTERSPELL, "oracle_id": "eeee-2", "name": "Brothers Yamazaki"}
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "scryfall.db"
        summary = scryfall_store.build_store(db_path, [dup_a, dup_b], {}, meta={})
        assert summary["card_count"] == 2  # both rows land in `cards`
        conn = scryfall_store.connect(db_path)
        try:
            # Only one is reachable by exact name lookup -- first-seen wins.
            card = scryfall_store.lookup_name_exact(conn, "Brothers Yamazaki")
        finally:
            conn.close()
        assert card is not None
        assert card.oracle_id == "eeee-1"


# --- meta table -----------------------------------------------------------


def test_meta_round_trips(tmp_path):
    db_path = _build(
        tmp_path, [], meta={"oracle_cards_updated_at": "2026-07-23T09:02:00Z"}
    )
    conn = scryfall_store.connect(db_path)
    try:
        value = scryfall_store.get_meta(conn, "oracle_cards_updated_at")
        missing = scryfall_store.get_meta(conn, "nope")
    finally:
        conn.close()
    assert value == "2026-07-23T09:02:00Z"
    assert missing is None


# --- connect() on a missing file ------------------------------------------


def test_connect_creates_schema_on_missing_file(tmp_path):
    db_path = tmp_path / "nested" / "scryfall.db"
    conn = scryfall_store.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM cards").fetchone()
    finally:
        conn.close()
    assert row[0] == 0
    assert db_path.exists()

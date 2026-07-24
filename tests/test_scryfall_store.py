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

# --- real-data regression fixtures (docs/plan-scryfall-local-bulk.md
# equivalence-check finding, c011): a bare single-face reference like
# "Valki, God of Lies" must resolve to the real modal_dfc card, not lose to
# an unrelated fuzzy near-match ("Loki, God of Lies") and not resolve to the
# non-playable art_series decoy that shares the exact same combined name
# pattern. Field values (mana costs, layout, oracle_ids) are the REAL
# Scryfall values, verified live 2026-07-23/24 against the actual bulk data.

VALKI_REAL = {
    "oracle_id": "907ae517-22d5-4ac7-bc3a-3f4d5eaeeb57",
    "name": "Valki, God of Lies // Tibalt, Cosmic Impostor",
    "oracle_text": "Front face text.\n//\nBack face text.",
    "type_line": "Legendary Creature // Legendary Planeswalker",
    "mana_cost": "",
    "layout": "modal_dfc",
    "mana_value": 1.0,
    "colors": ["B"],
    "color_identity": ["B", "R"],
    "faces": [
        {"name": "Valki, God of Lies", "mana_cost": "{1}{B}",
         "type_line": "Legendary Creature -- God", "oracle_text": "Front face text.",
         "power": "1", "toughness": "3", "loyalty": "", "defense": "",
         "colors": ["B"], "color_indicator": []},
        {"name": "Tibalt, Cosmic Impostor", "mana_cost": "{5}{B}{R}",
         "type_line": "Legendary Planeswalker -- Tibalt", "oracle_text": "Back face text.",
         "power": "", "toughness": "", "loyalty": "5", "defense": "",
         "colors": ["B", "R"], "color_indicator": []},
    ],
}

# Non-playable decoy: same face name, same combined-name PATTERN, wrong
# layout -- must never be preferred over the real card.
VALKI_ART_SERIES = {
    "oracle_id": "72230c49-0a41-4968-8fe7-6e8f596b1a31",
    "name": "Valki, God of Lies // Valki, God of Lies",
    "oracle_text": "",
    "type_line": "Card // Card",
    "mana_cost": "",
    "layout": "art_series",
    "mana_value": 0.0,
    "colors": [],
    "color_identity": [],
    "faces": [
        {"name": "Valki, God of Lies", "mana_cost": "", "type_line": "Card",
         "oracle_text": "", "power": "", "toughness": "", "loyalty": "",
         "defense": "", "colors": [], "color_indicator": []},
        {"name": "Valki, God of Lies", "mana_cost": "", "type_line": "Card",
         "oracle_text": "", "power": "", "toughness": "", "loyalty": "",
         "defense": "", "colors": [], "color_indicator": []},
    ],
}

# The real, unrelated card that out-scores Valki/Tibalt on a plain WRatio
# fuzzy match against "Valki, God of Lies" (91.4 vs 90.0) -- proves the new
# face-name tier must be tried BEFORE fuzzy, not just added as another
# fuzzy candidate.
LOKI = {
    "oracle_id": "6f72ce67-3c17-4338-904b-26e2bf4aecdc",
    "name": "Loki, God of Lies",
    "oracle_text": "Loki oracle text.",
    "type_line": "Legendary Creature -- God Sorcerer Villain",
    "mana_cost": "{1}{R}{R}",
    "layout": "normal",
    "mana_value": 3.0,
    "colors": ["R"],
    "color_identity": ["R"],
    "faces": [
        {"name": "Loki, God of Lies", "mana_cost": "{1}{R}{R}",
         "type_line": "Legendary Creature -- God Sorcerer Villain", "oracle_text": "Loki oracle text.",
         "power": "3", "toughness": "3", "loyalty": "", "defense": "",
         "colors": ["R"], "color_indicator": []},
    ],
}

# Two DIFFERENT playable cards sharing one face name, on purpose -- the
# face tier must still refuse (ambiguity guard), not silently pick one.
PLAYABLE_TWIN_A = {
    "oracle_id": "eeeeeeee-1111-1111-1111-111111111111",
    "name": "Twin Face // Alpha Back",
    "oracle_text": "", "type_line": "Creature // Creature", "mana_cost": "",
    "layout": "transform", "mana_value": 2.0, "colors": [], "color_identity": [],
    "faces": [
        {"name": "Shared Face Name", "mana_cost": "{1}{G}", "type_line": "Creature",
         "oracle_text": "", "power": "2", "toughness": "2", "loyalty": "", "defense": "",
         "colors": ["G"], "color_indicator": []},
        {"name": "Alpha Back", "mana_cost": "", "type_line": "Creature",
         "oracle_text": "", "power": "3", "toughness": "3", "loyalty": "", "defense": "",
         "colors": [], "color_indicator": []},
    ],
}
PLAYABLE_TWIN_B = {
    "oracle_id": "ffffffff-2222-2222-2222-222222222222",
    "name": "Twin Face // Beta Back",
    "oracle_text": "", "type_line": "Creature // Creature", "mana_cost": "",
    "layout": "transform", "mana_value": 2.0, "colors": [], "color_identity": [],
    "faces": [
        {"name": "Shared Face Name", "mana_cost": "{1}{U}", "type_line": "Creature",
         "oracle_text": "", "power": "1", "toughness": "4", "loyalty": "", "defense": "",
         "colors": ["U"], "color_indicator": []},
        {"name": "Beta Back", "mana_cost": "", "type_line": "Creature",
         "oracle_text": "", "power": "1", "toughness": "1", "loyalty": "", "defense": "",
         "colors": [], "color_indicator": []},
    ],
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


# --- face-name lookup tier (c011/Valki fix, added post-approval per Jon's
# ruling: "add a per-face-name lookup tier... tried BEFORE the fuzzy
# fallback, so an exact face-name match always beats a fuzzy near-match")


def test_face_name_exact_match_resolves_to_real_modal_dfc(tmp_path):
    # Loki (fuzzy near-match, would beat Valki/Tibalt on a plain WRatio
    # score) and the art_series decoy are BOTH in the store -- the face
    # tier must still find the real card by its front face's exact name.
    db_path = _build(tmp_path, [VALKI_REAL, VALKI_ART_SERIES, LOKI])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.lookup_face_name(conn, "Valki, God of Lies")
    finally:
        conn.close()
    assert card is not None
    assert card.name == "Valki, God of Lies // Tibalt, Cosmic Impostor"
    assert card.oracle_id == VALKI_REAL["oracle_id"]
    assert len(card.faces) == 2
    assert card.faces[0].name == "Valki, God of Lies"
    assert card.faces[0].mana_cost == "{1}{B}"
    assert card.faces[1].name == "Tibalt, Cosmic Impostor"
    assert card.faces[1].mana_cost == "{5}{B}{R}"
    assert card.faces[1].loyalty == "5"
    assert event is not None
    assert event["reason"] == "face_name_match"
    assert event["oracle_id"] == VALKI_REAL["oracle_id"]


def test_face_name_lookup_skips_non_playable_layout_when_alone(tmp_path):
    # ONLY the art_series decoy in the store (no real card) -- a face-name
    # hit on a non-playable layout does not count as a resolvable match;
    # the tier must report a clean miss so the caller can still fall
    # through to fuzzy (which might find nothing either, but that's the
    # caller's call, not this tier's to make).
    db_path = _build(tmp_path, [VALKI_ART_SERIES, LOKI])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.lookup_face_name(conn, "Valki, God of Lies")
    finally:
        conn.close()
    assert card is None
    assert event is None


def test_face_name_lookup_true_miss_when_no_face_matches(tmp_path):
    db_path = _build(tmp_path, [VALKI_REAL, LOKI])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.lookup_face_name(conn, "Not A Real Face Name At All")
    finally:
        conn.close()
    assert card is None
    assert event is None


def test_face_name_lookup_refuses_when_two_playable_cards_share_a_face_name(tmp_path):
    # The ambiguity guard extends to the face tier too (Jon's ruling:
    # "you're adding a higher-precision tier above fuzzy, not loosening the
    # guard") -- two genuinely different PLAYABLE cards sharing an exact
    # face name must refuse, not silently pick one.
    db_path = _build(tmp_path, [PLAYABLE_TWIN_A, PLAYABLE_TWIN_B])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.lookup_face_name(conn, "Shared Face Name")
    finally:
        conn.close()
    assert card is None
    assert event is not None
    assert event["reason"] == "ambiguous"
    assert set(event["candidates"]) == {
        "Twin Face // Alpha Back", "Twin Face // Beta Back",
    }


def test_face_name_lookup_on_empty_store_is_a_clean_miss(tmp_path):
    db_path = _build(tmp_path, [])
    conn = scryfall_store.connect(db_path)
    try:
        card, event = scryfall_store.lookup_face_name(conn, "Anything")
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

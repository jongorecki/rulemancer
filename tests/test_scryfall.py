# Tests for card enrichment (docs/plan-scryfall-local-bulk.md), REWRITTEN
# from the plan #3b live-fetch design it replaces.
#
# get_card() now resolves purely against a local snapshot (data/scryfall.db,
# built by scripts/refresh_scryfall_bulk.py) -- no live Scryfall call of any
# kind at answer time (Jon's ruling, plan Sec 10). Every test builds its own
# tiny fixture store via rulesagent.tools.scryfall_store.build_store() in
# tmp_path and monkeypatches `scryfall.DB_PATH` at it -- same isolation
# convention the old (live-fetch) test file used (its own tmp_path KVCache),
# just pointed at the new store shape. No network, ever.

import json

import pytest

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
BOLT_RULINGS = ["Ruling one.", "Ruling two."]

DOVINS_VETO = {
    "oracle_id": "22222222-2222-2222-2222-222222222222",
    "name": "Dovin's Veto",
    "oracle_text": "This spell can't be countered. Counter target instant or sorcery spell.",
    "type_line": "Instant",
    "mana_cost": "{1}{W}",
    "layout": "normal",
    "mana_value": 2.0,
    "colors": ["W"],
    "color_identity": ["W"],
    "faces": [],
}

VALKI = {
    "oracle_id": "33333333-3333-3333-3333-333333333333",
    "name": "Valki, God of Lies // Tibalt, Cosmic Impostor",
    "oracle_text": "Front face text.\n//\nBack face text.",
    "type_line": "Legendary Creature // Legendary Planeswalker",
    "mana_cost": "",
    "layout": "modal_dfc",
    "mana_value": 1.0,
    "colors": ["B"],
    "color_identity": ["B", "R"],
    "faces": [
        {
            "name": "Valki, God of Lies", "mana_cost": "{B}", "type_line": "Legendary Creature -- God",
            "oracle_text": "Front face text.", "power": "1", "toughness": "3", "loyalty": "",
            "defense": "", "colors": ["B"], "color_indicator": [],
        },
        {
            "name": "Tibalt, Cosmic Impostor", "mana_cost": "{2}{B}{B}{R}{R}", "type_line": "Legendary Planeswalker -- Tibalt",
            "oracle_text": "Back face text.", "power": "", "toughness": "", "loyalty": "5",
            "defense": "", "colors": ["B", "R"], "color_indicator": [],
        },
    ],
}


@pytest.fixture()
def _store(tmp_path, monkeypatch):
    """Build a small fixture store and point scryfall.DB_PATH at it. Returns
    a helper that (re)builds the store with the given cards/rulings -- most
    tests call it once; a couple need a fresh empty store."""
    db_path = tmp_path / "scryfall.db"

    def build(cards, rulings=None, meta=None):
        if db_path.exists():
            db_path.unlink()
        scryfall_store.build_store(db_path, cards, rulings or {}, meta or {})
        monkeypatch.setattr(scryfall, "DB_PATH", db_path)
        return db_path

    return build


@pytest.fixture(autouse=True)
def _reset_fallback_log():
    scryfall.pop_fuzzy_fallbacks()  # drain any leftover state before each test
    yield
    scryfall.pop_fuzzy_fallbacks()


# --- exact lookups ------------------------------------------------------------


def test_exact_oracle_id_lookup(_store):
    _store([BOLT, DOVINS_VETO])

    card = scryfall.get_card(BOLT["oracle_id"])

    assert card is not None
    assert card.name == "Lightning Bolt"
    assert card.oracle_text == BOLT["oracle_text"]
    assert card.mana_cost == "{R}"


def test_exact_name_hit_correct_casing(_store):
    _store([BOLT])

    card = scryfall.get_card("Lightning Bolt")

    assert card is not None
    assert card.oracle_id == BOLT["oracle_id"]


def test_case_normalized_exact_hit(_store):
    _store([DOVINS_VETO])

    card = scryfall.get_card("dovin's veto")

    assert card is not None
    assert card.name == "Dovin's Veto"


# --- fuzzy fallback -------------------------------------------------------


def test_fuzzy_fallback_hit_records_debug_event(_store):
    _store([BOLT, DOVINS_VETO])

    card = scryfall.get_card("Lightning Blot")  # typo, no exact match

    assert card is not None
    assert card.name == "Lightning Bolt"
    events = scryfall.pop_fuzzy_fallbacks()
    assert len(events) == 1
    assert events[0]["reason"] == "fuzzy_match"
    assert events[0]["ref"] == "Lightning Blot"
    assert events[0]["matched_name"] == "Lightning Bolt"
    assert events[0]["oracle_id"] == BOLT["oracle_id"]


def test_fuzzy_fallback_refuses_ambiguous_near_tie(_store):
    kessig = {**BOLT, "oracle_id": "44444444-4444-4444-4444-444444444444", "name": "Kessig Wolf"}
    dessig = {**BOLT, "oracle_id": "55555555-5555-5555-5555-555555555555", "name": "Dessig Wolf"}
    _store([kessig, dessig])

    card = scryfall.get_card("Messig Wolf")  # equidistant from both

    assert card is None
    events = scryfall.pop_fuzzy_fallbacks()
    assert len(events) == 1
    assert events[0]["reason"] == "ambiguous"
    assert set(events[0]["candidates"]) == {"Kessig Wolf", "Dessig Wolf"}


def test_true_miss_returns_none_with_no_fallback_event(_store):
    _store([BOLT, DOVINS_VETO])

    card = scryfall.get_card("Definitely Not A Real Card Xyz")

    assert card is None
    assert scryfall.pop_fuzzy_fallbacks() == []


def test_unknown_oracle_id_returns_none_no_fallback(_store):
    _store([BOLT])

    card = scryfall.get_card("99999999-9999-9999-9999-999999999999")

    assert card is None
    assert scryfall.pop_fuzzy_fallbacks() == []


# --- rulings ---------------------------------------------------------------


def test_rulings_join_stable_order(_store):
    _store([BOLT], {BOLT["oracle_id"]: BOLT_RULINGS})

    card = scryfall.get_card("Lightning Bolt")

    assert card.rulings == BOLT_RULINGS


# --- double-faced cards ------------------------------------------------------


def test_double_faced_card_round_trips_both_faces(_store):
    _store([VALKI])

    card = scryfall.get_card(VALKI["oracle_id"])

    assert card is not None
    assert len(card.faces) == 2
    assert card.faces[0].name == "Valki, God of Lies"
    assert card.faces[0].oracle_text == "Front face text."
    assert card.faces[1].name == "Tibalt, Cosmic Impostor"
    assert card.faces[1].oracle_text == "Back face text."
    assert card.faces[1].loyalty == "5"


# --- no_refresh is an inert documented no-op (Jon's ruling, Sec 6) --------


def test_no_refresh_flag_does_not_change_result(_store):
    _store([BOLT])

    without = scryfall.get_card("Lightning Bolt", no_refresh=False)
    with_flag = scryfall.get_card("Lightning Bolt", no_refresh=True)

    assert without == with_flag


# --- store not yet built (fresh checkout) ---------------------------------


def test_missing_store_file_is_a_clean_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(scryfall, "DB_PATH", tmp_path / "never_built.db")

    assert scryfall.get_card("Lightning Bolt") is None
    assert scryfall.pop_fuzzy_fallbacks() == []


# --- fallback log drains correctly -----------------------------------------


def test_pop_fuzzy_fallbacks_clears_after_reading(_store):
    _store([BOLT])
    scryfall.get_card("Lightning Blot")  # fuzzy hit -- populates the log

    first = scryfall.pop_fuzzy_fallbacks()
    second = scryfall.pop_fuzzy_fallbacks()

    assert len(first) == 1
    assert second == []


# --- bracket parsing (unchanged) --------------------------------------------


def test_bracket_parsing_multiple_cards():
    stripped, tokens = scryfall.parse_card_refs("[Dovescape] and [Dovin's Veto]")

    assert tokens == ["Dovescape", "Dovin's Veto"]
    assert stripped == "Dovescape and Dovin's Veto"


def test_bracket_parsing_no_brackets_yields_no_tokens():
    question = "what does Llanowar Elves do?"

    stripped, tokens = scryfall.parse_card_refs(question)

    assert tokens == []
    assert stripped == question

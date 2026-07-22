# Tests for the Scryfall card-enrichment tool (plan #3b,
# docs/plan-3b-scryfall-enrichment.md).
#
# Every test monkeypatches scryfall._http_get -- the single seam every real
# HTTP GET goes through -- so nothing here ever touches the network. Each
# test also gets its own on-disk cache file (tmp_path) and a reset in-memory
# cache/request-timer, so tests never see each other's state and never touch
# the real data/parsed/scryfall_cache.json.

import pytest

from rulesagent.tools import scryfall

CARD_JSON = {
    "name": "Dovin's Veto",
    "oracle_text": "This spell can't be countered. Counter target instant or "
    "sorcery spell.",
    "type_line": "Instant",
    "mana_cost": "{1}{W}",
    "oracle_id": "11111111-1111-1111-1111-111111111111",
    "rulings_uri": "https://api.scryfall.com/cards/dovins-veto/rulings",
}

RULINGS_JSON = {
    "object": "list",
    "data": [
        {"published_at": "2019-01-25", "comment": "This can counter an ability."},
        {"published_at": "2019-01-25", "comment": "This can't be countered itself."},
    ],
}

DFC_JSON = {
    "name": "Front // Back",
    "oracle_text": "",
    "type_line": "Creature // Creature",
    "mana_cost": "{2}{R}",
    "oracle_id": "22222222-2222-2222-2222-222222222222",
    "rulings_uri": "https://api.scryfall.com/cards/front-back/rulings",
    "card_faces": [
        {"name": "Front", "oracle_text": "Front face text."},
        {"name": "Back", "oracle_text": "Back face text."},
    ],
}

EMPTY_RULINGS_JSON = {"object": "list", "data": []}


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Give every test its own cache file and a clean in-memory cache/
    request-timer -- otherwise tests would leak card data (and cache-hit
    behavior) into each other, and the module-level cache would drift
    toward the real data/parsed/scryfall_cache.json."""
    monkeypatch.setattr(scryfall, "CACHE_PATH", tmp_path / "scryfall_cache.json")
    monkeypatch.setattr(scryfall, "_cache", None)
    monkeypatch.setattr(scryfall, "_last_request_at", 0.0)
    yield


def _fake_http_get(routes):
    """Build a fake _http_get that dispatches by URL, recording every call
    as (url, params) so tests can assert on what was actually requested."""
    calls = []

    def fake(url, params=None):
        calls.append((url, params))
        if url not in routes:
            raise AssertionError(f"unexpected URL requested: {url} {params}")
        return routes[url]

    fake.calls = calls
    return fake


# --- name lookup ----------------------------------------------------------


def test_name_lookup_returns_card_with_oracle_text_and_rulings(monkeypatch):
    fake = _fake_http_get(
        {
            "https://api.scryfall.com/cards/named": CARD_JSON,
            CARD_JSON["rulings_uri"]: RULINGS_JSON,
        }
    )
    monkeypatch.setattr(scryfall, "_http_get", fake)

    card = scryfall.get_card("dovins veto")

    assert card is not None
    assert card.name == "Dovin's Veto"
    assert card.oracle_text == CARD_JSON["oracle_text"]
    assert card.type_line == "Instant"
    assert card.mana_cost == "{1}{W}"
    assert card.oracle_id == CARD_JSON["oracle_id"]
    assert card.rulings == [r["comment"] for r in RULINGS_JSON["data"]]

    # Named (fuzzy) lookup, not the search/oracleid endpoint.
    named_calls = [c for c in fake.calls if c[0] == "https://api.scryfall.com/cards/named"]
    assert named_calls == [("https://api.scryfall.com/cards/named", {"fuzzy": "dovins veto"})]


# --- oracle_id lookup -------------------------------------------------------


def test_oracle_id_ref_routes_to_search_endpoint(monkeypatch):
    oid = "11111111-1111-1111-1111-111111111111"
    fake = _fake_http_get(
        {
            "https://api.scryfall.com/cards/search": {"data": [CARD_JSON]},
            CARD_JSON["rulings_uri"]: RULINGS_JSON,
        }
    )
    monkeypatch.setattr(scryfall, "_http_get", fake)

    card = scryfall.get_card(oid)

    assert card is not None
    assert card.name == "Dovin's Veto"
    # First call must be the search endpoint with q=oracleid:<uuid> -- NOT
    # the named/fuzzy endpoint.
    assert fake.calls[0] == (
        "https://api.scryfall.com/cards/search",
        {"q": f"oracleid:{oid}"},
    )
    assert not any(c[0] == "https://api.scryfall.com/cards/named" for c in fake.calls)


# --- double-faced / split cards ---------------------------------------------


def test_double_faced_card_joins_both_faces_no_half_dropped(monkeypatch):
    fake = _fake_http_get(
        {
            "https://api.scryfall.com/cards/named": DFC_JSON,
            DFC_JSON["rulings_uri"]: EMPTY_RULINGS_JSON,
        }
    )
    monkeypatch.setattr(scryfall, "_http_get", fake)

    card = scryfall.get_card("front back")

    assert card is not None
    assert card.name == "Front // Back"
    assert card.oracle_text == "Front face text.\n//\nBack face text."


# --- 404 --------------------------------------------------------------------


def test_unknown_card_name_returns_none(monkeypatch):
    def fake(url, params=None):
        return None  # simulates a 404 -- _http_get already normalizes this

    monkeypatch.setattr(scryfall, "_http_get", fake)

    assert scryfall.get_card("Definitely Not A Real Card Xyz") is None


def test_unknown_oracle_id_returns_none(monkeypatch):
    def fake(url, params=None):
        return None

    monkeypatch.setattr(scryfall, "_http_get", fake)

    assert scryfall.get_card("99999999-9999-9999-9999-999999999999") is None


# --- caching -----------------------------------------------------------------


def test_fresh_cache_entry_makes_no_http_call(monkeypatch):
    fake = _fake_http_get(
        {
            "https://api.scryfall.com/cards/named": CARD_JSON,
            CARD_JSON["rulings_uri"]: RULINGS_JSON,
        }
    )
    monkeypatch.setattr(scryfall, "_http_get", fake)

    first = scryfall.get_card("dovins veto")
    calls_after_first = len(fake.calls)
    assert calls_after_first == 2  # named lookup + rulings fetch

    second = scryfall.get_card("dovins veto")

    assert len(fake.calls) == calls_after_first  # no new network calls
    assert second == first


def test_entry_older_than_ttl_refetches(monkeypatch):
    fake = _fake_http_get(
        {
            "https://api.scryfall.com/cards/named": CARD_JSON,
            CARD_JSON["rulings_uri"]: RULINGS_JSON,
        }
    )
    monkeypatch.setattr(scryfall, "_http_get", fake)

    scryfall.get_card("dovins veto")
    assert len(fake.calls) == 2

    cache = scryfall._get_cache()
    cache["dovins veto"]["fetched_at"] -= (scryfall.TTL_DAYS + 1) * 86400

    scryfall.get_card("dovins veto")

    assert len(fake.calls) == 4  # re-fetched: named lookup + rulings again


def test_no_refresh_uses_stale_entry_without_fetching(monkeypatch):
    fake = _fake_http_get(
        {
            "https://api.scryfall.com/cards/named": CARD_JSON,
            CARD_JSON["rulings_uri"]: RULINGS_JSON,
        }
    )
    monkeypatch.setattr(scryfall, "_http_get", fake)

    scryfall.get_card("dovins veto")
    assert len(fake.calls) == 2

    cache = scryfall._get_cache()
    cache["dovins veto"]["fetched_at"] -= (scryfall.TTL_DAYS + 1) * 86400

    card = scryfall.get_card("dovins veto", no_refresh=True)

    assert len(fake.calls) == 2  # no new network calls despite the stale age
    assert card is not None
    assert card.name == "Dovin's Veto"


# --- bracket parsing ----------------------------------------------------------


def test_bracket_parsing_multiple_cards():
    stripped, tokens = scryfall.parse_card_refs("[Dovescape] and [Dovin's Veto]")

    assert tokens == ["Dovescape", "Dovin's Veto"]
    assert stripped == "Dovescape and Dovin's Veto"


def test_bracket_parsing_no_brackets_yields_no_tokens():
    question = "what does Llanowar Elves do?"

    stripped, tokens = scryfall.parse_card_refs(question)

    assert tokens == []
    assert stripped == question

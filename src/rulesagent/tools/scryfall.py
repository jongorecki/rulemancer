"""Scryfall card enrichment. Plan #3b (docs/plan-3b-scryfall-enrichment.md).

The reframe that shapes this module (Jon, 2026-07-21): this is NOT a router
that picks "card or rules." Rules are always retrieved; card data is
ADDITIONALLY pulled for any `[bracket]`-referenced card and handed to the
generator alongside the rules. A pure card question is just the degenerate
case where rules retrieval isn't relevant; a pure rules question references
no cards, so nothing extra is fetched.

Card references are `[Card Name]` or `[oracle-id-uuid]` tokens in the
question -- deterministic to parse, no LLM name-guessing. The `@`-triggered
autocomplete UI that produces these tokens is a separate, deferred, frontend
concern (see the plan) -- by the time a question reaches this module, cards
are already `[...]` tokens.
"""

import json
import re
import time
from pathlib import Path

import httpx

from rulesagent.contracts import Card

HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}
ATTRIBUTION = "Card data from Scryfall (scryfall.com)."
TTL_DAYS = 7
# Rulings get ADDED over time (WotC issues them after a set ships), so a
# permanent cache would serve stale enrichment forever. 7 days: rulings churn
# is slow, so this is generous on freshness while still being an actual TTL
# rather than "cache forever."

CACHE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "parsed" / "scryfall_cache.json"
# src/rulesagent/tools/scryfall.py -> repo root is four ".parent"s up, same
# depth/pattern as retrieve/rewrite.py's CACHE_PATH.

MIN_SPACING = 0.1
# Seconds between consecutive LIVE requests. Scryfall sends no rate-limit
# headers (verified in the plan's reachability spike) -- it relies on client
# courtesy, so we self-impose ~100ms spacing rather than hammering it.

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

CARD_TOKEN_RE = re.compile(r"\[([^\]]+)\]")
# `[...]` is what the pipeline parses -- NOT the `@` typing affordance (that's
# a deferred frontend concern; see the plan). Brackets delimit multi-word
# names cleanly and require no LLM name-guessing.

_cache: dict | None = None
# Module-level, lazily loaded once per process -- same pattern as
# retrieve/rewrite.py's _cache, so a run that looks up many cards pays one
# disk read instead of one per lookup.

_last_request_at = 0.0
# Wall-clock (monotonic) timestamp of the last LIVE request, used to enforce
# MIN_SPACING. Never touched by cache hits.


def parse_card_refs(question: str) -> tuple[str, list[str]]:
    """Pull `[Card Name]` / `[oracle-id]` tokens out of a question.

    Returns (stripped_text, tokens): `stripped_text` has every `[...]`
    replaced by its bare contents -- so "[Dovescape]" reads as "Dovescape",
    a natural sentence -- for use as both the rewriter's input and the
    generator's question text. `tokens` are the raw strings to feed to
    get_card(). A question with no brackets returns (question, []) --
    unchanged text, empty token list -- so the no-card path is a no-op.
    """
    tokens = CARD_TOKEN_RE.findall(question)
    stripped = CARD_TOKEN_RE.sub(lambda m: m.group(1), question)
    return stripped, tokens


def _get_cache() -> dict:
    global _cache
    if _cache is None:
        if CACHE_PATH.exists():
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def _save_cache() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_cache, f, indent=2, ensure_ascii=False)


def _http_get(url: str, params: dict | None = None) -> dict | None:
    """The single seam every real Scryfall GET goes through. Tests
    monkeypatch this one function -- no test hits the network, and no new
    test dependency (responses/vcr/etc.) is needed.

    Returns the parsed JSON body, or None on a 404 (unknown card / empty
    search) -- callers treat that as "not found," never as an exception.
    """
    response = httpx.get(url, headers=HEADERS, params=params, timeout=10.0)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _live_get(url: str, params: dict | None = None) -> dict | None:
    """Wraps _http_get with the courtesy spacing. Only ever called on an
    actual network path (never on a cache hit), so cached lookups stay
    instant and only genuine live traffic gets throttled."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_SPACING:
        time.sleep(MIN_SPACING - elapsed)
    result = _http_get(url, params)
    _last_request_at = time.monotonic()
    return result


def _card_from_json(data: dict) -> Card:
    oracle_text = data.get("oracle_text") or ""
    if not oracle_text and data.get("card_faces"):
        # Double-faced / split cards: oracle_text lives per-face. Join every
        # face rather than taking the first, so a card never loses half its
        # text. `name` is deliberately NOT rebuilt from the faces here --
        # the top-level `name` (already "Front // Back" where relevant) is
        # preferred, per the plan.
        oracle_text = "\n//\n".join(face.get("oracle_text", "") for face in data["card_faces"])

    rulings: list[str] = []
    rulings_uri = data.get("rulings_uri")
    if rulings_uri:
        rulings_data = _live_get(rulings_uri)
        if rulings_data:
            rulings = [r["comment"] for r in rulings_data.get("data", [])]

    return Card(
        name=data.get("name", ""),
        oracle_text=oracle_text,
        type_line=data.get("type_line", ""),
        mana_cost=data.get("mana_cost", ""),
        oracle_id=data.get("oracle_id", ""),
        rulings=rulings,
    )


def get_card(ref: str, no_refresh: bool = False) -> Card | None:
    """Look up a card by name or Scryfall oracle_id.

    `ref` is either a card name (routed through fuzzy /cards/named -- typo
    tolerant) or an oracle_id UUID (routed through /cards/search?q=oracleid:
    and the first result taken). 404 / no results -> None, not an exception.

    Cached in CACHE_PATH, keyed by `ref` itself (the token actually looked
    up) -- mirrors retrieve/rewrite.py's cache, which is keyed by the input
    question rather than by some normalized form of the model's output.
    A cached entry is used without a network call when it's fresh (age <=
    TTL_DAYS) OR when no_refresh=True (the eval-reproducibility freeze mode,
    which uses ANY cached entry regardless of age). Otherwise, a live fetch
    is made and the cache entry is created/updated.
    """
    cache = _get_cache()
    entry = cache.get(ref)
    if entry is not None:
        age_days = (time.time() - entry["fetched_at"]) / 86400
        if no_refresh or age_days <= TTL_DAYS:
            return Card(**entry["card"])

    if _UUID_RE.fullmatch(ref):
        search_result = _live_get(
            "https://api.scryfall.com/cards/search", params={"q": f"oracleid:{ref}"}
        )
        if not search_result or not search_result.get("data"):
            return None
        card_json = search_result["data"][0]
    else:
        card_json = _live_get("https://api.scryfall.com/cards/named", params={"fuzzy": ref})
        if card_json is None:
            return None

    card = _card_from_json(card_json)
    cache[ref] = {"fetched_at": time.time(), "card": card.model_dump()}
    _save_cache()
    return card

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

import httpx

from rulesagent.cache import KVCache
from rulesagent.contracts import Card, CardFace

HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}
ATTRIBUTION = "Card data from Scryfall (scryfall.com)."
TTL_DAYS = 7

CARD_CACHE_SCHEMA = 2
# Bumped when the Card shape changes (schema 2 added layout + per-face `faces` +
# mana_value + color_identity, per docs/plan-card-enrichment-fields.md). A cache
# entry whose schema doesn't match is treated as a miss and refetched, so
# old-schema entries (which lack `faces`) auto-upgrade instead of silently
# feeding the generator a card with no per-face data.
# Rulings get ADDED over time (WotC issues them after a set ships), so a
# permanent cache would serve stale enrichment forever. 7 days: rulings churn
# is slow, so this is generous on freshness while still being an actual TTL
# rather than "cache forever."

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

_cache = KVCache("scryfall")
# L3 (docs/plan-l3-sqlite-caches.md): data/cache.db's `scryfall` table, keyed
# by the ref token as-is; value is the {fetched_at, schema, card} entry as
# JSON (TTL + schema-bump logic stay INSIDE the value, unchanged).

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


def _face_from_json(f: dict) -> CardFace:
    """One CardFace from a Scryfall face object (or the top-level card object
    for a single-faced card -- same field names either way)."""
    return CardFace(
        name=f.get("name", "") or "",
        mana_cost=f.get("mana_cost", "") or "",
        type_line=f.get("type_line", "") or "",
        oracle_text=f.get("oracle_text", "") or "",
        power=f.get("power", "") or "",
        toughness=f.get("toughness", "") or "",
        loyalty=f.get("loyalty", "") or "",
        defense=f.get("defense", "") or "",
        colors=f.get("colors", []) or [],
        color_indicator=f.get("color_indicator", []) or [],
    )


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

    # Layout-first (Jon): read layout, then build the faces. A multi-face card
    # (card_faces present) gets one CardFace per printed face -- so each face's
    # own mana cost / type / power-toughness survives; a single-faced card gets
    # one CardFace built from the top-level object.
    if data.get("card_faces"):
        faces = [_face_from_json(f) for f in data["card_faces"]]
    else:
        faces = [_face_from_json(data)]

    return Card(
        name=data.get("name", ""),
        oracle_text=oracle_text,
        type_line=data.get("type_line", ""),
        mana_cost=data.get("mana_cost", ""),
        oracle_id=data.get("oracle_id", ""),
        rulings=rulings,
        layout=data.get("layout", "") or "",
        mana_value=data.get("cmc", 0.0) or 0.0,
        colors=data.get("colors", []) or [],
        color_identity=data.get("color_identity", []) or [],
        faces=faces,
    )


def get_card(ref: str, no_refresh: bool = False) -> Card | None:
    """Look up a card by name or Scryfall oracle_id.

    `ref` is either a card name (routed through fuzzy /cards/named -- typo
    tolerant) or an oracle_id UUID (routed through /cards/search?q=oracleid:
    and the first result taken). 404 / no results -> None, not an exception.

    Cached in data/cache.db's `scryfall` table (L3,
    docs/plan-l3-sqlite-caches.md), keyed by `ref` itself (the token actually
    looked up) -- mirrors retrieve/rewrite.py's cache, which is keyed by the
    input question rather than by some normalized form of the model's output.
    A cached entry is used without a network call when it's fresh (age <=
    TTL_DAYS) OR when no_refresh=True (the eval-reproducibility freeze mode,
    which uses ANY cached entry regardless of age). Otherwise, a live fetch
    is made and the cache entry is created/updated.
    """
    raw = _cache.get(ref)
    entry = json.loads(raw) if raw is not None else None
    if entry is not None and entry.get("schema") == CARD_CACHE_SCHEMA:
        # Only honor entries written by the current Card schema. An entry from
        # an older schema (no per-face `faces`) is treated as a miss and
        # refetched below, so it auto-upgrades rather than feeding the
        # generator a card missing its per-face data.
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
    entry = {"fetched_at": time.time(), "schema": CARD_CACHE_SCHEMA, "card": card.model_dump()}
    _cache.put(ref, json.dumps(entry, ensure_ascii=False).encode("utf-8"))
    return card

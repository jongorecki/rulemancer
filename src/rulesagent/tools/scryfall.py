"""Card enrichment (docs/plan-scryfall-local-bulk.md).

`get_card()` resolves LOCAL-FIRST against a snapshot of Scryfall's bulk data
(`data/scryfall.db`, built by scripts/refresh_scryfall_bulk.py) -- no live
network call for the common case, per Jon's original ruling (plan Sec 10):
"the whole point is zero network calls at answer time." This removes the
transient-failure class a live per-card fetch sat on (the c012 finding this
plan grounds out of, plan Sec 0) for every request the snapshot can answer.

GRACEFUL SELF-HEALING (design revision, post-approval): an EARLIER revision
of this module made a missing/empty snapshot a hard failure (get_card()
raised). Jon's ruling replaced that: a missing/empty snapshot is now NOT an
error -- get_card() falls back to a LIVE Scryfall fetch for that one lookup
(the pre-local-bulk mechanism, recovered from git history -- see
`_live_get_card()` below) AND kicks off a non-blocking background bulk
refresh so the snapshot repairs itself for every subsequent request. A
POPULATED snapshot that simply lacks one card is unaffected either way --
still a quiet `None`, never a live fetch, never a refresh trigger. Live
fallback only ever fires when the WHOLE snapshot is unusable, not per-card.

Card references are `[Card Name]` or `[oracle-id-uuid]` tokens in the
question -- deterministic to parse, no LLM name-guessing. Unchanged from
plan #3b.

Lookup path when the snapshot IS populated (plan Sec 4, extended
post-approval per the equivalence-check finding on c011/Valki -- a
per-face-name tier, Jon-approved):
  1. ref is a UUID  -> exact match on oracle_id
  2. else           -> exact match on case-normalized (combined) name
  3. miss on both   -> exact match on an individual FACE's name (playable
                       layouts only -- never token/art_series/emblem/etc.)
  4. miss           -> LOCAL fuzzy match (rapidfuzz), never network
  5. still nothing  -> None (a true miss)

Step 3 exists because a multi-faced card's bare, commonly-used reference
(e.g. "[Valki, God of Lies]") is neither its own combined display name
("Valki, God of Lies // Tibalt, Cosmic Impostor") nor reliably the winning
fuzzy candidate -- an unrelated card can out-score it on a plain string
comparison. An exact face-name match is unambiguous and must beat any
fuzzy near-match, so it is tried first.
"""

import logging
import re
import threading
import time

import httpx

from rulesagent.contracts import Card, CardFace
from rulesagent.tools import scryfall_store

logger = logging.getLogger(__name__)

ATTRIBUTION = "Card data from Scryfall (scryfall.com)."

DB_PATH = scryfall_store.DEFAULT_DB
# Module-level so tests can monkeypatch it at a tmp_path fixture store, same
# convention scryfall_store.DEFAULT_DB itself follows. Read fresh on every
# get_card() call (not cached at import time into a local), so a monkeypatch
# takes effect immediately -- see connect() calls below, which reference
# DB_PATH by name, not a captured copy.

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

CARD_TOKEN_RE = re.compile(r"\[([^\]]+)\]")
# `[...]` is what the pipeline parses -- NOT the `@` typing affordance (a
# deferred frontend concern). Brackets delimit multi-word names cleanly and
# require no LLM name-guessing.

_fuzzy_fallback_log: list[dict] = []
# Module-level side-channel (same pattern as the live-fetch politeness state
# below): every fuzzy-fallback / face-tier event -- a successful match OR a
# refused ambiguous near-tie -- is appended here by get_card(), since
# get_card()'s own signature/return type stay `Card | None` (plan Sec 4/6).
# RulesAgent.answer() drains this via pop_fuzzy_fallbacks() after resolving
# a request's refs and surfaces it on Debug.fuzzy_fallbacks (api/main.py),
# mirroring the last_crossref / selected_ruling_ids debug pattern already in
# the codebase. A clean miss (fuzzy found nothing close enough) is NOT
# logged here -- only a guard actually firing is worth counting (Jon's
# ruling: "measure how often it fires").


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


def pop_fuzzy_fallbacks() -> list[dict]:
    """Return and clear every fuzzy-fallback event recorded since the last
    call. Read by RulesAgent.answer() once per request, after resolving all
    of that request's card refs -- draining rather than peeking so events
    never leak into the next request's debug payload."""
    global _fuzzy_fallback_log
    events, _fuzzy_fallback_log = _fuzzy_fallback_log, []
    return events


# =============================================================================
# LIVE FALLBACK (recovered from git history, commit acdce54 -- the parent of
# 438767d, which replaced this module's original live-fetch design with
# local-only). Used ONLY when the local snapshot itself is missing/empty
# (self-healing bridge); a populated snapshot never reaches this code.
# Preserved close to verbatim, including its rate limiting -- this is
# recovered, not rewritten from scratch, per Jon's explicit instruction.
# =============================================================================

_LIVE_HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}
_LIVE_MIN_SPACING = 0.1
# Seconds between consecutive LIVE requests -- Scryfall sends no rate-limit
# headers, so this self-imposes ~100ms client-side courtesy spacing (same
# value/reasoning as the original module).

_last_live_request_at = 0.0
# Wall-clock (monotonic) timestamp of the last LIVE request, used to enforce
# _LIVE_MIN_SPACING. Only touched on the live-fallback path.


def _live_http_get(url: str, params: dict | None = None) -> dict | None:
    """The single seam every live Scryfall GET goes through on the fallback
    path. Returns the parsed JSON body, or None on a 404 (unknown card /
    empty search) -- callers treat that as "not found," never an
    exception."""
    response = httpx.get(url, headers=_LIVE_HEADERS, params=params, timeout=10.0)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _live_get(url: str, params: dict | None = None) -> dict | None:
    """Wraps _live_http_get with the courtesy spacing. Only ever called on
    the live-fallback path (never when the local snapshot is healthy)."""
    global _last_live_request_at
    elapsed = time.monotonic() - _last_live_request_at
    if elapsed < _LIVE_MIN_SPACING:
        time.sleep(_LIVE_MIN_SPACING - elapsed)
    result = _live_http_get(url, params)
    _last_live_request_at = time.monotonic()
    return result


def _live_face_from_json(f: dict) -> CardFace:
    """One CardFace from a Scryfall face object (or the top-level card
    object for a single-faced card -- same field names either way)."""
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


def _live_card_from_json(data: dict) -> Card:
    oracle_text = data.get("oracle_text") or ""
    if not oracle_text and data.get("card_faces"):
        # Double-faced / split cards: oracle_text lives per-face. Join every
        # face rather than taking the first, so a card never loses half its
        # text. `name` is deliberately NOT rebuilt from the faces here --
        # the top-level `name` (already "Front // Back" where relevant) is
        # preferred.
        oracle_text = "\n//\n".join(face.get("oracle_text", "") for face in data["card_faces"])

    rulings: list[str] = []
    rulings_uri = data.get("rulings_uri")
    if rulings_uri:
        rulings_data = _live_get(rulings_uri)
        if rulings_data:
            rulings = [r["comment"] for r in rulings_data.get("data", [])]

    if data.get("card_faces"):
        faces = [_live_face_from_json(f) for f in data["card_faces"]]
    else:
        faces = [_live_face_from_json(data)]

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


def _live_get_card(ref: str) -> Card | None:
    """The live-fallback lookup itself: same routing the pre-local-bulk
    get_card() used (UUID -> oracleid search; else -> fuzzy /cards/named).
    Called ONLY from get_card() when the local snapshot is missing/empty --
    never as a supplement to a healthy snapshot's own miss. Deliberately NOT
    cached (data/cache.db's old `scryfall` table stays dead, per the
    original plan's Sec 6 decision) -- this is a short self-healing bridge
    until the background refresh lands a real snapshot, not a permanent
    parallel cache."""
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
    return _live_card_from_json(card_json)


# =============================================================================
# BACKGROUND SELF-HEAL REFRESH
# =============================================================================

_refresh_lock = threading.Lock()
_refresh_thread: threading.Thread | None = None
# Module-flag concurrency guard: at most one self-heal background refresh
# runs at a time from THIS trigger. `_refresh_thread` is the currently-
# running (or last-run) thread; `is_alive()` is the dedup check, cleared
# back to None by the worker's own `finally` once it's done, so the next
# get_card() call on a still-missing snapshot can launch another attempt.


def _run_bulk_refresh() -> dict:
    """The actual refresh call -- a thin, directly-monkeypatchable seam.
    scripts/ isn't a package under src/, so this uses the same sys.path-
    insertion convention api/main.py already established for importing this
    exact function (admin endpoint). Passes `dest_path=DB_PATH` explicitly
    (this module's own, possibly-monkeypatched path) rather than relying on
    refresh_scryfall_bulk.refresh()'s default argument, which is bound once
    at that function's definition time and would NOT pick up a later
    DB_PATH override."""
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import refresh_scryfall_bulk

    return refresh_scryfall_bulk.refresh(dest_path=DB_PATH)


def _background_refresh_worker() -> None:
    global _refresh_thread
    try:
        summary = _run_bulk_refresh()
        logger.info("self-heal scryfall bulk refresh completed: %r", summary)
    except Exception as e:
        logger.warning("self-heal scryfall bulk refresh failed: %r", e)
    finally:
        with _refresh_lock:
            _refresh_thread = None


def trigger_background_refresh() -> bool:
    """Kick off a bulk refresh (build-to-temp + atomic swap, via the shared
    scripts/refresh_scryfall_bulk.refresh()) in a daemon background thread,
    if one isn't already running. Non-blocking -- returns immediately
    either way. Returns True if a new refresh was just launched, False if
    one was already in progress (the concurrency guard: never two
    concurrent refreshes from this trigger)."""
    global _refresh_thread
    with _refresh_lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return False
        _refresh_thread = threading.Thread(target=_background_refresh_worker, daemon=True)
        _refresh_thread.start()
        return True


def get_card(ref: str, no_refresh: bool = False) -> Card | None:
    """Look up a card by name or Scryfall oracle_id: LOCAL-FIRST against the
    snapshot store (`DB_PATH`), with a live-fallback + self-heal bridge for
    the whole-snapshot-unusable case (see module docstring).

    `no_refresh` is an INERT, documented no-op (Jon's ruling, plan Sec 6):
    under the pre-local-bulk design it meant "accept any cached entry
    regardless of TTL age." Nothing on either the local or live-fallback
    path caches by TTL any more, so there is nothing left for it to gate.
    Kept for zero call-site churn (answer.py, eval scripts all still pass
    it); scheduled for removal in a later cleanup slice.

    Behavior:
      - Snapshot populated: resolves via the local-only pipeline (exact
        oracle_id/name, face-name tier, local fuzzy) -- unchanged, no
        network, no refresh trigger, EVER, on a healthy snapshot. A real
        per-card miss here is a quiet `None`, exactly as before.
      - Snapshot missing or empty: resolves this one ref via a LIVE
        Scryfall fetch (`_live_get_card`) and kicks off a non-blocking
        background bulk refresh (`trigger_background_refresh`) so the
        snapshot repairs itself for subsequent calls. Never raises.
    """
    conn = scryfall_store.connect(DB_PATH)
    try:
        if not scryfall_store.is_populated(conn):
            trigger_background_refresh()
            return _live_get_card(ref)

        if _UUID_RE.fullmatch(ref):
            # A UUID ref that misses is a confirmed miss -- fuzzy-matching a
            # UUID string against card NAMES makes no sense, so this never
            # falls through to step 3.
            return scryfall_store.lookup_oracle_id(conn, ref)

        card = scryfall_store.lookup_name_exact(conn, ref)
        if card is not None:
            return card

        # Face-name tier (c011/Valki equivalence-check finding): an EXACT
        # match against an individual FACE's name, tried BEFORE fuzzy so it
        # always wins against a fuzzy near-match (e.g. "Loki, God of Lies"
        # out-scoring "Valki, God of Lies // Tibalt, Cosmic Impostor" on a
        # bare WRatio comparison). A genuine ambiguity at this tier (two
        # playable cards sharing a face name) is terminal -- refuses
        # outright rather than falling through to fuzzy, which could
        # silently pick one and defeat the guard.
        card, event = scryfall_store.lookup_face_name(conn, ref)
        if card is not None:
            if event is not None:
                _fuzzy_fallback_log.append(event)
            return card
        if event is not None:
            _fuzzy_fallback_log.append(event)
            return None

        card, event = scryfall_store.fuzzy_lookup(conn, ref)
        if event is not None:
            _fuzzy_fallback_log.append(event)
        return card
    finally:
        conn.close()

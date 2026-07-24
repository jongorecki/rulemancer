"""Card enrichment (docs/plan-scryfall-local-bulk.md).

REPLACES the earlier live-fetch design (plan #3b). `get_card()` now resolves
purely against a local snapshot of Scryfall's bulk data (`data/scryfall.db`,
built by scripts/refresh_scryfall_bulk.py) -- no live network call of any
kind at answer time. Per Jon's ruling (plan Sec 10): "the whole point is
zero network calls at answer time" -- this removes the entire transient-
failure class a live per-card fetch sat on (the c012 finding this plan
grounds out of, plan Sec 0).

Card references are `[Card Name]` or `[oracle-id-uuid]` tokens in the
question -- deterministic to parse, no LLM name-guessing. Unchanged from
plan #3b.

Lookup path (plan Sec 4, extended post-approval per the equivalence-check
finding on c011/Valki -- a per-face-name tier, Jon-approved):
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

import re

from rulesagent.contracts import Card
from rulesagent.tools import scryfall_store

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
# Module-level side-channel (same pattern as the old live-fetch module's
# `_last_request_at`): every fuzzy-fallback event -- a successful match OR a
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


def get_card(ref: str, no_refresh: bool = False) -> Card | None:
    """Look up a card by name or Scryfall oracle_id, against the LOCAL
    snapshot store (`DB_PATH`) only -- never a network call.

    `no_refresh` is an INERT, documented no-op (Jon's ruling, plan Sec 6):
    under the old live-fetch design it meant "accept any cached entry
    regardless of TTL age" (the eval-reproducibility freeze mode). A local
    snapshot lookup never triggers a download regardless of this flag --
    refresh is a fully separate, out-of-band process (scripts/
    refresh_scryfall_bulk.py) -- so there is nothing left for it to gate.
    Kept for zero call-site churn (answer.py, eval scripts all still pass
    it); scheduled for removal in a later cleanup slice.

    Raises `scryfall_store.ScryfallStoreEmptyError` if `DB_PATH` is missing
    or has zero cards (merge-safety guard, added post-approval): this
    design has no live fallback, so a missing/never-refreshed store would
    otherwise silently return None for every single lookup -- the bot would
    look "fine" while being blind to all card oracle text, with no error
    anywhere. That is a hard misconfiguration, not a per-card miss, so it
    fails loud instead. A genuinely populated store that simply lacks the
    requested card is completely unaffected -- that is still a quiet
    `None`, exactly as before.
    """
    conn = scryfall_store.connect(DB_PATH)
    try:
        scryfall_store.assert_populated(conn, DB_PATH)

        if _UUID_RE.fullmatch(ref):
            # A UUID ref that misses is a confirmed miss -- fuzzy-matching a
            # UUID string against card NAMES makes no sense, so this never
            # falls through to step 3.
            return scryfall_store.lookup_oracle_id(conn, ref)

        card = scryfall_store.lookup_name_exact(conn, ref)
        if card is not None:
            return card

        # Face-name tier (added post-approval, c011/Valki equivalence-check
        # finding): an EXACT match against an individual FACE's name, tried
        # BEFORE fuzzy so it always wins against a fuzzy near-match (e.g.
        # "Loki, God of Lies" out-scoring "Valki, God of Lies // Tibalt,
        # Cosmic Impostor" on a bare WRatio comparison). A genuine ambiguity
        # at this tier (two playable cards sharing a face name) is terminal
        # -- refuses outright rather than falling through to fuzzy, which
        # could silently pick one and defeat the guard.
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

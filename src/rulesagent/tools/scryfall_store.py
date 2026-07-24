"""Local Scryfall bulk-data snapshot store (docs/plan-scryfall-local-bulk.md).

`data/scryfall.db` -- a dedicated SQLite file, separate from `data/cache.db`
(Sec 3 of the plan). `cache.db`'s tables are ephemeral, per-key, TTL-governed
caches written continuously by live traffic (L3's whole design point). This
store is the opposite shape: a VERSIONED SNAPSHOT that gets replaced wholesale
on refresh (scripts/refresh_scryfall_bulk.py) and must never be read
half-written. Its own file makes "atomic swap" trivial (`os.replace()` one
file) without touching anything cache.db is concurrently reading/writing.

Every function here takes an already-open connection (or builds one via
`connect()`) -- per-op connections, mirroring cache.py's KVCache philosophy
("per-op connections are the simplest shape that's actually correct").
"""

import json
import sqlite3
from pathlib import Path

from rulesagent.contracts import Card

DEFAULT_DB = Path(__file__).parent.parent.parent.parent / "data" / "scryfall.db"
# src/rulesagent/tools/scryfall_store.py -> repo root is four ".parent"s up.

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS cards (
      oracle_id  TEXT PRIMARY KEY,
      name       TEXT NOT NULL,
      name_norm  TEXT NOT NULL,
      layout     TEXT NOT NULL DEFAULT '',
      card_json  TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_name_norm ON cards(name_norm)",
    """
    CREATE TABLE IF NOT EXISTS rulings (
      oracle_id  TEXT NOT NULL,
      idx        INTEGER NOT NULL,
      comment    TEXT NOT NULL,
      PRIMARY KEY (oracle_id, idx)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rulings_oracle ON rulings(oracle_id)",
    """
    CREATE TABLE IF NOT EXISTS card_faces (
      oracle_id       TEXT NOT NULL,
      face_idx        INTEGER NOT NULL,
      face_name_norm  TEXT NOT NULL,
      PRIMARY KEY (oracle_id, face_idx)
    )
    """,
    # Per-face-name lookup tier (docs/plan-scryfall-local-bulk.md, post-
    # approval fix for the c011/Valki finding): a single-faced card gets one
    # row whose face name equals the card's own top-level name (redundant
    # with `cards.name_norm`, harmless -- get_card() tries the exact-name
    # tier first and never reaches here for those). A multi-faced card gets
    # one row per printed face, so a bare single-face reference like "Valki,
    # God of Lies" is reachable even though it's not the card's own
    # (combined) display name.
    "CREATE INDEX IF NOT EXISTS idx_card_faces_name_norm ON card_faces(face_name_norm)",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)",
]

# Non-playable Scryfall layouts: bonus/decorative objects (art_series),
# tokens, and other non-spell/non-permanent objects that aren't "a card" in
# the sense Card/CardFace models one. The face-name tier (lookup_face_name)
# must never resolve a bare name reference to one of these when a real
# playable card also shares that face name -- this is exactly the Valki
# (modal_dfc) vs. decoy (art_series) case the equivalence check surfaced.
NON_PLAYABLE_LAYOUTS = frozenset({
    "token", "double_faced_token", "emblem", "art_series", "vanguard",
    "scheme", "planar",
})

# Jon's ruling (2026-07-23): "Fuzzy threshold: start at 90, with the explicit
# expectation it gets tuned against real queries." Ambiguity guard: "ship it,
# but measure how often it fires" -- the plan's own proposed margin (Sec 4,
# "e.g., <=3 points") is what ships; revisit only if real-world data shows it
# firing, per Jon's ruling. Both are module constants, not hardcoded inline,
# so tuning later is a one-line change.
FUZZY_THRESHOLD = 90.0
AMBIGUITY_MARGIN = 3.0

# The Card fields carried in `cards.card_json`, everything Card(...) needs
# EXCEPT `rulings` (that comes from the `rulings` table join, keyed by
# oracle_id, per Sec 3's schema split).
_CARD_JSON_FIELDS = (
    "name", "oracle_text", "type_line", "mana_cost", "oracle_id",
    "layout", "mana_value", "colors", "color_identity", "faces",
)


def normalize_name(name: str) -> str:
    """Case-insensitive exact-match key: casefold + collapse whitespace.
    Doubles as the fuzzy-match corpus normalization (Sec 3/4) -- one
    normalization used everywhere a name is compared."""
    return " ".join(name.strip().casefold().split())


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open (creating if missing) a scryfall.db connection with the schema
    in place. A missing/never-refreshed store behaves as "zero cards, every
    lookup is a clean miss" rather than crashing -- reasonable for a fresh
    checkout that hasn't run the import script yet."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    return conn


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row is not None else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def _row_to_card(conn: sqlite3.Connection, oracle_id: str, card_json: str) -> Card:
    fields = json.loads(card_json)
    rulings = [
        row[0]
        for row in conn.execute(
            "SELECT comment FROM rulings WHERE oracle_id = ? ORDER BY idx", (oracle_id,)
        ).fetchall()
    ]
    return Card(**fields, rulings=rulings)


def lookup_oracle_id(conn: sqlite3.Connection, oracle_id: str) -> Card | None:
    """Step 1 of get_card's lookup path (Sec 4): exact match on oracle_id."""
    row = conn.execute(
        "SELECT oracle_id, card_json FROM cards WHERE oracle_id = ?", (oracle_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_card(conn, row[0], row[1])


def lookup_name_exact(conn: sqlite3.Connection, name: str) -> Card | None:
    """Step 2 of get_card's lookup path (Sec 4): exact match on
    case-normalized name."""
    row = conn.execute(
        "SELECT oracle_id, card_json FROM cards WHERE name_norm = ?",
        (normalize_name(name),),
    ).fetchone()
    if row is None:
        return None
    return _row_to_card(conn, row[0], row[1])


def lookup_face_name(
    conn: sqlite3.Connection, name: str,
) -> tuple[Card | None, dict | None]:
    """Face-name lookup tier, tried between the exact combined-name match
    and the fuzzy fallback (get_card's step 2.5, added post-approval per
    Jon's ruling on the c011/Valki equivalence-check finding): an EXACT
    match against an individual FACE's name, not the card's own combined
    "Front // Back" display name. Never fuzzy -- this is a higher-precision
    tier ABOVE fuzzy, so it must win against any fuzzy near-match (the
    "Loki, God of Lies" case) rather than being folded into that scoring.

    Returns (card_or_none, event_or_none), same shape as fuzzy_lookup:
      - No face matches at all: (None, None) -- not logged, a clean miss,
        falls through to fuzzy exactly like today.
      - Every face-name match is on a NON-PLAYABLE layout (token/art_series/
        emblem/etc., see NON_PLAYABLE_LAYOUTS): treated the same as a clean
        miss -- (None, None) -- so a bare reference never resolves to a
        decorative/token object, and the caller still gets a chance via
        fuzzy on the rare shot a real card matches some other way.
      - Exactly one PLAYABLE card's face matches: (card, {"reason":
        "face_name_match", ...}) -- logged like a fuzzy hit, since it's
        still a fallback (the ref wasn't the card's own combined name).
      - More than one PLAYABLE card shares that exact face name: (None,
        {"reason": "ambiguous", ...}) -- refuses outright, same guard
        philosophy as fuzzy_lookup's ambiguity margin. This is a genuine
        exact-name tie (not a score-margin heuristic), so there's no
        threshold to tune -- any tie at this tier is real ambiguity.
    """
    norm = normalize_name(name)
    rows = conn.execute(
        "SELECT cf.oracle_id, c.name, c.layout FROM card_faces cf "
        "JOIN cards c ON c.oracle_id = cf.oracle_id "
        "WHERE cf.face_name_norm = ?",
        (norm,),
    ).fetchall()
    if not rows:
        return None, None

    # Dedupe to one entry per oracle_id (a card can have the same face name
    # twice, e.g. the art_series decoy's two identical faces).
    by_oracle_id: dict[str, tuple[str, str]] = {}
    for oracle_id, card_name, layout in rows:
        by_oracle_id[oracle_id] = (card_name, layout)

    playable = {
        oid: (card_name, layout)
        for oid, (card_name, layout) in by_oracle_id.items()
        if layout not in NON_PLAYABLE_LAYOUTS
    }
    if not playable:
        # Every match was decorative/non-spell (e.g. only the art_series
        # decoy exists, or this face name is genuinely only a token's) --
        # not a resolvable hit at this tier, and not worth logging as a
        # near-miss (mirrors fuzzy_lookup's "clean miss isn't logged").
        return None, None

    if len(playable) > 1:
        candidate_names = sorted(card_name for card_name, _ in playable.values())
        return None, {
            "ref": name,
            "reason": "ambiguous",
            "matched_name": None,
            "oracle_id": None,
            "score": 100.0,
            "candidates": candidate_names,
        }

    oracle_id = next(iter(playable))  # the one playable oracle_id
    card_name, _layout = playable[oracle_id]
    card = lookup_oracle_id(conn, oracle_id)
    return card, {
        "ref": name,
        "reason": "face_name_match",
        "matched_name": card_name,
        "oracle_id": oracle_id,
        "score": 100.0,
        "candidates": [],
    }


def fuzzy_lookup(
    conn: sqlite3.Connection,
    ref: str,
    threshold: float = FUZZY_THRESHOLD,
    ambiguity_margin: float = AMBIGUITY_MARGIN,
) -> tuple[Card | None, dict | None]:
    """Step 3 of get_card's lookup path (Sec 4): LOCAL-only fuzzy match
    against the name_norm corpus, never a network call (Jon's ruling, Sec
    10: "the whole point is zero network calls at answer time").

    Returns (card_or_none, event_or_none):
      - Genuine miss (nothing scores >= threshold): (None, None) -- NOT
        logged. Only a guard actually firing is worth counting (test 6;
        Jon's ruling: "measure how often it fires," not every miss).
      - Ambiguous near-tie (top two candidates within `ambiguity_margin`
        of each other): (None, {"reason": "ambiguous", ...}) -- refuses to
        guess between two near-equally-scored cards (test 5).
      - Successful fallback: (card, {"reason": "fuzzy_match", ...}) -- the
        event is the shape `Debug.fuzzy_fallbacks` surfaces (plan Sec 4):
        {ref, matched_name, oracle_id, score}, plus `reason`.
    """
    from rapidfuzz import fuzz, process

    rows = conn.execute("SELECT name_norm, name, oracle_id FROM cards").fetchall()
    if not rows:
        return None, None

    norm_ref = normalize_name(ref)
    choices = [r[0] for r in rows]
    matches = process.extract(norm_ref, choices, scorer=fuzz.WRatio, limit=2)
    if not matches:
        return None, None

    _, top_score, top_idx = matches[0]
    if top_score < threshold:
        return None, None  # clean miss -- nothing close enough to guess at

    if len(matches) > 1:
        _, second_score, second_idx = matches[1]
        if top_score - second_score <= ambiguity_margin:
            return None, {
                "ref": ref,
                "reason": "ambiguous",
                "matched_name": None,
                "oracle_id": None,
                "score": top_score,
                "candidates": [rows[top_idx][1], rows[second_idx][1]],
            }

    name, oracle_id = rows[top_idx][1], rows[top_idx][2]
    card = lookup_oracle_id(conn, oracle_id)
    return card, {
        "ref": ref,
        "reason": "fuzzy_match",
        "matched_name": name,
        "oracle_id": oracle_id,
        "score": top_score,
        "candidates": [],
    }


def build_store(
    db_path: Path,
    cards: list[dict],
    rulings_by_oracle_id: dict[str, list[str]],
    meta: dict[str, str],
) -> dict:
    """Build a fresh store at `db_path` from already-fetched-and-filtered
    card dicts (each carrying the `_CARD_JSON_FIELDS` keys + `rulings`,
    which is dropped here in favor of the `rulings_by_oracle_id` map) and a
    rulings map. `db_path` must not already exist -- callers build into a
    temp path first (refresh script Sec 5's atomic-swap design); this
    function refuses to silently append to / overwrite a live store in
    place so a half-built import can never be mistaken for a real one.

    Real Scryfall data has rare true duplicate DISPLAY NAMES on different
    oracle_ids (e.g. the two distinct "Brothers Yamazaki" creatures) -- not
    addressed by the plan's schema, found reading the real bulk data for
    this slice. The schema's UNIQUE index on name_norm can't hold two rows
    with the same name, so on a collision the FIRST card seen (by input
    order) keeps the name_norm slot; later same-named cards still get a row
    in `cards` (reachable by their own oracle_id) but not by exact-name
    lookup. Deterministic, not a crash -- see the build report for how
    often this actually fires in the real bulk file.

    Returns {"card_count": N, "ruling_count": N, "name_collisions": N}.
    """
    if db_path.exists():
        raise FileExistsError(
            f"{db_path} already exists -- build_store never overwrites a live "
            "store in place; build into a temp path and swap (Sec 5)."
        )
    conn = connect(db_path)
    try:
        card_count = 0
        ruling_count = 0
        name_collisions = 0
        seen_name_norms: set[str] = set()
        for c in cards:
            oracle_id = c["oracle_id"]
            name = c["name"]
            name_norm = normalize_name(name)
            layout = c.get("layout") or ""
            card_json = json.dumps(
                {k: c.get(k) for k in _CARD_JSON_FIELDS}, ensure_ascii=False
            )
            if name_norm in seen_name_norms:
                name_collisions += 1
                # Row still lands in `cards` (reachable by oracle_id / a
                # UUID ref) via INSERT OR IGNORE on the name_norm slot: we
                # write the card row with a UNIQUE-safe fallback by trying
                # the plain insert first, falling back to a modified
                # sentinel only in card_json's own key space is wrong --
                # simplest correct approach: attempt insert, on conflict
                # keep the FIRST winner and skip re-registering this name.
                try:
                    conn.execute(
                        "INSERT INTO cards (oracle_id, name, name_norm, layout, card_json) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (oracle_id, name, oracle_id, layout, card_json),
                        # name_norm intentionally set to the oracle_id itself
                        # for the LOSING duplicate: guarantees uniqueness
                        # without colliding with any real name, and the row
                        # stays reachable by oracle_id lookup either way
                        # (that query never touches name_norm).
                    )
                except sqlite3.IntegrityError:
                    pass
            else:
                seen_name_norms.add(name_norm)
                conn.execute(
                    "INSERT OR REPLACE INTO cards (oracle_id, name, name_norm, layout, card_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (oracle_id, name, name_norm, layout, card_json),
                )
            card_count += 1
            for i, comment in enumerate(rulings_by_oracle_id.get(oracle_id, [])):
                conn.execute(
                    "INSERT OR REPLACE INTO rulings (oracle_id, idx, comment) VALUES (?, ?, ?)",
                    (oracle_id, i, comment),
                )
                ruling_count += 1
            for i, face in enumerate(c.get("faces") or []):
                face_name = (face or {}).get("name") or ""
                if not face_name:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO card_faces (oracle_id, face_idx, face_name_norm) "
                    "VALUES (?, ?, ?)",
                    (oracle_id, i, normalize_name(face_name)),
                )
        for k, v in meta.items():
            set_meta(conn, k, str(v))
        conn.commit()
    finally:
        conn.close()
    return {
        "card_count": card_count,
        "ruling_count": ruling_count,
        "name_collisions": name_collisions,
    }

"""Slice 4 gated-demo storage (docs/superpowers/plans/2026-07-27-gated-demo.md
Task 1): the `codes` and `events` tables from the design spec, in a dedicated
SQLite db -- data/demo.db, NOT data/cache.db, so demo telemetry lives on its
own file the Fly volume mounts and the local cache stays untouched.

Same per-op-connection, WAL-mode pattern as rulesagent.cache.KVCache -- the
established convention here -- but with real columns instead of a KV blob,
because the admin view and the guards need to filter/aggregate on code_id,
ts, and kind.
"""
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DEMO_DB = Path(
    os.environ.get("DEMO_DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "demo.db"))
)
# src/rulesagent/demo_db.py -> repo root is three ".parent"s up, same as
# rulesagent.cache.DEFAULT_DB. DEMO_DB_PATH lets the Fly deployment point this
# at the mounted volume (/app/data/demo.db) without editing code.

_BUSY_TIMEOUT_MS = 5000

_CODES_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS codes ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "code TEXT UNIQUE NOT NULL, "
    "label TEXT, "
    "created_at TEXT NOT NULL, "
    "max_queries INTEGER, "
    "revoked_at TEXT, "
    "notes TEXT)"
)
_EVENTS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "code_id INTEGER, "
    "ts TEXT NOT NULL, "
    "kind TEXT NOT NULL, "
    "ip_hash TEXT, "
    "question TEXT, "
    "answered INTEGER, "
    "input_tokens INTEGER, "
    "output_tokens INTEGER, "
    "cost_usd REAL, "
    "latency_ms INTEGER)"
)
# Slice: admin-approved rotating example pool
# (.superpowers/sdd/2026-07-28-rotating-examples/task-1-brief.md). Approval
# happens in /admin, which runs in a Fly container and cannot commit to git,
# so the pool is production state rather than a versioned file -- these two
# tables carry the invariants a code review would otherwise enforce.
_EXAMPLES_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS examples ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "question TEXT NOT NULL, "
    "norm TEXT NOT NULL UNIQUE, "  # case/whitespace-folded, dedupe key
    "source_event_id INTEGER, "  # provenance; NULL if hand-written
    "approved_at TEXT NOT NULL, "
    "warmed_at TEXT, "  # NULL until the answer cache has it
    "retired_at TEXT)"  # soft delete; history is evidence
)
_EXAMPLE_REJECTS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS example_rejects ("
    "norm TEXT PRIMARY KEY, "
    "rejected_at TEXT NOT NULL)"
)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute(_CODES_SCHEMA)
    conn.execute(_EVENTS_SCHEMA)
    conn.execute(_EXAMPLES_SCHEMA)
    conn.execute(_EXAMPLE_REJECTS_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Code generation (moved here from scripts/codes.py -- Task: admin mint/
# revoke UI, .superpowers/sdd/2026-07-27-gated-demo/task-admin-mint-report.md.
# The CLI (scripts/codes.py) and the /admin mint form both need to mint a
# code; this is the ONE generator both import, so they can never drift into
# two different code shapes or two different collision-handling strategies.
#
# Codes are "word-word-word-NN" -- three short words plus a two-digit number,
# e.g. "beech-falcon-quill-85" (the design spec's prose: "three readable
# words + digits"). With 60 words this is 60 x 60 x 60 x 100 = 21,600,000
# possible codes, vs. 360,000 for the two-word shape -- 60x harder to guess,
# which matters because every guessed code costs Jon real API credits, and
# still short enough to read aloud or type off a phone.
WORDLIST = [
    "raptor", "quill", "cedar", "otter", "birch", "heron", "maple", "finch",
    "elm", "osprey", "fir", "lark", "pine", "swift", "yew", "plover", "ash",
    "crane", "willow", "vole", "spruce", "wren", "alder", "kite", "hazel",
    "falcon", "poplar", "grouse", "beech", "sparrow", "aspen", "raven",
    "hemlock", "condor", "juniper", "harrier", "cypress", "kestrel", "linden",
    "merlin", "walnut", "peregrine", "hickory", "gannet", "sycamore", "ibis",
    "dogwood", "puffin", "chestnut", "curlew", "magnolia", "tern", "rowan",
    "grebe", "sequoia", "shrike", "larch", "warbler",
]


def generate_code(existing: set[str] | None = None) -> str:
    """Mint a random word-word-word-NN code, retrying on collision against
    `existing` (the caller passes the current set of minted codes -- this
    function never touches the database itself, same separation as the rest
    of this module's plain functions)."""
    existing = existing or set()
    for _ in range(50):
        word1 = secrets.choice(WORDLIST)
        word2 = secrets.choice(WORDLIST)
        word3 = secrets.choice(WORDLIST)
        digits = f"{secrets.randbelow(100):02d}"
        code = f"{word1}-{word2}-{word3}-{digits}"
        if code not in existing:
            return code
    raise RuntimeError("could not generate a unique code after 50 attempts")


def create_code(db_path: Path, code: str, label: str, max_queries: int | None = 25,
                 notes: str = "") -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO codes (code, label, created_at, max_queries, revoked_at, notes) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (code, label, _now(), max_queries, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_code_by_value(db_path: Path, code: str) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM codes WHERE code = ?", (code,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def get_code_by_id(db_path: Path, code_id: int) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM codes WHERE id = ?", (code_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def list_codes(db_path: Path) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM codes ORDER BY id DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def revoke_code(db_path: Path, code_id: int) -> bool:
    conn = _connect(db_path)
    try:
        cur = conn.execute("UPDATE codes SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                            (_now(), code_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def log_event(db_path: Path, *, code_id: int | None, kind: str, ip_hash: str | None,
              question: str = "", answered: bool | None = None, input_tokens: int = 0,
              output_tokens: int = 0, cost_usd: float = 0.0, latency_ms: int = 0) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered, "
            "input_tokens, output_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code_id, _now(), kind, ip_hash, question,
             None if answered is None else int(answered),
             input_tokens, output_tokens, cost_usd, latency_ms),
        )
        conn.commit()
    finally:
        conn.close()


def count_queries(db_path: Path, code_id: int) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE code_id = ? AND kind = 'query'", (code_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["n"]


def code_stats(db_path: Path, code_id: int) -> dict:
    conn = _connect(db_path)
    try:
        unlocks = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE code_id = ? AND kind = 'unlock'", (code_id,)
        ).fetchone()["n"]
        agg = conn.execute(
            "SELECT COUNT(*) AS n, MIN(ts) AS first_seen, MAX(ts) AS last_seen, "
            "COALESCE(SUM(cost_usd), 0.0) AS total_cost FROM events "
            "WHERE code_id = ? AND kind = 'query'", (code_id,)
        ).fetchone()
    finally:
        conn.close()
    return {
        "unlocks": unlocks, "queries": agg["n"], "first_seen": agg["first_seen"],
        "last_seen": agg["last_seen"], "total_cost": agg["total_cost"],
    }


def events_for_code(db_path: Path, code_id: int) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE code_id = ? AND kind = 'query' ORDER BY id DESC",
            (code_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def daily_spend(db_path: Path, day: str) -> float:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM events "
            "WHERE kind = 'query' AND ts LIKE ?", (f"{day}%",)
        ).fetchone()
    finally:
        conn.close()
    return row["total"]


# Admin-approved rotating example pool (task-1-brief.md). Same
# per-op-connection pattern as the codes/events functions above: `_connect`
# opens a fresh connection, writes call `conn.commit()` explicitly, and
# `finally: conn.close()` always runs.

def normalize_question(text: str) -> str:
    """Case and whitespace folding, and nothing else.

    Must stay identical to the API's `_normalize_question`, which builds the
    answer-cache key -- so identical, in fact, that `main._normalize_question`
    is just a thin wrapper around this function rather than a second copy of
    the same three lines. If these two ever disagreed about what "the same
    question" means, an approved example could be warmed under one key and
    looked up under another: a permanent silent cache miss, which shows up as
    a slow paid click rather than as an error.
    """
    return " ".join(text.strip().lower().split())


def approve_example(db_path: Path, question: str, *,
                     source_event_id: int | None = None) -> int:
    """Approve `question` as an example. Returns its row id.

    Idempotent on the normalized form: approving the same question twice
    returns the existing row rather than creating a second one that would
    share its cache key.
    """
    norm = normalize_question(question)
    conn = _connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM examples WHERE norm = ?", (norm,)).fetchone()
        if existing is not None:
            return int(existing["id"])
        cur = conn.execute(
            "INSERT INTO examples (question, norm, source_event_id, approved_at) "
            "VALUES (?, ?, ?, ?)",
            (question.strip(), norm, source_event_id, _now()))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def reject_candidate(db_path: Path, question: str) -> None:
    """Remember a no, so the candidate list stops offering it."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO example_rejects (norm, rejected_at) VALUES (?, ?)",
            (normalize_question(question), _now()))
        conn.commit()
    finally:
        conn.close()


def mark_warmed(db_path: Path, example_id: int) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE examples SET warmed_at = ? WHERE id = ?",
                     (_now(), example_id))
        conn.commit()
    finally:
        conn.close()


def retire_example(db_path: Path, example_id: int) -> None:
    """Soft delete. The row stays so 'this was public once' stays answerable."""
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE examples SET retired_at = ? WHERE id = ?",
                     (_now(), example_id))
        conn.commit()
    finally:
        conn.close()


def list_examples(db_path: Path, *, include_retired: bool = False) -> list[dict]:
    sql = "SELECT * FROM examples"
    if not include_retired:
        sql += " WHERE retired_at IS NULL"
    sql += " ORDER BY approved_at DESC"
    conn = _connect(db_path)
    try:
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def pool_for_frontend(db_path: Path) -> list[str]:
    """Exactly the questions safe to show: approved, warmed, not retired.

    Anything else is either a paid slow click or a question Jon pulled.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT question FROM examples "
            "WHERE warmed_at IS NOT NULL AND retired_at IS NULL "
            "ORDER BY id").fetchall()
    finally:
        conn.close()
    return [r["question"] for r in rows]


def candidate_questions(db_path: Path, *, limit: int = 60) -> list[dict]:
    """Questions visitors asked that are neither approved nor rejected yet,
    most-asked first. Each carries `question`, `times_asked`, `answered_rate`
    and `event_id` (the most recent event it came from, for provenance).

    No content filtering happens here on purpose. Length or keyword rules
    would be a machine deciding what is safe to publish, and the entire point
    of this feature is that a person decides that.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, question, answered FROM events "
            "WHERE kind = 'query' AND question IS NOT NULL AND question <> '' "
            "ORDER BY id").fetchall()
        taken = {r["norm"] for r in conn.execute("SELECT norm FROM examples")}
        taken |= {r["norm"] for r in conn.execute("SELECT norm FROM example_rejects")}
    finally:
        conn.close()

    grouped: dict[str, dict] = {}
    for row in rows:
        norm = normalize_question(row["question"])
        if norm in taken:
            continue
        entry = grouped.setdefault(norm, {
            "question": row["question"].strip(),
            "times_asked": 0, "_answered": 0, "event_id": row["id"],
        })
        entry["times_asked"] += 1
        entry["_answered"] += 1 if row["answered"] else 0
        entry["event_id"] = row["id"]

    out = []
    for entry in grouped.values():
        entry["answered_rate"] = entry["_answered"] / entry["times_asked"]
        entry.pop("_answered")
        out.append(entry)
    out.sort(key=lambda e: (-e["times_asked"], e["question"]))
    return out[:limit]

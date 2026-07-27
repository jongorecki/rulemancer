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


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute(_CODES_SCHEMA)
    conn.execute(_EVENTS_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

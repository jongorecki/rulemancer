"""L3: the SQLite cache layer (docs/plan-l3-sqlite-caches.md).

Replaces the load-whole-dict/dump-whole-dict pickle/JSON caches with one
SQLite file (WAL mode) so concurrent processes can't corrupt them -- the
whole-file dumps could never promise that; INSERT OR REPLACE per row can.

One table per cache, schema `(key TEXT PRIMARY KEY, value BLOB)`. Every
get/put opens and closes its own connection -- cross-process safety is the
entire point, and per-op connections are the simplest shape that's actually
correct. Microseconds matter nowhere in this codebase; the expensive thing
is always the API call the cache avoids. No module-level dict layer -- that
memo is exactly what goes stale when another process writes.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "cache.db"
# src/rulesagent/cache.py -> repo root is three ".parent"s up.

_BUSY_TIMEOUT_MS = 5000


class KVCache:
    """A single (key TEXT PRIMARY KEY, value BLOB) table in DEFAULT_DB (or
    `db_path`, for tests). Callers own their own key/value encoding -- this
    class only ever sees bytes in, bytes (or None) out."""

    def __init__(self, table: str, db_path: Path = DEFAULT_DB) -> None:
        self.table = table
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{self.table}" (key TEXT PRIMARY KEY, value BLOB)'
        )
        return conn

    def get(self, key: str) -> bytes | None:
        conn = self._connect()
        try:
            row = conn.execute(
                f'SELECT value FROM "{self.table}" WHERE key = ?', (key,)
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row is not None else None

    def put(self, key: str, value: bytes) -> None:
        conn = self._connect()
        try:
            conn.execute(
                f'INSERT OR REPLACE INTO "{self.table}" (key, value) VALUES (?, ?)',
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

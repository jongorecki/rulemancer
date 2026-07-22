# Tests for the L3 SQLite cache layer (docs/plan-l3-sqlite-caches.md).
#
# Written before rulesagent.cache exists (TDD) -- watch these fail on
# `ModuleNotFoundError: No module named 'rulesagent.cache'` first, then
# implement KVCache to make them pass.
#
# Every test gets its own tmp_path db file, so nothing here ever touches the
# real data/cache.db.

import sqlite3

import pytest

from rulesagent.cache import KVCache


def test_get_put_round_trip(tmp_path):
    db = tmp_path / "cache.db"
    cache = KVCache("widgets", db_path=db)

    cache.put("k1", b"hello")

    assert cache.get("k1") == b"hello"


def test_missing_key_returns_none(tmp_path):
    db = tmp_path / "cache.db"
    cache = KVCache("widgets", db_path=db)

    assert cache.get("does-not-exist") is None


def test_put_upserts_overwrite_not_duplicate(tmp_path):
    db = tmp_path / "cache.db"
    cache = KVCache("widgets", db_path=db)

    cache.put("k1", b"first")
    cache.put("k1", b"second")

    assert cache.get("k1") == b"second"
    # INSERT OR REPLACE must not leave a duplicate row behind.
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM widgets").fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_separate_tables_do_not_leak_keys(tmp_path):
    db = tmp_path / "cache.db"
    a = KVCache("table_a", db_path=db)
    b = KVCache("table_b", db_path=db)

    a.put("shared-key", b"a-value")

    assert b.get("shared-key") is None


def test_wal_mode_is_set_on_the_db_file(tmp_path):
    db = tmp_path / "cache.db"
    cache = KVCache("widgets", db_path=db)
    cache.get("anything")  # any op opens a connection and sets the pragma

    conn = sqlite3.connect(db)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == "wal"


def test_persists_across_separate_kvcache_instances(tmp_path):
    """Nothing is held in a module-level dict or a long-lived connection --
    a brand new KVCache pointed at the same file must see prior writes."""
    db = tmp_path / "cache.db"
    KVCache("widgets", db_path=db).put("k1", b"value")

    reopened = KVCache("widgets", db_path=db)

    assert reopened.get("k1") == b"value"


def test_get_and_put_each_open_and_close_their_own_connection(tmp_path, monkeypatch):
    """Cross-process safety is the entire point (per the plan): every get/put
    must open a short-lived connection rather than reuse one held on the
    instance, so no connection outlives a single operation."""
    db = tmp_path / "cache.db"
    cache = KVCache("widgets", db_path=db)

    real_connect = sqlite3.connect
    opened = []

    def spy_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", spy_connect)

    opened.clear()
    cache.put("a", b"1")
    put_opened = list(opened)

    opened.clear()
    cache.get("a")
    get_opened = list(opened)

    assert len(put_opened) >= 1
    assert len(get_opened) >= 1
    # Every connection opened by the op must already be closed by the time
    # the call returns -- no lingering handle held on the instance.
    for conn in put_opened + get_opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_missing_parent_directory_is_created(tmp_path):
    db = tmp_path / "nested" / "dir" / "cache.db"
    cache = KVCache("widgets", db_path=db)

    cache.put("k1", b"value")

    assert db.exists()
    assert cache.get("k1") == b"value"

"""L3: migrate the five legacy pickle/JSON caches into data/cache.db
(docs/plan-l3-sqlite-caches.md).

For each legacy file that exists: read it, INSERT OR REPLACE every entry
into its SQLite table (via KVCache -- same key/value encoding the live call
sites now use), print `<table>: N entries migrated`. Then verify: row count
== source count, plus SAMPLE_N random keys per table round-trip byte-equal
to what was just written. Prints PASS/FAIL per table.

Idempotent -- safe to re-run (INSERT OR REPLACE). Legacy files are LEFT IN
PLACE; the new code just stops reading them -- delete manually once the
swap has soaked.

Run: uv run python scripts/migrate_caches_to_sqlite.py
"""

import json
import pickle
import random
import sqlite3
import sys
from pathlib import Path

from rulesagent.cache import KVCache

REPO = Path(__file__).parent.parent
PARSED_DIR = REPO / "data" / "parsed"

SAMPLE_N = 5


# --- per-legacy-cache loaders: legacy file(s) -> {str_key: bytes_value} ----
# Same key/value encoding the live call sites use post-swap (rewrite.py,
# tools/scryfall.py, tools/ruling_retrieval.py, evals/run_eval.py), so a
# migrated row reads back identically to one written by the new code.


def _load_rewrite() -> dict[str, bytes]:
    path = PARSED_DIR / "rewrite_cache.pkl"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = pickle.load(f)
    out = {}
    for (model, prompt_version, n, question), (queries, clarification) in data.items():
        key = json.dumps([model, prompt_version, n, question])
        out[key] = json.dumps([queries, clarification]).encode("utf-8")
    return out


def _load_scryfall() -> dict[str, bytes]:
    path = PARSED_DIR / "scryfall_cache.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {ref: json.dumps(entry, ensure_ascii=False).encode("utf-8") for ref, entry in data.items()}


def _load_ruling_emb() -> dict[str, bytes]:
    path = PARSED_DIR / "ruling_emb_cache.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {rid: json.dumps(vec).encode("utf-8") for rid, vec in data.items()}


def _load_query_emb() -> dict[str, bytes]:
    # One shared `query_emb` table (per the plan's fixed table set); glob
    # picks up every query_emb_{model}.pkl that ever existed on disk, in
    # case more than one model's file is present.
    out: dict[str, bytes] = {}
    for path in sorted(PARSED_DIR.glob("query_emb_*.pkl")):
        with open(path, "rb") as f:
            data = pickle.load(f)
        for text, vec in data.items():
            out[text] = pickle.dumps(vec)
    return out


def _load_rerank() -> dict[str, bytes]:
    path = PARSED_DIR / "rerank_cache.pkl"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = pickle.load(f)
    out = {}
    for (model, query, pool_ids), order in data.items():
        key = json.dumps([model, query, list(pool_ids)])
        out[key] = pickle.dumps(order)
    return out


CACHES: list[tuple[str, "callable"]] = [
    ("rewrite", _load_rewrite),
    ("scryfall", _load_scryfall),
    ("ruling_emb", _load_ruling_emb),
    ("query_emb", _load_query_emb),
    ("rerank", _load_rerank),
]


def migrate() -> dict[str, dict[str, bytes]]:
    """Write every legacy entry into its table. Returns {table: loaded_data}
    so verify() can check against exactly what was just written, without
    re-reading the legacy files a second time."""
    loaded: dict[str, dict[str, bytes]] = {}
    for table, loader in CACHES:
        data = loader()
        loaded[table] = data
        if not data:
            print(f"{table}: 0 entries migrated (no legacy source found)")
            continue
        cache = KVCache(table)
        for key, value in data.items():
            cache.put(key, value)
        print(f"{table}: {len(data)} entries migrated")
    return loaded


def verify(loaded: dict[str, dict[str, bytes]]) -> bool:
    """Row count == source count, plus SAMPLE_N random keys per table
    round-trip byte-equal. Prints PASS/FAIL per table; returns True iff
    every table with a legacy source passed."""
    all_ok = True
    for table, data in loaded.items():
        if not data:
            print(f"{table}: PASS (no legacy source, nothing to verify)")
            continue
        cache = KVCache(table)
        conn = sqlite3.connect(cache.db_path)
        try:
            row_count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        finally:
            conn.close()
        count_ok = row_count == len(data)

        sample_keys = random.sample(list(data.keys()), min(SAMPLE_N, len(data)))
        sample_ok = all(cache.get(k) == data[k] for k in sample_keys)

        ok = count_ok and sample_ok
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(
            f"{table}: {status} (rows {row_count}/{len(data)}, "
            f"{len(sample_keys)} sample keys byte-equal: {sample_ok})"
        )
    return all_ok


def main() -> int:
    loaded = migrate()
    print()
    ok = verify(loaded)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

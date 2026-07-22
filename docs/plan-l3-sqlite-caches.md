# Plan — L3: SQLite cache layer (deploy blocker #1)

Status: DRAFT for Jon's review (Rule 0). No implementation until approved.
Implementation is blocked anyway until the OpenRouter arm run exits — the
remaining arms launch fresh python processes that would import edited code.

## Goal

Replace every load-whole-dict/dump-whole-dict cache with SQLite (stdlib,
WAL), so concurrent processes can't corrupt them. This closes the
single-writer restriction (the triple rewrite-cache EOFError), unblocks
public deployment (L5.1), and migrates the queries/feedback JSONL stubs to
real tables (L6).

## Cache inventory (verified against the code, 2026-07-22)

| # | File | Module | Key | Value | Format |
|---|---|---|---|---|---|
| 1 | data/parsed/rewrite_cache.pkl | retrieve/rewrite.py | tuple (model, PROMPT_VERSION, n, question) | (queries, clarification) | pickle |
| 2 | data/parsed/scryfall_cache.json | tools/scryfall.py | ref token string | {fetched_at, schema, card} | json |
| 3 | data/parsed/ruling_emb_cache.json | tools/ruling_retrieval.py | "oracle_id#index" | list[float] | json |
| 4 | data/parsed/query_emb_{model}.pkl | evals/run_eval.py | query/rewrite string | np vector | pickle |
| 5 | data/parsed/rerank_cache.pkl | evals/run_eval.py | (model, query, pool ids) | reranked order | pickle |

Plus the two JSONL logs from api/main.py `_log_row`: queries.jsonl,
feedback.jsonl → become tables (L6 said "a queries table in the same
SQLite file L3 introduces").

**Scope note for Jon:** the roadmap named caches 1-4. #5 (rerank_cache) is
the same corruptible shape and lives one line away from #4, so this plan
includes it — flag if you'd rather keep it out.

## Design

### One file, one class

`data/cache.db` (gitignored, sits next to the pkl/json it replaces; on
Fly.io it lives on the volume). New module `src/rulesagent/cache.py`:

```python
class KVCache:
    def __init__(self, table: str, db_path: Path = DEFAULT_DB): ...
    def get(self, key: str) -> bytes | None: ...
    def put(self, key: str, value: bytes) -> None: ...
```

- One table per cache (`rewrite`, `scryfall`, `ruling_emb`, `query_emb`,
  `rerank`), schema `(key TEXT PRIMARY KEY, value BLOB)`.
- `PRAGMA journal_mode=WAL` set at first open; `busy_timeout=5000`.
- **Every get/put opens a short-lived connection.** Cross-process safety is
  the entire point; per-op connections are the simplest correct shape and
  microseconds matter nowhere in this codebase (the expensive thing is
  always the API call the cache avoids).
- `put` = `INSERT OR REPLACE` — idempotent, atomic per row. No partial
  writes possible, which is exactly what the whole-file dumps couldn't
  promise.

### Key/value encoding per call site

- rewrite: key `json.dumps([model, PROMPT_VERSION, n, question])`; value
  `json.dumps([queries, clarification])`. (Tuple keys can't be TEXT
  directly; JSON-list is deterministic and readable.)
- scryfall: key = ref token as-is; value = the existing entry dict as JSON
  (fetched_at + schema + card stay INSIDE the value — TTL and schema-bump
  logic unchanged).
- ruling_emb: key as-is; value JSON list[float] (matches today's format).
- query_emb / rerank: key = string / JSON-list; value = `pickle.dumps` of
  the numpy vector / order (numpy doesn't round-trip JSON cleanly; pickle
  inside a BLOB is fine — it's our own data).

### The module-level `_cache` dicts are DELETED, not kept as a layer

Today's in-process memo is exactly what goes stale when another process
writes — keeping it would preserve the bug behind a faster path. SQLite
reads are microseconds; nothing here is hot enough to need a memo. (If a
profile ever disagrees, add a read-through memo WITH a generation check —
not before.)

### What does NOT change

- Public signatures: `rewrite_query()`, `get_card()`, `select_rulings()`,
  `query_vectors()`, `cached_rerank()` — storage swaps, contracts don't.
- Cache-key semantics (PROMPT_VERSION in the rewrite key, CARD_CACHE_SCHEMA
  + TTL inside the scryfall value, never-cache-the-fallback in rewrite).
- Eval reproducibility: a frozen cache read returns the same bytes.

### api/main.py changes

- `_log_row` → `INSERT` into `queries` / `feedback` tables (columns
  matching today's row dicts; feedback joined by request_id). Keep the
  best-effort try/except — telemetry must never break an answer.
- **The `_lock` STAYS for now.** After this slice it no longer guards cache
  integrity, but it still guards the `agent.last_*` recorder reads (another
  request could overwrite them between answer() and the reads). Rescope the
  comment; the real fix (answer() returns a result object instead of
  recorder attributes) is its own small slice, not smuggled into this one.

## Migration

`scripts/migrate_caches_to_sqlite.py`:
1. For each legacy file that exists: read it, `INSERT OR REPLACE` every
   entry, print `<table>: N entries migrated`.
2. Verify: row count == source count, plus 5 random keys per table
   round-trip byte-equal. Print PASS/FAIL per table.
3. Idempotent — safe to re-run. Legacy files are LEFT IN PLACE (the new
   code just stops reading them); delete manually once the swap has soaked.

## Verification (the pass/fail gates)

1. Full test suite green (tests monkeypatch the seams, not the storage —
   expect little churn; any test reaching the old paths gets updated).
2. Migration script PASS output on the real caches.
3. Concurrency smoke: two parallel processes doing interleaved get/put on
   the same table (small script, ~200 ops each) — no exception, no lost
   writes, db intact (`PRAGMA integrity_check`).
4. Two parallel `/answer` requests (test port, NOT 8000) — both correct.
5. Retrieval eval before/after on frozen caches — byte-identical summary
   (proves reads are faithful).
6. `grep` — zero remaining reads of the five legacy cache paths.

## Out of scope

Streaming, rate limiting, CORS tightening, Dockerfile (all later L5 steps);
the last_* recorder refactor; deleting the legacy files.

# Plan — Scryfall local bulk snapshot (replaces live lookups) (DRAFT, pending Jon's review)

**Jon's rulings so far (2026-07-23):**
- **Fuzzy threshold: start at 90**, with the explicit expectation it gets tuned against real queries.
- **Ambiguity guard: ship it, but measure how often it fires.** Jon's hypothesis: near-ties will be rare enough that forced test scenarios are needed to exercise it at all. So every guard trigger gets logged/counted (same debug surface as fuzzy fallbacks), and the TDD suite's forced near-tie case (§7 test 5) is the primary exercise path. Revisit the margin only if real-world data shows it firing.
- **Calendar window: refresh starting 8 days before each set's `released_at` through 21 days after.** Grounding (Jon): prerelease is 7 days before the release date, and all cards are spoiled by prerelease — so day −8 catches the full spoiler set with a day of margin.
- Still open: `no_refresh` keep-vs-remove, admin endpoint shape, licensing sign-off (see Open questions).

Working Rule 0 artifact. No build until Jon signs off. **Sequencing: do NOT
start this until the prompt-v3 A/B (docs/plan-prompt-tuning.md §4, queued as
HANDOFF-development.md item #1) concludes.** That A/B assumes card data is a
fixed input across arms; swapping the card-data source mid-flight would
confound its results.

## 0. Why (grounded in the actual incident)

`get_card()` today (`src/rulesagent/tools/scryfall.py`) does two live network
things at answer time: a fuzzy name lookup (`/cards/named?fuzzy=`) or an
oracle_id search, plus a live fetch of the card's `rulings_uri`. Both are
cached (`data/cache.db` `scryfall` table, 7-day TTL) but a cache **miss**
still means a live call sits on the answer path — a real transient-failure
class (network blip, Scryfall hiccup, rate limit).

`docs/HANDOFF-development.md` (queue item #3) has this open: *"c012 finding:
NO multi-card bug in build_prompt — suspect `get_card()` fuzzy-match or
stale scryfall cache entry (fresh tracing session needed)."* This plan
doesn't prove that was the exact cause of c012's miss, but it **removes the
whole suspect class**: no live fuzzy match, no live-refetch race, no
network call of any kind at answer time. If Jon wants forensic certainty
on the historical incident specifically, that's still a separate call —
this plan fixes the mechanism, not the postmortem.

Also relevant, running in parallel: `docs/plan-q029-empty-answer-guard.md`
(not yet written as of this draft, queued in HANDOFF item #3) reportedly
includes a c012 **observability** slice — logging unresolved `[card]` refs
so a miss is visible instead of silent. That logging is orthogonal to this
plan (it's about surfacing "no card found," this plan is about "how card
lookup works") and should survive this change unchanged; this plan's local
lookup path should feed that same observability hook rather than replace it.

## 1. Verified, live, 2026-07-23 (not from memory)

**Bulk-data metadata** (`GET https://api.scryfall.com/bulk-data`):

| file | bytes (uncompressed) | ~size | updated_at (verified) |
|---|---|---|---|
| oracle_cards | 179,897,393 | ~172 MB | 2026-07-23 09:02 UTC |
| rulings | 25,850,549 | ~24.7 MB | 2026-07-23 09:00 UTC |

Both `updated_at` timestamps were within the hour of the live check —
confirms Scryfall's own docs page (`scryfall.com/docs/api/bulk-data`,
fetched live): *"Bulk data is only collected once every 12-24 hours... URLs
for files change their timestamp each day"* **even when content hasn't
changed**, and *"Updates to gameplay data (such as card names, Oracle text,
mana costs, etc) are much less frequent... downloading card data once per
week or right after set releases would most likely be sufficient."* This is
the direct evidence behind Jon's ruling that a timestamp change alone must
not trigger a download — the timestamp bumps daily regardless of whether
any card actually changed.

**Rate limits** (`scryfall.com/docs/api/rate-limits`, fetched live):
`/cards/search`, `/cards/named`, `/cards/random`, `/cards/collection` are
2/sec; bulk file *origins* (`*.scryfall.io`) have **no rate limit** — bulk
downloads aren't rate-limited the way point lookups are, but should still
be infrequent per the guidance above (courtesy, not a hard limit).

**Licensing** (`scryfall.com/docs/api`, fetched live — Wizards Fan Content
Policy pass-through): *"You may not simply repackage, republish, or proxy
Scryfall data. Your software must create additional value for end-users."*
Also: *"We encourage you to cache the data you download from Scryfall or
process it locally in your own system, at least for 24 hours... If you need
to rapidly look up card names... you must use the bulk data files."* Storing
oracle text + rulings locally to ground RAG answers (with our own rules
retrieval + relevance-selected rulings on top) reads as "additional value,"
not a bare repackage — but this is my read of their wording, not a legal
opinion. **Flagging for Jon's explicit sign-off before the future public
Fly.io deploy**, since that's the point this actually matters (a private
local file for a solo dev is clearly fine either way).

**Fuzzy-match corpus size** (`GET /catalog/card-names`, small metadata call,
~670 KB response, not a bulk file): **34,786** distinct English card names,
verified live. Confirms local fuzzy matching against this corpus is a
sub-second, in-memory operation — no reason it needs a network call.

**Set-release calendar** (`GET https://api.scryfall.com/sets`, verified
live): each set object has `released_at` (date), `set_type`, `digital`.
There is **no "prerelease date" or "spoiler start" field** — only the
official release date. Confirmed live (fields on a returned set object):
`card_count, code, digital, foil_only, icon_svg_uri, id, name,
nonfoil_only, object, parent_set_code, released_at, scryfall_uri,
search_uri, set_type, uri`. As of this check, the next non-token/digital
set is **hob (The Hobbit)**, `released_at = 2026-08-14` — about 3 weeks
out, a live worked example for the window logic below.

## 2. What the code does today (read, not assumed)

- **`tools/scryfall.py` `get_card(ref, no_refresh=False)`**: `ref` is either
  a UUID (routed to `/cards/search?q=oracleid:`) or a name string (routed
  to `/cards/named?fuzzy=`, Scryfall's own fuzzy match — typo-tolerant,
  live). Cached in `data/cache.db`'s `scryfall` table (`KVCache`, L3
  pattern), value = `{fetched_at, schema=2, card}`, `TTL_DAYS=7`. Rulings
  are fetched live per-card via `rulings_uri` inside `_card_from_json` and
  folded into the same cache entry — **not cached independently**.
- **`generate/answer.py` `RulesAgent.answer()`**: `parse_card_refs()` pulls
  `[Card Name]` / `[uuid]` tokens; `all_refs` collects this turn's + history
  turns' tokens, case-insensitively deduped; each ref goes through
  `get_card(ref, no_refresh=self.card_no_refresh)`; `None` results are
  silently dropped from `cards` (line 391's walrus-filtered comprehension).
  `no_refresh` today means "accept any cached entry regardless of TTL age" —
  the eval-reproducibility freeze mode.
- **`tools/ruling_retrieval.py`**: reads `card.rulings` (already populated
  by `get_card`) and does per-card relevance selection against the question,
  cached separately (`ruling_emb` table, keyed `oracle_id#index`, frozen).
  **This module needs zero changes** — it only ever touches
  `Card.rulings`, however that list got populated.
- **Frontend autocomplete flow** (`frontend/index.html` `autocompleteApi` →
  `GET /cards/autocomplete?q=`, proxied in `api/main.py` to Scryfall's own
  `/cards/autocomplete`): Scryfall's autocomplete endpoint returns **a bare
  list of name strings** (`{"data": [...]}`), nothing else. The frontend's
  `selectAC()` inserts `"[" + name + "] "` into the composer. **Confirmed:
  the frontend does NOT and cannot today supply `oracle_id`** — Scryfall's
  autocomplete simply doesn't return it. `[uuid]` tokens are still
  supported by `get_card`'s `_UUID_RE` branch (for history turns or other
  callers), so "prefer oracle_id when available" is already true at the
  resolution layer; there's just no live path producing one today. A local
  autocomplete built off our own name index *could* return `oracle_id`
  per-suggestion cheaply — noted as a natural future win, **explicitly out
  of scope here** (autocomplete redesign is a listed non-goal, §8).

## 3. Data model

**New file: `data/scryfall.db`** — a separate SQLite file from
`data/cache.db`, not a new table inside it. Reasoning: `cache.db`'s tables
are ephemeral, per-key, TTL-governed caches written continuously by live
traffic (L3's whole design point). This store is the opposite shape — a
**versioned snapshot** that gets replaced wholesale on refresh and must
never be read half-written. Keeping it in its own file makes "atomic swap"
trivial (`os.replace()` one file) without touching anything a running
request is concurrently reading/writing in `cache.db`. Mirrors the L3
philosophy (`docs/plan-l3-sqlite-caches.md`: "per-op connections... simplest
shape that's actually correct") one level up, at the file granularity.

```sql
CREATE TABLE cards (
  oracle_id  TEXT PRIMARY KEY,
  name       TEXT NOT NULL,       -- Scryfall's display name ("Front // Back" etc.)
  name_norm  TEXT NOT NULL,       -- casefold + strip, for case-insensitive exact match
  card_json  TEXT NOT NULL        -- the fields Card(...) needs, same shape scryfall.py builds today
);
CREATE UNIQUE INDEX idx_cards_name_norm ON cards(name_norm);

CREATE TABLE rulings (
  oracle_id  TEXT NOT NULL,
  idx        INTEGER NOT NULL,
  comment    TEXT NOT NULL,
  PRIMARY KEY (oracle_id, idx)
);
CREATE INDEX idx_rulings_oracle ON rulings(oracle_id);

CREATE TABLE meta (
  key TEXT PRIMARY KEY, value TEXT
  -- oracle_cards_updated_at, rulings_updated_at, imported_at, row_counts,
  -- last_auto_refresh_window, last_staleness_check — the store's own
  -- provenance, so the staleness check (§5) has something to compare against.
);
```

**Size estimate (honest hedge):** `Card` (`contracts.py`) only needs
name/oracle_text/type_line/mana_cost/oracle_id/layout/mana_value/colors/
color_identity/faces — a field-projected import (dropping legalities,
prices, images, purchase/related URIs, set metadata Scryfall's raw object
carries) should land well under the 172 MB raw oracle_cards figure. I'm
**not** guessing a number here beyond that direction — the import script
(§5) should print the actual `data/scryfall.db` size on its first real run
and that becomes the real answer, not a pre-build estimate.

**Fuzzy-match corpus:** the `name_norm` index doubles as the candidate list
for local fuzzy matching (34,786 distinct names, verified §1) — no separate
structure needed, `SELECT name FROM cards` is instant at this scale.

## 4. Lookup path

```
get_card(ref) →
  1. ref is a UUID  → SELECT ... WHERE oracle_id = ref            (exact, oracle_id)
  2. else           → SELECT ... WHERE name_norm = normalize(ref) (exact, case-normalized name)
  3. miss on both    → LOCAL fuzzy match against name_norm corpus (fallback)
  4. still nothing  → return None (miss)
```

**Fuzzy fallback (step 3):** local only, never network, per Jon's ruling.
Proposed library: **rapidfuzz** (new dependency — not currently in
`pyproject.toml`; MIT-licensed, C-extension, fast; stdlib `difflib` is
noticeably slower at this corpus size and has worse real-world MTG-name
behavior). Scorer: `rapidfuzz.process.extractOne` over the name corpus,
`WRatio` or `token_sort_ratio` (handles "Lightning bolt" vs "Lightning
Bolt" reordering-tolerant typos better than a plain ratio).

**Wrong-card safeguards** (the risk Jon flagged explicitly):
- High threshold (proposed starting point: score ≥ 90/100 — needs
  calibrating against real typo/partial-name queries before shipping, not
  guessed and frozen).
- **Ambiguity guard:** if the top-2 candidates' scores are within a small
  margin of each other (e.g., ≤3 points), treat it as **too ambiguous** and
  return a miss rather than guess — silently picking the wrong one of two
  near-tied cards is worse than an honest miss.
- **Always flagged, never silent:** every fuzzy-fallback hit is logged and
  surfaced in the API's `debug` payload — proposed shape: extend `Debug`
  (`api/main.py`) with `fuzzy_fallbacks: list[dict]`, each
  `{ref, matched_name, oracle_id, score}`. Mirrors the existing
  `last_crossref` / `selected_ruling_ids` debug-surfacing pattern already
  in the codebase (`answer.py` `last_crossref`, read by `main.py`). Module
  needs a side-channel (like the existing `_last_request_at` module state
  in `scryfall.py`) since `get_card`'s signature/return type stay
  unchanged (§6).

**True miss:** unchanged behavior — `get_card` returns `None`, `answer.py`'s
`all_refs` comprehension already drops `None`s silently. The **visibility**
of an unresolved ref is the parallel q029 plan's job (§0), not duplicated
here.

## 5. Refresh

**Import script** — `scripts/refresh_scryfall_bulk.py`, same shape as the
existing `scripts/migrate_caches_to_sqlite.py`:
1. Fetch `/bulk-data` metadata (small call).
2. Download `oracle_cards` + `rulings` (the real, infrequent network cost).
3. Transform: filter `lang == "en"` (per `scryfall-notes.md`'s existing
   intent), project to the fields `Card` needs, build `cards` + `rulings`
   + `meta` tables into a **temp file** (`data/scryfall.db.tmp` or a temp
   dir on the same volume as `data/`).
4. Sanity gate before swap: row counts sane (roughly matches the catalog's
   34,786-name ballpark, not zero, not wildly off), spot-check a handful of
   known oracle_ids round-trip.
5. **Atomic swap:** `os.replace(tmp, data/scryfall.db)` — atomic on POSIX
   and on Windows/NTFS when source and dest share a volume (same `data/`
   dir — must not cross volumes). A running server's next `get_card` call
   just opens whichever file exists at that instant; no reader ever sees a
   half-written store.
6. **Failure behavior:** any exception before step 5 aborts loudly (PASS/
   FAIL summary, matching the migration script's convention) and **the old
   `data/scryfall.db` is untouched** — the whole point of building in a
   temp path first.

**Three distinct triggers** (per Jon's spec — these are separate
mechanisms, not one):

1. **Set-calendar auto-refresh** (real download+swap, but gated to when
   content plausibly changed): Scryfall's `/sets` has no prerelease date
   (§1), so this is a **heuristic window** around each set's `released_at`
   — proposed: start ~14 days before (covers typical prerelease/spoiler
   lead time; a few days early just means a not-yet-spoiled card falls
   through to the fuzzy-fallback safety net a little longer, not harmful)
   through ~21 days after (Jon's "cover a few weeks post-release for errata
   churn"). Within an active window, refresh on a light cadence (proposed:
   every 3-4 days, not daily — 172 MB once a day for 5 straight weeks is
   more than the observed content-change rate justifies) rather than every
   day of the window. **Exact day-counts are a proposal, not a verified
   requirement — flagging for Jon to adjust at review.**
2. **Manual trigger (Jon):** `uv run python scripts/refresh_scryfall_bulk.py`
   (CLI) does a real refresh unconditionally, any time. A token-protected
   admin endpoint (`POST /admin/scryfall/refresh`, `Authorization: Bearer
   <ADMIN_TOKEN>` compared against an env var, matching the existing
   `os.environ.get(...)` key pattern in `openrouter_backend.py`/`rerank.py`)
   calls the **same shared import function** — not a duplicated code path
   — likely via FastAPI `BackgroundTasks` given the download size, with a
   `GET /admin/scryfall/status` to poll (design choice, flagged for
   review). **No admin UI** — that's explicitly out of scope (§8).
3. **Daily freshness check (cheap, metadata-only, never downloads):** a
   `GET /bulk-data` call (small) compares Scryfall's `updated_at` against
   `meta.oracle_cards_updated_at`/`rulings_updated_at` and logs/exposes a
   staleness signal — **this never itself triggers a download**, per Jon's
   ruling and the verified §1 evidence that the timestamp changes daily
   regardless of content. It exists so an out-of-band change (say, a
   correction issued outside any set-release window) doesn't go silently
   unnoticed between calendar windows.

## 6. Migration / compatibility

- **`get_card(ref, no_refresh=False)` keeps its signature and return type**
  (`Card | None`) — same L3 precedent ("Public signatures... storage swaps,
  contracts don't"), so `answer.py`'s call site (`get_card(ref,
  no_refresh=self.card_no_refresh)`) needs **zero changes**.
- **`no_refresh`'s meaning changes:** today it means "accept any cached
  entry regardless of TTL age" (an eval-freeze mode). With a local snapshot,
  a single `get_card` call never triggers a download regardless of this
  flag — refresh is fully decoupled (§5). So `no_refresh` becomes inert
  for this path. **Flagging for Jon:** keep it as a documented no-op (zero
  call-site churn) vs. remove it (honest, but touches every caller/test) —
  his call.
- **Old `scryfall` table in `data/cache.db`:** stop reading/writing it;
  leave the rows in place as dead data, matching the L3 migration script's
  own precedent ("Legacy files are LEFT IN PLACE... delete manually once
  the swap has soaked"). No urgency to drop it.
- **`ruling_emb` cache (unchanged, but one honest caveat):** still keyed
  `oracle_id#index`, still frozen. If a future rulings refresh **inserts a
  ruling ahead of an existing one** (shifting index positions for that
  oracle_id), the embedding cache would serve a stale vector against the
  wrong text. This risk **already existed** under the live 7-day-TTL cache
  (same key scheme) — this plan doesn't introduce it, just carries it
  forward. Not solved here; noted for awareness.
- **Eval harness:** frozen-cache eval reproducibility gets **stronger**,
  not weaker — a local snapshot can't change mid-request the way a live
  TTL cache theoretically could (benign race noted in today's docstring).
  Must ship **after** the current prompt-v3 A/B concludes (§ header) so it
  doesn't confound in-flight results by changing the card-data input.

## 7. Testing (TDD list)

All against a small **fixture** `scryfall.db` (a handful of known cards),
never the real 172 MB file — matches `tests/test_scryfall.py`'s existing
no-network, `tmp_path`-isolated convention.

1. Exact oracle_id hit.
2. Exact name hit (correct casing).
3. Case-normalized exact hit ("lightning bolt" → Lightning Bolt).
4. Fuzzy fallback hit on a near-miss typo — asserts the result **and** the
   fallback flag/debug entry is set.
5. Fuzzy fallback correctly **refuses** on an ambiguous near-tie (returns
   miss, not a guess).
6. True miss (garbage input, nothing close) → `None`, no fallback flag.
7. Rulings join: a card with N rulings returns them in stable index order,
   matching `ruling_id()`'s existing `oracle_id#index` expectation.
8. Atomic-swap crash safety: simulate a failure mid-import (exception
   before the `os.replace`) → old store file is byte-identical to before;
   a concurrent `get_card` call during the failed attempt still resolves
   correctly against the untouched old store.
9. Staleness-indicator logic: given a stubbed `/bulk-data` response with a
   newer `updated_at` than `meta`, the check reports staleness **without**
   invoking the download path (mock asserts it's never called).

## 8. Risks / regressions

| Risk | Detection / mitigation |
|---|---|
| Import ships a truncated/corrupt store | Row-count + spot-check sanity gate before swap (§5 step 4); failed gate aborts, old store untouched |
| Fuzzy fallback returns the wrong card | High threshold + ambiguity-margin guard (§4) + mandatory debug flag + periodic manual review of a fallback-hit log sample |
| Calendar window under/over-fires (misses a real spoiler wave, or refreshes needlessly) | Window bounds are a tunable proposal (§5), not hardcoded science — revisit against real set-release cadence after a season |
| Two refresh triggers race (calendar + manual same moment) | Shared import function + a simple "refresh in progress" guard (file lock or `meta` flag); second trigger becomes a no-op/queued rather than a concurrent double-write |
| `os.replace` not atomic if tmp/dest cross volumes | Build the tmp file inside `data/` itself, never `/tmp` or another drive |
| `ruling_emb` cache drift on index-shifting rulings updates | Pre-existing limitation (§6), not newly introduced; noted, not solved |
| Licensing read is wrong for the future public deploy | Cited Scryfall's actual wording (§1) but it's not a legal opinion — explicit go/no-go flagged for Jon before Fly.io ships this |

## 9. Non-goals

- **No admin panel UI.** Token-protected endpoint + CLI only, per Jon's
  explicit "real admin panel is later."
- **No autocomplete redesign.** The `@`-picker keeps proxying Scryfall's
  live `/cards/autocomplete` exactly as today; a local, oracle_id-carrying
  autocomplete is a natural future extension (noted §2) but not this plan.
- **No prompt/retrieval/generation changes.** `Card` contract, prompt
  formatting, ruling mini-RAG selection logic (`ruling_retrieval.py`) are
  untouched — this plan only changes **where card/ruling data comes from**,
  never how it's used once resolved.
- **No price/image data, no non-English cards** — matches today's scope
  (`Card` contract doesn't use prices/images; `lang == "en"` filter is
  already the stated intent in `scryfall-notes.md`).

## 10. Considered and rejected

- **Local exact-name miss falls back to a remote (live) fuzzy call as a
  last resort.** Rejected by Jon's explicit ruling — the whole point is
  zero network calls at answer time; a "local-first, remote-fallback"
  design would still leave the transient-failure class in place for every
  local miss, undermining the c012 rationale (§0).
- **Daily `updated_at`-changed → auto-download.** Rejected: verified live
  (§1) that Scryfall's bulk timestamps change roughly daily **regardless**
  of whether any card actually changed ("collected once every 12-24
  hours... URLs change their timestamp each day"). A naive timestamp
  trigger would download ~172 MB daily for no reason and make the
  staleness signal meaningless (it would fire constantly).
- **Load the whole 172 MB JSON into a module-level dict at process start.**
  Rejected: repeats the exact whole-file-in-RAM anti-pattern L3 just
  eliminated for the request caches (`docs/plan-l3-sqlite-caches.md`); adds
  multi-second parse time to every process/worker boot; gives no indexed
  lookup; multiple Fly.io workers would each hold a redundant full copy in
  RAM. SQLite (indexed, shared file, WAL-capable) is the established
  pattern here for a reason.
- **One shared table inside the existing `data/cache.db`.** Rejected in
  favor of a dedicated `data/scryfall.db` (§3) specifically so a refresh
  can be a single atomic whole-file swap without touching the concurrently
  read/written request caches, and so the two very different lifecycles
  (ephemeral per-key cache vs. versioned bulk snapshot) don't get conflated
  in one file.

## Open questions for Jon (review gate)

1. Fuzzy-match threshold + ambiguity margin (§4) — proposed starting
   values, need calibrating against real query examples before shipping.
2. Calendar-window day-counts and in-window refresh cadence (§5) — proposed
   numbers, not verified against real-world spoiler timing.
3. `no_refresh` parameter — keep as a documented no-op, or remove (§6)?
4. Admin refresh endpoint shape — background task + status-poll, or
   synchronous (§5)? Sign-off on `ADMIN_TOKEN` env-var pattern.
5. Licensing read for the future public Fly.io deploy (§1, §8) — explicit
   go/no-go before that deploy step, independent of this plan's approval.
6. `data/scryfall.db` real on-disk size — only knowable after the import
   script's first real run; is an estimate needed sooner for Fly.io volume
   sizing?

### Critical files referenced throughout
- `src/rulesagent/tools/scryfall.py`
- `src/rulesagent/generate/answer.py`
- `src/rulesagent/tools/ruling_retrieval.py`
- `src/rulesagent/cache.py`
- `src/rulesagent/api/main.py`
- `scripts/migrate_caches_to_sqlite.py` (pattern precedent)
- `docs/plan-l3-sqlite-caches.md`, `docs/scryfall-notes.md`,
  `docs/plan-rulings-on-demand.md`, `docs/plan-prompt-tuning.md`

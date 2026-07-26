# Plan — Backend API for the frontend (DRAFT, pending Jon's review)

Working Rule 0 artifact. No code until Jon reviews. This scopes the seam between
Jon's Claude-Design frontend and the `RulesAgent` engine.

## Purpose

Expose `RulesAgent` over HTTP so the frontend can POST a question and render the
answer. FastAPI (the pinned stack; `src/rulesagent/api/main.py` exists in the
skeleton but was never built). The API is a THIN wrapper over `RulesAgent` --
no new RAG logic lives here.

## The response contract is the crux (frontend-driven)

A bare `Answer{text, citations, answered}` is enough to *function*, but a good
rules-bot UI wants more than rule NUMBERS -- it wants to render the cited rule
TEXT, the card(s), and optionally how the answer was reached. Proposed shape:

```
POST /answer  { "question": "...[Card Name]..." }  ->
{
  "answer":    str,            # the prose
  "answered":  bool,           # false => show the "couldn't ground it" state
  "citations": [ {"id": "702.85a", "kind": "rule",   "text": "..."},
                 {"id": "Prowess", "kind": "glossary","text": "..."},
                 {"id": "Fork",    "kind": "card",    "text": null} ],
  "cards":     [ {"name": "Fork", "oracle_id": "...", "mana_cost": "{R}{R}",
                  "type_line": "Instant", "oracle_text": "...",
                  "rulings_used": ["..."]} ],   # only the mini-RAG-selected rulings
  "debug":     { "rewrites": [...], "retrieved_rules": [...],
                 "selected_ruling_ids": {...} }   # optional transparency panel
}
```

To fill this the API resolves citation ids to text via a `chunk_map` (rule id ->
chunk.text) built at startup, and reads the card data + selected rulings off the
agent. That needs one small `RulesAgent` addition: record `last_cards` (the
resolved cards used), alongside the existing `last_ruling_selection` /
`last_rewritten`. Card **images** aren't in our `Card` model -- the frontend can
fetch those from Scryfall by name/oracle_id, or we add `image_uri` to `Card`
(decision below).

## Second endpoint: card autocomplete (for the @-picker)

The frontend's `@`-triggered card picker needs suggestions. `GET
/cards/autocomplete?q=gray` -> `["Gray Merchant of Asphodel", ...]`. Two ways:
proxy Scryfall's `/cards/autocomplete`, or complete against a local card-name
index (faster, offline, needs the bulk names file). Proxying Scryfall is the
smaller build; local is the deferred nicety from scryfall-notes.md.

## The real technical risk: cache-race under concurrency

The scryfall / ruling-embedding / rewrite / query-embedding caches all
load-whole-dict then dump-whole-dict, so **two concurrent requests that both
write a cache clobber each other** (already a known bug, benign in single-process
evals). A web server serving concurrent requests WILL hit this. Options:

- **(a) single worker + an async lock** around the cache-writing paths -- the
  smallest fix, fine for a low-traffic demo.
- **(b) make the caches atomic / per-key** -- the proper fix (the deferred tech
  debt), needed for real concurrency.
- **(c) pre-warm + freeze** caches read-only in prod -- no writes, but an
  uncached card fails to enrich.

Lean: (a) for the demo, with (b) written down as the upgrade. This is the one
place the API can't just wrap the engine and ignore what's underneath.

## Streaming

Non-streaming first: the generator uses `messages.parse` (structured output),
which doesn't stream cleanly, and the frontend can show a loading state for the
few-second latency (rewrite + retrieval + generation). Token streaming is a
separate mode (stream prose, attach citations after) -- deferred unless the
frontend wants it now.

## Config / freshness

A live API wants FRESH Scryfall data (`card_no_refresh=False`) so newly-issued
rulings show, accepting a live fetch for uncached cards. The frozen `no_refresh`
mode is for eval reproducibility, not prod.

## Cost / abuse (only if public)

Every `/answer` spends real money: Anthropic (rewrite + generation) + Voyage
(embeds). A PUBLIC endpoint is uncapped paid-API exposure. If public, it needs
rate-limiting / a daily cap / light auth. If the demo is private or runs behind
your control, this is moot. **Decision: public demo or private?** -- it drives
this whole section.

## Startup / ops

Load the VectorStore pickle + build the `chunk_map` (parse CR + chunk) ONCE at
startup; one shared `RulesAgent`. Keys from `.env`. CORS for the frontend origin.
Health check at `GET /health`.

## Decisions (made 2026-07-22 — Jon)

1. **Enriched response** (the shape above: cited rule/glossary text + card data +
   optional debug). Needs `RulesAgent` to record `last_cards` and `last_retrieved`
   (it already records `last_rewritten` / `last_ruling_selection`).
2. **Card images: frontend pulls from Scryfall** using the name/oracle_id the API
   returns -- so NO backend image field and no cache-schema bump. (Trivial to add
   `image_uri` to the response later if the frontend would rather not round-trip.)
3. **Private demo** -- no rate-limiting/auth/cost controls in v1.
4. **Autocomplete: build now**, proxying Scryfall's `/cards/autocomplete` (people,
   Jon included, won't hand-type card names correctly without it).
5. **Non-streaming v1** -- loading state on the frontend covers the latency;
   token streaming deferred.
6. **Cache-race: single worker + a lock** around the cache-writing path for the
   demo; the atomic-per-key cache fix stays the written-down upgrade for real
   concurrency.

## Build checklist (v1)

- `RulesAgent`: record `last_cards`, `last_retrieved` (small additions).
- `api/main.py`: FastAPI app; startup loads VectorStore + builds `chunk_map`
  (parse + chunk) once, instantiates one `RulesAgent`; CORS for the frontend
  origin; a lock serializing `/answer`.
- `POST /answer` -> enriched response (resolve citations via `chunk_map`, cards
  via `last_cards`, debug via `last_retrieved` / `last_rewritten` /
  `last_ruling_selection`).
- `GET /cards/autocomplete?q=` -> proxy Scryfall.
- `GET /health`.
- Add `fastapi` + `uvicorn` deps if not present.

## Scope / not now

- Deployment target (where it runs) is separate from this scoping.
- No new retrieval/generation logic -- the API only wraps `RulesAgent` and
  resolves ids to text.

# Rulemancer API

Thin FastAPI wrapper over `RulesAgent` (`src/rulesagent/api/main.py`). Full
machine-readable spec: [`openapi.json`](openapi.json). Design + decisions:
[`plan-api.md`](plan-api.md).

## Run — one command

```bash
uv run python run.py
```

That's the whole thing: one process serves the API **and** the frontend
(`frontend/` is mounted as static files on the app) and opens your browser at
http://127.0.0.1:8000. Pass a port as the first argument to use another one;
set `RULESMANCER_NO_BROWSER=1` to skip the auto-open. First load waits a few
seconds while the vector store loads.

Interactive docs are served automatically once it's up:

- **Swagger UI** — http://localhost:8000/docs (try requests in the browser)
- **ReDoc** — http://localhost:8000/redoc
- **OpenAPI JSON** — http://localhost:8000/openapi.json

(The frontend can still be hosted separately if you ever want that — it calls
same-origin when served over http, and `window.RULESMANCER_API` overrides the
API base.)

## Endpoints

### `POST /answer`
Body: `{ "question": "...[Card Name]..." }` — the `[brackets]` mark cards.

Returns:

| field | meaning |
|---|---|
| `answer` | the prose answer |
| `answered` | `false` when the rules didn't cover it (the groundedness guard) |
| `citations[]` | `{ id, kind: rule\|glossary\|card, text }` — rule/glossary carry resolved CR text; card entries have `text: null` (see `cards`) |
| `cards[]` | `{ name, oracle_id, mana_cost, type_line, oracle_text, rulings_used }` — only the rulings the mini-RAG selected are included |
| `debug` | `{ rewrites, retrieved_rules, selected_ruling_ids }` — optional transparency |

Card **images** aren't returned — the frontend fetches them from Scryfall using
`oracle_id` / `name`.

### `GET /cards/autocomplete?q=gray`
`{ "suggestions": ["Gray Merchant of Asphodel", ...] }` — proxies Scryfall for
the frontend's `@`-picker. Needs ≥2 chars.

### `GET /health`
`{ "status": "ok", "ready": true }` — `ready` flips true once the vector store
has loaded.

## Limits (v1, private demo)

- **Single worker only.** A lock serializes `/answer` so the on-disk caches
  can't clobber. Real concurrency needs the atomic-cache fix (deferred).
- **Non-streaming.** `/answer` takes a few seconds; the frontend shows a loading
  state. Token streaming is deferred.
- **No auth / rate limiting** — private demo. Every call spends Anthropic +
  Voyage credits, so keep it private until those controls exist.

## Regenerating the spec

`docs/openapi.json` is generated from the app:

```bash
uv run python -c "import json,pathlib; from rulesagent.api.main import app; pathlib.Path('docs/openapi.json').write_text(json.dumps(app.openapi(), indent=2))"
```

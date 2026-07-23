# Plan — L5 deploy track: private demo → public Fly.io link

Rule 0. DESIGN ONLY, no code yet. Turns the L5 bullet list in
docs/plan-limitations-and-deploy.md and HANDOFF-development.md's "Deploy
track (L5)" queue item into a sequenced, independently-shippable set of
slices. L1/L3 are already shipped (see HANDOFF state) and aren't repeated
here. Fly.io is the settled host (Jon, 2026-07-22) — HF Spaces was
considered and dropped (sleep-on-idle wrong for sharing with testers).

## 0. Ground truth as of 2026-07-23 (read from the code, not memory)

- **Streaming: does not exist.** `POST /answer` (src/rulesagent/api/main.py)
  is one synchronous JSON response. answer.py's own comment confirms the
  Anthropic call is non-streaming and flags a real constraint: raising
  `max_tokens` past 16384 trips "the SDK's non-streaming 10-minute-timeout
  guard." Streaming is a **new slice**, not a flip of an existing flag.
- **CORS is wide open today:** `allow_origins=["*"]` (main.py), with a
  code comment "private demo; tighten to the frontend origin if it goes
  public." That comment is this slice's spec.
- **No rate limiting, no budget breaker, no kill switch anywhere.** Grepped
  the codebase — nothing exists. `/answer` calls `agent.answer()`
  unconditionally on every request.
- **No Dockerfile, no fly.toml, no .dockerignore.** All new.
- **`/health` already exists and is exactly what Fly wants:**
  `{"status": "ok", "ready": bool}`, ready flips true once the vector store
  loads at startup. No new endpoint needed for the health check slice.
- **The corpus IS fully materialized on disk today, and it's all
  gitignored** (`.gitignore`: `data/raw/`, `data/parsed/`, `data/cache.db*`).
  `data/parsed/vector_voyage-4-large.pkl` is a pickled `{model, chunks,
  embeddings}` dict — `chunks` carries every `Chunk.text`/`embed_text`
  string, i.e. **the full Comprehensive Rules text sits in that one file**,
  not just vectors. This is the exact object the redistribution concern is
  about. Since it's gitignored it's not IN git, but it IS present on disk
  locally — a naive `COPY . .` Dockerfile would bake it into an image layer
  regardless of git status. `.dockerignore` has to exclude it explicitly;
  git status alone doesn't protect the image.
- **Card/ruling data has nothing baked in today either** — `tools/scryfall.py`
  hits the live Scryfall API per-request and caches results in `cache.db`
  (an L3 SQLite cache, not a bulk snapshot). The local-bulk snapshot
  (docs/plan-scryfall-local-bulk.md) is a separate, not-yet-implemented
  slice — today's deploy has nothing extra to protect on the card side
  beyond the CR text.
- **Path resolution is already REPO-relative, which matters for the volume
  design below:** `main.py`'s `REPO = Path(__file__).parent.parent.parent.parent`
  and `cache.py`'s `DEFAULT_DB = Path(__file__).parent.parent.parent /
  "data" / "cache.db"` both resolve from `src/rulesagent/...`'s location,
  not a hardcoded path. If the image's WORKDIR is `/app` and the source
  tree is copied to `/app/src/...`, then `REPO` resolves to `/app` and
  `data/` resolves to `/app/data` — with **zero source changes**, mounting
  a Fly volume at `/app/data` makes every existing path (vector store,
  cache.db, chunk_map) point at the volume automatically.
- **Two of the three keys are load-bearing at runtime; the third isn't yet.**
  `VOYAGE_API_KEY` (embeddings) and `ANTHROPIC_API_KEY` (generation,
  `claude-sonnet-5` pinned) are read by their SDKs' default env vars and are
  required to boot/answer. `OPENROUTER_API_KEY` is used only by the eval
  harness (`.env.example`: "The app itself never uses it") — not a runtime
  secret until L2's generator call ships an OpenRouter-backed path. Still
  worth reserving the Fly secret slot now so L2 doesn't need a deploy step
  of its own later.
- **Fly.io basics, verified live (2026-07-23) against fly.io/docs:**
  `fly.toml` needs `app`, `primary_region`, `[build] dockerfile = "..."`,
  `[http_service]` (`internal_port`, `force_https`, `auto_stop_machines`,
  `auto_start_machines`, `min_machines_running` — the scale-to-zero knobs),
  a health check (`[[http_service.checks]]` or top-level `[checks.*]`,
  `path = "/health"`), and `[[mounts]]` (`source`, `destination`) for a
  persistent volume. Secrets set via `fly secrets set` are injected as env
  vars at Machine boot, NOT available at build time — consistent with
  keeping keys out of the image. The app must bind `0.0.0.0`, not
  `127.0.0.1` (run.py's default) — the container's entrypoint is a direct
  `uvicorn` invocation, not `run.py` (which also has stale-port-killing and
  browser-auto-open logic that's meaningless/wrong inside a container).
  Sources: fly.io/docs/reference/configuration/, fly.io/docs/apps/secrets/,
  fly.io/docs/languages-and-frameworks/dockerfile/.

## 1. Streaming

**The fix:** switch Anthropic's client call in answer.py's generation step
to streaming (`client.messages.stream(...)`), and add a **new** endpoint —
`POST /answer/stream` (SSE) — alongside the existing `POST /answer`, rather
than changing `/answer`'s response shape in place.

**Why additive, not in-place:** `/answer`'s structured `AnswerResponse`
(citations, cards, debug, tldr, suggested_followups — all resolved
server-side AFTER generation) is exactly the contract the eval harness and
grading tooling read today. Streaming naturally wants to send raw answer
TEXT progressively and resolve the structured fields (citations lookup,
card enrichment, telemetry log) once at the end — a genuinely different
response shape. Keeping `/answer` byte-stable protects every existing eval
number; the frontend switches to the new endpoint, `/answer` stays for
anything (evals, curl, `/docs` "try it out") that wants one JSON blob.

**What streams vs what resolves at the end:** stream the `answer.text`
token-by-token as SSE `data:` events; once the stream closes, emit one
final `data:` event carrying the full structured payload (tldr, answered,
citations, cards, suggested_followups, request_id, debug) — same shape as
`AnswerResponse` today, just delivered last instead of all at once. The
frontend renders the streamed text live, then swaps in citations/cards/tldr
tabs when the final event lands. Telemetry logging (`_log_row("queries",
...)`) moves to after the stream completes, same as today.

**Interplay with the budget breaker (#2):** the budget/rate check MUST run
BEFORE the stream opens (a rejected request should never start burning
tokens), so its guard function sits at the top of the new endpoint handler
exactly where it'll sit in `/answer` too — one guard function shared by
both endpoints, not duplicated logic.

**Verify:** existing `/answer` behavior and tests untouched (confirm no
test currently pins the JSON shape as a golden fixture that would need
updating for the new field, if any); manual browser check that streamed
text renders progressively and the final structured payload lands correctly
(citations drawer, tldr/full tabs, suggested-followup pills); a slow-network
throttle test in devtools to confirm the UX actually reads as "responsive"
and not just "technically streaming."

## 2. Abuse / cost protection (the most important slice before going public)

A public LLM endpoint with no cap is a financial-risk hole — this is the
one slice that has to be correct, not just present, before the URL is ever
shared.

**Three independent controls, all fail-closed, all checked before any
Anthropic/Voyage call is made:**

1. **Per-IP rate limit.** In-process, no new dependency: a dict of
   `ip -> deque[timestamp]`, guarded by a lock (the codebase already has
   this pattern — `main.py`'s `_lock`). Default: N answers/hour per IP
   (env var `RATE_LIMIT_PER_IP_PER_HOUR`, Jon picks N — see open questions).
   IP source: Fly terminates TLS at the edge and forwards the real client
   IP via `Fly-Client-IP` (or `X-Forwarded-For`) — use that header, not
   `request.client.host`, which would be Fly's internal proxy IP.
   Exceeding it returns HTTP 429 with a plain "slow down, try again in an
   hour" message. **Scope limitation, stated plainly:** this is correct for
   a single Fly Machine (the assumed deploy shape — see §5's scale-to-zero
   discussion). It stops being a true GLOBAL per-IP limit the moment the
   app runs on more than one Machine at once, since each Machine has its
   own in-memory dict. Acceptable for a hobby-scale demo; a shared store
   (Redis, or a `rate_limit` SQLite table in the same `cache.db`) is the
   fix if that ever changes — not needed now.
2. **Global daily budget breaker.** A new `budget_daily` table in the same
   `data/cache.db` (mirrors the L3 pattern — one more table, no new
   infrastructure): `(date TEXT PRIMARY KEY, spent_usd REAL, request_count
   INTEGER)`. Before calling the generator, check today's UTC-date row
   against `DAILY_BUDGET_CAP_USD` (env var, Jon's number — open question);
   if at/over cap, return 429 "demo budget hit for today, come back
   tomorrow" WITHOUT calling Anthropic/Voyage at all (fail fast — the
   whole point is not spending the tokens). After a successful call,
   increment the row using the ACTUAL usage the Anthropic SDK response
   returns (`response.usage.input_tokens` / `output_tokens` × the pinned
   model's per-token price, looked up live at implementation time — never
   from memory, per CLAUDE.md's pricing rule) rather than a flat guess per
   call — more correct, and the plumbing is a two-line addition next to
   the existing telemetry `_log_row` call.
3. **Kill switch.** A one-row `settings` table in `cache.db`
   (`key TEXT PRIMARY KEY, value TEXT`) checked at the very top of the
   answer path. Deliberately NOT an env var: Fly secrets/env changes need a
   Machine restart to take effect, but Jon wants to be able to flip the
   demo off instantly without a redeploy. A tiny one-line script (`UPDATE
   settings SET value='off' WHERE key='demo_enabled'`, run via `fly ssh
   console` + the Python REPL, or a `flyctl ssh sftp` one-liner) flips it
   live. When off, `/answer` and `/answer/stream` return a static "demo
   paused" response immediately — no LLM call, no rate/budget check even
   needed at that point.

**Order the guard function checks them:** kill switch → per-IP rate limit
→ daily budget. Cheapest/most totalizing check first (kill switch is a
single SQLite read), most specific last.

**Frontend note (small, in-scope here, not a new feature):** the chat UI
needs to handle a 429 gracefully (show the friendly message instead of the
existing "couldn't reach the rules engine" error state, which currently
assumes a network failure, not a deliberate throttle).

**Considered — `slowapi`:** a real FastAPI rate-limiting library exists and
was the HANDOFF's own suggestion ("slowapi or a tiny middleware"). Rejected
in favor of hand-rolled: the in-process dict is ~15 lines, needs no new
dependency, and the budget-breaker and kill-switch pieces need custom
SQLite logic regardless — a mixed slowapi+custom design is more moving
parts than one small guard module covering all three.

**Verify:** a scripted burst of requests from one fake IP confirms the
Nth+1 request 429s; a manually-inserted `budget_daily` row at/over cap
confirms the very next request 429s without an API call (check via a
network-request/log inspection, not just the response code — confirm
Anthropic/Voyage were never actually hit); flipping the kill-switch row
confirms an immediate refusal with no restart; all three checked against
BOTH `/answer` and `/answer/stream` once streaming ships.

## 3. CORS

**The fix:** `allow_origins=["*"]` → the deployed origin(s) only — the
Fly app's own URL (e.g. `https://rulemancer.fly.dev`) plus `http://
localhost:8000`/`http://127.0.0.1:8000` kept in the list so Jon's local
dev flow (`run.py`) still works unchanged. One-line change, already
flagged by the existing code comment.

**Why it matters even though the frontend is same-origin:** `main.py`
mounts the frontend from the SAME FastAPI process (`StaticFiles` at `/`),
so the shipped frontend never actually needs cross-origin CORS to talk to
its own API. The wildcard's real exposure is that ANY other website can
point a browser `fetch()` at the live `/answer` endpoint from a visitor's
browser and it'll be honored — free cost-control leakage that has nothing
to do with the frontend's own needs. Locking it down is pure risk
reduction with zero functional cost.

**Verify:** local dev (`run.py`) still loads and answers from
`localhost:8000` after the change; a manual cross-origin `fetch()` from an
unrelated origin against the deployed URL is rejected by the browser
(devtools console shows the CORS error) once deployed.

## 4. Dockerfile — and how the corpus gets onto the host without redistribution

**Image contents (uv-based, single stage):** Python 3.12 base, `uv sync
--frozen` (pyproject.toml pins `requires-python = ">=3.12"`; `uv.lock` is
already committed per plan-packaging.md's hygiene pass), then `COPY
src/ frontend/` explicitly — never `COPY . .`. `WORKDIR /app` so the
existing REPO-relative path logic (§0) resolves correctly without any
source change.

**`.dockerignore` (new file) — the actual enforcement mechanism:**
excludes everything `.gitignore` excludes (`data/raw/`, `data/parsed/`,
`data/cache.db*`, `.env`, `.venv/`, `tmp/`) PLUS anything `.gitignore`
doesn't need to care about but a Docker build context still would pick up
(`.git/`, `evals/answers/`, `data/parsed/*.html` grading artifacts, `.pytest_cache/`).
Docker does NOT read `.gitignore` — git-ignored status protects the repo,
not the image; the `.dockerignore` is the only thing that actually keeps
`vector_voyage-4-large.pkl` (full CR text, per §0) and `data/raw/*.txt`
out of any image layer. This is the whole redistribution fix, mechanically:
**the corpus is never in the build context in the first place.**

**Getting the corpus onto the running host, then — chosen approach: a Fly
volume mounted at `/app/data`, seeded once, reused across every redeploy.**

Because the volume is a Fly-managed disk separate from the image, it
persists across `fly deploy`s — the corpus is built/loaded once, not
re-baked into every image push. Two ways to get it onto the volume the
first time; recommending the simpler one to ship first:

- **(a) Manual one-time seed (recommended default, zero new code):** Jon
  runs the existing local pipeline exactly as today (`build_vector_indexes.py`
  reads `data/raw/MagicCompRules ....txt`, writes `data/parsed/
  vector_voyage-4-large.pkl`), then pushes the resulting `data/raw/` and
  `data/parsed/` onto the attached volume once (`flyctl ssh sftp shell` or
  attach-and-`scp` to a throwaway Machine). No new source code — the
  existing local build process IS the host build process, just executed by
  Jon once instead of automatically at boot. `data/cache.db` doesn't need
  seeding at all; `cache.py`'s `KVCache._connect()` already does `mkdir
  (parents=True, exist_ok=True)` + `CREATE TABLE IF NOT EXISTS`, so it
  self-creates empty on the volume the first time anything writes to it.
- **(b) Boot-time auto-build (nicer, but new code — a follow-on, not
  blocking first deploy):** an idempotent bootstrap step before `uvicorn`
  starts: if `/app/data/parsed/vector_voyage-4-large.pkl` is already on the
  volume, skip; if not, fetch the current CR text from its official source
  and run the same parse → chunk → embed pipeline that (a) runs locally
  today. This needs a NEW small fetch script (no such script exists yet —
  today's `data/raw/*.txt` was placed manually) and a verified-live, stable
  URL for the CR text, which hasn't been checked in this pass. Flagging
  this as a real follow-on rather than designing it fully now: it's
  genuinely nicer (redeploy-proof, no manual step if the volume is ever
  recreated) but adds a new failure surface (network fetch at boot) that
  the manual seed avoids entirely for a first public launch.

**Why NOT bake the index into the image (rejected, both reasons matter):**
(1) redistribution — a public image with the corpus in a layer IS
"repackag[ing]/republish[ing]" in a way the manual/volume approach isn't,
since nothing served publicly (the image) carries the raw text; (2)
practical — a chunking or CR-revision change would require a full image
rebuild+repush instead of just updating the volume's contents, and image
size grows with every embedding model added.

**Fail loud, not silent, if the volume is misconfigured:** if
`vector_voyage-4-large.pkl` is missing at boot, the app should refuse to
serve rather than silently answer with an empty/stale index — `main.py`'s
`lifespan()` already calls `VectorStore.load(...)` unconditionally, which
already raises (`FileNotFoundError`) if the file's absent; that's the
correct behavior already, just needs to be true on the deployed volume
path too. No source change needed here, just a deploy-time check.

**Verify:** `docker build` locally, then `docker run --rm <image> find
/app/data` (or inspect layers with `docker history`/`dive`) confirms zero
CR text/pickle content in the image; a fresh Fly volume with the manually
seeded `data/` boots and `/health` returns `ready: true`; deleting the
volume and re-seeding reproduces the same behavior (confirms nothing
image-side is silently caching a copy).

## 5. Fly.io config

**fly.toml shape** (verified live against fly.io/docs, §0):

```toml
app = "rulemancer"                # Jon's call on the actual name
primary_region = "ord"            # Chicago — closest to Jon; open question, see §13

[build]
dockerfile = "Dockerfile"

[http_service]
internal_port = 8080
force_https = true
auto_stop_machines = "stop"       # or "off" for always-on — open question, §13
auto_start_machines = true
min_machines_running = 0          # 1 for always-on

[[http_service.checks]]
path = "/health"
interval = "30s"
grace_period = "10s"

[[mounts]]
source = "rulemancer_data"
destination = "/app/data"

[[vm]]
size = "shared-cpu-1x"
memory = "512MB"
```

- **Health check:** points at the existing `/health`, which already
  reports `ready` false until the vector store loads — Fly's grace period
  needs to cover cold-start load time (measure once deployed; local vector
  store load is fast, but first-boot-after-scale-to-zero on a small Fly VM
  is unmeasured — flag as a thing to time after first deploy, not assumed).
- **Scale-to-zero vs always-on (Jon's call, §13):** scale-to-zero
  (`min_machines_running = 0`) is free-er but means the first visitor after
  idle eats a cold start (vector store reload from the volume, a few
  seconds based on local load times — unmeasured on Fly's actual disk
  speed). Always-on (`min_machines_running = 1`) costs a small continuous
  fee but every visitor gets a warm demo. Given the per-IP/budget guards
  already cap worst-case spend, always-on's incremental COMPUTE cost (not
  LLM cost) is the only new number to weigh — Jon's call, not a technical
  constraint either way.
- **Memory:** 512MB is a starting guess (numpy matrix over ~3,600×1024
  floats is small — a few tens of MB — plus FastAPI/uvicorn overhead); bump
  if the first deploy OOMs, no reason to over-provision blind.

**Verify:** `fly deploy` succeeds from a clean checkout with the volume
attached; `/health` shows `ready: true` within the grace period; a cold
start after scale-to-zero (if chosen) is timed once, live, and reported —
not assumed.

## 6. Secrets

`fly secrets set VOYAGE_API_KEY=... ANTHROPIC_API_KEY=... OPENROUTER_API_KEY=...`
— all three, even though only the first two are load-bearing today (§0),
so L2's eventual generator call doesn't need its own deploy step. Confirmed
nothing key-bearing is committed: `.env` is gitignored, `.env.example` ships
placeholder text only, and the Dockerfile/`.dockerignore` (§4) exclude
`.env` from the build context the same way they exclude `data/`.

**Verify:** `fly secrets list` shows all three names (values never
echoed); a grep of the git history / working tree for the literal key
strings turns up nothing (spot-check, not exhaustive — the keys were never
typed into a committed file per `.env.example`'s existing discipline).

## 7. Sequencing + interplay with other tracks

**Dependency on Scryfall local-bulk (docs/plan-scryfall-local-bulk.md):**
NONE, blocking. Today's card path hits live Scryfall per-request and
caches in `cache.db` (§0) — that already works standalone on a deployed
host exactly as it does locally, no bulk snapshot required. Local-bulk is
a quality/latency upgrade for LATER, addable to the same volume without
touching the deploy shape.

**Interplay with the SSO track (TODO-SSO.md):** no code overlap today —
there is no admin endpoint yet for SSO to protect (grepped `src/` for
`ADMIN_TOKEN`/`admin`: nothing exists; the local-bulk plan's
background+status-poll admin endpoint is itself not-yet-implemented).
SSO's first protected surface is that future admin endpoint, not the
public anonymous demo — deploying L5 does not gate or get gated by SSO.
The one real sequencing fact (from HANDOFF, not re-litigated here): if
OIDC lands BEFORE this deploy, its localhost callbacks work fine standalone
and don't block anything here; SAML, by its nature, needs a real ACS URL
and can only be tested meaningfully AFTER a live Fly URL exists — so SAML
is post-deploy regardless of which order Jon picks for OIDC. That
OIDC-timing choice is explicitly still open per HANDOFF and isn't this
plan's call to make.

**Recommended slice order:**
1. CORS fix (§3) — trivial, zero risk, do it any time, no reason to wait.
2. Abuse/cost guards (§2) — build and unit-test locally before anything is
   public; this is the one slice that must be verified correct, not just
   present, before a URL is ever shared.
3. Streaming (§1) — independent of guards' existence but the guard-check
   MUST wrap whichever endpoint(s) exist by the time this ships.
4. Dockerfile + `.dockerignore` (§4) — can be built and even deployed to a
   Fly app that Jon simply doesn't share the link for yet, to test the
   volume/boot/health-check plumbing in isolation from "is it safe to be
   public."
5. Fly.io config + secrets (§5, §6) — depends on §4 existing.
6. **Gate: do not share the URL publicly until §2 is verified live on the
   deployed instance**, not just locally — the guard's SQLite tables and
   IP-header handling behave differently once behind Fly's actual edge.
7. Feature shortlist + README (§8) — after the link is live and stable.

## 8. After deploy: feature shortlist + README

- **Feature shortlist:** docs/feature-ideas.md is already Jon-approved
  (clarify-then-escalate, legality chip, misconceptions gallery,
  permalinks, CR-gap flag, donate link, CR auto-update pipeline) — nothing
  new to design here, just the reminder that it's next after the link is
  live, per the existing queue order.
- **README:** docs/plan-packaging.md already has a full, detailed plan
  (structure, the "what I got wrong first" arc, quickstart, attribution
  footer, LICENSE/font decisions already made) — not re-designed here. Per
  this task's ask, its structure already calls for absorbing the six-arm
  graded table, the audit-pipeline story, and the competitive-landscape
  teardown (docs/competitive-landscape.md) into sections 2-3. **Note:** a
  draft `README.md` exists in the repo root already but is deliberately
  uncommitted (HANDOFF-development.md) — the packaging plan's job is to
  bring it up to date with everything shipped since it was drafted (prompt
  v3, the A/B table, telemetry, tldr/followups) and commit it, not start
  from scratch.

## 9. Pre-launch checklist (before the URL is ever shared)

- [ ] Budget breaker verified live: kill switch, per-IP limit, and daily
      cap all tested against the DEPLOYED instance (not just locally).
- [ ] `fly secrets list` shows `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`,
      `OPENROUTER_API_KEY` — none echoed, none in git history.
- [ ] CORS locked to the real Fly origin (+ localhost for dev); wildcard
      confirmed gone from the running config, not just the source.
- [ ] Image inspected (`docker history`/`dive`) — zero CR text or card data
      in any layer.
- [ ] `/health` green with `ready: true` on the deployed Machine.
- [ ] A cold-start timing (if scale-to-zero chosen) has actually been
      measured once, live, and is acceptable UX.

## 10. Risks / regressions

- **Runaway cost is risk #1.** Mitigated by the budget breaker being
  checked BEFORE any paid API call, fail-closed by design (§2). The
  residual risk is a bug in the guard itself (e.g. a race between the
  budget check and the increment under concurrent requests) — worth a
  concurrency smoke test (two simultaneous requests near the cap) as part
  of §2's verification, not just a serial test.
- **In-memory per-IP rate limiting resets on every Machine restart/redeploy**
  and doesn't hold across multiple Machines (§2) — accepted for a
  single-Machine hobby demo; would need a shared store if that changes.
- **Volume/path misconfiguration failing SILENTLY** would be worse than
  failing loudly — mitigated by the existing `VectorStore.load()` already
  raising on a missing file (§4), but worth confirming that failure
  actually surfaces as a crashed/unready Machine (and a red Fly health
  check) rather than a swallowed exception somewhere in `lifespan()`.
- **Cold-start latency on scale-to-zero is unmeasured** — a real UX risk
  if it's worse than expected; the fix (switch to always-on) is cheap and
  reversible, but the number needs to exist before deciding.
- **Streaming's new endpoint duplicates some logic with `/answer`** (citation
  resolution, telemetry logging, card enrichment output shape) — worth a
  shared helper function extracted once both exist, rather than copy-paste
  drift between the two response paths. Flagged for the implementer, not
  designed in detail here.

## 11. Considered and rejected

- **Baking the index into the image** — rejected: redistribution (§4) and
  it turns every corpus/model change into a full image rebuild instead of
  a volume update.
- **HF Spaces** — already rejected in plan-limitations-and-deploy.md
  (Jon, 2026-07-22): sleep-on-idle is wrong for sharing with testers.
  Not revisited here.
- **`slowapi` for rate limiting** — rejected in favor of a hand-rolled
  guard module (§2): the budget-breaker and kill-switch pieces need custom
  SQLite logic regardless, so one small shared module beats a
  slowapi-plus-custom-code split.
- **Redis (or any external store) for rate limiting** — overkill for a
  single-Machine hobby deploy; revisit only if the app ever scales past
  one Machine.
- **Env-var kill switch** — rejected in favor of a `cache.db` settings row
  (§2): env/secret changes need a Fly Machine restart to take effect; Jon
  wants to flip the demo off instantly without a redeploy.

## 12. Non-goals

- **User accounts / login.** Not part of this track. The only future
  authenticated surface is the SSO track's admin endpoint (local-bulk
  refresh), which doesn't exist yet and is scoped entirely separately
  (TODO-SSO.md). The public demo stays anonymous.
- **The eval harness.** Untouched by anything here — evals call
  `RulesAgent.answer()` in-process, never through the HTTP API, so none of
  this (streaming, guards, CORS, Docker) touches eval reproducibility.
- **Scryfall local-bulk.** Separate plan, not a deploy blocker (§7).
- **Horizontal scaling / multi-Machine.** This whole design (in-memory
  rate limiting, a single mounted volume) assumes ONE Fly Machine. Scaling
  out is a real future change, not addressed here.
- **Boot-time auto-fetch-and-build of the corpus (§4's option b).** Noted
  as a nicer follow-on, not designed or blocking for the first public
  launch.

## 13. Open questions for Jon

1. **Fly region** — `ord` (Chicago, closest to Jon) is the default guess
   in §5's fly.toml sketch; confirm or pick another.
2. **Scale-to-zero vs always-on** — cost vs cold-start-UX tradeoff (§5);
   no technical blocker either way once §2's guards are in place.
3. **The daily budget cap number (USD)** — `DAILY_BUDGET_CAP_USD` (§2);
   needs Jon's number, informed by the pinned generator's actual per-call
   cost (measure live at implementation time, not from the earlier ~$0.55-
   0.85/50-run estimate, which was itself flagged as unmeasured).
4. **Per-IP rate limit (requests/hour)** — `RATE_LIMIT_PER_IP_PER_HOUR`
   (§2); a starting default can be proposed at implementation time, but
   it's Jon's number to set.
5. **Manual seed (§4a) vs boot-time auto-build (§4b) for the first
   deploy** — recommending (a) to ship faster with zero new code; confirm
   that's the right tradeoff for a first public launch versus building (b)
   up front.

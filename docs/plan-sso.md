# Plan — SSO track (OIDC, then SAML, then the breakage lab)

**Working Rule 0 artifact. DESIGN ONLY — no source changes in this pass.**
No build until Jon signs off on each slice below (this track ships as three
independently-approved slices, not one big patch — see §0).

**Source of intent:** `TODO-SSO.md` (committed 2026-07-23). **Integration
rulings already on record** (`docs/HANDOFF-development.md` "SSO track ADDED",
`DECISIONS.md` #4 2026-07-23): SSO never gates the anonymous public demo;
its first protected surface is the local-bulk admin refresh endpoint
(`docs/plan-scryfall-local-bulk.md`); the breakage lab is Jon-driven, not
agent-coded; OIDC ships next (pre-deploy, before local-bulk), SAML + the
breakage lab ship after the L5 Fly.io deploy. This plan does not re-litigate
any of that — it designs the how.

## 0. Why three slices, not one

This is a resume-evidence track as much as a feature: the value is in Jon
being able to explain, cold, what each piece does and why it broke. Bundling
OIDC + SAML + the lab into one patch would (a) violate the approved
sequencing — OIDC needs no deployed URL, SAML does — and (b) muddy the
review: an auth diff is high-risk (see §6) and reviewable in one pass only
if it's scoped to one login mechanism at a time. So:

1. **OIDC slice** — ships next, localhost-only, protects the admin endpoint.
2. **SAML slice** — ships after L5 deploy, needs real public URLs for ACS.
3. **Breakage lab + writeup** — ships after SAML, Jon executes it by hand.

Each gets Jon's sign-off independently before its own build starts.

## 1. Verified live, 2026-07-23 (not from memory)

**Authlib's Starlette/FastAPI OIDC pattern** (`docs.authlib.org`, v1.3.1
Starlette client docs, fetched live — the v0.15-era "FastAPI OAuth Client"
page 404s now, confirming the API moved under the general
`starlette_client` docs):

```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    "okta",  # or "entra"
    client_id=...,
    client_secret=...,
    server_metadata_url="https://<tenant>/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
)

# login route
client = oauth.create_client("okta")
return await client.authorize_redirect(request, redirect_uri)

# callback route
client = oauth.create_client("okta")
token = await client.authorize_access_token(request)
userinfo = token["userinfo"]  # Authlib parses + verifies the id_token itself
```

Confirmed live: registration keys off `server_metadata_url` (OIDC
discovery — Authlib fetches the provider's `.well-known` doc itself, no
manual issuer/JWKS wiring needed), `authorize_redirect(request, redirect_uri)`
starts the flow, `authorize_access_token(request)` completes it and hands
back a parsed/verified `userinfo`.

**NEEDS CONFIRMATION AT BUILD (flagged, not verified):** whether Starlette's
`SessionMiddleware` (backed by `itsdangerous`, not currently a dependency —
see §7) is load-bearing for OIDC's `state`/`nonce` round-trip specifically,
or only documented for the OAuth1 request-token case. The fetched docs are
explicit for OAuth1 ("saves the request token in sessions") but don't spell
out the OIDC case in the version fetched. Every real-world Authlib+FastAPI
example I'm aware of does wire `SessionMiddleware` before `oauth.init_app`/
`OAuth()` and it's the mechanism Authlib uses to stash `state`/`nonce`
between the redirect and the callback (there's no other place to put it in
a stateless request cycle) — treat that as the working assumption, but
implementation should smoke-test a login with `SessionMiddleware` **absent**
first to see the actual failure mode before wiring it, so the "why" is
verified firsthand rather than assumed (this doubles as breakage-lab-style
groundwork for the OIDC slice itself).

**SAML SP library choice: `python3-saml`, not `pysaml2`.** Both are viable
(WebSearch, live) but differ in the install story:
- `python3-saml` depends on `python-xmlsec`, which needs the `xmlsec1-dev`
  headers (a real Linux package, not just pip) to build — a genuine install
  consideration on the Fly.io host (Dockerfile needs an apt layer for it,
  same category of concern as any C-extension dependency).
- `pysaml2` shells out to an `xmlsec1` **binary** rather than linking
  `python-xmlsec`, which is arguably a lighter footprint, but its docs
  describe it as WSGI-native with framework adapters needed elsewhere, and
  `python3-saml` is the more commonly cited "the SAML library" for a from-
  scratch Python SP (per the live search results, including community
  discussion of it being "the prevailing wisdom").
- **Choosing `python3-saml`.** Reason: it's the library TODO-SSO.md names
  first, its request/response API (`OneLogin_Saml2_Auth`) maps cleanly onto
  a single FastAPI route pair (`/saml/login`, `/saml/acs`), and the xmlsec
  install cost is a one-time Dockerfile line, not an ongoing tax. Flagging
  for Jon: if the Fly.io image build turns out to fight the xmlsec headers
  (possible on slim base images), `pysaml2` is the documented fallback —
  noted here so a swap mid-slice isn't a surprise if it happens.

**Okta / Entra free-tier OIDC app registration** (grounded in the ordinary,
well-documented developer-tenant flow, not re-fetched live this pass since
TODO-SSO.md already names both as the target IdPs and neither vendor's
dev-tenant terms are in question):
- Both give, per registered app: **issuer / discovery URL**
  (`.well-known/openid-configuration`), **client ID**, **client secret**,
  and a **redirect URI allowlist** you configure per-app.
- Both permit `http://localhost:<port>/...` redirect URIs on a dev/free
  tenant — this is exactly what makes the OIDC slice deployable-free per
  the approved sequencing (§0). Entra's app registration additionally wants
  a platform type set to "Web" (not SPA) for a server-side authorization-
  code flow like Authlib's.
- SAML side (for the later slice) needs the IdP's own **SAML metadata XML**
  (entity ID, SSO URL, signing certificate) imported into the SP config, and
  the SP's metadata (entity ID, **ACS URL**, certificate if signing
  requests) registered back on the IdP — a two-way exchange, per
  TODO-SSO.md's own framing ("metadata exchange, ACS URL, attribute
  mapping"). This needs a real public ACS URL, hence post-deploy (§0).

## 2. Ground truth from the code (read, not assumed)

- **`src/rulesagent/api/main.py`**: today's FastAPI app has **zero auth**.
  No middleware beyond CORS (`allow_origins=["*"]`, explicitly commented
  "private demo; tighten... if it goes public"). Every route (`/answer`,
  `/feedback`, `/health`, `/cards/autocomplete`) is open, and the frontend
  is mounted as static files at `/` with no gate in front of it. **This is
  exactly the surface that must NOT change** — SSO adds new routes and
  wraps ONE new admin route; it must not touch `/answer` or the static
  mount in any way that adds friction for an anonymous visitor.
- **`frontend/index.html`**: confirmed (grep) zero existing auth/login/token
  surface — the only "token" hits are the `@`-picker's unrelated
  `currentAtToken()` text-parsing helper. The chat UI has nothing to wire
  around; SSO is additive, not a retrofit of existing UI.
- **`run.py`**: serves on port 8000 via `uvicorn.run("rulesagent.api.main:app", ...)`.
  Jon runs this himself; **this plan must not require binding or killing
  it** — OIDC dev testing needs its own throwaway port or Jon's own running
  instance, same convention `HANDOFF-development.md` already states for
  browser-pane testing ("test elsewhere").
- **`docs/plan-scryfall-local-bulk.md` §5 "Manual trigger"**: the admin
  refresh endpoint is APPROVED-but-not-yet-built as `POST
  /admin/scryfall/refresh` (background task) + `GET
  /admin/scryfall/status` (poll), gated today by `Authorization: Bearer
  <ADMIN_TOKEN>` compared against an env var — "matching the existing
  `os.environ.get(...)` key pattern in `openrouter_backend.py`/`rerank.py`."
  Confirmed live: `openrouter_backend.py:84` does exactly
  `os.environ.get("OPENROUTER_API_KEY")` — a bare env-var read, no secrets
  manager, consistent with this repo's existing secret-handling convention
  (`.env` + `python-dotenv`, per `HANDOFF-development.md`). **SSO's job is
  to upgrade this bearer-token gate to a real authenticated session**, not
  to invent a new secret-handling pattern.
- **`pyproject.toml`**: no auth-adjacent dependency exists today (no
  `authlib`, `itsdangerous`, `python3-saml`, `pysaml2`). All of these are
  NEW dependencies this track introduces, each flagged where first needed.

## 3. Slice 1 — OIDC (ships next, pre-deploy, localhost only)

**Scope:** log in against Okta, then against Entra, from a route that only
needs `http://127.0.0.1:<port>` — no deployed URL required, matching the
approved sequencing. Protects exactly one thing: the admin refresh endpoint
from `plan-scryfall-local-bulk.md`.

### 3a. New routes (additive to `main.py`, all under an `/admin` or `/auth`
prefix — never touching `/answer`, `/feedback`, `/health`,
`/cards/autocomplete`, or the static mount)

- `GET /auth/login/{provider}` — `provider` in `{"okta", "entra"}`;
  `oauth.create_client(provider).authorize_redirect(request, redirect_uri)`.
- `GET /auth/callback/{provider}` — `authorize_access_token(request)`,
  read `userinfo` (email claim), check against an **allowlist** (see 3c),
  set a session cookie marking the request authenticated, redirect to a
  small `/admin` landing page (new, minimal — not the chat UI).
- `GET /auth/logout` — clears the session.
- `POST /admin/scryfall/refresh`, `GET /admin/scryfall/status` (from the
  local-bulk plan) gain a dependency (FastAPI `Depends`) that requires an
  authenticated + allowlisted session **instead of, or in addition to,**
  the bearer `ADMIN_TOKEN`. **Open question for Jon (§8):** keep
  `ADMIN_TOKEN` as a secondary/CLI-friendly path (e.g. the CLI refresh
  script keeps using it, only the HTTP route requires SSO) or retire it
  entirely once SSO is live? Local-bulk's plan approved the bearer-token
  design before this track existed, so this is a genuine upgrade decision,
  not a foregone one.

### 3b. Session handling

- Starlette `SessionMiddleware` (`itsdangerous`-backed, new dependency)
  added to the app, `secret_key` from an env var (never committed, same
  convention as `ADMIN_TOKEN`/`OPENROUTER_API_KEY`). Cookie scoped
  `httponly`, `samesite="lax"` (enough for a same-site redirect-based login
  flow; not `"none"` — no cross-site posting need here), `secure=True` once
  behind HTTPS (post-deploy; localhost dev can relax this — flagged for
  the security review pass in §6, not decided unilaterally here).
- Session holds only what's needed to check the allowlist on each admin
  request (email/subject claim + issued-at for expiry), not the raw
  ID token.

### 3c. Allowlist

- A small, explicit list (env var, e.g. `ADMIN_ALLOWED_EMAILS`, comma-
  separated — or a JSON/YAML file if the list grows) of identities
  permitted to hit the admin endpoint, checked against the verified
  `userinfo` email claim after login. **Why an allowlist and not "any
  authenticated user":** Okta/Entra dev tenants can have more than one
  test identity; authentication alone (proving who you are) is a different
  question from authorization (whether that identity should get admin
  access) — the endpoint stays admin-only even though two IdPs can vouch
  for a login.

### 3d. Secrets

- Per-provider `client_id` / `client_secret` (Okta, Entra) + the session
  `secret_key`, all env vars in `.env` (existing convention, `python-dotenv`
  already a dependency) — **never committed**, matching how
  `ANTHROPIC_API_KEY`/`VOYAGE_API_KEY`/`OPENROUTER_API_KEY` already work in
  this repo.

### 3e. What "done" looks like

Jon logs in at `/auth/login/okta`, lands authenticated, hits
`/admin/scryfall/refresh` successfully; logs out; logs in at
`/auth/login/entra`, same result; an unauthenticated request to the admin
endpoint is rejected (401/403, not a silent no-op); a login from an email
NOT on the allowlist is rejected post-authentication. The public chat UI
and `/answer` are demonstrably unaffected (a quick before/after smoke check,
not a new test suite, since nothing in that path changes).

### 3f. TDD / test approach (auth code gets tests, not just a manual walk-through)

- **Mock the IdP**, don't hit real Okta/Entra in the test suite (matches
  the existing no-network test convention, `tests/test_scryfall.py`'s
  `tmp_path`-isolated style) — stub `server_metadata_url` responses and a
  fake token/userinfo payload.
- Cases to cover: valid login → allowlisted email → admin route succeeds;
  valid login → non-allowlisted email → 403; **redirect-URI validation**
  (a callback claiming a `redirect_uri` outside the registered set is
  rejected — this is the classic open-redirect/token-leak vector);
  **state mismatch** (callback arrives with a `state` that doesn't match
  what was issued → rejected, not silently accepted); **nonce reuse/replay**
  on the ID token; **session expiry** (an old session cookie past its
  lifetime is treated as unauthenticated, not indefinitely valid);
  missing/tampered session cookie on the admin route → 401.

## 4. Slice 2 — SAML (ships after L5 Fly.io deploy)

**Gate:** needs a real public HTTPS URL for the ACS (Assertion Consumer
Service) endpoint — Okta/Entra's SAML metadata exchange won't accept a
`localhost` ACS, unlike OIDC's redirect URI. This is the concrete technical
reason this slice is sequenced after deploy, not a preference.

- **Library:** `python3-saml` (§1) — new dependency, plus the system-level
  `xmlsec1-dev` headers baked into the Fly.io `Dockerfile` (a new apt-layer
  line; flagged so it doesn't surprise the deploy slice's own plan).
- **New routes:** `GET /saml/metadata` (serves the SP's own metadata XML
  for the IdP side of the exchange), `POST /saml/acs` (receives and
  validates the IdP's SAML response), `GET /saml/login` (redirects to the
  IdP's SSO URL).
- **Config per IdP:** IdP metadata (entity ID, SSO URL, signing cert)
  imported; SP metadata (entity ID, ACS URL, cert if request-signing is
  enabled) registered back on Okta and Entra separately — this is
  genuinely two configurations, not one, which is the point (TODO-SSO.md:
  "multi-IdP is the whole point").
- **Attribute mapping:** each IdP's assertion carries email/name under
  different attribute names/formats by default — this slice's job is to
  map both onto the same internal identity shape the allowlist (§3c)
  already checks, so the admin-protection logic doesn't fork per-IdP.
- **What "done" looks like:** Jon logs into the admin surface via SAML
  through Okta, then through Entra, same allowlist enforcement as OIDC,
  same admin endpoint protected (SAML becomes an alternate login path to
  the SAME protected surface, not a second protected surface).
- **This slice gets its own follow-up Rule 0 plan** once L5 ships and real
  URLs exist — the design above is directional, not final; SAML's IdP-
  specific quirks (metadata XML dialects, clock-skew tolerance defaults,
  signature-algorithm mismatches) are exactly what TODO-SSO.md expects to
  surface, and some of that is only discoverable once real metadata from
  both tenants is in hand.

## 5. Slice 3 — Breakage lab + writeup (Jon-driven, after SAML)

**Structured as a checklist Jon executes by hand** — per the standing
ruling (`HANDOFF-development.md`: "delegating it defeats its interview
purpose... same principle as grading"). This plan's job is to lay out the
checklist and tooling, not to script the breaking.

| # | Failure mode to induce | How to break it (Jon, by hand) | Expected symptom | Diagnosis tool |
|---|---|---|---|---|
| 1 | Expired/rotated signing certificate | Rotate the IdP's signing cert (or edit the SP's stored cert to an old/expired one) | SAML response validation fails; SP rejects the assertion | SAML-tracer: inspect the signature block, compare cert fingerprint/validity window |
| 2 | Wrong ACS URL | Misconfigure the ACS URL on the IdP side (typo or stale value) | IdP posts the assertion to the wrong endpoint, or SP rejects it as a destination mismatch | SAML-tracer: check the `Destination`/`Recipient` attribute in the response vs the actual ACS |
| 3 | Mis-mapped email/name attribute | Change the attribute-mapping config so email maps to the wrong claim/format | Login "succeeds" but the SP resolves the wrong (or no) identity — allowlist check fails unexpectedly | SAML-tracer: inspect the `<AttributeStatement>` values vs what the SP expects |
| 4 | Clock skew between IdP and SP | Skew the SP host's clock (or the IdP's, whichever is practical) past the assertion's validity window | Assertion rejected as expired/not-yet-valid even though the login just happened | SAML-tracer: compare `NotBefore`/`NotOnOrAfter` against actual wall-clock time |
| 5 (bonus) | Bad audience/entity ID | Set the SP's `entity_id` to not match what the IdP issued the assertion for | Assertion rejected: audience restriction violated | SAML-tracer: inspect `<AudienceRestriction>` vs configured SP entity ID |

For each row: break it, watch the actual failure (screenshot or copy the
real error), diagnose with SAML-tracer, fix it back, and write the
symptom → cause chain in prose. That prose IS the deliverable (§5.1).

### 5.1 Writeup

- A `docs/` page (or README section) per TODO-SSO.md §5: each failure mode,
  what it looked like from the user's side (the actual error message/UX),
  and how it was diagnosed — the resume/interview artifact. Style: match
  this repo's existing honest, evidence-grounded tone (no invented
  metrics, no "enterprise-scale" inflation — see §7).

## 6. Security review requirements (auth is high-risk — flag, don't skip)

Per `Token-Economy-Policy.md`'s high-risk list (auth is named explicitly),
this track's actual implementation — not this design doc — gets:

- **Strongest-available-model review** on the OIDC/SAML code itself before
  it's considered done, not just a fresh-context functional reviewer.
- **A security-focused pass** covering, at minimum: token validation
  (signature, issuer, audience, expiry all actually checked, not just
  presence), session handling (cookie flags, expiry, fixation — is the
  session ID rotated on login?), CSRF (state-parameter check IS the CSRF
  defense for the OIDC redirect flow — must be verified as enforced, not
  assumed), redirect-URI validation (exact-match against a registered
  allowlist, not a prefix/substring check — a common real-world SSO bug),
  state/nonce (both single-use, both checked, not just generated),
  secret storage (no client secret or session key ever lands in a commit,
  log line, or error message).
- This review happens **per slice** (OIDC review before OIDC ships, SAML
  review before SAML ships) — not deferred to the end of the whole track.

## 7. What MUST stay open / non-goals / considered-and-rejected

**Must stay open, unconditionally:** the anonymous chat demo (`/answer`,
`/feedback`, `/health`, `/cards/autocomplete`, the static frontend mount).
No slice in this track may add a login wall, a cookie requirement, or any
added latency/friction to those routes. SSO's blast radius is the admin
surface only.

**Non-goals:**
- Not a user-accounts feature for end users of the public demo — visitors
  stay anonymous forever, full stop.
- Not enterprise-production auth — this is a personal-project resume
  artifact at hobby scale, honestly framed as such (see below).
- No admin UI beyond what's minimally needed to demonstrate a login
  (matches `plan-scryfall-local-bulk.md`'s own "no admin panel UI"
  non-goal — this track doesn't expand that scope either).

**Considered and rejected:**
- **Gating the whole demo behind SSO.** Rejected — kills the public demo,
  which is the actual point of the project (job-hunt evidence needs to be
  visitable by a recruiter without a login).
- **Rolling a hand-written OIDC/SAML implementation.** Rejected —
  TODO-SSO.md is explicit that using libraries correctly IS the
  professional skill being demonstrated here; hand-rolled token/assertion
  validation is also a well-known way to introduce exactly the security
  bugs §6 exists to catch.
- **One combined OIDC+SAML slice.** Rejected (§0) — breaks the approved
  pre/post-deploy sequencing and makes the security review harder to scope.

**Honest resume framing (already Jon's language, TODO-SSO.md):**
"Implemented OIDC and SAML SSO in a personal project against Okta and
Microsoft Entra ID, including attribute mapping and debugging assertion
failures." Personal-project framing, public repo link, no claim of
enterprise production use — matches this repo's existing honesty norms
(no invented metrics, no scale inflation) already applied throughout
`docs/plan-*.md`.

## 8. Open questions for Jon (review gate)

1. **`ADMIN_TOKEN` fate once OIDC ships** (§3a): keep the bearer-token path
   alive for the CLI refresh script (non-interactive, no browser) while
   the HTTP admin route requires SSO, or retire the bearer token entirely
   and give the CLI script its own service-auth story later? This wasn't
   decided when `plan-scryfall-local-bulk.md` was approved (SSO didn't
   exist yet as a track).
2. **Cookie `secure` flag for local dev** (§3b): relax to `secure=False`
   only on localhost (dev convenience) vs. always `True` and accept that
   local OIDC testing needs `https://localhost` (extra setup friction) —
   which does Jon want for the dev loop?
3. **SessionMiddleware's exact role in OIDC's state/nonce handling** (§1):
   flagged as needing a firsthand smoke test at build time rather than
   trusted from docs alone — fine to proceed on that basis, or does Jon
   want it nailed down by direct Authlib source-reading before build
   starts?
4. **SAML library fallback trigger** (§1): if `python3-saml`'s xmlsec
   install fights the Fly.io base image, is switching to `pysaml2`
   mid-slice an acceptable pivot, or should that decision come back to
   Jon first given it'd touch the SAML slice's design?
5. **Allowlist storage shape** (§3c): a single env var is fine for "just
   Jon," but is a comma-separated env var sufficient long-term, or would
   Jon rather it live in a small config file from day one (easier to
   extend if a second admin identity is ever added)?

### Critical files referenced throughout
- `src/rulesagent/api/main.py`
- `frontend/index.html`
- `run.py`
- `docs/plan-scryfall-local-bulk.md` (§5 admin endpoint — the protection target)
- `TODO-SSO.md` (source of intent)
- `DECISIONS.md` (#4, 2026-07-23 — SSO timing ruling)
- `docs/HANDOFF-development.md` ("SSO track ADDED" entry)
- `pyproject.toml` (new deps land here: `authlib`, `itsdangerous`, `python3-saml`)

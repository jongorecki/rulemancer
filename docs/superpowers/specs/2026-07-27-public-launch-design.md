# Rulemancer public launch — design

**Status:** design only, approved by Jon 2026-07-27. No code until the
implementation plan is written and ruled on (Rule 0).

**Goal.** Put Rulemancer in front of hiring managers as job-search evidence: a
current README, a public repo, a permanent evidence page, and a live demo that
specific named people can unlock and that cannot overspend.

**Audience.** A hiring manager or engineering lead who has ~5 minutes, has never
played Magic, and is deciding whether Jon can do applied AI work. They are not
reading `DECISIONS.md`. They read the README, maybe the results page, maybe click
the demo.

**The claim being made.** The methodology, not the percentage. The defensible
line is "he measures things properly, characterises his instrument, and overturns
his own conclusions when the evidence says to" — the accuracy number is
supporting evidence for that, not the headline claim.

---

## Decisions already made

| Decision | Ruling | Rationale |
|---|---|---|
| Demo access | Per-person access codes, not one shared passphrase | Lets Jon see who actually opened it and revoke one person without breaking everyone's link |
| Public surface | Public repo **and** live site **and** curated results page | Jon's call; strongest showing |
| Results page | Curated narrative of ~6 findings, not the raw 44-arm dashboard | The dashboard was built for Jon, not for strangers |
| Architecture | Static evidence split from the live app | Opposite failure modes: evidence must never be down and costs nothing; the demo costs money per request and can hit a cap |
| Order | Evidence surface first, Fly demo second | The evidence is the part that can't be lost, and it's free |
| Store questions asked | **Yes**, full text | Most useful signal; what a hiring manager asks says more than a hit counter |
| Fly sizing | **Always-on**, ~$5/mo | A 10-20s cold start is the first impression on a link clicked once |

## Prerequisites Jon has to supply

These are account-level and cannot be done by an agent. None block slice 1.

- **GitHub** — account exists (`github.com/jongorecki`). Needs an empty
  `rulemancer` repo, or authorisation for `gh repo create`.
- **Cloudflare Pages** — free account needed for slice 3. GitHub Pages is the
  fallback and needs nothing extra.
- **Fly.io** — account plus a payment method for slice 4 (always-on
  `shared-cpu-1x` is ~$5/mo). `flyctl` installed and authenticated.
- **Approval to spend ~$1** in Anthropic credits to measure the real cost per
  serve, so the budget cap is set from data.

## Non-goals

- No streaming responses. Nice, not required for a first impression.
- No user accounts, email capture, or analytics SDK. Access codes cover it.
- No re-running any eval to improve a number before launch. Ship what is
  measured. A 3-point gain sits inside judge instability anyway.
- No redesign of `evals/metrics_history.html`. It stays an internal tool; the
  results page is separate and purpose-built.
- The running bake-off is **not** a dependency. If it lands before launch its
  numbers get added; if not, launch without it.

---

## Slice 1 — README rewrite

Full rewrite. The current README is ~5 days and a dozen findings stale, and two
of its claims are now wrong.

**Must be removed or corrected:**

- The "31/31 correct on 31 rules questions" framing as the headline accuracy
  evidence. Superseded by 1,409 measured questions. The 31-question grading
  remains mentionable as *human* grading, which is rarer and more valuable, but
  it is not the accuracy claim.
- "The API runs a single worker with a lock, because the caches are whole-file
  read and write." Stale — caches moved to per-key SQLite writes; the lock now
  only guards `agent.last_*` recorder reads between `answer()` and read-back.
- The "rules retrieval turned out to be dead weight" paragraph. This is the
  conclusion that got overturned. It must be restated, not deleted (see below).
- The generator-bakeoff row as the current model evidence. Superseded by the
  fair cross-model comparison.

**Must be added, each sourced from a committed results doc:**

| Finding | Source of truth |
|---|---|
| Headline: ~86% on all 1,409 questions, 95% CI [83.96, 87.60]; per level 96.1 / 90.3 / 84.2 / 67.9; Corner Case 71.0% | `docs/results-headline-accuracy.md` |
| The rules reversal: 98.84% → 15.12% under scrambled retrieval on 86 card-free questions; correct framing is "rules are redundant *given card text*" | `docs/results-rules86-placebo.md` |
| Refusal not confabulation: declined on 90.7% of corrupted rows, confabulated on 3.5% | same |
| Fair cross-model: opus-5 85.88% vs gpt-5-mini 70.05%, +15.8 under gpt-5-mini's own family judge; four judges across three families agree within 3.4 points; mechanism is refusal rate 11.1% vs 0.7% | `docs/results-crossmodel-fair.md` |
| Judge characterised both ways: FP 4.4% (CI to 10.9%), FN 0/77 (CI [0%, 4.7%]) including a census of all 53 hard-level passes | `docs/results-judge-false-negatives.md`, `docs/results-judge-error-rate.md` |
| Level 3 at 67.9% as the stated weakness, with the qualitative failure modes | `docs/results-failure-taxonomy.md` |
| List price misled: `openai/gpt-5` measured $0.0377/row vs opus's $0.031 batched | `docs/results-crossmodel-fair.md` |

**Accuracy phrasing rule.** Never three significant figures. The README says
"roughly 86%, ±2pp sampling and a further ~4pp of instrument variance." Every
percentage on the page carries its population (how many questions, which set).

**Structure.** Keep what already works — the Tibalt story, "what didn't work,"
the ASCII pipeline diagram, Attribution. Add the new findings as a results
section that links out to the evidence page. Add a demo link and an access-code
line ("codes are handed out individually; ask Jon").

**Voice.** Jon's, per the workspace rules: contractions, plain words, varied
sentence length, no em dashes, no corporate filler, no announced honesty.

**Verification.** Every number in the README traced to a committed results doc by
a reviewer subagent that reads the docs, not the README's own claims. Any figure
that can't be traced comes out.

## Slice 2 — Publish the repo

Prerequisite for slices 3 and 4 being linkable. **Nothing is pushed until the
sweep passes.**

1. **Secrets sweep.** `.env` is present in the working tree with live
   `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY`. **Pre-checked 2026-07-27 and clean:**
   `.env` is gitignored (`.gitignore:4`) and appears in no commit across all
   **320**; `git log -S` finds no `sk-ant-api`, `sk-or-v1`, or Voyage `pa-` key
   anywhere in history; `git grep` finds none in the tree. The formal sweep still
   runs against the published clone (below) — this pre-check means it is
   confirmation, not discovery.
2. **If any key ever touched a commit:** it gets rotated, and publishing waits.
   Rewriting history is not sufficient on its own once a repo is public.
3. **Content decision on `docs/` — needs Jon's ruling.** ~900 KB of internal
   history, and **the 320-commit history is published along with `HEAD`**, so
   "leave a file out" means either accepting it stays reachable in history or
   squashing. Three options:
   - **(a) Publish everything, history included.** 320 commits of real iterative
     work is itself strong evidence, and the handoff docs' candour about
     mistakes reads well to an engineer. Costs: the internal process notes name
     Jon's API balances and read as instructions-to-an-agent.
   - **(b) Publish everything except `docs/archive/` and the handoff docs at
     `HEAD`,** accepting they remain in history. Cheap, tidy front door, honest.
   - **(c) Fresh squashed repo** with only curated files. Cleanest, but throws
     away the commit history that demonstrates process.

   **Default if unruled: (b).** Keep `results-*.md`, `DECISIONS.md`, `LOG.md`,
   `DESIGN.md`, `API.md` — they *are* the methodology evidence. Drop
   `docs/archive/` and the handoff docs from `HEAD`.
4. **Data files.** `data/raw/` (CR text) and `data/parsed/` (vector pickle) stay
   gitignored. The pickle embeds the full CR text, which is a redistribution
   problem under the Fan Content Policy.
5. **Untracked working files.** ~30 `_*.py`, `_*.txt`, `_*.json` scratch files
   and `sh.exe.stackdump` are loose in the tree. Clean or ignore before publish.
6. Push to `github.com/jongorecki/rulemancer`, public, with a description and
   topics. The repo already carries an MIT `LICENSE`.

**Verification.** A fresh-context subagent clones the *published* repo to a temp
dir and reports: any credential-shaped string, any CR text, any file Jon wouldn't
want public. Clone, not the local tree — the local tree is not what shipped.

## Slice 3 — Static evidence site

**What it is.** A single dark-mode page telling the six findings in order, plus
the rendered README as a second page. Free hosting, no server, no cold start, no
dependency on the demo being up.

**Generated, not hand-written.** A build script reads the committed eval JSON /
results docs and emits the HTML, so a number on the page cannot drift from the
data that produced it. Hard-coding the figures into HTML by hand is the failure
mode this exists to prevent.

**Content, in order:**

1. What it is, in two sentences, for someone who doesn't play Magic.
2. The headline number with its error bars and its population.
3. The reversal — a prior conclusion overturned by a $3.49 experiment. Framed as
   the methodology story, because it is the strongest item on the page.
4. Refusal as a measured safety property.
5. The fair cross-model comparison and the frozen-prompt-cache design that makes
   it fair.
6. The instrument: how the judge was validated on both sides, and why the
   headline is more likely an understatement.
7. The known weakness: level 3 at 67.9%, named modes, no spin.
8. Links: repo, live demo, and the full 44-arm dashboard for anyone who wants
   everything.

**Design bar.** Workspace UI/UX gate applies on the first pass: visual hierarchy,
consistent spacing and type scale, WCAG AA contrast, one accent colour, dark
default, responsive, tables that scroll inside their own container. Use the
existing `branding/` and `design-system/` assets so it matches the app.

**Hosting.** Cloudflare Pages (free tier, no sleep). GitHub Pages is an
acceptable fallback if Cloudflare setup stalls.

**Verification.** Render it, screenshot it at desktop and mobile widths, and
look. Not markup inspection. Check contrast numerically.

## Slice 4 — Gated demo on Fly.io

### 4a. Access codes

**`codes` table** (SQLite, on the Fly volume so it survives deploys):

| column | purpose |
|---|---|
| `id` | primary key |
| `code` | three readable words + digits, e.g. `raptor-quill-42`; survives being typed off a phone |
| `label` | who it's for, e.g. "Cribl — Jane R." |
| `created_at` | |
| `max_queries` | nullable; default 25 |
| `revoked_at` | nullable; revoking one code doesn't touch the others |
| `notes` | free text |

Codes are minted by CLI: `python scripts/codes.py new --label "..."`, and listed
with `python scripts/codes.py list`.

**`events` table** — one row per unlock, query, or denial:

| column | purpose |
|---|---|
| `code_id` | nullable (a denied unlock has no valid code) |
| `ts` | |
| `kind` | `unlock` / `query` / `denied` |
| `ip_hash` | salted hash, not the raw IP |
| `question` | full text, on Jon's ruling |
| `answered` | did the bot answer or decline |
| `input_tokens`, `output_tokens`, `cost_usd` | |
| `latency_ms` | |

**Flow.** Visitor hits the demo → gate page → enters code → server validates
against `codes` → sets a signed cookie (HMAC over code id + issue time, 7-day
expiry) → `/answer` requires a valid cookie → every call writes an `events` row.

### 4b. Guards — these exist before the URL exists

- **Per-code cap.** At `max_queries`, that code gets an honest "this demo code is
  used up, ask Jon for another" page.
- **Global daily budget breaker.** A dollar ceiling across all codes per day.
  Trips to a friendly page, never a 500. Set from a *measured* cost per serve.
- **Per-IP rate limit on unlock.** Stops brute-forcing the code space.
- **CORS.** Currently `allow_origins=["*"]`. Locked to the demo's own origin.

**Cost model.** Batched eval measured $0.031/row at a 50% batch discount, so a
live serve is expected around **$0.06**. This gets measured with a handful of
real queries before the cap is set (~$1, approved as part of the plan). Against
~$50 Anthropic, a 25-query default cap is ~$1.50 per person, so 20 codes cannot
overspend the balance.

### 4c. Admin view

`/admin`, protected by a separate admin token. Per code: label, unlocks, queries,
first and last seen, total cost, remaining quota, and the questions asked, newest
first. Plus a global daily-spend line against the cap.

### 4d. Container and infra

- **Dockerfile** — new. `run.py` is a local dev launcher (kills ports, opens a
  browser) and is not the container entrypoint; the container runs
  `rulesagent.api.main:app` under uvicorn.
- **`.dockerignore`** — new, and load-bearing: Docker does not read
  `.gitignore`, so this is the thing that keeps CR text and secrets out of the
  image.
- **Fly volume** at `/app/data`, seeded manually once with the vector pickle
  (16.9 MB) and the Scryfall DB (73 MB). Not baked into the image —
  redistribution risk and rebuild cost.
- **Secrets** via `fly secrets set`, never in the image.
- **Always-on**, `shared-cpu-1x`, sized for the pickle load. Region: nearest to
  US-central.

**Verification.** Guards are tested against the live deployed URL before the URL
is shared with anyone: exceed a per-code cap and see the friendly page; trip a
test budget cap; hammer the unlock endpoint and get rate-limited; confirm a
revoked code stops working. The gate is explicit — **no link goes to a human
until those four checks pass live.**

---

## Risks

| Risk | Mitigation |
|---|---|
| A key is found in git history during the sweep | Pre-checked clean 2026-07-27 across 320 commits, so this is now unlikely. If one turns up anyway: rotate first, publish second. Non-negotiable, blocks slice 2. |
| Demo overspends the Anthropic balance | Per-code caps + global daily breaker, both live before sharing. Caps sized from a measured cost. |
| Evidence page goes down with the demo | That's why they're split. The evidence site has no runtime dependency on Fly. |
| A README number can't be traced to a results doc | Reviewer subagent reads the docs, not the README. Untraceable figures get cut. |
| Fly volume seeding is fiddly and blocks launch | Slices 1-3 ship independently; the demo is additive, so a stall doesn't hold the evidence. |
| Bake-off results land mid-work and change a number | Numbers are generated from committed data, so a rebuild picks them up. Bake-off is not a launch dependency. |

## Definition of done

1. README rewritten; every figure traced to a committed results doc.
2. Repo public at `github.com/jongorecki/rulemancer`; clone-and-scan finds no
   credentials and no CR text.
3. Evidence site live on a free host, generated from real data, rendered and
   visually checked at two widths.
4. Demo live on Fly, always-on, gated by per-person codes, with all four guard
   checks passing against the deployed URL.
5. Jon holds a minted code and the admin URL, and has seen his own visit in the
   admin table.

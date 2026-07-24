# Handoff — Rulemancer: v4 BUILT and GRADED (failed its go test), v5 plan drafted (supersedes all prior handoffs; git has them)

## SESSION-END STATE — 2026-07-24 (read this whole block first; it supersedes everything below it, including the 07-23 block)

**The v4 + condition-E slice was planned, built, run, and graded end to end in
this session. v4 FAILED its own go criterion. ONE decision is open and it
blocks everything: the v4 go/no-go. Master currently ships the failed
candidate.**

### THE OPEN DECISION (Jon's, first thing)
`PROMPT_VERSION = 4` is live on master. It failed its go test, costs +1,215
tokens/query, did not fix c014, and drops gpt-5-mini to a 3-answer gap — which
trips Jon's own pre-commitment #3 ("gap ≥3 → sonnet stays pinned") and
mothballs the ~8x cheaper generator option. **Controller recommendation:
revert production to v3**, keep v4's content as the input to the v5 candidate
(docs/plan-v5-and-gold-discovery.md Slice A). Not done — Jon has not ruled.

### The v4 A/B RESULT (Jon-graded, strict, partial = not-correct)
| Arm | v3 cond-C | v4 | Delta |
|---|---|---|---|
| sonnet (production) | 46/50 | **46/50** | **0** — zero divergence, all 50 questions, both runs |
| gpt-5-mini (L2 candidate) | 45/50 | **43/50** | **−2** — c002, c011 stable-flipped correct→wrong |

- Verdicts: `evals/verdicts_v4e.json`. Report: `evals/report-v4e.md`.
- **c014 never moved** — the mana-arithmetic failure the whole notation legend
  was built for. v4 made the model *state* the cost breakdown correctly
  ("3 total mana: 1 generic + 2 green") and still reach the wrong conclusion.
  The bottleneck is multi-step reasoning about cost modification, not notation.
- **Groundedness 2 → 0** on comparable arms in condition C. The only real win.
- Jon's c011 note — *"old ruling, not updated one"* — is a **stale-ruling data
  bug** in the corpus, now the backlog's first `data-bug` entry. Retrieval was
  byte-identical between v3 and v4, so both saw the same stale ruling; v3
  answered around it, v4 leaned on it.

### CONDITION E: CLOSED on latency, not accuracy (DECISIONS.md 2026-07-24)
Measured single-request: sonnet **9.3s** · gpt-5-mini default **16.0s** ·
gpt-5-mini `effort=high` **69.7s** (7,424 of 7,839 completion tokens were
reasoning). Jon's ruling: unusable for an interactive product. **Streaming
cannot rescue it** — a reasoning model emits zero output tokens while
reasoning, so the L5 deploy plan's SSE answer doesn't apply. Both high-effort
runs were killed mid-flight; they were never graded and should not be re-run.
The deferred L2 decision now rests entirely on the DEFAULT gpt-5-mini cell.

### What SHIPPED this session (committed, reviewed)
- **Prompt v4** (`8c7550f`): 4a–4e + 3b, `PROMPT_VERSION` 3→4, two-tier Scryfall/CR
  notation legend. Every symbol verified against the repo's own CR
  (`data/raw/MagicCompRules 20260619.txt`) and Scryfall's Colors-and-Costs doc.
  Includes the mana-value counting rule (hybrid counts 1, `{2/W}` counts 2,
  `{X}/{Y}/{Z}` count 0) and the `{P}` = pawprint / NOT-Phyrexian
  disambiguation. Half-mana and infinite symbols excluded (Un-set only, Jon's
  ruling); **tests assert their absence**. SYSTEM 5,189 → 10,045 chars.
- **Condition-E reasoning passthrough** (`b19b0b3`): optional `reasoning` dict,
  default-off and byte-identical when unset; `--reasoning` CLI recorded into
  run metadata; `--retry-errors` HARD-ERRORS on an explicit mismatch. Effort
  enum verified live against the API's own validator (LOG.md).
- **`evals/build_prompts_v4.py`** (`cbfa3f8`): derives `_prompts_v4.json` from
  condition C by swapping ONLY the `system` field. Four gates, `--check` mode.
  Independently verified: 50/50 user blocks byte-identical.

### THE METHOD THAT MADE THIS WORK — reuse it
**SYSTEM-swap on a frozen capture.** `_prompts_C.json` stores `{system, user}`
separately per question, so a SYSTEM-only change can reuse condition C's `user`
blocks verbatim. v3 and v4 then answer from **byte-identical retrieval** — the
30-34% embedding nondeterminism is absent, not merely controlled — and the v3
baselines need no re-run (6 runs became 4). Any future prompt-only A/B should
do this. Gate 1 (hash the captured system against the recorded v3 digest
`25aa69e1…`) is the load-bearing check: without it, a drifted capture still
produces a clean 50/50 user-block match against the wrong baseline.

### OPERATIONAL LESSONS PAID FOR IN THIS SESSION (do not relearn these)
- **Never pipe a long-running python run through `| tail`.** It block-buffers
  stdout (progress invisible) AND masks python's exit code behind tail's 0 — a
  crashed run reported "exit code 0" and stayed hidden for 40 minutes. Use
  `PYTHONUNBUFFERED=1` and redirect to a log file.
- **Verify agent self-reports against the filesystem and process table.** A run
  agent reported "monitors armed, grid running" while **two of four runs had
  never been launched** — including the entire condition-E cell, the
  decision-relevant arm. Thirty seconds of `ls` + `Get-CimInstance` found it.
- **A real bug, unfixed, worth a slice:** `openrouter_backend.py`'s `_attempt()`
  wraps `data = r.json()` in a try that catches only `httpx` errors, so a
  malformed/truncated HTTP 200 body kills the whole run **with zero rows
  saved**. That is what crashed the first default r2. Runs write once at the
  end, so there is no partial credit — incremental writes would also make the
  ~1hr background-job ceiling survivable.
- **Queue builders emit rows without `cited_text`**, so the grading UI renders
  every citation as "(text not found as a chunk)". This silently degraded the
  v3ab grading session too (all 144 rows). Fixed ad hoc for the v4 queue via
  `build_arm_review.py`'s chunk map; the builders themselves are still divergent.

### THE QUEUE — what's next
1. **Jon rules on v4 go/no-go** (above). Blocks everything else.
2. **docs/plan-v5-and-gold-discovery.md** — NEW, drafted this session, four
   independently-approvable slices, all awaiting review:
   - **A. Selective symbol injection (the v5 candidate)** — scan the CARDS (and
     the question) for symbols, inject only those definitions as a reference
     section. Jon's design. Scanning cards rather than the whole context is
     deliberate: **CR 107.4 enumerates every symbol in the game**, so a
     context-wide scan would be worse than today's static block. Pure code, no
     model call; the rewriter structurally cannot see it (`rewrite_query` at
     answer.py:600 runs before `build_prompt` at :685).
   - **B. Miss-variance probe** — 3 draws per missed question under v3 and v4 at
     frozen retrieval, ~$1.40. Misses: sonnet c012/c014/c015/q029; gpt-5-mini
     c004/c012/c015/q014/q016. Honest limit: c012/c015/q016/q014 have no gold
     rule in the frozen context at all, so no prompt can fix them.
   - **C. Keyword-ablation probe** — does naming "trample"/"deathtouch" in c002
     steer retrieval to keyword-definition rules and away from damage
     assignment? Retrieval-only, cents. Fix (if any) belongs in the rewriter,
     never in rewording gold questions.
   - **D. Automated gold-rule discovery** — Jon: *"I don't want to do it by hand
     if I don't absolutely have to."* Two stages: wide corpus sweep for
     candidates, then bounded ablation for necessity. `evals/ablate_gold.py` is
     the precedent and states the ceiling: it ablates only CITED rules, so it
     cannot find gold that was never retrieved (the q016 case). Proposes, never
     writes — Jon encodes. Validation gate: must reproduce existing hand-curated
     gold before it's trusted on questions that lack it.
3. **Still queued from before, untouched:** docs/plan-rewriter-model-bakeoff.md,
   docs/plan-scryfall-local-bulk.md (approved), docs/plan-sso.md (OIDC),
   docs/plan-deploy.md (budget breaker is the critical slice), plus the owed
   post-hoc citation-filter slice (groundedness pre-commitment #1, partially
   discharged 2026-07-24) and the stale-ruling data bug from c011.

### Two null results now point the same direction
L1 proved **retrieval** wasn't the gap (gold was already in the pool). v4 proved
**prompt wording** isn't either (zero divergence on the incumbent). What's left
is generation-model capability — which reframes L2 from "can we save money" to
"is there headroom above sonnet at all."

---

# Previous handoff — 2026-07-23 evening (superseded above, kept for context)

You are picking up **Rulemancer** (package `rulesagent`): a RAG agent over the
MTG Comprehensive Rules with a per-card rulings mini-RAG, FastAPI backend,
shipped chat frontend. Repo: `D:\Job_hunt\mtg-rules-bot`. Job-hunt
proof-of-work (applied AI / RAG) — **articulation beats polish**: every
decision must be explainable cold. End goal: public demo on Fly.io.

## SESSION-END STATE — 2026-07-23 evening (read this whole block first; it supersedes everything below it)

**This session ended with NOTHING running and SIX Rule 0 plans drafted, all
awaiting Jon's review before any build. His context filled up; this handoff
is the reset. All work is committed (git log through 63487ed).**

### What SHIPPED and is DONE (reviewed, committed):
- **Prompt v3** (f9a70fe): six §1 bullets + two §2 rewriter bullets;
  `answer.py PROMPT_VERSION=3`; rewriter v2 with **v1 still selectable**
  (`rewrite_version` param); Part B ruling-query union togglable
  (`ruling_query_mode`). **ADOPTED as interim production prompt** — v4 to
  supersede.
- **The v3 A/B — COMPLETE** (Tasks 1-3, all reviewed): B/C/D conditions ×
  2 runs × 6 arms, 1798/1800 rows clean (persistent exception:
  gemini-flash-lite D c003). Assemble-once prompt cache
  (evals/answers/_prompts_{B,C,D}.json) fixed a REAL 30-34% retrieval
  nondeterminism (Voyage embed has no cache on the live path). Jon graded
  the 72-stable-flip queue (evals/verdicts_v3ab.json).
- **q029 empty-answer guard + c012 observability SHIPPED** (197ac79,
  390545b, review approved, 152/152 tests): blank-answer degenerate guard,
  uncited-success flag (Debug.uncited_success), unresolved-ref logging
  (Debug.unresolved_card_refs, crash→graceful).
- **Opus-grader calibration v1+v2 DONE** (verdict: audit lens, NOT a
  delegate grader — 78% primary vs the judge's 95% bar).
- **Note-harvester TOOL shipped** (evals/harvest_grading_notes.py): mines
  Jon's grading `note` fields into docs/grading-feedback-backlog.md,
  categorized (prompt-tuning = the prompt-v4 feed, retrieval-gap, display-ui,
  etc.). **RE-RUN IT after every grading export** (reads evals/verdicts_*.json
  + ~/Downloads/answer_verdicts*.json).

### The v3 A/B RESULT (correct/50, Jon-graded, strict):
sonnet **46** (flat, 0 flips) · gpt-5-mini **45** (+3, cond C) · v4-pro **45**
(+1) · v4-flash **44** (+2) · v3-2 **43** (flat) · gemini **37** (regressed).
Decisions (DECISIONS.md 2026-07-23): **v3 GO (interim)**; **Part B union does
NOT ship** (D<C on the best arms); **L2 generator switch to gpt-5-mini
DEFERRED** until prompt-v4 + condition-E test whether it reaches ≥46.
gpt-5-mini is ~8x cheaper than sonnet (MEASURED; the old "25-50x" was vs the
reasoning-OFF deepseek arms).

### THE QUEUE — six Rule 0 plans, all drafted, ALL AWAIT JON'S REVIEW (none built):
1. **docs/plan-prompt-v4.md** — FULLY RULED, ready to implement. Full Scryfall
   notation legend (replaces the mana block; CORE mana/tap/hybrid tier the
   eval validates + REFERENCE energy/snow/loyalty tier for the full card pool,
   in the GENERATION system prompt, cache-friendly, no-lecture guard, symbol
   defs verified at build NOT memory); §1d timing bullet KEPT SEPARATE;
   multiplayer refinement (Jon's verbatim wording); assumption disclosure.
2. **docs/plan-condition-e-reasoning.md** — enable/raise OpenRouter `reasoning`
   on gpt-5-mini, measure vs sonnet 46. KEY FACT: sonnet is NOT thinking today
   (default), so E tests raising gpt-5-mini effort vs a non-thinking incumbent.
   GATES the deferred L2 switch. Pairs with v4.
3. **docs/plan-rewriter-model-bakeoff.md** — retrieval-only bakeoff: gpt-5-mini/
   deepseek/gemini vs Haiku control as the query rewriter, scored on gold
   recall (mean±spread over 3 runs to control embedding noise). Targets the
   documented retrieval gaps q016/q014/c019. Phase 2 (generation A/B) only if
   a candidate wins recall.
4. **docs/plan-scryfall-local-bulk.md** — APPROVED (all questions ruled,
   licensing signed off); implement AFTER the A/B track settles. Local
   card+rulings snapshot (data/scryfall.db), exact-then-local-fuzzy lookup
   (threshold 90), −8/+21-day set-calendar refresh + admin endpoint. Kills the
   network/fuzzy-match failure class (c012's root).
5. **docs/plan-sso.md** — OIDC slice NEXT (Authlib+FastAPI, Okta+Entra dev
   tenants, localhost callbacks) protecting the local-bulk admin endpoint;
   anonymous demo stays open. SAML + Jon-driven breakage lab + writeup
   post-deploy. Auth = HIGH-RISK (strongest-model + security review at build).
6. **docs/plan-deploy.md** — Fly.io. THE critical slice is the budget breaker
   (global daily spend cap + per-IP rate limit + kill switch — a public LLM
   endpoint without it is a financial hole). CORS is wide-open today; no
   Dockerfile/fly.toml exist; /answer is synchronous (streaming is new). Corpus
   redistribution fix: .dockerignore + Fly volume, never bake CR text in the
   image.

### Jon's IMMEDIATE next actions (his calls, not an agent's):
- Grade the **2 ungraded v3ab rows** (gemini-flash-lite B_r2: c006, c014) if
  he wants gemini's count exact (gemini isn't a production candidate, so low
  priority).
- **Review the six plans** and rule on their open questions (each plan lists
  them). Then pick implementation order. Suggested sequencing (his call):
  prompt-v4 → condition-E (settles L2) → rewriter bakeoff, with SSO OIDC
  sliding in next per his timing ruling, and local-bulk + deploy after the
  A/B track. A **follow-up groundedness slice** is also owed (read the 7
  flagged instances, decide on a fix) per the 2026-07-23 pre-commitments.

### Standing facts a fresh session needs:
- **BILLING RULE (Jon 2026-07-23, also in workspace memory):** batch
  Claude-labor (grading, calibration, analysis) runs as in-session Opus
  SUBAGENTS on Jon's subscription, NEVER scripted Anthropic API calls. API
  spend is for the product/eval arms only (a $3.41 API mistake triggered this).
- **c004 ruling (2026-07-22):** sonnet + v4-pro c004 flipped partial→
  correct-with-note; baselines are 46/44. Verdict files carry the ruling tag.
- **Retrieval is nondeterministic** (~30-34% chunk drift, Voyage no-cache) —
  the assemble-once prompt cache is the control; any future A/B must use it.
- **tmp/ is gitignored** (holds throwaway clones like TheJudge, mined for
  prompt ideas — nothing copied verbatim).
- **Sandbox gotcha:** heredoc-to-file python scripts run via
  `.venv/Scripts/python.exe "$CLAUDE_JOB_DIR/tmp/x.py"` intermittently see a
  wrong cwd (file reads return empty). Prefer inline `python -c` for
  data reads, or absolute paths.
- **Cost (measured):** gpt-5-mini ~$0.0059/query vs sonnet ~$0.048 std /
  ~$0.032 intro (Sonnet 5 pricing $3/$15, intro $2/$10 through 2026-08-31,
  from the claude-api skill — never quote model pricing from memory).

## Read these FIRST (source of truth, not this summary)

- `DESIGN.md` — build plan and **Working Rule 0: plan before code.** No
  implementation until a written plan exists and Jon has reviewed it.
- `DECISIONS.md` — every non-obvious decision with reasoning.
- `LOG.md` — raw build log (2026-07-22 has two big entries; git log is the
  full trail).
- `docs/plan-prompt-tuning.md` — **THE PENDING DECISION** (see Queue #1).
- `docs/plan-limitations-and-deploy.md` — the roadmap (L1-L8 + Fly.io track).
- `docs/feature-ideas.md` — Jon's approved feature shortlist + evidence.
- `docs/competitive-landscape.md` — six-bot teardown, README positioning raw
  material.
- `.superpowers/sdd/progress.md` — session ledger (task/commit/review trail).

## How Jon works (respect these)

- **Rule 0: plan before code.** Write the plan, get his review, THEN build.
- **Token economy:** Opus orchestrates/judges; Sonnet implements against
  approved specs (subagent-driven: fresh implementer -> fresh-context
  reviewer -> fix loop, evidence not assertions); Haiku for mechanical
  fixes; Fable ONLY for the hardest design work with Jon's explicit OK
  (used once: the prompt-tuning plan).
- **Do-not-delegate:** eval questions, gold, grading criteria, reading
  failures are Jon's. The transitive-grading pipeline extends his reach
  (judge routes same/different; his verdicts transfer); it never grades.
- **Judge instrument is FROZEN:** judge_bakeoff's prompt + gpt-5-mini
  (95% agreement, 0/21 live audit errors). Rewording it invalidates the
  bakeoff AND the transitive pipeline. Do not touch.
- **Commit per slice** on master; end commit messages with the
  Co-Authored-By line. **Verify UI by PIXELS** (screenshots; Jon's screen
  is final — browser pane can't resize, so 375/768 checks are his).
- **SINGLE-WRITER RULE IS RETIRED** (L3 shipped): caches are SQLite/WAL,
  concurrent eval runs + server are safe. Still check `git status` for a
  parallel session's edits before implementing (two sessions collided on
  L3 and converged by luck).
- **NEVER assert an MTG or model fact from memory.** Ground in CR/Scryfall/
  live check. Model pricing: never from memory (claude-api skill).

## State update — 2026-07-23 (READ THIS FIRST; supersedes the 07-22 state below where they conflict)

- **Prompt v3 SHIPPED** (f9a70fe, review approved, verbatim-verified): all
  six §1 bullets + two §2 rewriter bullets from docs/plan-prompt-tuning.md
  (APPROVED with amendments — see its header). answer.py PROMPT_VERSION=3;
  rewrite.py "v2" with **v1 selectable** (rewrite_version param, cache-keyed);
  Part B union togglable (ruling_query_mode="raw"|"union").
- **c004 RULED (flipped)**: sonnet + v4-pro c004 partial→correct-with-note.
  Baselines now sonnet 46/50, v4-pro 44/50 (verdict files updated, notes
  retained; DECISIONS.md has the rubric meaning). §1d's c004 predicted
  flips are off the board.
- **A/B sweep COMPLETE** (Task 2: 9c20ffb, be2a286, 2491c8c, fix b0b9546;
  review Approved): conditions B (gen-v3+rw-v1+raw), C (v3+v2+raw),
  D (v3+v2+union) × 2 runs × 6 arms. 1,798/1,800 rows clean; persistent
  exception gemini-flash-lite D c003 (both runs, provider-side).
  **CRITICAL DISCOVERY**: retrieval embedding (Voyage) is nondeterministic —
  30-34% of questions can draw different chunks between captures. Fixed
  within the A/B by an assemble-once prompt cache
  (evals/answers/_prompts_{B,C,D}.json; both runs share a capture).
  Condition A's prompts were never captured → A-vs-new comparisons carry
  unquantifiable retrieval-draw variance; Task 3 tags affected questions.
- **Task 3 IN FLIGHT** (judge-compare vs A verdicts via frozen pipeline,
  stable-flip intersection, groundedness tripwire, Jon's grading queue +
  evals/report-v3-ab.md). Outputs: evals/judge_pairs_v3ab_*.json.
- **Opus-grader calibrations DONE** (v1: 22805b2 — API, $3.41, a billing
  mistake, see below; v2: b0af49b prep + f5968cc results — in-session
  subagents on Jon's subscription): v1 76.4% / v2 78.3% primary agreement,
  boundary 83.3%→86.7%, vs frozen-judge bar 95%. VERDICT: Opus is an
  audit lens, NOT a delegate grader. Card data fixed the coherent-but-wrong
  class (16 disagreements resolved) but introduced 12 new ones.
- **BILLING RULE (Jon, 2026-07-23)**: batch Claude-labor (grading,
  experiments) runs as in-session subagents on Jon's SUBSCRIPTION, never
  scripted Anthropic API calls; API credits are for the product/eval arms
  only. (Also in workspace memory.)
- **Plans APPROVED by Jon 2026-07-23, implementation pending:**
  - docs/plan-q029-empty-answer-guard.md — **SHIPPED 2026-07-23**
    (197ac79 + 390545b, review Approved, 152/152 tests): blank-text
    degenerate guard, weak-fallback tightening, uncited-success flag
    (Debug.uncited_success), unresolved-ref observability
    (Debug.unresolved_card_refs, crash→graceful, warning-log audit).
  - docs/plan-scryfall-local-bulk.md (fully ruled: threshold 90 tunable,
    measure-first ambiguity guard, refresh window −8/+21 days around set
    release [prerelease = release−7, Jon], no_refresh stays documented
    no-op, admin = background+status-poll+ADMIN_TOKEN, **Scryfall
    licensing SIGNED OFF** — DECISIONS.md). Implement AFTER the A/B
    concludes and its follow-ups settle.
- **New gotchas**: background bash jobs die at ~1hr (kill-and-resume
  cycles; runners need resume logic — Task 2's has it). evals/answers/
  still has no .gitignore entry (discipline-only). gpt-5-mini D r2 +
  repairs used --retry-errors (now model-guarded).
- **Pending Jon after Task 3**: grade the stable-flip queue; v3 go/no-go;
  Part B ship call (D vs C); L2 generator call; RulesGuru-150 (ruled: after
  this A/B).
- **SSO track ADDED (Jon, 2026-07-23; spec: TODO-SSO.md, committed):**
  OIDC (Authlib) then SAML vs Okta + Entra dev tenants, breakage lab +
  writeup. Resume-driven. Integration decisions on record: SSO never gates
  the anonymous public demo; its first protected surface is the local-bulk
  admin refresh endpoint (upgrades the ADMIN_TOKEN design); the breakage
  lab is JON-DRIVEN (delegating it defeats its interview purpose — same
  principle as grading). Sequencing: Jon chooses OIDC-before-deploy
  (localhost callbacks work with both IdPs; resume-urgent) vs whole track
  after L5 — not yet ruled. Each slice gets its own Rule 0 plan; auth =
  high-risk area (strongest-model review).

## State (all of 2026-07-22; commits through ~075d3f6+ — git log is the trail)

- **L3 SQLite caches SHIPPED** (09683fc + 9127491 review fixes): five
  whole-file caches -> data/cache.db (WAL, per-op conns), queries/feedback
  JSONL -> tables, telemetry logs on failure. 6/6 gates incl. byte-identical
  retrieval eval. Deploy blocker #1 cleared.
- **L1 cross-refs SHIPPED** (92fa295..30ac5db): mechanism correct + tested
  (18 TDD tests), organic ranks untouched, last_crossref debug field.
  HONEST NULL RESULT: none of q016/c011/q029 were retrieval gaps (gold was
  already in pool) — generation is the quality frontier. Part B
  (--ruling-query union) MEASURED: 16/25 -> 20/25 load-bearing rulings,
  0 regressions, ships only on Jon's call.
- **Ticker slice** (36f0994): sequential 13-phase turn walk, 2500ms; new
  homepage example (trample+deathtouch). q001 identity flake fixed
  (80d02c7, frozen-store double, 5x green).
- **Six-arm HUMAN-GRADED table** (the L2 evidence; c004 ruling 2026-07-22
  flipped sonnet + v4-pro c004 partial→correct-with-note, see DECISIONS.md):
  sonnet-v2 46/50 · v3.2 43 · v4-pro 44 · v4-flash 42 · gpt-5-mini 42 ·
  gemini 38 (10 wrong — stable-but-wrong). All arms answered from
  byte-identical prompts, so gaps are pure generation. Mechanical
  citation-proxy MISLED on extremes (gpt-5-mini underrated, gemini
  overrated) — proxy is triage only, cards are invisible to it (gold=[]).
- **Transitive grading pipeline SHIPPED** (819bbc7, ae5d5d8, b4deac2;
  review approved): evals/judge_arm_pairs.py routes pairs vs Jon's graded
  reference; 250 -> 56 hand-grades (78% cut); audit 0/21 errors.
  Roll-up: manual wins; >10% audit disagreement = arm falls back manual.
  Adapter evals/build_arm_review.py; combined queue
  evals/build_combined_diff.py (--split fans a combined export back out).
  All verdicts committed: evals/verdicts_*_{manual,final}.json (075d3f6).
- **Sonnet cost estimated** (not measured): ~$0.55-0.85 per 50-run
  (~129k in / ~28k out at $3/$15; tokenizer + adaptive-thinking
  uncertainty). = ~25x v3.2, ~50x v4-flash. Decision dashboard:
  data/parsed/l2-model-decision.html (gitignored, rebuildable from the
  committed verdict files if needed).
- **Fable prompt-tuning plan WRITTEN** (docs/plan-prompt-tuning.md, DRAFT):
  6 surgical system-prompt bullets (~520 tok; F1 card-role, F2 mana
  semantics, F4 multiplayer, F5 assumptions, F7 card-text-overrides,
  F3/F6 clarity) + 2 rewriter bullets + Jon's oracle-text-to-rewriter
  pass-through as its OWN section (structurally sound; cards already
  resolve before rewrite in current code; needs cache-key fingerprint;
  NEW risk: Haiku role-drift; recommended as separate flag/version).
  Predicted flips: 3x c002, 3x c014, 2x c004, v4-flash:c016 (highest
  conf), 3x q014 (hedged). Riskiest: multiplayer bullet vs groundedness
  rule. c012 finding: NO multi-card bug in build_prompt — suspect
  get_card() fuzzy-match or stale scryfall cache entry (fresh tracing
  session needed).
- **Feature shortlist approved** (docs/feature-ideas.md): clarify-then-
  escalate (#1, WotC-patent-validated), legality chip, misconceptions
  gallery, permalinks (post-L3), CR-gap flag, donate link, CR auto-update
  pipeline (#8, gated blue-green design). Rewriter's `clarification` =
  rules-talk translation, NOT a clarifying question.

## THE QUEUE (priority order)

1. **Jon reads docs/plan-prompt-tuning.md and rules on prompt v3.**
   Controller's recommendation on record: adopt the 6+2 wording bullets as
   v3, A/B via the existing harness (re-run arms, transitive judge-compare
   v3 vs v2, hand-grade diffs only); hold oracle-text as its own slice.
2. **Pending Jon micro-decisions:** ~~c004 partial-flips~~ RULED 2026-07-22:
   FLIPPED to correct-with-note (see DECISIONS.md — sonnet 46/50, v4-pro
   44/50 now; verdict files updated, note retained; §1d's c004 predicted
   flips are off the board); L2 generator call (sonnet
   45/50 at ~25x cost vs v3.2 43/50 — may reasonably wait for v3 results);
   Part B union ship; RulesGuru-150 extension (~$10).
3. **Code slices needing plans (Rule 0):** q029 empty-answer guard
   (answered:true + blank text slips _degenerate(); production answer
   path); c012 Scryfall fuzzy-match/stale-cache tracing.
4. **Deploy track (L5):** streaming, per-IP rate limit + budget breaker,
   CORS, Dockerfile, Fly.io (index builds ON host — CR text in a public
   image is redistribution; keys as secrets). Then feature shortlist +
   README (absorb the six-arm table + audit story + competitive landscape;
   draft README exists, deliberately uncommitted).

## Environment & gotchas

- Python via `uv run` / .venv\Scripts\python.exe; PYTHONIOENCODING=utf-8
  everywhere; `.env` has VOYAGE/ANTHROPIC/OPENROUTER keys.
- **Pinned:** voyage-4-large embeddings; generation claude-sonnet-5 (until
  L2 call); rewriter claude-haiku-4-5; judge gpt-5-mini (FROZEN).
- **Jon runs run.py on port 8000 — never bind/kill it.** Test elsewhere.
- Detached background jobs report phantom exit code -1 after completion —
  read the output log tail, not the code (runs print "... DONE" markers).
- Browser pane: resize_window claims success but doesn't resize; file://
  blocked — serve via throwaway `python -m http.server 890x`, kill after.
- OpenRouter backend retries 429s/truncations (d810287) — first-attempt
  reliability still differs per model (ops table in the dashboard).
- evals/answers/ is untracked (big data); verdicts_*.json in evals/ ARE
  tracked. data/parsed/ is gitignored (generated).
- Untracked leftovers Jon may keep/delete: README.md (draft, deliberately
  uncommitted), branding-preview/, design-system/, evals/merge_arm_gap.py
  (parallel session's tool), sh.exe.stackdump (junk), evals/answers/
  gap_*.json (junk artifacts of a stopped run).
- Grading UI: evals/build_grading_ui.py (--in review-format json). Six
  per-arm HTMLs + grading_all_diff.html in data/parsed/. Exports download
  as answer_verdicts.json (browser appends " (N)").
- doc metadata rule, resume rules, token economy live in
  D:\Job_hunt\CLAUDE.md — applies here too.

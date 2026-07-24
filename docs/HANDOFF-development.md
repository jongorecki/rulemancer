# Handoff — Rulemancer: v5 grid BUILT and GATED, awaiting Jon's run

**This file replaces the previous handoff rather than prepending to it. Git has
every earlier version (`git log -- docs/HANDOFF-development.md`); the 07-23 and
07-24 blocks are preserved there. They were superseded, and carrying them
forward was filling Jon's context — which is the whole reason this file is now
short.**

## SESSION-END STATE — 2026-07-25

Rulemancer (package `rulesagent`): a RAG agent over the MTG Comprehensive Rules
with a per-card rulings mini-RAG, FastAPI backend, shipped chat frontend. Repo
`D:\Job_hunt\mtg-rules-bot`. Job-hunt proof-of-work (applied AI / RAG) —
**articulation beats polish**: every decision must be explainable cold. End
goal: public demo on Fly.io.

### THE ONE OPEN THING

**The v5 grid is built, gated, and not yet run. Jon starts the run.** 64
generations, ~$1, no new captures, no fresh-grade rows. Everything below it is
already done.

### Read these FIRST (in this order — they are the spec, this file is only a map)

1. `docs/plan-v5-symbol-injection.md` — the approved plan for everything that
   shipped this session, plus §7 (phase 2, c020) which has NOT shipped.
2. `docs/plan-run-progress.md` — the progress/heartbeat slice.
3. `DECISIONS.md` — the two 2026-07-25 entries at the end are this session's.
4. `DESIGN.md` — **Working Rule 0: plan before code.**

Do NOT read the older plan docs unless a task needs them; several are
superseded (`plan-v5-and-gold-discovery.md` Slices A and B are replaced by
`plan-v5-symbol-injection.md`; its Slice C, gold discovery, is still live).

### HOW JON WORKS — respect these exactly

- **Rule 0: plan before code.** Write the plan, get his review, then build.
- **USE SUBAGENTS. THIS IS EXPLICIT (Jon, 2026-07-25):** *"you can totally use
  subagents because now our context is already at 39% which is insane."* The
  previous session burned a large fraction of context doing implementation
  inline before he said this. **Do not work through a multi-slice build in the
  lead model's context.** Dispatch scoped implementation to Sonnet subagents
  against the written plan, with fresh-context review, and keep the lead for
  judgment. If your harness appears to restrict the Agent tool, say so to Jon
  early and ask — do not silently absorb the work inline.
  - Parallelise only across **disjoint file sets**, and forbid `git add -A` /
    `git add .` in every agent prompt. The real hazard with concurrent agents
    is staging, not logic: one agent sweeping another's half-written files into
    its commit. Explicit paths only.
  - Demand **evidence, not assertions** — real pasted command output, real
    counts. Tell agents to STOP and report if the spec is wrong rather than
    improvising. Three agents did exactly that this session and all three
    findings were correct.
- **Token economy:** Opus orchestrates and judges; Sonnet implements against
  approved specs; Haiku does bulk fetch/filter/verify with compact returns.
  Fable only for the hardest design work with Jon's explicit OK.
- **Do-not-delegate:** eval questions, gold, grading criteria, and reading
  failures are Jon's. The judge routes; it never grades.
- **Judge instrument is FROZEN:** `judge_bakeoff`'s prompt + gpt-5-mini. Never
  reword it.
- **Never assert an MTG or model fact from memory.** Ground in the repo's own CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Model pricing always
  via the claude-api skill. This caught a real error this session — the plan
  claimed Charging Rhino has trample; it does not.
- **Billing:** batch Claude-labour (grading, calibration, analysis) runs as
  in-session subagents on Jon's subscription, never scripted Anthropic API
  calls. API spend is for the product/eval arms only.
- **Commit per slice** on master, ending messages with the Co-Authored-By line.
- Jon runs `run.py` on port 8000 — **never bind or kill it.**
- Python is `.venv/Scripts/python.exe`; `PYTHONIOENCODING=utf-8` everywhere.

### WHAT SHIPPED THIS SESSION (all committed, all tests green)

| commit | what |
|---|---|
| `97adea0` | Both Rule 0 plans |
| `edea4a4` | **Production reverted to v3** via a SYSTEM version registry |
| `51de4bc` | DECISIONS.md — v4 no-go + c002 scoring exclusion |
| `66bce98` | Slice 2 — selective symbol injection |
| `611fe7b` | Plan: c011 symbol-count correction (see the warning below) |
| `228aa24` | Progress heartbeats + incremental writes |
| `3f5e961` | Slice 3 — the grid derivation, all five gates passing |
| `5900392` | Plan: measured cost table + Jon's no-pre-commitment ruling |

**v4 is NO-GO and reverted.** It failed its own go criterion: sonnet 46 → 46
with **zero** judge-detectable divergence across all 50 questions and both runs,
under byte-identical retrieval, for ~+1,215 tokens on every query — and **no
prompt caching exists on either path**, so that is paid in full. It never moved
c014. Reverted by version-selecting, not deleting: `SYSTEM_VERSIONS` in
`answer.py` holds v3, v4 and v4nl, and `PROMPT_VERSION` picks production. v4
must stay runnable because the grid generates from it.

**The grid** (`evals/build_prompts_variant.py`, 2×2 bullets × injection):

| | no injection | injection |
|---|---|---|
| **v3 bullets** | A: v3 — production baseline | B: v3 + injection |
| **v4 bullets** | C: v4nl | **D: v5 — the candidate** |

All four derived for all 50 questions from the frozen `_prompts_C.json`. Five
gates pass: v3 digest, user-block equality (50/50 × 4), card-block extraction
(19/19), over-trigger (50/50), production parity (50/50).

### JON'S RULINGS THIS SESSION (do not relitigate)

1. v4 no-go; v3 is production. Low urgency — nothing is deployed, Jon is the
   only caller.
2. v5 = v4's bullets with per-symbol definitions injected, not the full
   dictionary attached.
3. Add a **v3 + injection** arm — this is what makes the design a factorial and
   any v5 win attributable.
4. Scope = the symbol-bearing misses, which derive to the six card misses.
5. **c002 excluded from scoring**, kept as a monitored row. See DECISIONS.md —
   this moved v4's gpt-5-mini regression from −2 to −1 and the gap from 3 to 2,
   which is *out* of the band where pre-commitment #3 auto-pins sonnet.
6. His rewritten question is **c020**, a new id — c002 stays frozen. Phase 2.
7. Inject when a symbol appears in the question with no card attached.
8. No paired keyword variant of c020.
9. **Fix-it-first**: see whether v5 fixes the misses before perturbing inputs.
10. **NO pre-commitment on the tie-break.** The controller proposed that cell D
    must beat cell B by enough to justify ~510 tokens/query; Jon declined and
    will decide from the numbers and the actual answers. What replaces it is a
    reporting requirement: **cost must sit beside accuracy in the same table.**

### THE RUN — what Jon does next

Four variants × the phase-1 question set, 2 runs per cell, stable-flip rule
unchanged. Scoring: sonnet c012/c014/c015; gpt-5-mini c004/c012/c015/c011.
Monitored, non-scoring: c002 (gpt-5-mini). 8 arm-question pairs × 4 variants ×
2 runs = **64 generations**.

Watch it with `evals/watch_runs.py` (percentage per run plus a grand total;
STALLED and DEAD detection). **Never pipe a long-running python run through
`| tail`** — it block-buffers stdout and masks the exit code behind tail's 0.
Use `PYTHONUNBUFFERED=1` and redirect to a log file.

Then: judge-compare against the existing verdicts (the judge routes; only
genuine changes reach Jon), Jon grades the queue, and the report must put
per-query token cost beside each cell's correct-count.

**Measured cost per query vs v3:** v4 +1,214 tok everywhere; cell D +603 card /
+509 rules; cell B +93 card / **0** rules. Cell B is free on 31 of 50 questions.

### OPERATIONAL LESSONS PAID FOR THIS SESSION

- **`str.replace()` does not error on a missed anchor.** A plan edit silently
  no-opped and was committed with a message describing work that never
  happened (`611fe7b` — corrected by `5900392`, message left as written). The
  script printed "plan corrected", which only proved it ran. **Always re-read
  the file and assert the content landed**, then let the check fail loudly.
- **Backticks inside a double-quoted `git commit -m` trigger command
  substitution** and silently eat text. Use a heredoc (`-F -` with `<<'EOF'`).
- **A resume guard must key on everything that determines the output.** The
  incremental-write resume compared model/rewrite_version/ruling_query_mode/
  reasoning — every one of which is identical across all four grid cells, which
  differ *only* by prompt file. Reusing an `--out` path would have silently
  served rows from a different prompt. A fix was dispatched (guard must include
  the prompts-cache identity and HARD-ERROR on mismatch) but had not reported
  at handoff time. **VERIFY THIS BEFORE THE RUN** — check the resume guard in
  `evals/run_openrouter_arm.py` compares the prompts cache, and that
  `evals/watch_runs.py` shows a percentage column and a grand total. If either
  is missing, finish it first; the grid is exactly the scenario that trips it.
- **Verify agent self-reports against the filesystem.** Every agent report this
  session was accurate, but the two defects that mattered were both found by
  reading the code rather than the report.

### STILL QUEUED

- **Phase 2 — c020** (`plan-v5-symbol-injection.md` §7): needs a fresh capture
  and, having no baseline, every row is fresh grading for Jon (~8 rows at v3
  and v5 only). Deliberately deferred per ruling #9.
- **Owed documentary edit:** mark c002 non-scoring in `evals/cards.jsonl` and
  add the c020 row. Deliberately NOT done before the run — do not mutate eval
  inputs immediately before running. DECISIONS.md and the plan already record
  both.
- Untouched from before: `plan-rewriter-model-bakeoff.md`,
  `plan-scryfall-local-bulk.md` (approved), `plan-sso.md` (OIDC),
  `plan-deploy.md` (the budget breaker is the critical slice),
  `plan-v5-and-gold-discovery.md` Slice C (gold discovery), the owed post-hoc
  citation-filter slice, and the stale-ruling data bug from c011.
- **L2 is live again.** With c002 excluded, gpt-5-mini sits at a 1-answer gap
  under v3 — the most favourable that comparison has ever looked.

### ENVIRONMENT & GOTCHAS

- `.env` has VOYAGE/ANTHROPIC/OPENROUTER keys. Pinned: voyage-4-large
  embeddings, generation claude-sonnet-5, rewriter claude-haiku-4-5, judge
  gpt-5-mini (FROZEN).
- Background bash jobs die at ~1hr; detached jobs report phantom exit code −1
  after completing — read the log tail, not the code. Incremental writes and
  resume now make this survivable.
- `evals/answers/` is untracked (big data); `evals/verdicts_*.json` in `evals/`
  ARE tracked. `data/parsed/` is gitignored.
- Heredoc-to-file python scripts intermittently see a wrong cwd — prefer inline
  `python -c` or absolute paths.
- Browser pane: `resize_window` claims success but doesn't; `file://` is
  blocked — serve via a throwaway `python -m http.server 890x`, kill after.
- Untracked leftovers Jon may keep or delete: `README.md` (draft, deliberately
  uncommitted), `branding-preview/`, `design-system/`, `evals/merge_arm_gap.py`,
  `evals/build_v4_c_reference.py`, `sh.exe.stackdump`, `test_results.txt`.
- Doc-metadata rules, resume rules and the token-economy policy live in
  `D:\Job_hunt\CLAUDE.md` and `D:\Job_hunt\Token-Economy-Policy.md` — they apply
  here too.

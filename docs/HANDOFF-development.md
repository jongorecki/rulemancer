# Handoff — Rulemancer: cost tool hardened, combat tool is next

**Replaces the prior handoff (git has every version). Written at the end of the
second 2026-07-24 session, which fixed the cost-tool reliability defect that was
task #1, folded Jon's manual regrade into a corrected accuracy number, and
completed the combat-damage plan's deferred research.**

## THE ONE THING TO DO FIRST

**Jon rules on whether to build the combat-damage assigner — the completed
build-prep research made the case genuinely weaker, so this is a real
go/shelve/pivot decision, not a rubber stamp.** `docs/plan-combat-damage-tool.md`
§1-10 is the design; **§11 (build-prep research)** grounded it and found:

- **ROI is thin.** Only **7 of 164** combat-tagged rows are genuinely
  assignment-shaped (~0.5% of the 1,409-row corpus): rg78, rg86, rg581, rg1917,
  rg2079, rg3195, rg5308 (rg3195/rg5308 hit all three target rules — strong test
  cases). Rare enough to weaken the ROI per the plan's own §8 bar. Weigh against
  the demo/articulation value in §9 (a second "found a recurring failure class,
  built a deterministic tool for it" is a real story even at low volume).
- **The plan's CR citations were wrong (grounding caught it):** 509.2 is priority
  timing, not the assignment-order rule (that's 510.1c alone); **510.5 does not
  exist**; first strike is 702.7, not 702.4 (which is double strike only). Fix in
  the docstring if built.
- **The proposed trigger regex misses 6 of 7 real examples** — real phrasing is
  "what is the maximum damage… can deal/assign," not "how much." §11 has a
  4-branch regex that catches 7/8 (rg86 "will both blockers die?" has no damage
  word — needs a different trigger).
- **⚠️ Loop-gating trap:** the tools-off terminal-round machinery from `1dfe6d4`
  is keyed specifically to `use_cost_tool` in three places (`answer.py` ~1452,
  ~1475, ~1507), NOT "any tool fired." A combat trigger added without broadening
  those checks would **silently reinherit the exact cap-exhaustion bug we just
  fixed.** And `TOOL_ROUND_CAP` (3 → only 2 tool rounds) likely needs raising for
  a double-strike two-call sequence.

**Given the weak ROI, the live question is combat vs. the layer-system tool** —
Jon's own regrade reinforced layers on four separate misses, and layers targets
the weakest tier (Corner Case, 50%). That's Jon's lever call.

**Task #1 from the prior handoff — the cost-tool reliability defect — is DONE**
(commit `1dfe6d4`). Root cause was **cap-exhaustion**, not the payload/parse
collision the report guessed: 16 of 17 failing attempts were the model emitting
`tool_use` on every round until `TOOL_ROUND_CAP` nulled the response. Fix landed
three coupled changes (details below). Empty-output dropped from ~29% to **0/24**.

## HOW JON WORKS (unchanged, load-bearing)

- **Rule 0: plan before code.** Every `plan-*.md` is design-only until Jon rules.
  A bug-fix on already-approved code uses systematic-debugging, not a fresh plan;
  a NEW tool needs a plan and a ruling.
- **USE SUBAGENTS.** Dispatch scoped implementation to Sonnet against a written
  plan; keep the lead for judgment/review/talking to Jon. Haiku for bulk
  fetch/filter/verify with compact returns. This session ran ~5.
- **Do-not-delegate:** eval questions, gold, grading verdicts, **reading
  failures** (the lead reads the garbled/failed outputs itself).
- **Judge is FROZEN** (`judge_bakeoff` prompt + gpt-5-mini). Never reword.
- **Never assert an MTG/model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Pricing via claude-api.
- **Billing:** Claude-labour on subscription subagents; API spend is for
  product/eval arms only. **The account API usage cap is currently the binding
  constraint** — see ENVIRONMENT.
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 4.8`
  trailer (repo convention). `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`.
  Jon runs the app on port 8000 — never bind/kill it.
- **Verify your own writes / evidence not assertions.** `str.replace()` no-ops
  silently — re-read and assert. Never `| tail` a long run (masks the exit code)
  — `PYTHONUNBUFFERED=1` + a log file. **A single favourable run is not a rate**
  — aggregate before claiming reliability. Subagents that background a long run
  and yield a "standing by" placeholder must instead poll the log in-turn.

## THE STRATEGY (unchanged through-line)

This is a **card-interaction reasoning product.** Held-out (RulesGuru-150):
sonnet **72%** raw / **75.3%** after Jon's regrade, monotonic by difficulty.
Retrieval overfit badly (recall@50 100% tuned vs **63%** held-out) AND barely
predicts correctness — the model answers card questions from **oracle text**, not
retrieved CR rules. **So the levers are REASONING (tools) and CARD-DATA quality.**
Caveat surfaced by the holdout report: retrieval **coverage** is the
under-measured lever, and **sonnet-as-rewriter improves held-out coverage** (@50
75% vs haiku 63%) — the rewriter question is live again on the *retrieval* side.

## THE TOOL ROADMAP (the core direction)

Pattern: the model orchestrates + reasons; deterministic tools own the exact
sub-computations it narrates right and then botches.

1. **Cost calculator — SHIPPED + HARDENED** (`da0449e`, `e763e91`, `1dfe6d4`).
   Reliable now; the loop it uses is the shared machinery for every later tool.
2. **Combat-damage assigner — PLANNED, plan complete but ROI now looks thin**
   (`plan-combat-damage-tool.md`, §11: only 7 genuinely assignment-shaped
   questions exist in the corpus). Jon's go/shelve/pivot call — see THE ONE
   THING; if built, mind the `use_cost_tool` loop-gating trap.
3. **State-based-action checker** — idea, not planned.
4. **Layer-system resolver (CR 613)** — idea; targets the weakest tier (Corner
   Case, 50%). **Reinforced this session:** Jon's regrade flagged layers on four
   separate misses (rg3868, rg807, rg811, rg633 — "timestamp order and layers is
   genuinely super weird").
5. **Question-classification pipeline step** (Jon's idea) — route to the right
   tool + boost relevant rules. ADDITIVE (offer-more, never restrictive),
   deterministic-first. Not yet planned.
6. **NEW tool ideas from this session's regrade notes:**
   - **Trigger-type identifier** — "enters-the-graveyard" vs "leaves-the-
     battlefield" triggers (rg608).
   - **Ability-type / ability-definer tool** — what counts as an ability,
     mana-ability vs not (rg549; rg517 Deathrite Shaman first ability is not a
     mana ability because it targets).
   - **Replacement-effect ordering tool** — order of multiple replacement
     effects + best outcome, and recognizing when things are a *single* ability
     so replacements resolve together (rg1095, rg1953).
7. **DO NOT build the keyword-reminder-text tool** (redundant with oracle text,
   epistemically risky) — already ruled out.

**Data idea (not a tool):** load a card's *rulings* when the card is loaded
(rg517, rg7215 — the Minas Tirith ruling got ignored when it applied).

## WHAT SHIPPED THIS SESSION (all on master)

- **Cost-tool reliability fix** (`1dfe6d4`). Instrumented repro
  (`evals/_phase1_costtool_repro.py`, 24 gens) root-caused cap-exhaustion. Three
  changes: (a) `tool_choice={"type":"none"}` on the final tool round so the model
  can't loop and must emit the Answer; (b) a **malformed-answer guard**
  (`_malformed`: leakage markers + <30-char fragment) that routes garbled draws
  to the existing retry→honest-decline path instead of shipping them as
  `answered=True` — high-precision, coherent-uncited answers untouched (q029
  preserved); (c) `_needs_cost_tool` excludes mana-*production* questions (rg289
  FP). Verified: 354 tests, empty 0/24, degenerate 0/24, no false positives.
- **RulesGuru regrade folded** (`d742d34`). Jon regraded all 42 sonnet misses: 2
  actually correct (judge wrong), 6 partial, 34 wrong → **75.3% (113/150), 110 W
  / 6 D / 34 L** at half-credit. Upward-only (the 108 judge-passes weren't
  re-audited). Report: `docs/report-rulesguru-holdout.md`; verdicts:
  `data/parsed/rulesguru_disagreement_verdicts.json`.
- **Combat plan build-prep research** (`plan-combat-damage-tool.md` §11) — CR
  grounding that corrected 3 wrong citations, the ROI count (only 7 of 164 tagged
  rows are genuinely assignment-shaped), a calibrated trigger regex, and the
  `use_cost_tool` loop-gating trap noted in THE ONE THING.

## RESIDUALS / OPEN ITEMS FROM THIS SESSION

- **rg6636 rep3 word-salad** — still ships as `answered=True`-but-uncited (~1/24).
  Left uncaught deliberately (a guard loose enough to catch real-prose word-salad
  risks nuking a real terse answer); it's flagged in `last_uncited_success`
  telemetry, so it's monitorable, not silently trusted.
- **rg6916 rep1** — leaked scratchpad text landed in an `answered=False` decline
  (out of the guard's `answered=True` scope). Small UX follow-up.
- **Sentinel de-conflation** — the empty-output path still logs `"error"` for both
  cap-exhaustion and validation-empty; distinguish them (less urgent now that
  cap-exhaustion is structurally impossible on the tool path).
- **rg3391 long-context empty** — a *different* empty-output cause than the
  cost-loop one. Jon's note says "raise max_tokens"; but the repro showed baseline
  empties were NOT truncation (nowhere near the 16384 cap), so that hypothesis is
  suspect — repro rg3391 specifically before assuming.

## HELD / BLOCKED ON JON

- **Scryfall local-bulk + per-face + self-heal** (`worktree agent-
  a818653b08eb516a4`, ~8 commits, NOT merged; complete + verified, 302 tests,
  29/29 equivalence; self-heal removes the missing-db catastrophe). Landing is a
  deliberate reconciliation. ⚠️ **The `answer.py` conflict is now THREE-way:** the
  branch's fuzzy-fallback wiring vs master's cost-calc tool loop vs this session's
  new `tool_choice:none` + `_malformed` guard. **Keep all three.** Master has no
  `scryfall.db` (first `get_card` self-heals → 180MB download; pre-build or accept
  it).
- **Lever decisions Jon owes** — v5 go/no-go, L2 generator, and the rewriter-on-
  the-retrieval-side question (holdout data delivered; sonnet rewriter lifts
  coverage).

## STILL QUEUED (untouched)

`plan-sso.md` (tied to Jon's job-hunt auth-evidence goal — see the rulemancer
memory), `plan-deploy.md` (budget-breaker slice), Slice C gold discovery,
`plan-c011-stale-rulings.md` (diagnosed, frozen), the miss-partition diagnostic
(largely mooted — retrieval barely predicts correctness). **Measurement gap:** no
held-out *pure-rules* eval set exists yet — needed to test whether the CR-rule RAG
earns its keep (RulesGuru is 98% card questions, so oracle text confounds it).

## ENVIRONMENT & GOTCHAS

- **API usage cap** — the account hit its Anthropic API usage limit 2026-07-24;
  **resets 2026-08-01** (Jon can raise it sooner). Until then, every live
  sonnet-5 eval/harness/product-arm run 400s. Subscription subagent labour is
  unaffected. This gates the combat-tool validation and any repro.
- ~17+ merged agent worktrees may remain; prune with `git worktree remove`. **KEEP
  `agent-a818653b08eb516a4`** (Scryfall, unmerged).
- Answer object field for the answer text is **`.text`**, not `.answer`.
- The RulesGuru API re-randomizes card/name text per refetch; `rulesguru_full.jsonl`
  is a frozen snapshot (stable on gold/level/tags, not byte-reproducible).
- Repro harness: `evals/_phase1_costtool_repro.py` writes a classification log +
  `_records.json` (per-round `stop_reason`/`content_types`/`tool_attached`/usage —
  the records are how cap-exhaustion vs the forced terminal round was diagnosed).
- Doc-metadata / token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md`.

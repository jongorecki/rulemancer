# Handoff — Rulemancer: tool era begun, reliability fix is task #1

**Replaces the prior handoff (git has every version). Written end of the
2026-07-24 session, which shipped the first agent tool, validated it, held-out-
tested the bot, and reframed the strategy around card-interaction reasoning.**

## THE ONE THING TO DO FIRST

**Fix the cost-tool-loop reliability defect, then continue the other tools.**
The `calculate_cost` tool works (c014/Trinisphere proven) but has a **~21%
empty-output failure rate on the tool path** (3 of 14 tool-fired generations)
against a **~0% non-tool baseline**. Report: `docs/report-costtool-validation.md`.
This is a blocker and it must be fixed BEFORE building the combat/layer tools —
they reuse the same tool-loop machinery (`answer.py`, the `TOOL_ROUND_CAP` inner
loop) and would inherit the defect.

Likely causes to investigate (systematic-debugging: reproduce first):
- the large `calculate_cost` tool-result payload (all the X-breakdowns) colliding
  with the final `messages.parse(..., output_format=Answer)` turn;
- the tool round-trip nesting inside the existing 2-attempt empty/degenerate-draw
  retry loop — the two retry layers may interact badly.
Reproduce by running c014 (or the 5 fired qids: rg289, rg897, rg1487, rg6636,
rg6916) through `RulesAgent.answer()` repeatedly and catching the empty-output
`stop_reason=error` case. Minor, fold in: the cost trigger fired on rg289, a
mana-PRODUCTION question where a cost calc is the wrong instrument — tighten
`_needs_cost_tool` to exclude production.

## HOW JON WORKS (unchanged, load-bearing)

- **Rule 0: plan before code.** Every `plan-*.md` is design-only until Jon rules.
- **USE SUBAGENTS.** This session ran ~18 in worktrees, disjoint file sets, no
  `git add -A`, evidence-not-assertions, STOP-and-report on a wrong spec.
- **Do-not-delegate:** eval questions, gold, grading verdicts, reading failures.
- **Judge is FROZEN** (`judge_bakeoff` prompt + gpt-5-mini). Never reword.
- **Never assert an MTG/model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Pricing via claude-api.
- **Billing:** Claude-labour on subscription subagents; API for eval/product arms.
  Jon funded console + OpenRouter for eval runs this session.
- Commit per slice on master, heredoc messages. `.venv/Scripts/python.exe`,
  `PYTHONIOENCODING=utf-8`. Jon runs the app on port 8000 — never bind/kill it.
- Worktree agents MUST set `PYTHONPATH=<worktree>\src` or they silently test the
  original repo's code. `data/raw/` and `evals/answers/` are gitignored (absent
  in worktrees).

## THE STRATEGY (three findings deep — this is the through-line)

This is a **card-interaction reasoning product.** Evidence:
1. Held-out (RulesGuru-150): sonnet **72%**, gpt-5-mini **57%**, monotonic by
   difficulty (`report-rulesguru-holdout.md`). First non-circular measurement.
2. Retrieval OVERFIT badly (recall@50: 100% on the tuned 31-set vs **63%**
   held-out) AND retrieval barely predicts correctness — the model answers card
   questions from **oracle text**, not retrieved CR rules.
3. Full import (1,409 Qs): only **9 are pure-rules** (`report-rulesguru-full-
   import.md`). Real questions are 99.4% card-interaction.

**Therefore the levers are REASONING (tools) and CARD-DATA quality — NOT abstract
rule-retrieval coverage.** That's why the tool era (cost, combat, layers) and the
Scryfall card-data work are the right investments, and why rerank/coverage
dropped to third priority.

## THE TOOL ROADMAP (the new core direction)

Pattern: the model orchestrates + reasons; deterministic tools own the exact
sub-computations it narrates correctly and then botches.

1. **cost calculator — SHIPPED** (merged, `da0449e`+`e763e91`). Validated:
   correct, safe trigger (0% FP), narrow (2.5%), but the reliability defect above.
2. **combat-damage assigner — PLANNED** (`plan-combat-damage-tool.md`). Next tool
   after the reliability fix. Motivated by c020 (Stampeding Rhino trample vs
   Vampire Nighthawk deathtouch); the plan designs out the "blocker's deathtouch
   is the wrong side" trap. ~164 combat-tagged questions in the full import as a
   validation set. CR text grounding deferred to build (data/raw absent in
   worktree — ground on master).
3. **state-based-action checker** and **layer-system resolver (CR 613)** — ideas,
   not yet planned. Layers targets the Corner Case tier (50%, the weakest).
4. **DO NOT build the keyword-reminder-text tool** — Jon and I concluded it's
   redundant with oracle text AND epistemically risky (simplified gloss crowds
   out the authoritative rule).
5. **Jon's idea — a question-CLASSIFICATION pipeline step** (route to the right
   tool + boost relevant rules). Worth planning. Design constraint: ADDITIVE
   (offer-more), never a restrictive router; deterministic-first (the cost
   trigger hit 0% FP, so heuristics can be clean). Not yet planned.

## WHAT SHIPPED THIS SESSION (all merged unless noted)

- v5 grid graded (fixes nothing on sonnet); `judge_v5.py`; `report-v5-grid.md`.
- Rewriter bakeoff: gpt-5-mini worse than haiku; `report-rewriter-bakeoff.md`.
- RulesGuru held-out eval + full 1,409 import + both reports.
- Retrieved-id logging on both runners; empty-rewrite crash fix.
- Tool-use spike (de-risked tool integration); cost calculator + validation.
- Two rulings in DECISIONS.md: injection ratified as production; RulesGuru gold
  canonical (its authors are certified judges — Jon is not).
- Plans written: cost-calc, combat, miss-partition, rerank, rulesguru-instrument
  (live); rulings-recall (SHELVED); citation-filter (mini-plan). c020 row added,
  c002 marked non-scoring.

## HELD / BLOCKED ON JON

- **Scryfall local-bulk + per-face + self-heal** (`worktree-agent-a818653b08eb-
  516a4`, ~8 commits, NOT merged). Complete + verified (302 tests, 29/29
  equivalence). Self-heal removes the catastrophe (missing db → live fallback +
  background rebuild). **Landing is a deliberate reconciliation** — the branch is
  ~15.8k lines behind master with an `answer.py` conflict (its fuzzy-fallback
  wiring vs master's cost-calc loop; keep BOTH). Master has no `scryfall.db` (first
  get_card self-heals → 180MB download; pre-build it or accept the download).
  Full steps in the Scryfall block below.
- **Jon's manual regrade** of the 42 sonnet/RulesGuru auto-judge disagreements
  (grading UI at `data/parsed/grading_rulesguru_disagreements.html`, builder
  `evals/build_rulesguru_disagreement_ui.py`, data `evals/rulesguru_disagreements_
  sonnet.json`). Jon was ~halfway at session end. **When he exports the
  `{id,verdict,note}` JSON, fold it into a corrected accuracy number** — every
  "correct" he finds raises the 72%.
- **The lever decisions** (v5 go/no-go, L2 generator) — his call; data delivered.

## STILL QUEUED (untouched)
`plan-sso.md`, `plan-deploy.md` (budget-breaker slice), Slice C gold discovery,
`plan-c011-stale-rulings.md` (diagnosed, frozen), the miss-partition diagnostic
(largely mooted by finding #2 — retrieval barely predicts correctness, so the
retrieval-vs-reasoning split is confounded on card questions).

## ENVIRONMENT & GOTCHAS

- ~17 merged agent worktrees may remain; prune with `git worktree remove`. KEEP
  `agent-a818653b08eb516a4` (Scryfall, unmerged).
- Answer object field for the answer text is **`.text`**, not `.answer` (bit the
  validation script once).
- `str.replace()` no-ops silently on a missed anchor — re-read + assert. Never
  pipe a long run through `| tail` (masks exit code — bit us twice).
- The RulesGuru API re-randomizes card/name text per refetch; `rulesguru_full.jsonl`
  is a frozen snapshot (stable on gold/level/tags, not byte-reproducible).
- Doc-metadata / token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md`.

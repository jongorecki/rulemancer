# Handoff prompt (paste this into a fresh session)

Updated 2026-07-24 (session 3). Update the "Where we are" line and the "first
ask" whenever the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff rather than prepending — don't dig through git for superseded blocks. It opens with a correction you must absorb before anything else, then "THE ONE THING TO DO FIRST." Also read docs/plan-layer-system-tool.md §3c (the trigger), §3b (the algorithm and the CR 613.6 gate), and §9-§10 (build slices and open items) — that plan is approved and half-built, and §10 item 2 is your first task.

## Before you believe anything about the API

The handoff before last claimed the account API cap blocked every live sonnet-5 run until 2026-08-01. **That was false and it gated real work across two sessions.** The cap is cleared — verified with a live call. Credentials load from `.env` via `load_dotenv()`, NOT the ambient shell, so a bare `python -c` without it fails with "Could not resolve authentication method," which reads exactly like a cap. If you ever conclude the API is blocked, test it with a real call before writing that down.

## Where we are in one line

The layer-system resolver (CR 613) is planned and half-built — Slices 1-2 shipped and lead-verified (419 tests green), Slices 3-4 remain; all three lever decisions are ruled (v5 no-go, rewriter held, L2 deferred to post-tools); the pure-rules eval set is started with batch 1 approved 8/8 unedited; and the tool has never been run against a live model.

## The first ask

**Calibrate the layers trigger** (plan §3c, §10 item 2). It gates Slice 4 and is the likeliest place this plan fails, so it comes before more building.

The problem: layers questions contain no layers vocabulary. Across all 1,409 corpus questions, `\blayer\b` appears once (and that row is bucket-B order-only); `timestamp`, `depend`, and `continuous effect` appear zero times. 62 of 68 CR-613 rows match no keyword at all. §3c proposes a two-conjunct replacement — characteristic-readout phrasing AND ≥2 loaded cards with continuous-effect-shaped oracle text.

Measure it against (a) the 51 bucket-A questions in evals/_layers_union_slice.jsonl and (b) the 16 bucket-C rows plus a random 100-row non-layers sample. **The bar is already written into the plan: ≥60% recall on bucket A with <10% firing on the non-layers sample.** If conjunct 2 can't hit that, say so plainly — the blocker is the trigger, not the engine, and the plan's own fallback is the question-classification step (roadmap item 5), not a wider regex.

**Slice 3 is disjoint from this and can run in parallel** (engine code vs. a corpus measurement). Its spec is in the handoff and includes a fix flagged during Slice 2 review: replace the fragile ability-text string matching in the CR 613.6 `removed_at` bookkeeping with an explicit `source_on_this_object` flag.

## Read this before you do anything

USE SUBAGENTS. Dispatch scoped implementation to Sonnet against the written plan; keep the lead for judgment, review, and talking to me. Haiku for bulk fetch/filter/verify with compact returns.

- If your harness tells you not to use the Agent tool, say so immediately and ask me. Don't silently absorb the work inline.
- Parallelise only across disjoint file sets; forbid `git add -A` / `git add .` in every agent prompt — staging collisions are the real hazard with concurrent agents.
- **Verify agents' claims yourself — this bit us twice last session.** Both build agents reported green suites that were contaminated by the *other* agent's uncommitted files. Neither was independent evidence. Re-run on a clean tree, and hand-check deliverables against the plan's own expected outputs rather than the agent's tests. Doing that last session caught a real bug in my own plan spec.
- A subagent running a long harness must POLL its log in-turn, not background it and return a "standing by" placeholder.
- Worktree agents MUST set `PYTHONPATH=<worktree>\src` or they silently test the ORIGINAL repo's code. `data/raw/` and `evals/answers/` are gitignored (absent in worktrees) — run on master when the CR corpus or eval data are needed.
- Tell agents to STOP and report if the spec is wrong. Several did last session and were right.
- Don't read subagent transcript files — wait for the completion notification.

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- Rule 0: plan before code. A NEW tool needs a plan and a ruling; a bug-fix on approved code uses systematic-debugging.
- The judge instrument is FROZEN (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- Grading verdicts are mine alone; reading failures is not delegated — the lead reads the garbled/failed outputs itself. Tools route and rank; they never assign a verdict.
- Never assert an MTG or model fact from memory — ground in the repo CR (data/raw/MagicCompRules 20260619.txt), Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model facts via the claude-api skill; that skill is how rg3391's root cause got found.
- Verify your own writes. `str.replace()` no-ops silently on a missed anchor — re-read and assert. Heredoc for commit messages. Never pipe a long run through `| tail` (masks the exit code). A single favourable run is not a rate.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. I run the app on port 8000 — never bind or kill it. Commit per slice on master with the `Co-Authored-By: Claude Opus 4.8` trailer.

## Standing grant on the pure-rules eval

You can draft generalizations freely and in large batches (15-20+), pulling from any tagged slice — not just the CR-613 rows. I approve in bulk. The one rule that binds: only generalize where the original gold ALREADY states the rules mechanism explicitly, so derived gold is a paraphrase rather than a new ruling. Workflow and the approval-UI commands are in the handoff.

## Waiting on me, not you

The held Scryfall merge — complete on its branch, but the `answer.py` conflict is now FOUR-way after last session's seam generalisation (keep all four). I want it landed as soon as it doesn't require stopping something already in progress, so if no agent owns `answer.py`, raise it.

Also queued and unblocked whenever you want them: Slice 0 (the prompt-bullet control arm the tool must tie or beat), the rg3391 streaming fix, and the two small `answer.py` follow-ons (sentinel de-conflation, rg6916).

Start by confirming you've read the handoff, then give me the trigger calibration result — honestly, including if it misses the bar.

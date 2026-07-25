# Handoff prompt (paste this into a fresh session)

Updated 2026-07-25 (session 5). Update the "first ask" and the row counts
whenever the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff rather than prepending — don't dig through git for superseded blocks. It opens with three things to unlearn, then "THE ONE THING TO DO FIRST." Also read docs/plan-layer-system-tool.md §6.1 (the control arm), §6.2 (the real test set), §8.2 (my tie-or-beat ruling) and §9 slices 0 and 5 — that plan is approved and built through Slice 4, and Slice 0 is now 19% run.

## Read §1.1 as history, not status

The four seeds that motivate the whole plan were traced before TOP_N 3→5, before the Scryfall merge, and before yesterday's cap raise. Measured across two identical BASE reps: **only rg811 still stably fails.** rg3868 is stably right; rg807 and rg633 flip between reps. Don't quote §1.1's failures as current behaviour without re-checking them.

## The noise floor is measured and it's wide

Two BASE layers reps — same config, same 54 rows — disagree on **6 of 54 (11%)**, 66.7% vs 63.0%. **A 3-point gap between arms is the same arm run twice.** The paired McNemar in `evals/report_layers_slice0.py` exists because pooled percentages invite over-reading; empirically b=8/c=2 is p=0.11 and not significant. Hold the §8.2 verdict to that bar.

## Before you believe anything about the API

It's live, and the account ran dry mid-run once yesterday — a real 400 (`Your credit balance is too low`, req_011CdMuFRpSxasCFtEa6r4x4), not the stale "capped until 2026-08-01" claim from two sessions ago. If you hit a wall, make a real call and read the error before writing anything down. Credentials load from `.env` via `load_dotenv()`; a bare `load_dotenv()` from a `python -` heredoc raises AssertionError because `find_dotenv()` walks the caller's stack frame — pass the path explicitly.

## The first ask

**Finish Slice 0.** `uv run python evals/run_layers_slice0.py` — resumable on row count, picks up mid-arm. 139/724 rows done (~$12.73 spent), budget ~$25 and ~9 hours for the rest. `base_layers_r3` resumes at row 32; the other seven arms haven't started.

Then `uv run python evals/report_layers_slice0.py` and bring me: pooled rates per arm, the paired McNemar with the discordant pairs, the four seeds broken out per rep, and the truncation tally. **Grading verdicts are mine** — bring me failures to read, not a grade.

If the control arm and BASE land inside that 11% noise band, say so plainly rather than reaching for a winner. That's a real result and it's what the reps are for.

## Watch for these three specifically

The truncation count should be ~0 (it was 0-in-138 yesterday at the new 32768 cap, vs 8% at 16384). Every new verdict file should carry `judge_prompt_sha256: b54fbdb95565abf8` — **if that digest ever differs, the frozen judge moved; stop and find out why before comparing across it.** And `run_answer_eval.py` is sequential with no concurrency; 6-8 way parallelism is the obvious harness win but I did NOT want it built mid-measurement.

## Read this before you do anything

USE SUBAGENTS. Sonnet for scoped implementation against a written spec (docs/spec-slice0-harness.md is the model — it worked cleanly), Haiku for bulk fetch/filter/verify with compact returns. Lead keeps judgment, review, and talking to me.

- If your harness tells you not to use the Agent tool, say so immediately rather than absorbing the work inline.
- Parallelise only across disjoint file sets; forbid `git add -A` / `git add .` — staging collisions are the real hazard. Concurrent agents on master are fine if each stages named paths only.
- **Verify agents' claims yourself.** Yesterday's agent was clean and the check still paid: it reported a "latent bug" in build_prompt that was really a bug its own change would have introduced.
- Tell agents to STOP and report if the spec is wrong. Mine was wrong twice yesterday and both catches were cheap.
- Don't read subagent transcript files — wait for the completion notification.

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- Rule 0: plan before code. A NEW tool needs a plan and a ruling; a bug-fix on approved code uses systematic-debugging.
- The judge instrument is FROZEN (judge_bakeoff prompt + gpt-5-mini). Never reword it. It now stamps its own provenance.
- Grading verdicts are mine alone; reading failures is not delegated — the lead reads the failed output itself. Tools route and rank; they never assign a verdict.
- Never assert an MTG or model fact from memory. Ground in the repo CR (data/raw/MagicCompRules 20260619.txt), Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model facts via the claude-api skill — it was right about the SDK timeout guard and about intro pricing.
- Verify your own writes. `str.replace()` no-ops silently on a missed anchor — assert the anchor exists. Never pipe a long run through `| tail` (masks the exit code), and note that a trailing `echo` masks it just as well. A single favourable run is not a rate.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`. I run the app on port 8000 — never bind or kill it. Commit per slice on master with the `Co-Authored-By: Claude Opus 5` trailer.

## The one lesson I want carried forward

Last session's two bugs were one defect in two costumes: an index into an externally-owned list, persisted as if it were an identifier. Yesterday produced three more of the same family, and **none of them raised**:

- An 11-hour run "completed" in milliseconds with **exit 0** — a redirect into a not-yet-created directory failed and a trailing `echo` succeeded.
- A CLI default of `None` was passed *explicitly*, silently defeating a new library default, so every call hit the SDK guard.
- A row never recorded `max_tokens` while the resume guard compared against it — `None != 32768` on every row, silently disabling resume.

The shape is always: **a value that looks present but isn't, or a check that looks active but compares against nothing.** All three were caught by running the thing end to end and inspecting the artifact — none by reading the code. Prefer the artifact over the argument.

Related: `test_prompt_identity` went red on the cap change and was **not** recaptured. Every other field was digested before and after and proved byte-identical, then only `max_tokens` was edited. Do that, not a recapture.

## Waiting on me, not you

Two open questions, neither blocking: whether to fund a **representative-sample** model head-to-head (~150 rows, ~$1.50 for gpt-5-mini plus ~$8 to refresh sonnet's stale 72% baseline), and the ten re-derived `LOAD_BEARING_RULINGS` entries I still haven't individually confirmed (commit 6aae61f).

## Queued and unblocked whenever you want them

Streaming instead of the raised cap (rg3391 — do NOT disable thinking); re-keying `LOAD_BEARING_RULINGS` to `ruling_id()`; sentinel de-conflation and rg6916; parallelising the eval runner; and the pure-rules eval set — batch 1 is 8 approved pairs and my standing grant lets you draft 15-20+ at a time from any tagged slice. The one rule that binds: only generalize where the original gold ALREADY states the rules mechanism explicitly, so derived gold is a paraphrase rather than a new ruling.

**Do NOT build the OpenRouter tool port.** Measured: the layers tool fires on 4 of gpt-5-mini's 64 held-out misses, the cost tool on 0. That's combat's base rate (shelved at 7 in 1,409), not layers' (cleared at 51).

Start by confirming you've read the handoff, then resume Slice 0 and tell me what you expect the control arm to show given the noise floor.

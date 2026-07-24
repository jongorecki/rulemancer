# Handoff prompt (paste this into a fresh session)

Updated 2026-07-24 (session 4). Update the "Where we are" line and the "first
ask" whenever the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff rather than prepending — don't dig through git for superseded blocks. It opens with three things to unlearn, then "THE ONE THING TO DO FIRST." Also read docs/plan-layer-system-tool.md §6.1 (the control arm), §6.2 (the real test set), §8.2 (my tie-or-beat ruling) and §9 slices 0 and 5 — that plan is approved and is now built through Slice 4.

## Before you believe anything about the API

The API is live. I re-verified it last session with a real `claude-sonnet-5` call (15 in / 3 out, `stop_reason=end_turn`). Credentials load from `.env` via `load_dotenv()`, NOT the ambient shell — and **a bare `load_dotenv()` from a `python -` heredoc raises `AssertionError`**, because `find_dotenv()` walks the caller's stack frame and there isn't one. Pass the path explicitly: `load_dotenv("D:/Job_hunt/mtg-rules-bot/.env")`. That failure looks like neither auth nor a cap; don't misread it as either.

Two sessions ago a stale "the account is capped until 2026-08-01" claim gated real work across two sessions. Don't recreate that. If you ever conclude the API is blocked, test it with a real call before writing it down.

## Where we are in one line

The layer-system resolver (CR 613) is **fully built — Slices 1-4 done, 519 tests green on a clean tree** — the trigger is calibrated and verified against the *shipped* function (77.8% bucket-A recall, 5.1% firing), the held Scryfall merge is landed, and two production bugs caused by positional identifiers were found and fixed; **the tool has still never been run against a live model.**

## The first ask

**Slice 0, then Slice 5.** Everything about this tool so far is offline evidence.

Slice 0 is the control arm — one prompt variant with CR 613.6 + 611.3a quoted, run on the four seeds *and* a non-layers regression sample, several reps, aggregated. Per my §8.2 ruling **the tool has to tie or beat it**, on win-rate *and* regression, because a system-prompt bullet is a global change while the tool only fires when triggered. Do it first: it's nearly free and it's the bar.

Then Slice 5: tool-on vs tool-off over the COMPUTE bucket plus the regression arm, frozen judge, compared against Slice 0 on both measures. Record the round-usage histogram while you're there — it's free with the same run and it settles whether `TOOL_ROUND_CAP` is right with data rather than assumption.

Use `evals/_layers_buckets.json` for bucket membership (A=54, B=1, C=13). The plan's "51" was a hand-count that was never persisted; the file is the durable record.

**If the tool loses to the control arm, say so plainly.** That's a real possible outcome and it's the whole reason the control arm exists.

## Read this before you do anything

USE SUBAGENTS. Dispatch scoped implementation to Sonnet against the written plan; keep the lead for judgment, review, and talking to me. Haiku for bulk fetch/filter/verify with compact returns.

- If your harness tells you not to use the Agent tool, say so immediately and ask me. Don't silently absorb the work inline.
- Parallelise only across disjoint file sets; forbid `git add -A` / `git add .` in every agent prompt — staging collisions are the real hazard. Concurrent agents on master are fine if each stages named paths only.
- **Verify agents' claims yourself.** Last session an agent called a red test "unrelated, pre-existing." It was unrelated to its change and it was *not* pre-existing — the same suite had been green an hour earlier. Chasing it found a live production bug. Both times a suite claim got checked, the check paid.
- A subagent running a long harness must POLL its log in-turn, not background it and return a "standing by" placeholder.
- Worktree agents MUST set `PYTHONPATH=<worktree>\src` or they silently test the ORIGINAL repo's code. `data/raw/` and `evals/answers/` are gitignored (absent in worktrees) — run on master when the CR corpus or eval data are needed.
- Tell agents to STOP and report if the spec is wrong. Several did last session and were right.
- Don't read subagent transcript files — wait for the completion notification.

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- Rule 0: plan before code. A NEW tool needs a plan and a ruling; a bug-fix on approved code uses systematic-debugging.
- The judge instrument is FROZEN (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- Grading verdicts are mine alone; reading failures is not delegated — the lead reads the garbled/failed outputs itself. Tools route and rank; they never assign a verdict.
- Never assert an MTG or model fact from memory. Ground in the repo CR (data/raw/MagicCompRules 20260619.txt), Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model facts via the claude-api skill.
- Verify your own writes. `str.replace()` no-ops silently on a missed anchor — re-read and assert. Heredoc for commit messages. Never pipe a long run through `| tail` (masks the exit code). A single favourable run is not a rate.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. I run the app on port 8000 — never bind or kill it. Commit per slice on master with the `Co-Authored-By: Claude Opus 4.8` trailer.

## The one lesson I want carried forward

Both bugs last session were the same defect wearing different clothes: **an index into an externally-owned list, persisted as if it were an identifier.** The Scryfall merge reordered each card's rulings, and everything keyed on position silently pointed at the wrong text — 92% of the ruling embedding cache, and 100% of the eval gold. Nothing crashed either time; the cache one still returned plausible rulings with plausible cosines.

What caught it was a byte-identity fixture, the kind of test people delete as brittle. So: **never quiet a red identity fixture by recapturing it until you've proved the delta is fully explained.** Recapturing first would have buried a live bug.

## Waiting on me, not you

Ten re-derived `LOAD_BEARING_RULINGS` entries I haven't individually confirmed (before→after is in commit `6aae61f` and in inline comments next to each). Raise them and I'll look.

## Queued and unblocked whenever you want them

Re-keying `LOAD_BEARING_RULINGS` to `ruling_id()` so it can't rot again; the rg3391 streaming fix (stream — don't just raise `max_tokens`, and do NOT disable thinking); the two small `answer.py` follow-ons (sentinel de-conflation, rg6916); and more pure-rules eval pairs — you can draft 15-20+ at a time from any tagged slice and I approve in bulk. The one rule that binds: only generalize where the original gold ALREADY states the rules mechanism explicitly, so derived gold is a paraphrase rather than a new ruling.

Start by confirming you've read the handoff, then give me the Slice 0 control-arm result — honestly, including if it looks like the tool will struggle to beat it.

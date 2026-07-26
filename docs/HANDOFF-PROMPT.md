# Handoff prompt (paste this into a fresh session)

Updated 2026-07-26 (session 10). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at
D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens
with seven things to unlearn, because last session found that every instrument
used to measure retrieval was broken.

## The headline findings, so you don't re-derive them

**Answer accuracy and retrieval accuracy are different instruments.** The judge
compares our answer to the reference answer and never reads `q.gold` or
`q.match`. Everything found last session hit retrieval measurement only. **Every
published accuracy number survives. Every published retrieval number does not.**

**~60% of the corpus cannot measure retrieval at all.** A no-rules control arm
(90 rows, all five levels) answered with zero rules in context and got
**59.5% corpus-weighted** correct anyway. Concentrated at the easy end: L0 86.7%,
L1 70.0%, L2 40.0%, L3 50.0%, Corner 30.0%. Evaluate retrieval on the hard
subset; corpus-wide measurement halves the signal.

**`hit_at()` over-credits retrieval ~3x.** The full 1,409-question corpus is
`match: "any"` on every row, with 745 rows (52.9%) listing 2+ gold rules, max 10.
Real coverage on the hard arms is 17.4% against a reported 48.1%.

**10.9% of the corpus has no gold rules at all** (153 rows; 33% of L0).

**The full-run projection is now 82.8% [78.2-86.6%] at 100% coverage, $73-91.**
The L0 arm (97.1%, 207 questions) closed the last untested level and nearly
halved the interval. But L0's high score is mostly the model's own knowledge —
86.7% of L0 is confounded.

**The gold miner is ~half reproducible.** Same prompt, same 50 questions, twice:
0.4867 mean Jaccard.

## The first ask

**Gold is priority one — Jon's explicit ruling. He has also ruled out
hand-grading at scale, so every step must be machine-decidable.**

1. **Necessity (leave-one-out) test on the 38-question inflation worklist**
   (`evals/coverage_backfill.json`). **Restrict to rows the control showed are
   NOT confounded** — that omission cost the OR-group run 5 of its 21 verdicts.
2. **Fix the 153 empty-gold rows.**
3. **Rule on the 54+1 mis-encoded conjunctions**, apply, re-run the coverage
   backfill.
4. **Then decide the full run.**

Open the dashboard first — `evals/metrics_history.html`, rebuild with
`python evals/build_metrics_history.py`. It carries the decision panel, the new
retrieval-coverage section, what is unresolved, and the roadmap with status, cost
and dependencies.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's **Claude Max subscription**. But
`mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any Python in this repo that
constructs an Anthropic client bills **API credits** — a separate pool. Standing
preference: batch Claude-labor onto subscription subagents, keep credits for eval
arms. Anything spending credits gets an explicit ask with a hard ceiling and a
pilot checkpoint, however small. **An arm's cost per question does not transfer
to a different kind of arm** — removing rules doubled-to-tripled output tokens,
and output is 5x the price of input.

## Read this before you do anything

**Explain things properly.** Jon: *"you just need to explain things a little
better so I can understand and be a partner here instead of an observer."*
Define jargon at first use, lead with what a thing means, show examples.

- **Rule 0: plan before code.** A new tool needs a spec and a ruling.
- **Complete $0 work without asking** — but split local compute (genuinely free)
  from "$0 in credits" (free only on a subscription subagent).
- **Verify agents' claims against the underlying data before relaying them.**
  Last session that caught five separate errors, every one of them sound
  arithmetic with a wrong sentence wrapped around it.
- **Subagent deliverables must land in the repo, never the session scratchpad.**
- **Never run the full pytest suite while an eval arm is running** — it races
  with `evals/answers/_progress/` and gives false failures.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. For pricing import
  `rulesagent.pricing` — do NOT load the claude-api skill.
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.**
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON with
  `encoding="utf-8"`. Suite is `uv run pytest` (**929 passing**). Commit per
  slice on master with the `Co-Authored-By: Claude Opus 5` trailer.

## The one lesson to carry forward

**An instrument that has never been tested is not a measurement, it is an
assumption with a number attached.**

Gold rule sets were asserted by a miner and treated as truth from the moment they
were written. Nothing checked whether the listed rules were the ones a question
needs, whether they were all required or any one sufficed, whether the miner
would produce the same set twice, or whether the question needed rules at all.
Four defects, all downstream of that single omission, all invisible because the
numbers looked reasonable.

The corollary: **a confound in one experiment can invalidate a different
experiment that never mentioned it.** The OR-group test was designed, costed, run
and reported without anyone connecting it to the control arm running in parallel
— and the control decided which of its verdicts meant anything.

Start by confirming you've read the handoff, then open the dashboard.

# Handoff prompt (paste this into a fresh session)

Updated 2026-07-26 (session 8). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens
with four things to unlearn, then what shipped.

## The headline findings, so you don't re-derive them

**Both approved switches are applied and Jon has confirmed them.** `GEN_MODEL` is
`claude-opus-5` with `GEN_EFFORT="low"`, and `REWRITE_N` is 3. His words: *"opus
low is the meta moving forward."* Don't re-litigate either.

**A third of the derivability "failures" were the judge, not the bot.** Jon
graded the 15; five are rows where both answers say the same thing and the judge
called it a disagreement. The real "we got it wrong" count is 5, not 11 — and
the entire "gold was incomplete" category (4 rows) dissolves, taking the 92.7%
ceiling and the single-id heuristic with it.

**The judge is also nondeterministic.** Same answers, same frozen instrument:
1 verdict flip per 100 rows, and 100/100 entries with different reasoning prose.
A published accuracy must name its judging run.

**Cost is not one number.** opus-low is 24.8% cheaper on hard questions and 9.1%
*more expensive* on easy ones until sonnet's intro pricing ends 2026-08-31.
Opus at `effort=low` emits a flat ~1,200 output tokens whatever the difficulty;
sonnet's scales with the problem. Token ratios alone do not establish cost —
price it.

## The first ask

**1. Apply the 5-row rescore Jon approved** (`rg7215`, `rg549`, `rg1718`,
`rg851`, `rg811` -> correct) **and correct `docs/results-derivability.md`**:
withdraw the incomplete-gold category, the 92.7% ceiling, and the "single-id rows
are the risk group" heuristic; replace with the 93.3-95.3% range and the class
breakdown in the handoff.

**2. Write `docs/results-gold-audit-batch1.md`.** ⚠️ `results-easy-regression.md`
already links this file and it does not exist — a dangling reference left by the
last session. Fix it in the same pass.

**3. Build weighted scoring.** Jon ruled: **flat across L0-L3, Corner Case 0.5.**
The spec (`docs/spec-weighted-scoring.md`) predates the ruling and still frames
it as a recommendation — it is decided. Zero API; it is a re-scoring pass over
`by_level_counts` already present in every verdict file.

Then: the out-of-range ruling-citation bug (3 of 15 rows), and measuring the
judge's false-negative rate — that last one gates how much to trust every
accuracy number in the repo, including the ones written yesterday.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's **Claude Max subscription**. But
`mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any Python in this repo that
constructs an Anthropic client bills **API credits** — a separate pool. Mining is
subagent work; eval runs are API credits. Voyage embeddings are a third pool
(voyage-4-large, $0.12/M, and query embedding is ~8 microdollars per question —
never the thing to optimise).

## Read this before you do anything

**Explain things properly.** Jon: *"you just need to explain things a little
better so I can understand and be a partner here instead of an observer."*
Define jargon at first use, lead with what a thing means, show examples.

- **Rule 0: plan before code.** A new tool needs a spec and a ruling.
- **USE SUBAGENTS** for bulk work — but if your harness forbids the Agent tool
  unless Jon asks (it did last session), **say so immediately** rather than
  quietly absorbing the work.
- **Verify claims yourself, and verify the right thing.** Structural
  verification is not quality verification.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. **Model IDs and pricing
  come from the claude-api skill** — last session's cost correction depended on it.
- **Verify by rendering** for UI. Serve on a scratch port; **Jon runs the app on
  port 8000 — never bind or kill it.**
- Never pipe a long run through `| tail`. PowerShell `*>` buffers until exit, so
  a running job's log is 0 bytes and looks dead — check the output artifact.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is
  `uv run pytest` (**582 passing**). Commit per slice on master with the
  `Co-Authored-By: Claude Opus 5` trailer.

## The one lesson to carry forward

Last session's defect was *a claim inherited and repeated without being checked*.
This session's is **a number is a snapshot of a file at a time, not a fact**: a
results doc recorded 76.0%, the verdict file was rewritten between the read and
the commit, and the commit shipped a doc and a data file that disagreed with each
other. Re-read a number from its file at the moment you publish it, and record
what produced it.

The corollary: **the eval instrument is itself an experiment subject.** The judge
was treated as fixed because its prompt is frozen. Frozen prompt does not mean
deterministic output, and it does not mean correct output — both turned out false
in one afternoon.

Start by confirming you've read the handoff, then do the rescore and the
derivability correction.

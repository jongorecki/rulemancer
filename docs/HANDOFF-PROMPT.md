# Handoff prompt (paste this into a fresh session)

Updated 2026-07-26 (session 9). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at
D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens
with five things to unlearn, because last session published a correction that was
itself wrong and had to be reversed.

## The headline findings, so you don't re-derive them

**Arm B is 91.3%, not 93.3%.** 137/150, two overturns
(`evals/verdicts_derivability_B_human.json`). **93.3% is now the ceiling, not the
score.** Jon adjudicated three disputed rows on 2026-07-26 and the RulesGuru gold
was correct on all three.

**The judge is less broken than it looked.** Its false-negative rate on the
flagged side is **2 of 15, not 5**. Its false-positive rate — the direction
nobody had ever checked — is **≤4.4%** and that is an upper bound, not a point
estimate (`docs/results-judge-error-rate.md`). It remains nondeterministic:
~1 verdict flip per 100 rows, so a published accuracy must name its judging run.

**Retrieval is the bottleneck, with direct causal evidence.** Three questions
(`rg7215`, `rg549`, `rg811`) were answered *wrong* with the gold rules alone and
*right* once retrieval supplied the missing rule. The "gold was incomplete"
category, the 93.3% ceiling and the single-id heuristic were withdrawn
mid-session and are all **reinstated**.

**opus-5/low dominates sonnet-5** on both benchmark sets — +13.0pp easy, +9.3pp
hard, while costing 27% and 50% less per question. Both gaps clear their noise
floors. Sonnet emits ~3× the output tokens.

**A full RulesGuru run over all 1,409 questions costs $73–91** at a projected
80.3% [71.7–86.8%]. Cost is not the blocker.

## The first ask

**1. Run an L0-only pipeline arm** (~$11, 207 questions). **Zero L0 questions
have ever gone through the pipeline** — 0 rows across all 10 pipeline arms. It is
~15% of the corpus and its easiest slice, so the 80.3% projection likely reads
low. This is the cheapest way to shrink the interval before committing to the
full run.

**2. Batch 2 of the gold audit** (`rg1802`, `rg4440`, `rg5628`, plus
h2h/costbase; build with `--provenance run`). **Grade the bottom line before the
reasoning** — batch 1's three misgrades all had strong, well-cited reasoning
attached to the wrong conclusion, and the grading followed the reasoning.

**3. Then decide the full run.**

Open the dashboard first — `evals/metrics_history.html`, rebuild with
`python evals/build_metrics_history.py`. It carries the decision panel, what is
unresolved and what would change it, and the roadmap with status, cost and
dependencies for everything planned.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's **Claude Max subscription**. But
`mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any Python in this repo that
constructs an Anthropic client bills **API credits** — a separate pool. Jon's
standing preference: batch Claude-labor onto subscription subagents and keep the
credits for eval arms. Voyage embeddings are a third pool (query embedding is
~8 microdollars per question — never the thing to optimise).

## Read this before you do anything

**Explain things properly.** Jon: *"you just need to explain things a little
better so I can understand and be a partner here instead of an observer."*
Define jargon at first use, lead with what a thing means, show examples.

- **Rule 0: plan before code.** A new tool needs a spec and a ruling.
- **Subagents:** Jon authorised parallel agents last session. If your harness
  forbids the Agent tool unless he asks, **say so immediately** rather than
  quietly absorbing the work.
- **Verify agents' claims yourself against the underlying data.** Every agent
  result last session was checked before being relayed; two had real errors in
  framing that only surfaced that way.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. **Model IDs and pricing
  come from the claude-api skill.**
- **Verify by rendering** for UI. Serve on a scratch port; **Jon runs the app on
  port 8000 — never bind or kill it.**
- Never pipe a long run through `| tail`. PowerShell `*>` buffers until exit, so
  a running job's log is 0 bytes and looks dead — check the output artifact.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is
  `uv run pytest` (**645 passing**). Commit per slice on master with the
  `Co-Authored-By: Claude Opus 5` trailer.

## The one lesson to carry forward

**Anything used as ground truth is an experiment subject, including a person.**

Last session audited the LLM judge, got human labels back, and rewrote a
published result on those labels *without checking them against the answer text*
— applying none of its rigour to the instrument that had just replaced the one it
was auditing. Three of five labels were wrong; the correction was wrong; the
original result had been right.

The corollary: when the thing you measure *with* changes — judge to human, one
question set to another, one arm kind to another — the safeguards do not follow
it automatically. You have to move them. That failure recurred three times last
session in three different costumes.

Start by confirming you've read the handoff, then open the dashboard.

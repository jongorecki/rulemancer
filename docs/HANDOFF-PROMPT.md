# Handoff prompt (paste this into a fresh session)

Updated 2026-07-26 (session 7). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens
with three things to unlearn, then the two switches Jon has already approved.

## The headline findings, so you don't re-derive them

**Retrieval is the bottleneck, not reasoning.** Hand the model only the gold
rules and it answers **90%** (135/150). Production sits at ~75-82%. Repairing the
4 rows where gold was incomplete puts the ceiling at **92.7%**; 11 questions
(7.3%) are unreachable by any retrieval work at all. This is the first
measurement separating retrieval failure from reasoning failure, and it inverts
an assumption made earlier the same session.

**The prior handoff's model comparison was measured on two different question
sets.** Sonnet's 63.0/66.7% is n=54; opus's 75.0% is n=68. "The same bucket" was
false. On the shared 54, opus-no-rewriter is 72.2%.

**Mined gold is a draw, not a fact.** Two runs on identical questions produce
identical gold on 26% of rows, mean overlap 0.54.

## The first ask

**Apply the two switches Jon approved 2026-07-26**, both one-line constants in
`src/rulesagent/generate/answer.py`:

1. `GEN_MODEL` -> `"claude-opus-5"` with `effort="low"`. Controlled head-to-head
   on the same 54 questions, same rewriter/ruling/system version, same frozen
   judge: **opus-low 75.9% vs sonnet 64.8% mean, +11.1pp**, both opus reps above
   both sonnet reps, paired +9/-4. 23% cheaper today, ~48% after sonnet's intro
   pricing ends 2026-08-31. Jon's framing: a **cost decision with supporting
   quality evidence**, not a quality claim that happens to save money.
2. `REWRITE_N` 1 -> 3. +3.8pp on `groups`@15 over production, paired +10/-4, for
   +$0.0005/question. Below the 7pp bar that was fixed before the run — Jon
   overrode a null result because the change is nearly free and revertible.

Then **finish the easy-set regression check.** Generation was nearly done when
the session ended: the opus arms and the completed hard rep2 are all 50/50 and
54/54 on disk; the two sonnet arms were still running. Judging of the opus arms
was launched and deferred — **check whether the verdict files already exist
before re-running the judge.** Exact filenames and the command are in the
handoff.

No regression confirms the switch; a regression doesn't reverse it (Jon decided
on cost) but tells you to watch simple questions. Sonnet's within-arm noise on
the hard set was 6 of 54 (11%), so a gap smaller than that is not a finding.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's **Claude Max subscription**. But
`mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any Python in this repo that
constructs an Anthropic client bills **API credits** — a separate pool. Mining is
subagent work; eval runs are API credits. An account usage cap was hit this
session mid-run and Jon lifted it; roughly $17 of the allocation remained.

## Read this before you do anything

**Explain things properly.** Jon, 2026-07-26: *"you get a little over my head on
things you're not explaining... you just need to explain things a little better
so I can understand and be a partner here instead of an observer."* Define jargon
at first use, lead with what a thing means before what it is, show concrete
examples.

USE SUBAGENTS. Opus on the subscription for mining/analysis, Sonnet for scoped
implementation against a written spec. If your harness forbids the Agent tool,
say so immediately rather than absorbing the work inline.

- **Verify agents' claims yourself** — it caught real things every time.
- **But verify the right thing.** Nine mining batches passed every structural
  check while their OR-groups meant the wrong thing. Structural verification is
  not quality verification.
- Don't read subagent transcript files — wait for the completion notification.
- Never pipe a long run through `| tail` / `Select-Object -First`: it closes the
  pipe and reports a false non-zero exit. PowerShell `*>` buffers until exit, so
  a running job's log is 0 bytes and looks dead — check the output artifact.
- Rule 0: plan before code. A NEW tool needs a spec and a ruling.
- The judge instrument is FROZEN (judge_bakeoff prompt + gpt-5-mini, digest
  `b54fbdb95565abf8`). Never reword it. It runs through OpenRouter, so it is
  unaffected by Anthropic limits.
- Never assert an MTG or model fact from memory. Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is
  `uv run pytest` (573 passing). Commit per slice on master with the
  `Co-Authored-By: Claude Opus 5` trailer.
- Jon runs the app on port 8000 — never bind or kill it.

## The one lesson to carry forward

Last session's defect was *a value that looks like an identity but is really a
position*. This session's is **a claim inherited and repeated without being
checked**: "the same bucket" (false, and repeated all session), the miner prompt
edited mid-run because it looked like prose rather than a parameter, and "zero
violations" which was true but narrower than it sounded. Numbers arrive with
claims attached about how they were produced, and those claims are exactly as
checkable as the numbers. Open the file.

## Ruled by Jon, cleared to act

- **Both switches above — APPROVED.**
- **Placement pass defaults to NEVER PROMOTE.** ~800 existing gold ids the miners
  didn't rediscover need homes: alternative inside the group covering their step,
  or kept as not-load-bearing. Anything an agent thinks deserves its own required
  group is **flagged to Jon, not applied** — the old flat `any` label already
  declared that id sufficient alone, so promoting it to required contradicts its
  own label. Record in DECISIONS.md when built.
- **Security work added to the plan** (Jon, 2026-07-26): prompt-injection
  hardening, the cost guard already specified in `docs/plan-deploy.md` §2 but
  never built, and authentication (`TODO-SSO.md`).
- **`docs/spec-cr-update-check.md` — APPROVED**, still unbuilt. Zero API,
  self-testing, completely independent of everything else.

## Still waiting on Jon

Whether to double-mine for stability (0.54 run-to-run overlap), whether to
re-pass v3's 105 conjunctive OR-groups (would move published recall numbers
down), and whether to resume mining as-is (809 rows left, ~2.4M subscription
tokens).

Start by confirming you've read the handoff, then apply the two switches and
collect the in-flight run.

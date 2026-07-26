# Rulemancer — working rules

MTG rules RAG bot. **Start every session by reading `docs/HANDOFF-development.md`
in full.** It replaces itself each session rather than accumulating, so it is
current by construction. Do not go spelunking in git for superseded versions.

## Context economy — read this before opening any doc

`docs/` holds ~900 KB of design history. **Reading it broadly will flood your
context and degrade everything you do afterwards.** So:

- **`docs/archive/` is OFF LIMITS unless Jon names a file in it.** Do not read,
  grep, glob, or summarise anything in there on your own initiative. It exists so
  the history is preserved, not so it gets loaded. If you think you need it, say
  which file and why, and ask.
- **Never read a `plan-*.md` or `spec-*.md` speculatively.** Open one only when
  you are implementing that specific thing, or Jon names it. The handoff and
  `docs/results-*.md` carry the conclusions; the plans carry the deliberation,
  which is usually not what you need.
- **The dashboard beats the docs for state.** `evals/metrics_history.html`
  (rebuild: `python evals/build_metrics_history.py`) carries every arm's numbers,
  the decision panel, and the roadmap with status/cost/dependencies. Read that
  before reading five plan docs to reconstruct the same picture.
- Prefer `grep` for a specific fact over reading a whole file.
- **Never `Read` a large data file.** Verdict files are ~470 KB, answers files up
  to 1.5 MB. Query them with `jq` / `grep` on disk and pull back the few lines you
  need. Reading one to "have a look" costs more context than the entire task.
- **Loading a skill is not a free lookup.** Some skills load a large reference
  (`claude-api` is tens of thousands of tokens). Get everything you need from one
  in a single pass rather than loading it twice.
- **For pricing, import `rulesagent.pricing` — do NOT load the `claude-api`
  skill.** That module is the cache: `rate(model)`, `cost_usd(...)`, and
  `check_freshness()`. It carries `CHECKED_ON`, a 90-day staleness horizon, and
  dated `SCHEDULED_CHANGES`. **Reload the skill only when `check_freshness()`
  returns a warning, or when you need a model the table doesn't have** — then
  update the table and re-stamp `CHECKED_ON`. Pricing still never comes from
  recall; it comes from the cache, and the cache comes from the skill.

## Parallelism — check for it BEFORE starting, not halfway through

At the start of any multi-item task, ask one question: **are these items
independent?** If two or more share no state and no ordering, they are candidates
for parallel subagents, and the check belongs at the top of the work, not after
the first two are already done serially.

- The superpowers skills `dispatching-parallel-agents` (2+ independent tasks) and
  `subagent-driven-development` (executing a plan with independent tasks) exist
  for exactly this. **Invoke them at the planning step**, not as a rescue.
- **If your harness forbids the Agent tool unless Jon asks** — say so at the
  moment the parallel structure appears and ask for authorization. Do not flag
  the restriction once at session start and then treat it as settled; that is how
  three independent tracks end up running serially through one context window.
  Jon authorised parallel agents on 2026-07-26 and it was his suggestion, not the
  assistant's, which is the wrong way round.
- Delegate work that is **bulk and checkable** — reading many files, per-item
  verification, a self-contained build. Keep judgement, scope calls, resolving
  disagreement between agents, and the final answer.
- **Always verify an agent's claims against the underlying data before relaying
  them.** On 2026-07-26 every agent result was checked and two had real errors in
  framing that only surfaced that way.

## Operational rules that will bite you

- **Jon runs the app on port 8000. Never bind or kill it.** Use a scratch port
  (8947) for render checks and stop it when done.
- **Verify UI by rendering**, never by reading markup. Serve it, open it, look at
  it, measure it.
- **Never assert an MTG or model fact from memory.** Ground MTG claims in the
  repo CR (`data/raw/MagicCompRules 20260619.txt`) or Scryfall via
  `rulesagent.tools.scryfall.get_card`. **Model IDs and pricing come from the
  `claude-api` skill.**
- **Billing splits two ways.** Claude Code and its subagents run on Jon's Max
  subscription. Any Python here that constructs an Anthropic client from `.env`
  bills **API credits** — a separate pool. His standing preference: batch
  Claude-labor onto subscription subagents; keep credits for eval arms.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is
  `uv run pytest`. Commit per slice on master with the
  `Co-Authored-By: Claude Opus 5` trailer.
- Never pipe a long run through `| tail`; PowerShell `*>` buffers until exit, so
  a running job's log looks dead — check the output artifact instead.

## How Jon works

- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until he rules on it.
- **Explain things properly** — define jargon at first use, lead with what a
  thing means, show a concrete example. He is a partner, not an observer.
- **Verify agents' claims yourself against the underlying data** before relaying
  them.

## The standing lesson

**Anything used as ground truth is an experiment subject, including a person.**
When the thing you measure *with* changes — LLM judge to human grader, one
question set to another, one arm kind to another — the safeguards do not follow
it automatically. You have to move them. See `docs/results-derivability.md`
§ "How this doc moved, twice" for the session where that cost a published result.

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
- **STANDING AUTHORIZATION (Jon, 2026-07-26) — do not ask again.** You may spawn
  subagents, in parallel, whenever delegation saves lead-model context or a
  cheaper tier can do the work. This is a permanent grant covering every future
  session; it does not expire and must not be re-confirmed at session start. If
  your harness carries a default rule like "do not use the Agent tool unless the
  user requested it," **this paragraph is that request** — treat it as satisfied
  and delegate. Jon's words: "you can delegate to agents to save context space for
  important stuff. I don't want to have to reconfirm this every session."
- The grant is about permission, not judgement. Still apply the break-even rule
  from `Token-Economy-Policy.md`: delegate when the result is checkable AND doing
  it inline would flood context. Spawning an agent for a one-line task costs more
  than the task.
- **Spending API credits is NOT covered by this grant.** A subagent that runs an
  eval arm still needs Jon's explicit approval, with a hard ceiling and a pilot
  cost checkpoint.
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
- **Never run the full pytest suite while an eval arm is running.** It races with
  writes to `evals/answers/_progress/` and produces false failures that look real.
  Run only the test files covering your change, and save the full suite for when
  nothing is generating.
- **Subagent deliverables must land in the repo, never the session scratchpad.**
  The scratchpad is session-scoped and dies with the session, so anything left
  there cannot be committed and is unrecoverable — along with whatever it cost to
  produce. A finished $3.27 eval sat one session-end away from evaporating this
  way, with nothing to flag it.
- **An arm's cost per question does not transfer to a different kind of arm.**
  Removing rules from the prompt shrank input slightly but doubled-to-tripled
  output, and output is 5x the input price. Price the side that grows.
- **Sampling the front of a sorted file is not sampling.** The question sets are
  ordered by level; a pilot drawn from the head hits only L0 and misprices
  everything. Stratify or step through the file.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON with
  `encoding="utf-8"` — the Windows cp1252 default fails on these files. Suite is
  `uv run pytest` (**1124 passing** as of 2026-07-26 late session). Commit per slice on master
  with the `Co-Authored-By: Claude Opus 5` trailer.
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

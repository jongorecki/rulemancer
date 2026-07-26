# Archive — do not read unless Jon names a file

**This folder is off limits by default.** Nothing in here should be read,
grepped, globbed, or summarised on your own initiative. If you think you need
something from it, say which file and why, and ask.

## Why it exists

`docs/` had grown to ~894 KB of design history — roughly 220,000 tokens if
anything read it broadly. That is enough to fill a context window before any work
starts, and a filled context window degrades everything that happens afterwards.
Moving the finished deliberation out took the top level down **57%**.

The history is preserved, not deleted. It just no longer loads by default.

## What is in here

33 `plan-*.md` and `spec-*.md` documents whose work is **finished** — shipped,
cut, or superseded. The rule applied: **a design doc stays at the top level only
if live work still points at it** (the current handoff, a results or report doc,
`CLAUDE.md`, or an open roadmap item). Everything else moved.

These are *deliberation*, not conclusions. Where the work shipped, the conclusion
now lives in the code and in a `docs/results-*.md`; the plan records how we got
there, which is rarely what a future session needs.

## Where to look instead

| You want | Read |
|---|---|
| Current state, in order | `docs/HANDOFF-development.md` |
| Every arm's numbers, the decision, the roadmap | `evals/metrics_history.html` (rebuild: `python evals/build_metrics_history.py`) |
| What a finished experiment concluded | `docs/results-*.md`, `docs/report-*.md` |
| What is planned, its status, cost and dependencies | the Roadmap section of the dashboard — it inventories these archived docs too |

The dashboard's roadmap covers all 48 design docs including the archived ones,
with status, evidence, cost and dependencies. **Read that instead of opening
files in here** — it is the index, and it is a few KB rather than 500.

## Adding to the archive

When a plan's work is done and its conclusion lives somewhere else, move it here
and make sure the roadmap inventory still resolves it (there is a test that fails
if a design doc goes missing from the inventory). Do not archive:

- anything an open or partially-done roadmap item depends on
- `results-*.md` or `report-*.md` — those are conclusions, and they are small
- the handoffs
- **tests.** A passing test is not old work, it is an active guard on current
  behaviour. Archiving one removes coverage silently, since the suite still goes
  green with the assertion no longer running. Jon's ruling, 2026-07-26: docs move
  when we are done with them, tests do not.

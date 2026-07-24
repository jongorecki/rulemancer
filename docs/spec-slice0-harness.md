# Build spec — Slice 0 harness prerequisites (layer-system tool)

**Status: approved by Jon 2026-07-24. This is a build spec, not a plan** — it
implements prerequisites for `docs/plan-layer-system-tool.md` §6.1 / §9 Slice 0,
which is already ruled on (§8.2). No new tool, no new design decisions.

Slice 0 measures a **control arm** (a system-prompt bullet quoting CR 613.6 +
611.3a) against a **base arm**, on the 54-row bucket-A COMPUTE set and on a
frozen non-layers regression sample. Neither arm may have the layers tool
attached. None of that is runnable today. This spec closes the four gaps.

**Everything here is offline. No task in this spec makes an API call.**

---

## Why each task exists (read before implementing)

1. **`_needs_layers_tool` fires on 77.8% of bucket A.** With no suppression
   switch, a "control arm" run today would silently carry the layers tool on ~42
   of 54 rows, and the measurement would be meaningless. This is the gap that
   blocks Slice 0 outright.
2. **`RulesAgent` has no system-version knob.** `SYSTEM_VERSIONS` exists
   (`answer.py`) but the agent reads the module-level `SYSTEM`. The control arm
   needs a second registered version without moving production.
3. **Answer rows record no usage, `stop_reason`, or tool-call data.** Slice 5's
   round-usage histogram (§9) has nothing to read, and the rg3391 truncation
   class is invisible — a `max_tokens` truncation currently scores as an
   ordinary wrong answer.
4. **The regression sample must be frozen and committed**, or the two arms are
   not measured on the same rows.

---

## Global rules (apply to every task)

- Run on `master`. Do **not** create a worktree — `data/raw/` and
  `evals/answers/` are gitignored and absent from worktrees.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`.
  Suite is `uv run pytest`, run in full, exit code checked.
  **Never pipe a long run through `| tail`** — it masks the exit code.
- **Never run `git add -A` or `git add .`.** Stage named paths only.
- Jon runs the app on port 8000. Never bind or kill it.
- TDD: failing test first, then the implementation.
- **If any part of this spec is wrong, contradicts the code, or cannot be
  implemented as written: STOP and report. Do not improvise a different
  design.** Several past agents were right to stop; that is the expected
  behaviour, not a failure.
- Do not "fix" a red byte-identity fixture by recapturing it. If
  `SYSTEM`/`build_prompt` identity fixtures go red, that means production moved
  and the change is wrong — stop and report.

---

## Task 1 — layers-tool suppression switch

**File:** `src/rulesagent/generate/answer.py`, `tests/` (extend the existing
scripted-fake-client pattern in `tests/test_cost_tool_loop.py`).

- Add `layers_tool: bool = True` to `RulesAgent.__init__`; store as
  `self.layers_tool`.
- In `RulesAgent.answer()`, the gate becomes:
  `use_layers_tool = self.layers_tool and _needs_layers_tool(question, cards)`.
- **Do not modify `_needs_layers_tool` itself.** It is the calibrated, verified
  trigger (77.8% bucket-A recall at 5.1% firing). The switch sits outside it.
- Do **not** add a cost-tool switch. The cost tool stays at its production
  default in every arm so it is constant and cannot confound the comparison.

**Tests (all offline, scripted fake client):**
- `layers_tool=False` on a question that trips the trigger → `RESOLVE_LAYERS_TOOL`
  is absent from the request's `tools`, **and** `LAYERS_TRIGGER_SENTENCE` is
  absent from `call_system`.
- `layers_tool=False` does not disturb the cost tool: a cost-triggering question
  still attaches `CALCULATE_COST_TOOL` and its trigger sentence.
- Default (`layers_tool=True`) behaviour is unchanged on a trigger-firing
  question.

---

## Task 2 — `system_version` knob + the control-arm system prompt

**Files:** `src/rulesagent/generate/answer.py`, `evals/run_answer_eval.py`,
`tests/`.

### 2a. Register the new system version

Add, next to the existing `SYSTEM_V3` / `SYSTEM_V4` / `SYSTEM_V4NL` definitions:

```python
# CR 613.6 + 611.3a, pasted verbatim from
# data/raw/MagicCompRules 20260619.txt (read with encoding="utf-8-sig").
# This is the Slice 0 CONTROL ARM intervention (plan-layer-system-tool.md
# Sec 6.1) -- deliberately minimal: the two rule texts plus one framing
# clause, no coaching or worked examples. A heavily-coached bullet would be
# a different intervention than the one Sec 6.1 specifies, and a win by it
# would not be interpretable as "the prompt bullet works".
LAYERS_CR_BULLET = (
    "When reasoning about continuous effects and the layer system, apply "
    "these rules exactly as written:\n"
    "613.6. If an effect should be applied in different layers and/or "
    "sublayers, the parts of the effect each apply in their appropriate "
    "ones. If an effect starts to apply in one layer and/or sublayer, it "
    "will continue to be applied to the same set of objects in each other "
    "applicable layer and/or sublayer, even if the ability generating the "
    "effect is removed during this process.\n"
    "611.3a A continuous effect generated by a static ability isn’t "
    "“locked in”; it applies at any given moment to whatever its "
    "text indicates."
)

SYSTEM_V3_613 = SYSTEM_V3 + "\n" + LAYERS_CR_BULLET
```

The `’` / `“` / `”` escapes are the curly apostrophe and curly
double quotes as they appear in the CR. **Preserve them exactly** — do not
normalise to ASCII quotes. Verify with a test that asserts the bullet substring
appears verbatim in the file `data/raw/MagicCompRules 20260619.txt` (read with
`encoding="utf-8-sig"`), for both rule sentences.

Register it: `SYSTEM_VERSIONS["v3+613"] = SYSTEM_V3_613`.

**`PROMPT_VERSION` stays `3` and `SYSTEM` stays `SYSTEM_VERSIONS[PROMPT_VERSION]`.**
Production must not move.

### 2b. Thread it through the agent

- `RulesAgent.__init__(..., system_version: int | str = PROMPT_VERSION)`.
- Unknown key → raise `ValueError` naming the valid keys (not a bare `KeyError`).
- The agent's `answer()` must assemble the prompt using the *instance's* system
  string, not the module-level `SYSTEM`.

**Check `build_prompt`'s signature before choosing how.** Existing call sites
(`evals/build_prompts_variant.py`, `evals/build_prompts_v4.py`,
`evals/run_openrouter_arm.py`, the identity fixtures) import and rely on
`SYSTEM` / `build_prompt` as they are. Pick the **minimal-blast-radius** approach
— most likely an optional `system_override=None` parameter that defaults to the
current module-level behaviour. **If threading it would change `build_prompt`'s
output for any existing caller, STOP and report instead of proceeding.**

### 2c. CLI flag

`evals/run_answer_eval.py` gains `--system-version` (default: production), passed
straight into `RulesAgent(system_version=...)` and recorded in each output row.

**Tests:**
- A default agent's assembled system string is **byte-identical** to `SYSTEM`.
  This is the production-didn't-move guard; it must be an explicit assertion.
- `system_version="v3+613"` produces exactly `SYSTEM + "\n" + LAYERS_CR_BULLET`.
- Both CR sentences appear verbatim in the repo CR text file.
- Unknown version raises `ValueError` listing valid keys.
- The existing byte-identity fixtures stay green, untouched.

---

## Task 3 — per-row run telemetry

**File:** `evals/run_answer_eval.py` (plus whatever minimal surface on
`RulesAgent` is needed to expose the round count).

Each output row gains:

| field | source | notes |
|---|---|---|
| `stop_reason` | the generation response | makes rg3391-class truncation visible instead of scoring as a wrong answer |
| `tool_calls` | `agent.last_tool_calls` | already registered on the agent |
| `tool_rounds` | rounds consumed by the tool loop | **Slice 5's round-usage histogram reads this** |
| `usage` | input / output / cache tokens | rows currently record no token usage at all |
| `system_version` | the `--system-version` arg | provenance |
| `layers_tool` | the layers-tool switch | provenance |

- `answer.py` runs a `for _round in range(TOOL_ROUND_CAP)` loop. **First check
  whether `last_tool_calls` already carries enough to derive the round count.**
  If it does, derive it and say so in the report. If it does not, expose it
  explicitly (e.g. `self.last_tool_rounds`) rather than inferring from list
  length.
- `_answer_from_frozen_prompt()` is a single `messages.parse` call with **no
  tool loop**. Rows generated that way must record `tool_rounds: None`. **Do not
  fake a value** — the absence is real and load-bearing information.
- Rows written by an older run without these fields must still load. Do not
  break `_load_resumable`.

**Tests:** a scripted-fake-client run asserts each field is present and carries
the value the fake produced, including the `tool_rounds: None` frozen-prompt case.

---

## Task 4 — freeze the regression sample

**Files (new, disjoint from Tasks 1-3):**
`evals/build_layers_regression_sample.py`, `evals/_layers_regression_sample.jsonl`.

Build a **frozen, committed** 100-row non-layers sample:

- **Population:** rows of `evals/rulesguru_full.jsonl` whose `id` is **not** in
  `evals/_layers_union_slice.jsonl` (the 68 CR-613-citing rows), **and** which
  carry a truthy `answer_gold`.
- `random.seed(613)`, then `random.sample(population, 100)`.
- Write rows out in master-file (`rulesguru_full.jsonl`) order, schema unchanged
  from the source rows, so it drops straight into
  `run_answer_eval.py --questions` and `judge_rulesguru.py --questions`.

**The docstring must record this deviation:**
`evals/calibrate_layers_trigger.py` builds its `non_layers_plain` sample from
`non_union_rows` with the same `seed(613)` but **without** the `answer_gold`
filter. This sample adds that filter, because a row with no gold contributes
nothing to a correctness measurement and `judge_rulesguru.py` skips it. The two
samples are therefore **not identical** and must not be described as the same
set. Excluding the union ids guarantees zero overlap with the bucket-A win-rate
set.

Print a summary on run: population size, sample size, and how many candidate
rows the gold filter removed.

**Test:** running the builder twice produces a byte-identical file
(determinism), and no sampled id appears in `_layers_union_slice.jsonl`.

---

## Verification and commit

- Full `uv run pytest`, exit 0, on a clean tree. Report the pass count.
- One commit per task group, **named paths only**, heredoc message.
- Trailer: `Co-Authored-By: Claude Opus 5` — the prior handoff says "Opus 4.8"
  because that was the model then; naming the model that actually did the work
  is the point of the trailer.
- Report back: what changed, the suite result with its count, and anything in
  this spec that turned out to be wrong.

# Spec — effort knob, no-rewrite arm, model override

Written 2026-07-25. Jon ruled: spec all three, build them, then run the 10-row
opus-low cost base, then the model bakeoff (grok excluded on Jon's call).

Scope is three knobs needed before any of the planned measurement can run. It is
deliberately small. It does **not** include the bakeoff itself, the confidence
score, self-consistency, or the runner parallelisation — those are separate.

---

## 0. What already exists (do not rebuild)

Verified by reading, 2026-07-25:

- `RulesAgent.__init__` already takes **`rewrite: bool = True`** (`answer.py:1485`),
  and the call site is a clean gate: `if self.rewrite:` (`answer.py:1793`). The
  no-rewrite path is already reasoned about — `ruling_query_mode="union"` documents
  its own `rewrite=False` fallback (`answer.py:1565`, `1810`). **Nothing in the
  agent needs to change for no-rewrite.**
- `run_answer_eval.py` already has **`--model`** (`:237`, default `GEN_MODEL`), and
  already records `model` per row (`:491`) and enforces it in the resume guard
  (`:131`). **The model override exists.** Task 3 is verification only.
- `GEN_MODEL = "claude-sonnet-5"` (`answer.py:34`) stays pinned. Production default
  does not move in this spec.

So the only genuinely new mechanism is **effort**.

---

## 1. Task 1 — `effort` on RulesAgent and the generation call

### Why

There is no `output_config` or `effort` anywhere in `src/`. Every Anthropic call
today runs at the API default `effort: "high"`. Measured cost is ~90% thinking
tokens (`rg3868`: 10,622 output tokens for a ~700-token answer), so effort is the
primary cost lever and it is currently not expressible.

### Change

`RulesAgent.__init__` gains `effort: str | None = None`.

- `None` (default) → **the request body is byte-identical to today**. No
  `output_config` key is added at all. This is the compatibility guarantee:
  every existing caller, test, and prior run file is unaffected.
- A string → validated eagerly at construction against
  `{"low", "medium", "high", "xhigh", "max"}`, then passed to the generation call
  as `output_config={"effort": <value>}`.

Validate at construction, not at call time — same discipline as `system_version`
(`answer.py:1584`) and the `max_tokens`/`request_timeout` guard (`:1534`). An
unknown effort must never reach a live API call 40 minutes into a batch.

### The integration risk, stated plainly

The generation call is `self._gen_client.messages.parse(..., output_format=Answer,
**round_kwargs)` (`answer.py:1968`). `messages.parse()` derives its own
`output_config.format` from `output_format=Answer`. Passing a caller-supplied
`output_config={"effort": ...}` alongside it may:

  (a) merge correctly,
  (b) be silently dropped, or
  (c) collide and overwrite the format, breaking structured output.

**(b) is the dangerous one** and is exactly this repo's recurring defect shape: a
value that looks present but isn't. It will not raise. It will produce a run that
looks like an effort arm and is actually a default-effort arm.

Resolve it empirically before wiring anything downstream (see Verification).
If `.parse()` cannot carry effort, the fallback is to build `output_config`
explicitly with both `effort` and the JSON-schema `format` on `messages.create()`
— but that is a larger change and needs its own ruling, so **stop and report**
rather than doing it inside this task.

### Telemetry

`effort` is recorded per row alongside `max_tokens` / `system_version` /
`layers_tool` (`run_answer_eval.py:526-532`), and added to the resume guard
(`:131-138`). A row that recorded no effort must not be treated as
interchangeable with an effort arm.

Record the value actually passed (`None` stays `null`), never a defaulted-in
string — the `max_tokens` resume bug (`None != 32768` on every row, silently
disabling resume) came from exactly this kind of mismatch.

### CLI

`run_answer_eval.py` gains `--effort` with choices
`low|medium|high|xhigh|max`, default **not passed** (→ `None`). Mirrors the
`--reasoning` default-off discipline in `run_openrouter_arm.py:557`.

---

## 2. Task 2 — `--rewrite-version none`

### Change

Add `"none"` to the `--rewrite-version` choices on **both** runners
(`run_openrouter_arm.py:544`, `run_answer_eval.py:255`).

Mapping, at the point where `RulesAgent` is constructed:

- `"v1"` / `"v2"` → `RulesAgent(rewrite=True, rewrite_version=<value>)` — unchanged.
- `"none"`        → `RulesAgent(rewrite=False)`. Leave `rewrite_version` at its
  default; it is inert when `rewrite=False`.

### Provenance

The run file records `rewrite_version: "none"` verbatim. This keeps the file
self-describing and keeps the existing provenance/resume guards working unchanged
— they compare the recorded string, and `"none"` is simply a third distinct value.

Do **not** record `rewrite_version: "v2"` with a separate boolean. One field, three
values, no way to read a no-rewrite run as a v2 run.

### Note for the OpenRouter runner

`_capture_prompt()` takes `rewrite_version` (`run_openrouter_arm.py:154`) and
threads it into `RulesAgent`. The `none` mapping happens there too, so a captured
prompt cache built under `none` is distinguishable from one built under `v2`.

---

## 3. Task 3 — model override (verification only)

No code change expected. Confirm `--model claude-opus-5` flows through
`RulesAgent(model=...)` to `messages.parse(model=self.model)` and is recorded per
row. If anything hardcodes `GEN_MODEL` downstream of the constructor, fix that and
say so.

---

## 4. Verification — evidence, not argument

Every check below must produce a pass/fail artifact. Per this repo's standing
lesson: prefer the artifact over the argument, and never pipe a long run through
`| tail` (it masks the exit code, as does a trailing `echo`).

1. **Suite green.** `uv run pytest` — expect 537+ passed, exit 0, on a clean tree.

2. **Prompt identity holds.** `tests/test_prompt_identity.py` must stay green with
   `effort=None`. If it reddens, the "byte-identical by default" guarantee is
   already broken — stop.

3. **Effort actually reaches the API — the load-bearing check.** Two live single-
   question calls on the same question, `effort="low"` and `effort="high"`, with
   `usage` captured from each. Thinking-token counts must differ materially.
   *Near-identical output-token counts across the two = effort is being dropped
   (case (b) above). That is a FAIL, not a curiosity.* Report the two numbers.

4. **No-rewrite is really off.** One run at `--rewrite-version none` with
   `show_rewrite` observable: `agent.last_rewritten` must be `None`, and no
   `claude-haiku-4-5` rewriter call may appear. Assert the absence; don't infer it.

5. **Resume guard rejects a mismatched arm.** Point a `--effort low` run at a run
   file recorded under a different effort and confirm it refuses rather than
   silently appending. Same for `rewrite_version`.

6. **Verify the writes.** `str.replace()` no-ops silently on a missed anchor —
   assert each anchor exists before editing, and re-read after the final write.

---

## 5. What this unblocks, in order

1. **10-row opus-low cost base** — `--model claude-opus-5 --effort low
   --rewrite-version none`, 10 rows, via the pipeline (API, ~$1-2, Jon approved).
   Returns measured cost/question and a truncation check from recorded `usage`.
2. **Model bakeoff** (separate spec): deepseek-v4-flash, gpt-5-mini (Flex),
   sonnet-5 @ low as the single anchor, opus-5 @ low if the cost base justifies
   it — each × rewrite {v2, none}. Grok excluded, Jon's call.

## 6. Out of scope

Confidence scoring, k=3 self-consistency, abstention thresholds, runner
parallelisation, Batch API, prompt caching, and the CR gold-mining run. Each is
its own spec. Nothing here changes production defaults: `GEN_MODEL`,
`PROMPT_VERSION`, `SYSTEM`, `GEN_MAX_TOKENS`, and the rewriter all stay put.

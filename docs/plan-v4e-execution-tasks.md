# Execution tasks — prompt-v4 + condition-E, one slice, one grading session

**Rule 0 artifact. DESIGN ONLY — no code until Jon reviews this document.**

Implements the APPROVED designs in `docs/plan-prompt-v4.md` (Jon's six
rulings, 2026-07-23) and `docs/plan-condition-e-reasoning.md`. Those two
docs are the requirements authority; this is the controller's decomposition
and the measurement design. Same role `docs/plan-v3-execution-tasks.md`
played for the v3 A/B.

## Jon's rulings that shape this slice (2026-07-23 evening / 2026-07-24)

1. **v4 and condition-E ship as ONE slice**, measured on one grid, graded in
   one session — Jon's grading time is the scarce resource, and E's
   attribution is only clean if the prompt is fixed across its cells.
2. **v4 arm prompts come from a SYSTEM-SWAP on the existing condition-C
   capture**, not a fresh capture pass. v3 and v4 then differ by the SYSTEM
   string and nothing else.
3. **Condition-E cells: default + high only.** No `medium` cell.
4. **Groundedness follow-up does NOT enter v4.** Jon read the 7 flagged
   instances and ruled v4 ships exactly as its six rulings specify. The
   post-hoc citation-filter question stays alive as its own later slice
   (DECISIONS.md pre-commitment #1 is partially discharged, not dropped).
5. **Decision set is gpt-5-mini vs sonnet only** (plan-prompt-v4.md ruling
   #1). gemini, both DeepSeeks, v4-flash are out of the loop.

## Global constraints (bind every task)

- The v4 bullet texts are applied **verbatim** from `docs/plan-prompt-v4.md`
  §2 (items 4a–4e) plus the §3b redundant-emphasis clause (ruling #4). No
  rewording, no extra SYSTEM edits, no bullets from anywhere else — in
  particular nothing groundedness-related (ruling #4 above).
- **§1d stays its own bullet.** 4c is added *alongside* it, never merged
  into it (plan-prompt-v4.md ruling #5). The minor overlap is accepted.
- **Symbol definitions in the notation legend are verified at BUILD time**
  against Scryfall or the CR, never written from model memory
  (plan-prompt-v4.md ruling #6). CORE tier (mana/tap/hybrid/Phyrexian/{X})
  and REFERENCE tier (energy/snow/loyalty) are labeled as the ruling
  specifies, with the no-lecture guard included.
- The legend is **always-on and ungated** (ruling #2) — no conditional
  rendering, so the assembled prompt stays a single fixed string per
  question and the byte-identical-prompt methodology survives.
- Legend goes in the **generation SYSTEM only**. Not the rewriter, not the
  judge.
- **The gpt-5-mini judge prompt and `judge_bakeoff` artifacts are FROZEN.**
  No edits, ever.
- **Grading verdicts are Jon's alone.** The judge routes and ranks; it never
  assigns a verdict.
- Jon runs `run.py` on port 8000 — never bind or kill it; test elsewhere.
- `PYTHONIOENCODING=utf-8` on every Python invocation.
- Never assert an MTG or model fact from memory. Model pricing via the
  claude-api skill, never memory.
- **Billing:** the six runs are product/eval arms → OpenRouter/Anthropic API
  spend is correct and expected. Any batch Claude-labor (analysis,
  calibration) runs as in-session subagents on Jon's subscription, never
  scripted API calls.
- Commit per slice on master with the session's Co-Authored-By trailer.
- Detached background jobs report phantom exit code -1 and die at ~1hr —
  read the log tail for DONE markers; runners need resume logic.

## Ground truth verified for this plan (read from the artifacts, not assumed)

- `evals/answers/_prompts_C.json` = `{rewrite_version, ruling_query_mode,
  n_questions, prompts: {qid: {system, user}}}`. Its `system` is **5,189
  chars**, matching plan-prompt-v4.md §0's measured v3 SYSTEM exactly.
- **Both runners already answer from a frozen prompt.**
  `evals/run_answer_eval.py` (sonnet, native Anthropic path) and
  `evals/run_openrouter_arm.py` both take `--prompts-cache` and call
  `_answer_from_frozen_prompt(client, model, system, user)`. No new run
  machinery is needed for the swap.
- `run_answer_eval.py` validates that the cache's `rewrite_version` /
  `ruling_query_mode` match the run's flags — the derived v4 file must
  preserve condition C's values (`v2` / `raw`) or runs will refuse to start.
- `_answer_from_frozen_prompt` infers `cards_present` from the frozen *user*
  string, which a SYSTEM swap does not touch.
- **The v3 baselines already exist and do NOT need re-running**: condition C,
  r1 + r2, for both sonnet and gpt-5-mini, already graded (sonnet 46,
  gpt-5-mini 45). This slice adds six new runs, not twelve.
- `answer.py` has **no generation-side SYSTEM version selector** (only
  `rewrite.py` has `SYSTEM_VERSIONS` for the rewriter). v4 replaces `SYSTEM`
  in place; v3 continues to exist only inside the frozen capture file. That
  is sufficient for this A/B and no selector should be added.

## The grid

| Cell | Prompt | Model | reasoning | Runs | Baseline it moves against |
|---|---|---|---|---|---|
| sonnet / v4 | v4 | `claude-sonnet-5` | n/a (native path, no thinking param) | 2 | sonnet cond C v3 = **46** |
| gpt-5-mini / v4 / default | v4 | `openai/gpt-5-mini` | unset (server default) | 2 | gpt-5-mini cond C v3 = **45** |
| gpt-5-mini / v4 / high | v4 | `openai/gpt-5-mini` | `{"effort": "high"}` | 2 | its own default cell |

Every cell answers from the **same** frozen `user` blocks as the v3
baselines. The only variables in the grid are the SYSTEM string (v3→v4) and
the reasoning effort (unset→high). Sonnet's config is untouched — no
`thinking` parameter is added (plan-condition-e-reasoning.md §1, §11).

---

## Task 1 — Prompt v4 (code)

**Requirements source: `docs/plan-prompt-v4.md` §2 (4a–4e), §3b, §6, and
rulings #2–#6. Read those in full; the bullet texts there are the strings to
insert.**

1. **Before editing**, record and report the `sha256` of the current v3
   `SYSTEM` string. Task 3 asserts the captured prompts against this digest.
2. `src/rulesagent/generate/answer.py`:
   - 4a: replace §1b in place with the full Scryfall notation legend
     (CORE + REFERENCE tiers, no-lecture guard, worked mana example retained
     per ruling #3), same insert point.
   - 4b: revise §1c in place (multiplayer, Jon's verbatim wording,
     "defending player(s)" plurality).
   - 4c: add the generalized assumption-disclosure bullet **alongside** §1d,
     which stays unchanged (ruling #5).
   - 4d: new bullet immediately before §1f.
   - 4e: append the no-false-starts clause to §1f.
   - §3b: the short redundant-emphasis clause in the intro paragraph
     (ruling #4).
   - Bump `PROMPT_VERSION` 3 → 4 and add its changelog line in the existing
     docstring style (v1/v2/v3 entries are the pattern).
3. **Verify every symbol definition in the legend against a live source**
   (Scryfall notation docs or the CR) before writing it. Report the source
   per symbol. A definition that can't be verified does not ship.
4. Regenerate `tests/fixtures/prompt_identity.json` per `build_prompt`'s
   docstring so the byte-identical guarantee holds for v4.
5. Full test suite green; report counts (152/152 was the last known state).

**Verification (evidence, not assertion):** a diff of the SYSTEM string
showing each of 4a–4e and §3b at its specified insert point; §1d shown
present and unchanged; the per-symbol source list; suite output.

## Task 2 — Condition-E reasoning passthrough (code)

**Requirements source: `docs/plan-condition-e-reasoning.md` §2, §3.**

1. **Live-verify first** which `reasoning.effort` values OpenRouter's
   `openai/gpt-5-mini` route actually accepts (§3 flags `max`/`xhigh`/
   `minimal`/`none` and the `context`/`mode` fields as unverified). We only
   need `high`, but send nothing the route rejects or silently ignores.
2. `src/rulesagent/generate/openrouter_backend.py`: optional
   `reasoning: dict | None = None` on `generate()`/`_attempt()`; when set,
   `body["reasoning"] = reasoning` before the POST. **Default None so every
   past eval number is unchanged.** Nothing else in `_attempt()` moves —
   retry logic, schema, seed, temperature handling all untouched.
3. `evals/run_openrouter_arm.py`: `--reasoning {low,medium,high}` shorthand
   mapped to `{"effort": ...}`, plus the raw-JSON escape hatch. Record the
   chosen value into the output file's metadata alongside `model` /
   `rewrite_version` so a run is self-describing.
4. `ORResult.usage` already captures whatever OpenRouter returns — confirm
   reasoning-token counts land there with no schema change, and report them
   per run in Task 4.
5. TDD for the body-builder branch (reasoning absent → body has no
   `reasoning` key, byte-identical to today; reasoning set → key present,
   nothing else changed). Suite green.

**Verification:** the recorded live check of accepted effort values; a test
proving the default path's request body is unchanged; suite output.

## Task 3 — Derive `_prompts_v4.json` (the system-swap)

1. New small script `evals/build_prompts_v4.py`: read
   `evals/answers/_prompts_C.json`, assert **all** entries share one
   `system` string and that its sha256 equals Task 1's recorded v3 digest,
   then write `evals/answers/_prompts_v4.json` with every `system` replaced
   by the current `answer.SYSTEM` (v4) and every `user` copied **byte for
   byte**.
2. Preserve `rewrite_version` (`v2`) and `ruling_query_mode` (`raw`) from
   condition C, plus a new `derived_from: "_prompts_C.json"` and both SYSTEM
   digests, so the file is self-describing and the runners' validation
   passes.
3. Assert the id set equals `lib_v3ab.ALL_QIDS` (50 questions) and that the
   output contains exactly one distinct system string.

**Verification:** a byte-equality check over all 50 `user` fields (v4 file vs
condition C) printing PASS/FAIL per question and a total; the two SYSTEM
digests; the id-set assertion. This check is the whole basis for the claim
that a flip is attributable to the prompt, so it gets reported explicitly,
not summarized.

## Task 4 — Run the grid (6 runs)

1. Six runs total, per the grid above: sonnet via `run_answer_eval.py
   --prompts-cache evals/answers/_prompts_v4.json`, gpt-5-mini ×2 configs
   via `run_openrouter_arm.py` with the same cache. Two runs per cell.
2. Output naming encodes prompt version, cell and run — e.g.
   `evals/answers/<arm>_v4[_high]_r<1|2>*.json`, extending the existing
   scheme; state the exact scheme in the report.
3. Record per run: determinism pins actually in force (seed; the gpt-5-mini
   `NO_TEMPERATURE` exception), failure/retry counts, `finish_reason` and
   truncated-parse rates (plan-condition-e-reasoning.md §9 flags reasoning ×
   structured-output as untested), token usage including reasoning tokens,
   and measured cost per cell.
4. Runs are long — run detached with resume logic, poll for DONE markers.

**Verification:** row counts (50 per run, 300 total), the exception list,
and the usage/cost table.

## Task 5 — Judge-compare, stable flips, Jon's queue

1. Judge-compare each v4 cell against its graded condition-C v3 reference
   using the existing frozen `evals/judge_arm_pairs.py` pipeline
   **unchanged**. State which verdict files were read as the reference.
2. **Stable-flip rule** (unchanged from the v3 A/B): a flip counts only if
   both runs of a cell agree on it. Unstable flips are logged separately and
   excluded from both the go/no-go arithmetic and Jon's queue.
3. Re-run `evals/groundedness_v3ab.py`'s check (or its direct equivalent)
   over the v4 answers and report the count against the current signed-off
   level (7 instances / 5 questions across all arms). A spike is a
   discussion trigger, not an auto-no-go — Jon has already ruled the current
   level acceptable.
4. Build Jon's grading queue (stable flips only, question-grouped) and a
   report: per-cell correct-counts vs baselines (sonnet 46, gpt-5-mini 45),
   the c014/c002/c011/c012/q008/q014/q019/q026 predicted-flip scorecard from
   plan-prompt-v4.md §6, tripwire counts, unstable-flip list, and the cost
   table.
5. **Then stop.** Jon grades. Nothing downstream of the queue is decided by
   an agent.

## Go / no-go

- **No-go 1 (unchanged, absolute):** any net correct-count drop for
  `claude-sonnet-5` on stable flips. v4 does not ship over a sonnet
  regression regardless of what it gains on gpt-5-mini.
- **Go for v4:** sonnet flat-or-up AND gpt-5-mini up. Jon's call on a mixed
  result.
- **The L2 gate (condition-E's actual question):** does gpt-5-mini reach
  **≥46** at `effort=high`? If yes, the deferred L2 generator switch becomes
  a live zero-compromise option and routes to Jon's review of the flipped
  answers — **not** an automatic switch (plan-condition-e-reasoning.md §7,
  §11). If it stays at 45 or moves narrowly while cost/latency rise, sonnet
  stays pinned and the result is recorded for the writeup either way.

## Explicitly NOT in this slice

- No groundedness bullet in v4 (Jon's ruling); the post-hoc citation-filter
  slice stays queued separately.
- No conditional/gated rendering of the legend (ruling #2) — that was
  plan-prompt-v4.md's v4.1 idea and stays there.
- No `Answer` schema change, no per-model prompts, no retrieval/`TOP_K`
  change, no `rewrite.py` change (plan-prompt-v4.md §8).
- No sonnet `thinking` parameter (plan-condition-e-reasoning.md §11).
- No DeepSeek reasoning-on secondary arm. **Controller default: skipped**
  as out of the narrowed decision set — plan-condition-e-reasoning.md §12
  question 3 was never explicitly ruled, so Jon can reverse this at review.
- No rewriter bakeoff, no local-bulk, no SSO, no deploy work.
- Nothing touches the frozen judge.

## Risks

| Risk | Mitigation |
|---|---|
| A late SYSTEM edit lands after the identity fixture regenerates, silently desyncing the fixture | Task 1 regenerates the fixture as its LAST step; Task 3's digest assertion catches any drift between the code's SYSTEM and the derived prompts file |
| Reasoning × structured output interacts badly (truncation at `max_tokens=16384`) | Task 4 records `finish_reason` and truncated-parse rates per run rather than assuming success |
| Condition C's capture is subtly wrong for a v4 comparison | Task 3's per-question byte-equality check over all 50 user blocks is reported in full, PASS/FAIL |
| The legend's REFERENCE tier (energy/snow/loyalty) is unexercised by the 19-question card eval | Already labeled as untested-by-current-eval in ruling #6; it ships as deploy-insurance and is described that way in the report, not as a validated win |
| Token bloat regresses a weak arm | Moot by ruling #1 — the weak arms are out of the decision set; gpt-5-mini *gained* from v3 |
| Two sessions collide on master | `git status` check before each implementer dispatch (the L3 collision precedent) |

## Review protocol

Subagent-driven with fresh-context reviews: fresh implementer → fresh-context
reviewer → fix loop, evidence not assertions, per task. Tasks 1 and 2 are
independent code changes and can be implemented in parallel; Task 3 depends
on both; Tasks 4 and 5 are sequential after that. Commit per task on master.

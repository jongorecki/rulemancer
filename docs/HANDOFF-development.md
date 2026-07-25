# Handoff — Rulemancer: Slice 0 is 19% run, and it already found two things that change the plan

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-25 session, which built the Slice 0 harness, shipped a production cap
raise on measured evidence, ran the first live arms of the layer-system tool
work, and measured two numbers nobody had: within-arm noise, and gpt-5-mini's
real standing against sonnet.**

Suite is **537 passed, exit 0** on a clean tree. Six commits: `b46dd6e`,
`3843b2b`, `7d2dec6`, `ce38d0d`, `80c6493`, `9508063`.

---

## ⚠️ FIRST, UNLEARN THIS

**1. "The tool must tie or beat the control arm" now has a measured noise floor,
and it is large.** Two BASE layers reps — identical config, identical 54 rows —
disagree on **6 of 54 rows (11%)**: 66.7% vs 63.0%. Unstable rows are `rg126`,
`rg132`, `rg1932`, `rg633`, `rg783`, `rg807`. **A 3-point difference between arms
is indistinguishable from the same arm run twice.** Any §8.2 verdict has to clear
this bar, and the paired McNemar test in `evals/report_layers_slice0.py` is there
because pooled percentages invite over-reading. Empirically: b=8/c=2 gives
p=0.11 (not significant); you need roughly b=10/c=0 before it is real.

**2. Two of the four §1.1 seeds are no longer stably failing, and one is fixed by
a model at a tenth the cost.** Per rep, under BASE (tool off): `rg3868` PASS/PASS,
`rg811` fail/fail, `rg807` fail/PASS, `rg633` PASS/fail. So of the plan's four
motivating failures, only **rg811** is stably wrong today. `rg3868` is stably
right. The traces in §1.1 predate `TOP_N` 3→5, the Scryfall merge, and the cap
raise — treat them as historical, not current.

**3. The API is live, but the account ran out of credit mid-run once.** A real
400 (`Your credit balance is too low`, `req_011CdMuFRpSxasCFtEa6r4x4`) killed
arm 1 at row 34. Jon topped it up and the run resumed. This is NOT the stale
"capped until 2026-08-01" claim from two sessions ago — if you hit a wall, test
with a real call and read the error before writing anything down.

---

## THE ONE THING TO DO FIRST

**Finish Slice 0.** `uv run python evals/run_layers_slice0.py` — it is resumable
on row count and will pick up mid-arm. 139 of 724 rows are done (~$12.73 spent);
budget roughly **$25 and 9 hours** for the rest.

```
base_layers_r1     54/54  judged      <- complete
base_layers_r2     54/54  judged      <- complete
base_layers_r3     31/54  -           <- resumes here
control_layers_r1..r3, base_regression_r1..r2, control_regression_r1..r2  not started
```

Then `uv run python evals/report_layers_slice0.py` for pooled rates, the paired
McNemar, the four seeds per rep, and the truncation tally. **Grading verdicts are
Jon's** — bring him the discordant pairs to read, not a grade.

Everything needed for Slice 5 is already wired: `--no-layers-tool` for the
tool-off arm, per-row `tool_rounds` for §8.3's round-usage histogram.

---

## WHAT SHIPPED THIS SESSION

**The Slice 0 harness** (`docs/spec-slice0-harness.md`, built by a Sonnet agent
against the written spec, verified independently on a clean tree):

- `RulesAgent(layers_tool=False)` + `--no-layers-tool`. **Without this Slice 0 was
  impossible** — the trigger fires on 77.8% of bucket A, so a "control" arm would
  have silently carried the tool on ~42 of 54 rows.
- `SYSTEM_VERSIONS["v3+613"]` + `--system-version`. CR 613.6 and 611.3a pasted
  verbatim from `data/raw/MagicCompRules 20260619.txt`, curly quotes intact,
  asserted against the corpus by a test. `PROMPT_VERSION` and `SYSTEM` unmoved.
- Per-row telemetry: `stop_reason`, `tool_calls`, `tool_rounds`, `usage`,
  `system_version`, `layers_tool`, `max_tokens`. Rows previously recorded **no
  token usage at all**, so cost and truncation were invisible after the fact.
- `_layers_regression_sample.jsonl` — 100 frozen non-layers rows, seed 613.
  Verified by set comparison to be **identical** to `calibrate_layers_trigger.py`'s
  plain sample (the `answer_gold` filter is a no-op on today's corpus), so the
  regression arm runs on exactly the rows the 5.1% fire rate was measured against.

**`GEN_MAX_TOKENS` 16384 → 32768 in production** (Jon's call, on evidence). 8% of
bucket-A rows truncated at 16384 and the failure mode is a **total loss**, not a
short answer: `rg131` spent the whole cap on thinking twice and returned a
98-char degrade sentinel. At 32768 it answered correctly. **The point is margin,
not size** — the recovered run used 12,550 tokens, *under* the old cap. Thinking
length is stochastic (`rg87` drew 12,419 then 10,206; `rg130` 15,712 then 7,266),
so the old cap had no headroom for the tail. Confirmed at scale: **0 truncations
in 138 rows** at the new cap, with one draw at 19,225 that would have died.

**`GEN_REQUEST_TIMEOUT = 900.0`, and it is not optional.** The SDK refuses a
non-streaming `messages.parse()` whose `max_tokens` implies >10 minutes
(`_calculate_nonstreaming_timeout`), skipping that check only when a timeout is
given per-request or the client's timeout differs from the SDK default. The two
constants move together or every production call raises. `RulesAgent` now fails
**at construction** with a message naming this class rather than dying mid-batch.
Streaming is still the better long-term fix (residuals, rg3391).

**The gpt-5-mini head-to-head** — see the next section.

---

## THE HEAD-TO-HEAD, AND WHAT IT DID NOT SETTLE

Jon's driver: sonnet is too expensive. Measured: **$0.0960/question vs
$0.0098 — about 10x.**

36 paired rows (18 sonnet misses + 18 level-matched hits from BASE r1), no tools
either side: **7 recovered / 6 regressed, exact McNemar p = 1.0.** A tie.

Read it with three corrections attached:

- **The judge IS gpt-5-mini** (`judge_bakeoff` + `openai/gpt-5-mini`, frozen). This
  arm was graded by its own family. A loss would be strong evidence; a tie is weak.
- **Its regressions are mostly refusals** — 5/36 declines vs sonnet's **0/36**, and
  4 of its 6 regressions *are* those declines.
- **One of its two headline wins is not a win.** It answered `rg807` and `rg811`
  correctly (verified by reading both against gold, not by trusting the judge) —
  but sonnet passes `rg807` in rep 2. Only **rg811** is a row sonnet stably fails
  and gpt-5-mini gets right.

**It does not overturn the 15-point held-out gap.** These are bucket-A CR 613 rows,
not a representative sample. If cost stays a live concern, the next spend is a
head-to-head on a *representative* set (~150 rows ≈ $1.50 for gpt-5-mini), not
more layers rows.

**Do not build the OpenRouter tool port to chase this.** Measured: of gpt-5-mini's
64 held-out misses, the layers tool fires on **4** and the cost tool on **0**. 60
of 64 would get byte-identical prompts. That is combat's base rate (7 in 1,409 →
shelved), not layers' (51 → cleared). The port itself is de-risked and viable —
`docs/spike-tool-use-findings.md` §4 proves gpt-5-mini calls tools and honors
`tools` + strict `response_format` together over OpenRouter, and scopes the work
to three changes in `openrouter_backend.py` — but it would move at most 3 questions.

---

## HOW JON WORKS (unchanged, load-bearing)

- **Rule 0: plan before code.** Every `plan-*.md` is design-only until Jon rules. A
  bug-fix on approved code uses systematic-debugging; a NEW tool needs a plan.
- **USE SUBAGENTS.** Sonnet for scoped implementation against a written spec, Haiku
  for bulk fetch/filter/verify with compact returns. Lead keeps judgment, review,
  and talking to Jon.
- **Do-not-delegate:** eval questions, gold, grading verdicts, **reading failures**
  (the lead reads the failed output itself). Tools route and rank; never a verdict.
- **Verify agents' claims yourself.** This session's agent was clean, but the check
  still paid: it reported a "latent bug" in `build_prompt`'s `convo_ctx` branch that
  was really a bug its own change would have introduced.
- **Parallelise only across disjoint file sets.** Forbid `git add -A` / `git add .`
  in every agent prompt.
- **Judge is FROZEN** (`judge_bakeoff` prompt + gpt-5-mini). Never reword.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Model facts via the
  claude-api skill — it was right about the SDK guard and the intro pricing.
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 5`
  (the trailer names the model that did the work; prior handoffs said 4.8 because
  that was the model then). `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`.
  Suite is `uv run pytest`. Never pipe a long run through `| tail`.
  **Jon runs the app on port 8000 — never bind or kill it.**
- Don't read subagent transcript files; wait for the completion notification.

---

## THE LESSON TO CARRY

Last session's two bugs were one defect in two costumes: **an index into an
externally-owned list, persisted as if it were an identifier.** This session
produced three more of the same family, and none of them raised:

- The driver "completed" an 11-hour run in milliseconds, **exit 0**. The redirect
  into a not-yet-created log dir failed and a trailing `echo` succeeded. Same
  masked-exit-code hazard as `| tail`.
- The CLI's `--request-timeout` defaulted to `None` and was passed **explicitly**,
  silently defeating a new library default. Every call raised the SDK guard.
- The row never recorded `max_tokens`, but the resume guard compared against it —
  `None != 32768` on every row, **silently disabling resume**.

The shape: *a value that looks present but isn't, or a check that looks active but
compares against nothing.* All three were caught by running the thing end to end
and inspecting the artifact — none by reading the code. The fail-fast constructor
check in `answer.py` converts one of them into a loud failure permanently.

Also: `test_prompt_identity` went red on the cap change. It was **not** recaptured.
Every other field was digested before and after and proved byte-identical, then
only `max_tokens` was edited. Do the same next time.

---

## RESIDUALS / OPEN ITEMS

- **`.gitattributes` now pins `_layers_regression_sample.jsonl` to `-text`.**
  `core.autocrlf=true` would otherwise hand a clean clone CRLF while the builder
  writes LF, reddening the byte test for a reason unrelated to its contents.
  Apply the same to any future frozen fixture.
- **One row has `stop_reason: None`** in `base_layers_r3` (the row in flight when
  the run was stopped). Harmless; it will be regenerated on resume.
- **rg3391 — stream instead of raising the cap.** Still the better fix; the cap
  raise plus timeout override is the cheap one. `answer.py`'s comment at the
  generation call was amended to stop over-generalising from the empty-output case.
- ~~The verdict files don't record which judge produced them.~~ **DONE** (`15644d4`,
  Jon ruled). Every verdict file now carries `judge_model` and
  `judge_prompt_sha256` (currently `openai/gpt-5-mini` / `b54fbdb95565abf8`) in
  its summary block. The prompt and model are untouched — this stamps what ran.
  **Files written before 2026-07-25 carry no stamp**, including
  `layers_slice0_verdicts_base_layers_r1/r2.json` and
  `h2h_verdicts_gpt5mini.json`; read their provenance from git. They were
  deliberately not backfilled — asserting provenance into an artifact after the
  fact is the move that makes the stamp worthless. If a later run's digest ever
  differs from `b54fbdb95565abf8`, the instrument moved: stop and find out why
  before comparing anything across it.
- **Sonnet's 72%/75.3% held-out baseline is stale.** Measured 07-24 00:29 —
  pre-tools, pre-cap-raise — and `stop_reason` wasn't recorded then, so there is no
  way to tell how much of it was truncation. Re-running the 150 on today's pipeline
  is ~$7-8 and refreshes the number the whole strategy argues from.
- **Arm B of the head-to-head was never run** (gpt-5-mini as *rewriter* as well as
  generator). Needs a `rewrite_model`/`rewrite_backend` knob on `RulesAgent`;
  `rewrite_query()` already takes `model` and has a `backend == "openrouter"` branch.
  The rewriter bakeoff predicts it loses (ties haiku @5, worse at every other depth).
- Sentinel de-conflation, rg6916 rep1 leaked scratchpad, re-key
  `LOAD_BEARING_RULINGS` to `ruling_id()`, and the ten unreviewed gold
  re-derivations (commit `6aae61f`) are all still open and unblocked.

## HELD / BLOCKED ON JON

- Nothing blocks the work. Two open questions: the judge-provenance stamp above,
  and whether to fund a representative-sample model head-to-head.

## STILL QUEUED

`plan-sso.md` (tied to Jon's job-hunt auth-evidence goal), `plan-deploy.md`,
Slice C gold discovery, `plan-c011-stale-rulings.md` (diagnosed, frozen), and the
pure-rules eval set — batch 1 is 8 approved pairs and **Jon's standing grant lets
you draft 15-20+ at a time**. The one binding rule: only generalize where the
original gold ALREADY states the rules mechanism explicitly, so derived gold is a
paraphrase rather than a new ruling.

---

## ENVIRONMENT & GOTCHAS

- **Cost, measured, at intro pricing ($2/$10 per MTok through 2026-08-31):** bucket-A
  layers question ≈ **$0.096** (~90s); non-layers regression question ≈ **$0.023**
  (~38s); gpt-5-mini via OpenRouter ≈ **$0.0098** (~36s). Full Slice 0 ≈ $37 and
  ~11 hours **sequential** — `run_answer_eval.py` has no concurrency. 6-8 way
  parallelism would cut it to ~2h and is the obvious next harness win, but it was
  deliberately not built mid-measurement.
- Adaptive thinking dominates output: rg3868 spent 10,622 output tokens on a
  ~700-token answer. `max_tokens` bounds thinking **and** text together.
- `data/scryfall.db` exists locally (76 MB, 38,336 cards, gitignored). Local-first
  resolution works offline; don't run `scripts/refresh_scryfall_bulk.py` casually.
- **Oracle text and P/T are per-face** — `Card.faces[i].oracle_text`.
  `getattr(card, "power")` returns `None` even for a plain creature.
- Answer object field for the answer text is **`.text`**, not `.answer`. The
  OpenRouter arm rows call it `text` too and carry **no `answer_gold`** —
  `evals/report_h2h.py` adapts that shape so the frozen judge is reused unchanged.
- `evals/answers/` and `data/parsed/` are gitignored; verdict JSONs in `evals/` are
  tracked.
- `_answer_from_frozen_prompt()` runs **no tool loop** — a frozen-prompts arm cannot
  be compared against a tool arm. It now inherits `agent._gen_client` and
  `agent.max_tokens` so it can't drift to a different budget.
- The calibration script's `CardCache` returns `_FakeCardForRegex` objects with no
  `mana_cost`, so it can measure the layers trigger but not the cost trigger. For
  both, resolve real cards via `rulesagent.tools.scryfall.get_card(name,
  no_refresh=True)` against the local DB.
- Chrome extension blocks `file://`; serve local HTML over `http.server`, never port
  8000.
- Doc-metadata / token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md`.

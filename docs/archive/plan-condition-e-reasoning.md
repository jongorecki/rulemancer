# Plan — Condition E: reasoning-enabled generation

**DESIGN ONLY. No code changes in this document or its authoring.** Source
files read for grounding: `src/rulesagent/generate/openrouter_backend.py`,
`src/rulesagent/generate/answer.py`, `evals/run_openrouter_arm.py`,
`evals/lib_v3ab.py`, `docs/plan-openrouter-models.md`,
`docs/plan-rewriter-model-bakeoff.md` (style/format match), `DECISIONS.md`
(2026-07-23 v3 A/B outcome + four pre-commitments), `docs/plan-prompt-v4.md`.
Live-fetched OpenRouter's reasoning-tokens doc for the request-parameter
shape (2026-07-23) — see §3 for what's confirmed vs still needs a build-time
check.

## 0. Problem / motivation

The prompt-v3 A/B (`DECISIONS.md` 2026-07-23) ran every OpenRouter arm
through `openrouter_backend.py`'s `_attempt()` body builder, which sends
`messages`, `provider`, `seed`, `response_format`, `max_tokens=16384`, and
`temperature` (skipped for `gpt-5-mini`) — **no `reasoning` field, confirmed
by reading the body dict directly (lines 103-119).** Two consequences
already measured:

- The DeepSeek arms ran with reasoning effectively off (0 reasoning tokens
  in recorded usage) — untested lever, not a deliberate off-decision.
- `gpt-5-mini` reasoned anyway, because OpenAI's o-series/gpt-5 family
  defaults reasoning **on** server-side even with no `reasoning` field sent
  (its ~2,575 completion tokens on the v3 arm include reasoning tokens,
  per the session's measured usage data). Its **effort level was whatever
  OpenRouter/OpenAI default to** — never explicitly set, never swept.

Graded result (`DECISIONS.md` 2026-07-23, strict grading, r1/r2 double-run):
**sonnet 46/50 (flat) vs gpt-5-mini 45/50 (+3 over v2, best on cond C)** —
one answer apart. Jon's own pre-commitment (#3 in the four pre-commitments):
*"gap ≥3 → sonnet stays pinned"* — a 1-answer gap is inside the zone where
the L2 generator call was explicitly deferred, not decided, pending
**prompt-v4 and condition-E (this plan)** (`DECISIONS.md` 2026-07-23, "L2
generator" bullet).

**Jon narrowed the decision set to gpt-5-mini vs sonnet only** (gemini and
the other cheap arms dropped, `docs/plan-prompt-v4.md` ruling #1). So the
decision-relevant question this plan answers is narrow: **does raising
gpt-5-mini's reasoning effort above its untouched default close the last
answer of gap with sonnet?** The lever is effort *level*, not on/off —
gpt-5-mini already reasons by default.

## 1. Sonnet's own thinking config today (apples-to-apples check)

Read `answer.py`'s generation call (lines 569-576): `self.client.messages.parse(model=self.model, max_tokens=16384, system=system, messages=msgs, output_format=Answer)`. **No `thinking` parameter is set anywhere in `RulesAgent.answer()` or `__init__`** — sonnet's calls carry no explicit thinking/effort config. That means the current baseline (46/50) is sonnet running **without extended thinking turned on**, i.e. sonnet is not already "reasoning" in the deliberate-effort sense either. This makes the comparison in this plan apples-to-apples in the relevant way: both sides today are running their *default* inference mode (gpt-5-mini defaults to some reasoning; sonnet defaults to none), and condition E's question is specifically whether *raising* gpt-5-mini's effort past its own default closes the gap — not whether reasoning-vs-no-reasoning is a fair fight in the abstract. Turning on sonnet's extended thinking too is explicitly out of scope here (see Non-goals, §7) — it would move the baseline mid-experiment and isn't what Jon asked to test.

## 2. Code change needed (additive, small)

Thread a `reasoning` field into `openrouter_backend.py`'s body builder,
off by default so existing behavior — and every past eval number — is
unchanged:

- New optional parameter on `generate()`/`_attempt()`, e.g.
  `reasoning: dict | None = None` (or a per-model default-off constant
  mirroring `NO_TEMPERATURE`'s pattern — call it `REASONING` config, keyed
  by model id, defaulting to `None`/absent).
- When set, add `body["reasoning"] = reasoning` before the POST — nothing
  else in `_attempt()` changes (retry logic, schema, seed, temperature
  handling all untouched).
- `ORResult` already has a free-form `usage: dict` field (line 67) that
  captures whatever OpenRouter returns in the response's `usage` object —
  reasoning-token counts arrive there with no schema change needed, same as
  today's DeepSeek/gpt-5-mini usage capture.
- `evals/run_openrouter_arm.py` gains a `--reasoning` CLI passthrough (a
  JSON string or a small `low|medium|high` shorthand mapped to
  `{"effort": ...}`) so a condition-E run is one flag, not a code edit per
  arm — same pattern as the bakeoff plan's `--backend`/`--model` flags.
- No change to `build_prompt()`, `answer.py`, the assembled prompt, or the
  frozen judge. Condition E changes **inference config only**.

## 3. OpenRouter `reasoning` parameter — confirmed shape + open item

Live-fetched `openrouter.ai/docs/use-cases/reasoning-tokens` (2026-07-23).
**Fetch succeeded.** Confirmed core shape, cross-checked against
`openrouter_backend.py`'s existing model-quirk comments:

```json
"reasoning": {
  "effort": "low" | "medium" | "high",
  "max_tokens": 2000,
  "enabled": true,
  "exclude": false
}
```

- **Effort-based control** (`reasoning.effort`): OpenAI o-series / gpt-5
  family — this is `gpt-5-mini`'s knob. `effort` and `max_tokens` are
  mutually exclusive (send one, not both).
- **Token-budget control** (`reasoning.max_tokens`, minimum ~1024): Anthropic
  and some other families use this shape instead — not our lever here since
  sonnet stays on its native Anthropic path (`answer.py`), never OpenRouter.
- Reasoning tokens are **billed as output tokens** ("considered output
  tokens and charged accordingly," per the doc) — confirms the cost model
  in §5 below.
- Returned in `message.reasoning` / `message.reasoning_details`, included by
  default unless `exclude: true`.

**Needs live re-confirmation before build:** the fetched page also listed
`"max"`/`"xhigh"`/`"minimal"`/`"none"` effort values and two extra fields
(`context`, `mode`) beyond the four above. The fetch tool summarizes fetched
content through an intermediate model rather than returning raw docs text,
so those extras are plausible but **unverified** — before writing the code,
confirm directly against OpenRouter's current docs or a live test call
which effort values `openai/gpt-5-mini` actually accepts (the plan only
needs `low`/`medium`/`high` to answer Jon's question, so this is a
belt-and-suspenders check, not a blocker).

**DeepSeek arms:** the live fetch didn't resolve model-by-model support for
`deepseek/deepseek-chat-v3.2` (or v4) specifically — flag as needing the
same build-time `supported_parameters` check `openrouter_backend.py`'s
header comment already does for temperature/seed/response_format
(2026-07-22 precedent). Secondary arm only (§4); doesn't gate the primary
gpt-5-mini-vs-sonnet result.

## 4. Experiment design

**Prompt dependency:** condition E runs against whichever prompt is live
at build time. Today that's v3 (`PROMPT_VERSION = 3`, interim production
per `DECISIONS.md`); v4 is designed (`docs/plan-prompt-v4.md`) but not yet
Jon-approved-and-shipped. If v4 ships first, condition E runs on v4;
otherwise on v3. State this explicitly in the run's writeup so a reader
knows which prompt condition E measured against — don't let it be implicit.

**Primary arms** (the decision-relevant ones):

| Arm | Change from the v3 A/B baseline | Purpose |
|---|---|---|
| `gpt-5-mini`, reasoning unset (repeat) | none — re-run as the control for THIS experiment | confirms 45/50 still reproduces before comparing |
| `gpt-5-mini`, `reasoning.effort="high"` | new `reasoning` field added | the actual lever — does raising effort push it to ≥46? |
| `sonnet-v3` (unchanged incumbent) | none | the 46/50 target, untouched |

A "medium" effort cell is optional filler if `low`/default vs `high` alone
leaves an ambiguous middle result (e.g. high overshoots on cost/latency but
low-effort-explicit doesn't move the needle) — not required to answer the
go/no-go question, so treat as a stretch cell, not core scope.

**Secondary/optional arm** (mentioned for completeness, not the focus):
DeepSeek v3.2/v4 with `reasoning.enabled=true` (off→on is a much bigger
lever there than gpt-5-mini's default→high). Worth one exploratory run
since the code change is shared, but Jon's narrowing (§0) means this
doesn't feed the L2 decision — record it, don't gate on it.

**Question set / grading:** same 50-question set (31 rules + 19 card), same
condition-A/B/C/D grading harness pattern (`evals/lib_v3ab.py`), same
strict-grading convention (partial = not-correct) used for the 46/45
baseline so condition E's number is comparable on the same scale. Jon
grades (do-not-delegate, per every prior arm in this A/B).

## 5. Determinism

- Reasoning adds output variance on top of whatever draw-to-draw variance
  already exists — the established **double-run (r1/r2) stable-flip rule**
  from the v3 A/B (`DECISIONS.md` 2026-07-23 graded rollup) applies
  unchanged: run each question twice per arm, treat a flip between runs as
  unstable rather than trusting a single draw.
- `gpt-5-mini` still rejects `temperature` (`NO_TEMPERATURE` set,
  `openrouter_backend.py` line 41) — already handled, no change needed;
  `seed=42` still sent for whatever determinism-reduction effect it has on
  a reasoning model (none guaranteed, same caveat the module's own
  docstring already states for temp=0).
- Retrieval nondeterminism is controlled the same way every prior arm
  controlled it: the assemble-once prompt cache
  (`evals/answers/_prompts_*.json`) plus warm rewrite/scryfall caches
  (`evals/run_openrouter_arm.py`'s `_RecordingClient` pattern, lines 12-25)
  — condition E reuses this unchanged. Reasoning changes inference config
  only, never the assembled prompt, so the byte-identical-prompt A/B
  methodology (guarded by `tests/test_prompt_identity.py`) still holds.

## 6. Cost

Reasoning tokens are billed output tokens (§3), so raising effort raises
cost — but from a small base. Measured (2026-07-23, `DECISIONS.md`):
gpt-5-mini ~$0.0059/query at its **current, unset-effort default** vs
sonnet ~$0.048/query (std) / ~$0.032 (intro) — already ~8x/~5x cheaper
*with* whatever reasoning it already does by default. Rough bound: even a
generous 3-4x increase in completion tokens from raising effort to `high`
would land gpt-5-mini around $0.02-0.024/query — still comfortably under
sonnet's $0.032-0.048 range. This is a rough bound, not a measurement;
record the actual `usage.completion_tokens`/reasoning-token counts from the
condition-E run itself rather than trusting this estimate. This is
product-pipeline eval spend (API-appropriate), not the subscription-
subagent grading/analysis-labor rule.

## 7. Go/no-go

- **gpt-5-mini reaches ≥46/50 at raised effort** → matches or beats sonnet.
  Per Jon's pre-commitment #3 (`DECISIONS.md`, gap ≥3 → sonnet stays;
  implicitly gap <3 is Jon's call to make), this makes the L2 switch a
  live, no-compromise option — proceed to Jon's actual go/no-go read of the
  flipped answers (not an auto-switch; the pre-commitment was about the
  gap threshold, not a green light to ship without review).
- **gpt-5-mini stays at 45 or moves narrowly (still <46) while cost/latency
  rise** → the lever doesn't pay for itself; sonnet stays pinned per the
  existing deferred-decision framing. Record whether effort helped at all
  (even a non-decisive +0-1) since it's still evidence for the writeup.
- **gpt-5-mini regresses** (e.g. reasoning-induced verbosity or overthinking
  hurts a mana/multiplayer answer the way condition D overloaded the
  weakest arms, `DECISIONS.md` "Part B" bullet) → note the failure mode,
  still no-go, and flag whether it's a schema/structured-output interaction
  worth a follow-up.

This experiment is explicitly the decider for the **deferred L2 generator
call** (`DECISIONS.md` 2026-07-23, "L2 generator" bullet) — condition E's
result is one of the two named blockers (with prompt-v4) Jon set before
that call gets made.

## 8. Interplay

- **Pairs with prompt-v4** (`docs/plan-prompt-v4.md`): both are "spend a
  little on the cheap arm to close the gap" levers — v4 targets prompt
  content (mana notation, assumption disclosure), condition E targets
  inference config (reasoning effort). They're independent changes that
  could compound; run order matters for attribution (see Open questions).
- **Gates the L2 generator switch** (`DECISIONS.md` 2026-07-23) — this plan
  and prompt-v4 are the two named preconditions before that decision is
  revisited.
- **Independent of the rewriter bakeoff** (`docs/plan-rewriter-model-
  bakeoff.md`) — that plan is about the upstream `rewrite_query()` model,
  frozen context for this one; condition E only touches the final
  generation call, same boundary the v3 A/B already respected.

## 9. Risks / regressions

- **Reasoning-model structured-output interaction is untested here.**
  `gpt-5-mini` already does strict `response_format` json_schema fine
  without an explicit `reasoning` field; raising effort could in principle
  change how much the model "thinks before the schema" and interact with
  truncation at `max_tokens=16384` (the same budget-exhaustion class
  `answer.py`'s own comments warn about for sonnet, lines 538-544) — worth
  watching `finish_reason`/truncated-parse rates in the condition-E run,
  not assumed safe by default.
- **Attribution ambiguity if v4 and condition-E land close together**: a
  score change could come from the prompt or the reasoning lever or both.
  Mitigate by running condition E against a clearly-labeled fixed prompt
  version (§4) and stating which one in the result, same discipline the
  v3 A/B already used for its condition labels.
- **Unverified extra `reasoning` fields** (§3) — low risk (the plan only
  needs `effort`), but confirm before coding to avoid sending a field
  OpenRouter rejects or silently ignores.

## 10. Considered and rejected

- **Jumping straight to a production GEN_MODEL switch without measuring
  reasoning** — rejected; this is exactly the "1-answer concession vs
  zero-compromise" distinction Jon's deferred-decision rationale already
  drew (`DECISIONS.md` 2026-07-23). Measure first.
- **Running condition E across all five original arms** (gemini, both
  DeepSeeks, v4-flash included as primary) — rejected per Jon's explicit
  narrowing to gpt-5-mini vs sonnet (`plan-prompt-v4.md` ruling #1); kept
  DeepSeek as an optional secondary arm only, not primary scope.
- **Skipping the double-run** to save cost, given gpt-5-mini is already
  cheap — rejected; reasoning specifically adds variance (§5), so this is
  the run where the stable-flip check matters most, not least.

## 11. Non-goals

- Not changing sonnet's config (no `thinking`/extended-thinking param added
  to `answer.py`'s call in this plan — see §1's note that this would move
  the baseline mid-experiment).
- Not a prompt change (v4 is its own plan).
- Not touching the frozen judge.
- Not an automatic production switch — any go result still routes through
  Jon's review of the actual flipped answers, per the existing L2
  pre-commitment.

## 12. Open questions for Jon

1. Run order vs prompt-v4: test condition E on v3 now (faster, but risks a
   second experiment once v4 ships), or wait for v4's Jon-approval and run
   condition E once against whichever prompt is then current (cleaner
   attribution, slower)?
2. Is a `medium` effort cell worth the extra grading pass, or is
   default-vs-`high` sufficient to answer the go/no-go?
3. Is the DeepSeek reasoning-on secondary arm worth running in the same
   pass (shared code, marginal extra cost) or skip it entirely since it's
   already out of the narrowed decision set?
4. Confirm before build: exact effort values OpenRouter's `gpt-5-mini`
   route actually accepts (§3's flagged unverified extras) — quick
   real-call check, not blocking the plan's design.

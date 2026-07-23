# Plan — Rewriter model bakeoff (retrieval-only, phase 1)

**DESIGN ONLY. No code changes in this document or its authoring.** Source
files read for grounding: `src/rulesagent/retrieve/rewrite.py`,
`src/rulesagent/generate/answer.py` (`REWRITE_MODEL`, `REWRITE_N`, `GEN_MODEL`),
`src/rulesagent/generate/openrouter_backend.py`, `evals/run_eval.py`,
`evals/ablate_gold.py`, `evals/retrieval_noise_v3ab.py`, `evals/lib_v3ab.py`,
`docs/plan-openrouter-models.md`, `docs/grading-feedback-backlog.md`.

## Problem / motivation

`REWRITE_MODEL = "claude-haiku-4-5"` (answer.py:49) is pinned and sits
upstream of every generation arm — `rewrite_query()` runs once per question
before retrieval, so its output quality gates what every downstream generator
(sonnet-5, or any OpenRouter arm) can possibly find. Jon's hypothesis: a
stronger model doing the rewrite step could close some of the retrieval gaps
documented in `docs/grading-feedback-backlog.md` — q016 (117.3c/601.2h ranked
189/109, never retrieved, Jon's own note says "Fix = query rewriting (#3)")
and q014 (802.2/507.1 multiplayer rules not surfacing) — for a fraction of
what it would cost to upgrade the generator itself to sonnet-tier reasoning
on every arm.

**Framing that must not slip:** rewriting is not a reasoning task, it's a
translation task — "turn a casual question into search phrasing that matches
the CR's prose vocabulary" (rewrite.py's own module docstring, line 1-2). A
model that reasons well about MTG rules is not automatically a good
rewriter, and a model that's a good rewriter doesn't need to reason about
rules at all. So the bakeoff must score models on **retrieval effect** (does
the gold rule get retrieved and ranked well after this model's rewrite?),
never on whether the model's own rules understanding sounds good. This is
also what makes phase 1 cheap: no generation call, no judge, no human
grading — just rewrite → retrieve → check gold recall, reusing
`evals/run_eval.py`'s existing any@k/all@k metric machinery.

## Candidate rewriter models

| Model (candidate id, verify at build) | Why it's in the bakeoff |
|---|---|
| `openai/gpt-5-mini` (OpenRouter) | Jon's headline pick — reasons about rules well, cheap; **rejects `temperature`** (reasoning model, confirmed both in rewrite.py's own `TEMPERATURE_OK` comment and openrouter_backend.py's `NO_TEMPERATURE` set) |
| `deepseek/deepseek-chat-v3.2` (OpenRouter) | Already a known-good OpenRouter citizen — used as a generator/judge candidate in `plan-openrouter-models.md` and already has answer files in `evals/answers/deepseek-v3-2_*.json`; accepts `temperature=0`; cheap (~$0.14/$0.28 per MTok per that plan) |
| `google/gemini-2.5-flash-lite` (OpenRouter) | Cheapest of the three (~$0.10/$0.40 per MTok per plan-openrouter-models.md); gives spread on the cheap end; flagged there as prone to truncated/partial-JSON responses under load — same retry handling openrouter_backend.py already has for this model family should carry over |
| `claude-haiku-4-5` (current, Anthropic-routed) | Control arm — must stay in the bakeoff so every candidate is measured against the actual shipped baseline, not against each other only |

Model IDs above are OpenRouter slugs and must be re-verified at build time the
same way `openrouter_backend.py`'s header comment already flags ("verified
against OpenRouter's supported_parameters (2026-07-22)") — OpenRouter model
availability and slugs drift.

## The routing question (the plan's main code-design content)

**Confirmed today:** the rewriter is Anthropic-routed only. `rewrite.py`
calls `anthropic.Anthropic()` / `client.messages.parse(...)` directly
(rewrite.py:193-232) with `output_format=_Rewrites`, a Pydantic model
(`queries: list[str]`, `clarification: str | None`). There is no
OpenRouter path in the rewrite module today — `openrouter_backend.py` exists
only for the **generation** eval arm (its own docstring: "The shipped app
never routes through this module").

**What has to change to test a non-Anthropic rewriter model:** the rewriter
needs a second call path that goes through `openrouter_backend.py`'s
pattern — POST to OpenRouter's `/chat/completions` with
`response_format: {"type": "json_schema", "json_schema": {"strict": true,
"schema": ...}}` — instead of `anthropic.Anthropic().messages.parse()`.
Concretely:

1. **Schema reuse is straightforward.** `_Rewrites` is already a small
   Pydantic model (`queries`, `clarification`) — the same
   `.model_json_schema()` + `additionalProperties: false` + `required` shape
   `openrouter_backend.py`'s `_answer_schema()` builds for `Answer` applies
   unchanged to `_Rewrites`. No new schema-translation code needed, just the
   same helper pattern reused (or literally imported/generalized) for a
   different Pydantic class.
2. **The rewriter needs its own thin OpenRouter call**, not
   `openrouter_backend.generate()` as-is — that function is built around
   `Answer` specifically (schema, `ORResult` fields for generation
   attribution) and around generation's system/user prompt shape. The
   cleanest design is a new function alongside it (or a small
   `openrouter_backend.py` generalization) that takes `(system, user, model,
   schema)` and returns parsed JSON + attribution, reusing the existing
   retry logic (429/5xx backoff, the DeepInfra/StreamLake retryable-400
   detection, truncated-parse re-ask) verbatim since none of that is
   generation-specific.
3. **`rewrite_query()` needs a backend switch.** Today its signature takes
   `model: str, client: anthropic.Anthropic | None`. The bakeoff-friendly
   shape is closer to `rewrite_query(question, model, n, backend="anthropic"
   | "openrouter", ...)`, dispatching to the existing Anthropic path when
   `backend="anthropic"` (byte-identical, zero risk to the shipped path) and
   to the new OpenRouter path otherwise. Keep `REWRITE_MODEL =
   "claude-haiku-4-5"` and the implicit `backend="anthropic"` default
   completely unchanged — this is additive, not a replacement.
4. **Temperature handling per candidate.** `TEMPERATURE_OK = {"claude-haiku-4-5"}`
   in rewrite.py already gates `temperature=0` by model for the Anthropic
   path. The OpenRouter path needs the equivalent gate —
   `openrouter_backend.py`'s `NO_TEMPERATURE = {"openai/gpt-5-mini"}` already
   encodes exactly this for gpt-5-mini; deepseek-v3.2 and gemini-flash-lite
   both accept `temperature=0` per that module's header comment. Reuse
   `NO_TEMPERATURE` (or a rewrite-specific copy of it) rather than inventing
   a new constant — same reasoning-model exception applies to a rewriter
   call as to a generation call.
5. **Cache key is already model-aware — no schema change needed.** The
   rewrite cache key is `json.dumps([model, version, n, question])`
   (rewrite.py:183). Adding a new `model` string (e.g.
   `"openai/gpt-5-mini"`) as a bakeoff arm automatically gets its own cache
   row; nothing about the cache table needs to change. This is a genuine
   design gift — the bakeoff can lean on the existing cache instead of
   building a separate one.
6. **Determinism caveat carries over unchanged.** rewrite.py's own comment
   already documents that `temperature=0` "cuts (does not eliminate)" draw
   variance and cites a measured 68-77% recall@5 swing without it. Whatever
   is true for Haiku is presumptively true for the OpenRouter candidates too
   — phase 1's method (below) has to control for this, not assume any
   candidate is more deterministic than Haiku turned out to be.

None of this touches `generate/answer.py`'s shipped `GEN_MODEL` or
`REWRITE_MODEL` defaults. The production rewriter stays Haiku until a result
plus Jon's sign-off says otherwise — same non-goal framing as
`plan-openrouter-models.md`'s generation A/B.

## Phase 1 — retrieval-only eval method

**Metric:** reuse `evals/run_eval.py`'s existing any@k/all@k recall
machinery unmodified. Run one full pass per candidate rewriter model over
the same 31 rules questions (`evals/questions.jsonl`) at the same
production k (`GEN_TOP_K`, whatever `answer.py` ships — check at build
time, don't hardcode a new k). No generation call, no judge, no grading UI —
just: rewrite each question with candidate model X, embed the rewrites,
retrieve, and score gold-id recall exactly like `run_eval.py` already does
for the BM25/vector/hybrid method comparison. This is what makes the whole
experiment cents-cheap: the rewriter call is a short question in / a
handful of short query strings out (openrouter_backend.py-style pricing
napkin math below), and retrieval is already instrumented.

**The single most important methodology point — embedding nondeterminism
control.** Discovered 2026-07-23: ~30-34% of questions draw materially
different retrieved chunks between captures because Voyage's `embed_query`
has no cache on the live path (unlike the query-embedding cache `run_eval.py`
otherwise uses for repeatable BM25/vector runs — this gap is specific to the
live embed call, not the eval's cached-corpus embeddings). This directly
threatens a rewriter bakeoff: a recall difference between two candidate
rewriters could just as easily be embedding draw noise as rewriter quality,
and the v3ab retrieval-noise classifier
(`evals/retrieval_noise_v3ab.py`) already proved this exact failure mode —
condition C and D shared the *same* rewriter and *still* disagreed on
retrieved rules ids for a nontrivial fraction of questions, tagged
`retrieval_noise_suspect`.

The bakeoff must not treat a single retrieval pass per candidate as ground
truth. Required control, adapting the two mechanisms already in the repo:

- **Multiple retrieval runs per rewriter, report mean ± spread.** For each
  candidate model, run the full 31-question retrieval pass **3 times**
  (matching the "3 questions x 3 draws" variance spot-check
  `plan-openrouter-models.md` already prescribes for generation temp=0
  arms) and report recall@k as a mean with the observed range, not a single
  number. A candidate whose recall@5 is 74/77/71 across three clean runs is
  not meaningfully different from Haiku's already-known 68-77% swing; a
  candidate that holds steady at 84/85/83 is a real signal.
- **Assemble-once capture for the head-to-head comparison.** Borrow the
  v3ab pattern directly: capture each candidate's assembled rewrite output
  (the `queries` list actually sent to the embedder) to a per-arm file —
  `evals/answers/_rewrites_<model>.json` in the same spirit as
  `evals/answers/_prompts_B/C/D.json` — so a later re-run can diff "did the
  RULES retrieval change because the rewriter changed, or because the same
  rewrite text embedded differently this time." This reuses
  `retrieval_noise_v3ab.py`'s exact classification logic
  (`identical` / `expected_rewriter_diff` / `retrieval_noise_suspect`)
  with the rewriter model swapped in for the B/C/D axis.
- Report per-model recall as "mean recall@5 across 3 runs, N of 31
  questions flagged retrieval_noise_suspect" rather than a bare percentage —
  the noise-suspect count is itself part of the result, since a rewriter
  that produces more stable retrieval (fewer noise-suspect flags at fixed
  embedding behavior) is a real quality signal independent of raw recall.

**In-role check (does the rewriter stay a rewriter).** A reasoning model
like gpt-5-mini asked to "rewrite this into CR vocabulary" may over-think,
editorialize, hedge, or answer the question instead of translating it — the
Haiku-tuned `SYSTEM_V2` prompt (rewrite.py:88-119) was never tuned against a
reasoning model's instruction-following style. Score this alongside recall,
not instead of it:
- **Terseness/in-role check**: for each candidate's `queries` output, flag
  any rewrite that (a) contains a direct yes/no or rule-number answer to the
  question rather than a restated search query, (b) exceeds roughly 2-3x the
  median rewrite length across the other candidates, or (c) drops the
  `clarification: null` default when nothing in the question actually
  requires it (over-triggering the clarification field is itself a sign the
  model is reasoning about the *answer*, not the *query*). This can be a
  simple heuristic pass over the captured `_rewrites_<model>.json` files,
  not a second judge call — keep phase 1 judge-free per the framing above.
- If a candidate needs prompt tuning to stay in role, that's an expected
  finding, not a bakeoff failure — note it and decide per-candidate whether
  a light prompt tweak (still v2-equivalent in spirit) is worth testing
  before writing the candidate off. Do not silently reuse the exact
  Haiku-tuned wording as if it's guaranteed to transfer.

**q016 / q014 spot-checks (the documented targets).** Independent of the
aggregate recall numbers, explicitly re-check these two by hand for every
candidate:
- **q016**: does 117.3c and/or 601.2h now retrieve inside the production
  top-k (today: ranked 189/109, i.e. not retrieved at all)?
- **q014**: does 802.2 (and 507.1) surface for the multiplayer
  defending-player question that today cites the wrong supporting rule?

A candidate that wins on aggregate recall but doesn't move q016/q014 is a
weaker result than the framing implies — these are the two failures Jon
specifically attributed to the rewriter, so they're the sharpest test of
whether the hypothesis is right, not just whether some numbers moved.

**Two more rewriter-attributed targets from the v3ab grading (added 2026-07-23,
docs/grading-feedback-backlog.md):**
- **c019** (Kicker/ability-copy land count): Jon's note — "seems like a wording
  difference is causing the issue, or the fact that we're not referring to
  copying the ability specifically twice while it's on the stack. that's
  something for our rewriter." A rewriter that phrases the query around
  "copies of an activated ability on the stack" is the hypothesis to test.
- **q014 (APNAP priority frequency)**: Jon — "we need to find the ruling that
  before moving from one step to another, each player receives priority in
  APNAP order and pull that more frequently." The rewriter should surface the
  priority-order rule (approx. 117.3/117.4) for multiplayer-combat questions,
  not just the combat-damage rules. Complements the existing q014 802.2 target.

These four (q016, q014-multiplayer, q014-APNAP, c019) are the phase-1
hand-checked retrieval targets. All four are Jon-diagnosed rewriter/retrieval
gaps, not guesses.

## Phase 2 — promotion criteria (generation A/B, conditional)

Phase 2 (a generation A/B, following `plan-openrouter-models.md`'s existing
harness) is **only** run if phase 1 produces a rewriter that:
1. Beats Haiku's mean recall@5 (and recall@k at the production k) by a
   margin clearly outside the observed noise spread — e.g. mean recall@5
   more than one full noise-spread-width above Haiku's mean, not just a
   nominally higher single-run number.
2. Specifically resolves q016 and/or q014 (or gets meaningfully closer —
   e.g. rank 189/109 dropping into single digits even if not top-5).
3. Passes the in-role check without requiring prompt surgery so extensive
   that it stops being a fair comparison to Haiku's untouched v2 prompt.

If a candidate clears all three, phase 2 is: run that rewriter model
upstream of the existing generation arms (sonnet-5 default, plus whichever
OpenRouter generation arms are still active) exactly per
`plan-openrouter-models.md`'s method — Jon grades, retrieval is no longer
the frozen variable, generation is. This is the only point where Jon's
judgment is required before spending anything beyond phase 1's retrieval
calls.

## Cost estimate

Per rewriter call: one short question in, `n` short query strings out
(REWRITE_N=1 in production; the bakeoff can test at n=1 to match production,
regardless of what generation-side experiments use). At 31 questions x 3
runs x 3 non-Haiku candidates = 279 rewrite calls, each on the order of a
few hundred input tokens and well under a thousand output tokens. Using
`plan-openrouter-models.md`'s own napkin-math style: even at gpt-5-mini's
higher per-token rate this is a few hundred thousand tokens total across
the whole bakeoff — cents, not dollars. Retrieval calls (embedding +
BM25/vector fusion) are the existing eval harness's normal cost, unchanged
by this plan. No generation calls and no judge calls in phase 1, so phase 1
total cost is bounded by the rewriter calls alone.

**Billing note (so this isn't mis-applied):** these are product-pipeline API
calls — the rewriter is part of Rulemancer's actual retrieval path, not
grading/analysis labor — so OpenRouter/Anthropic API spend is the correct
and expected billing path here. This is NOT the "batch Claude-labor on
subscription subagents, never API credits" case from the user's billing
preference; that rule concerns Claude-labor for analysis/writing work, not
a product's own model calls. Nothing about this plan should route through
subscription Claude Code subagents as a cost-avoidance measure.

## Risks / regressions

| Risk | Mitigation |
|---|---|
| Embedding draw noise masquerading as rewriter-quality difference | 3-run mean±spread per candidate + assemble-once capture + noise-suspect classification (phase-1 method, above) — the single most important item in this plan |
| Reasoning model drifts out of "terse search query" role | In-role heuristic check on captured `_rewrites_<model>.json`; candidate-specific prompt tuning treated as an expected finding, not silently reused Haiku wording |
| A candidate wins on aggregate recall but not on q016/q014 | Explicit spot-check gate in promotion criteria — aggregate win alone does not clear phase 1 |
| OpenRouter model slugs/pricing drift | Re-verify against OpenRouter's `supported_parameters` at build time, same discipline `openrouter_backend.py`'s own header comment already calls out |
| New OpenRouter rewriter path accidentally changes the shipped Anthropic path | Backend dispatch is additive (`backend="anthropic"` default unchanged); byte-identity of the existing Anthropic call path is the acceptance bar, same pattern as the generation A/B's prompt-byte-identity fixture |
| Cache collisions between bakeoff arms and production cache | None expected — cache key already includes `model`, so a new model string is a new row by construction; no schema change needed |
| Promoting a rewriter based on a single lucky run | Multi-run requirement in phase-1 method; sonnet-5's own documented draw variance (c018 empties, "the 77% lucky roll") is the cautionary precedent |

## Non-goals (explicit)

- **NOT a generation change in phase 1.** `GEN_MODEL` stays sonnet-5 and
  every existing eval number stays attached to it. Phase 1 is retrieval
  metrics only.
- **NOT touching the frozen judge.** The transitive-grading judge pipeline
  is out of scope, same carve-out `plan-prompt-tuning.md` already states for
  judge prompts.
- **NOT changing `REWRITE_N`.** REWRITE_N=1 in production is a separate
  lever (how many rewrites per question) from which model does the
  rewriting. Don't conflate them — if a promoted model later warrants
  testing REWRITE_N>1, that's a follow-up plan, not part of this one.
- **NOT replacing Haiku as the default** based on phase 1 alone — phase 1
  produces evidence; only Jon's review of that evidence plus a phase 2
  result (if triggered) can change `REWRITE_MODEL`.

## Considered and rejected

- **Jumping straight to a generation A/B with candidate rewriters** — i.e.
  skip phase 1 and just run full generation arms with each candidate
  upstream. Rejected: this is strictly more expensive (generation tokens +
  judge or Jon-grading time) for a question phase 1 answers directly and
  cheaply. The whole point of separating rewriting from reasoning is that
  retrieval effect is measurable without ever calling a generator — spending
  generation-tier cost to answer a retrieval-tier question wastes the
  advantage the framing exists to capture.
- **Skipping the noise control and trusting a single retrieval pass** —
  rejected outright; the v3ab retrieval-noise finding is recent (2026-07-23)
  and directly contradicts the assumption that one clean run per candidate
  is comparable.
- **Building a brand-new cache table for bakeoff rewrites** — rejected; the
  existing `(model, version, n, question)` cache key already isolates
  bakeoff arms from production and from each other with zero schema work.

## Open questions for Jon

1. **Candidate list confirmation** — keep all three (gpt-5-mini,
   deepseek-v3.2, gemini-flash-lite), or trim/add given gemini-flash-lite's
   known truncation flakiness under load (already documented in
   `openrouter_backend.py`'s retry-handling comments for the generation
   arm)?
2. **Production k for the recall metric** — confirm the current `GEN_TOP_K`
   value to lock phase 1's headline number to the actual retrieval depth the
   generator sees, not just recall@5 in isolation.
3. **Prompt-tuning latitude** — if a candidate fails the in-role check with
   the unmodified v2 `SYSTEM` prompt, is a bounded prompt tweak (kept
   "v2-equivalent in spirit") acceptable within phase 1, or should any
   prompt change require its own approval step like the v1→v2 rewriter
   change did (per rewrite.py's changelog comment)?
4. **Relationship to condition-E (reasoning-enabled generation) and the
   current v3 A/B** — this rewriter bakeoff is independent of both: it
   doesn't touch generation, doesn't touch the frozen judge, and doesn't
   require the v3 A/B to be resolved first. But it pairs naturally with
   both under the same theme ("spend a little on the cheap upstream part
   to close the gap with sonnet before spending more on generation itself").
   Confirm Jon wants this run as its own track rather than folded into
   either.
5. **Sequencing** — run this now, or after the v3 A/B / packaging work
   currently in flight (mirroring the sequencing question
   `plan-openrouter-models.md` already poses)?

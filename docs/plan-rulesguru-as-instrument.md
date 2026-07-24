DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.

# Plan — RulesGuru-150 as a held-out eval instrument (retrieval + answer quality)

Written 2026-07-23. Follows `docs/plan-rulesguru-import.md` (the import build,
already shipped) and clears the gate `docs/plan-prompt-tuning.md:235` set:
*"RulesGuru-150 extension happens after this A/B"* — the prompt-tuning A/B is
complete, so that gate has cleared. Grounding read: `evals/rulesguru.jsonl`,
`evals/questions.jsonl`, `evals/judge_rulesguru.py`, `evals/run_eval.py`,
`evals/run_answer_eval.py`, `src/rulesagent/contracts.py` (`EvalQuestion`,
`Chunk`), `src/rulesagent/retrieve/rewrite.py` (SYSTEM_V1 anti-overfit
comment), `docs/plan-rulesguru-import.md`.

## 0. What this plan is and is not

It is a proposal for **how to use an instrument that already exists on disk**.
`evals/rulesguru.jsonl` was fetched and converted under the prior plan; nothing
about the file changes here. This plan designs two consumption paths —
retrieval recall and answer-quality judging — and states the caveats needed to
read either one honestly. No code is written or changed by this document.

## 1. My own verification of the controller's numbers

Re-derived directly from `evals/rulesguru.jsonl` (150 lines) with a read-only
Python one-liner, independent of the numbers handed to me:

| Claim | Controller | My measurement | Match |
|---|---|---|---|
| Total questions | 150 | 150 | yes |
| Non-empty `gold` | 134 | 134 | yes |
| Mean gold ids / golded question | 2.16 | 2.1641791044776117 | yes |
| Distinct gold ids | 219 | 219 | yes |
| `match` field | all `"any"` | `Counter({'any': 150})` | yes |
| `answer_gold` present | all 150 | 150 | yes |
| `level` split | 30 each × 5 tiers | `{'0': 30, '1': 30, '2': 30, '3': 30, 'Corner Case': 30}` | yes |
| Mean cards/question | 2.51 | 2.506666666666667 | yes |

All eight numbers match exactly. Additionally measured, not previously
stated: `complexity` splits 137 Simple / 12 Intermediate / 1 Complicated (a
long tail, not a clean three-way split — see §3.2), and every row carries
`tags` and `url`.

**One claim I could NOT independently re-verify: "all 219 gold ids resolve
against the parsed CR corpus."** This worktree has no `data/raw/` or
`data/parsed/` directory (both are gitignored, and the note at the top of my
task confirms they "may be absent") — `parse_comprehensive_rules(CR_PATH)`
fails with `FileNotFoundError` here, so I cannot run
`{c.source_id for c in chunk_rules(*parse_comprehensive_rules(CR_PATH))}`
myself. I did confirm the *shape* of the claim independently: `Chunk`
(`src/rulesagent/contracts.py:93-133`) has exactly the five fields stated —
`source_id, kind, section, text, embed_text` — and citation ids are keyed on
`source_id`, not `rule_id`, matching the task brief verbatim. The
CR-resolution figure itself is taken on the controller's word, not
independently confirmed, and should be re-run by whoever has the CR text
present (a five-line script; see §6 for the plumbing it would use).

## 2. Two distinct uses — kept separate

RulesGuru-150 supports two different evaluations that share a data source and
nothing else. Conflating them (one report, one number, "RulesGuru accuracy")
would hide which system — retrieval or generation — is actually being
measured.

### 2a. Retrieval eval: recall@k against the 134 golded questions

Machinery: `evals/run_eval.py`, unchanged. It already accepts
`--questions PATH` (see `docs/plan-rulesguru-import.md` §2) and already scores
`match: "any" | "all" | "groups"` per question (`EvalQuestion.match`,
`src/rulesagent/contracts.py:167`). Pointing `--questions
evals/rulesguru.jsonl` at the existing BM25/vector/hybrid/rerank arms needs no
new code — this is an invocation, not a build. The 16 card-less/empty-gold
rows are skipped for scoring automatically (same rule the import plan
specified) and the run still reports them in its summary line.

What it measures: does the retriever surface the CR rules a *human judge*
(RulesGuru's curators) considered load-bearing for a *community-submitted*
scenario, independent of anything tuned against `questions.jsonl`.

### 2b. Answer-quality eval: auto-judge via the existing frozen judge

Machinery: `evals/run_answer_eval.py --questions evals/rulesguru.jsonl`
(generates cited answers, carries `answer_gold` through — already wired) then
`evals/judge_rulesguru.py` (already built — see §4). This measures the whole
pipeline's output against a human-written reference answer, not just whether
the right chunk was in the top-k. A retrieval win does not guarantee an
answer-quality win (the generator can retrieve the right rule and still
misapply it — see `plan-v5-symbol-injection.md`'s c014 finding, a case
exactly like this) and an answer-quality win does not prove retrieval
improved (the generator's priors can cover a gap in retrieval). Report both
numbers side by side, never one standing in for the other.

**These two evals are never merged into a single score.** Every report from
this instrument states clearly which of the two it is.

## 3. The stratification opportunity

`level` gives 30 questions each at five difficulty tiers (0, 1, 2, 3, Corner
Case). Report recall@k (2a) and judge accuracy (2b) **broken down by level**,
not just as one scalar over all 134/150.

### 3.1 Why a scalar hides the finding that matters

A single recall number cannot distinguish "this intervention helps everywhere
a little" from "this intervention helps Corner Case questions and quietly
regresses level-0 questions" — and the second pattern is exactly what a
prompt/retrieval change chasing a hard-question win would produce by making
the system more aggressive at inferring intent, at the cost of easy,
literal questions. `evals/judge_rulesguru.py` already computes `by_level`
accuracy (lines 169-177 of that file) for the answer-quality side; this plan
proposes the retrieval side do the same, using the identical five buckets so
the two breakdowns line up column-for-column.

### 3.2 A caveat the level breakdown surfaces, not hides

`complexity` is heavily skewed (137 Simple / 12 Intermediate / 1 Complicated)
while `level` is a clean 30/30/30/30/30. Any report that slices by
`complexity` instead of `level` would be reporting noise at the Intermediate
and Complicated tiers (n=12 and n=1). **Level, not complexity, is the correct
stratification axis** for this set — stated here so a future report doesn't
reach for the wrong field.

## 4. What already exists vs. what this plan adds

**Already built (nothing here re-does it):**

- `evals/fetch_rulesguru.py` — fetch + convert (prior plan).
- `evals/rulesguru.jsonl`, `evals/rulesguru_raw.json` — the 150-question set,
  committed.
- `run_eval.py --questions PATH` and `run_answer_eval.py --questions PATH` —
  both already generalized to accept any eval file matching the
  `EvalQuestion`-shaped fields; RulesGuru's extra fields (`level`,
  `complexity`, `answer_gold`, `tags`, `url`, `submitter`) are ignored by the
  loaders that don't need them and read directly by the ones that do
  (`judge_rulesguru.load_meta` reads `level`/`complexity` straight from the
  jsonl rather than through the `EvalQuestion` contract, exactly because
  those fields aren't on that contract).
- `evals/judge_rulesguru.py` — the full auto-judge pipeline: loads answered
  rows carrying `answer_gold`, calls the adopted frozen judge (gpt-5-mini via
  OpenRouter, the bake-off winner), asks for a same/different verdict plus a
  one-line reason, writes `evals/rulesguru_verdicts.json` with an overall
  accuracy figure **and already breaks it down `by_level`** (its own summary
  block, lines 169-186). Disagreements are listed explicitly
  (`summary.disagreements`) as exactly the rows Jon should spot-check —
  this is decision #2 of `plan-rulesguru-import.md` already implemented, not
  a proposal.

**What this plan adds — none of it new code, all of it usage design:**

- The decision to actually *run* the retrieval side (2a) against this set,
  which nothing in the repo does yet — `run_eval.py` has never been invoked
  against `rulesguru.jsonl`, only wired to accept it.
- The level-stratified retrieval report (§3), mirroring what
  `judge_rulesguru.py` already does for answer quality, so retrieval and
  answer-quality breakdowns are reportable in the same shape.
- The `match`-semantics comparability caveat (§5.1) — nobody has stated
  whether a RulesGuru recall number can sit next to a `questions.jsonl`
  recall number in the same table. It cannot, without a caveat; §5.1 supplies
  it.
- The sequencing statement (§6) that the prompt-tuning gate has cleared.
- The cost estimate (§7) for a full run of each eval, so "run it" is a
  scoped, sized decision rather than an open-ended one.

## 5. Honest caveats

### 5.1 `match: "any"` is a looser bar — and the two sets don't share it

RulesGuru: **all 150 rows use `match: "any"`** (verified, §1) — a question
counts as a retrieval hit if **any one** of its ~2.16 gold ids lands in the
top-k. This is the loosest of the three modes `EvalQuestion` supports.

`questions.jsonl`, measured the same way: **21 questions have no `match`
field at all** (defaulting to `"any"` per `EvalQuestion.match`'s Pydantic
default, `src/rulesagent/contracts.py:167`), **9 are explicitly `"all"`**
(every gold id must be retrieved), and **1 is explicitly `"any"`**. So
`questions.jsonl` is a genuine mix — 22 "any" (71%) and 9 "all" (29%) — where
Jon made a per-question call about how strict the bar should be, presumably
based on whether a question's gold ids are true alternatives or a
must-cite set.

**Consequence: a recall@5 number from `rulesguru.jsonl` and a recall@5 number
from `questions.jsonl` are not directly comparable**, because they are not
measuring the same thing. RulesGuru's number is uniformly the easier bar
(any one of ~2.16 ids); `questions.jsonl`'s number is a blend where 29% of
questions demand every gold id. A retriever could score higher on RulesGuru
purely because its bar is looser, with zero change in actual retrieval
quality. Any report comparing the two sets must either (a) run
`run_eval.py --match-both` (which already exists — it forces both "any" and
"all" scoring on identical rankings, per `run_eval.py`'s own docstring) on
both files and compare like-for-like columns, or (b) present the two numbers
side by side with this caveat attached, never as one combined figure.

### 5.2 Distribution differences, measured

RulesGuru's questions differ from Jon's own set in ways that matter for
reading the results:

- **Card attachment.** RulesGuru averages 2.51 cards/question (verified,
  §1). `questions.jsonl` averages **0.0** — the field is entirely absent
  from every row I inspected, not merely empty. `questions.jsonl` is a
  purely rules-text set; RulesGuru is predominantly card-scenario-driven.
  This means RulesGuru exercises the card-enrichment path (`answer.py`'s
  `[Card Name]` token parsing, `_format_cards`) that `questions.jsonl` barely
  touches, and any regression specific to card handling would show up on
  RulesGuru and be invisible on the existing 31.
- **Authorship and phrasing.** RulesGuru questions are community-submitted
  to a public site with named players and multiplayer conventions (see
  `judge_rulesguru.py`'s judge-only preamble about which player letter is
  active) — a different register from the hand-written, deliberately
  MTG-example-free rewriter prompt (`rewrite.py`'s `SYSTEM_V1` comment: "no
  MTG examples, no rule numbers, no wording drawn from
  evals/questions.jsonl, so this can't be overfit to the 31-question eval
  set"). That anti-overfit guard is exactly why RulesGuru is useful as a
  held-out check — the rewriter was never tuned to see this phrasing style.
- **Scale.** 134 golded questions vs. 31 total (30 golded-ish — not all 31
  necessarily carry gold; not re-verified here since it's out of scope, the
  point is n). At n=134, one question is 0.75 percentage points; at n=31 it
  is 3.2. A single flipped question moves the RulesGuru number roughly 4x
  less than it moves the current headline number — this is the practical
  case for using it to detect small regressions the 31-question set is too
  small to resolve.

### 5.3 Status of the gold

RulesGuru's `citedRules` are **human-written, but by RulesGuru's own curators
and submitters — not by Jon.** This project's standing rule (`DESIGN.md`,
echoed in `EvalQuestion`'s own docstring: *"the question set and what counts
as correct are Jon's, not a model's"*) is that gold is Jon's to encode. This
external gold does not meet that bar as written — it was authored by a third
party, not delegated by Jon to a model, but also not originated by Jon.

Proposed treatment, for Jon's ruling: **treat as advisory, not accepted
wholesale and not requiring a full hand-audit either.** Concretely — run the
retrieval eval and report the numbers as "RulesGuru's own citations," never
silently relabeled as "gold" without that qualifier in any report or table
header. For the answer-quality side, the existing spot-check-disagreements
workflow (`judge_rulesguru.py`'s stated design, decision #2 of the import
plan) is the right amount of scrutiny — Jon reviews the cases where the judge
says the bot's answer diverges from RulesGuru's, not every row. If a specific
disagreement turns out to hinge on a gold citation Jon thinks is wrong (not a
model error), that question's row gets a note to that effect and is excluded
from scoring going forward, the same pattern already used for c002 in
`plan-v5-symbol-injection.md` §6 (excluded from the score, kept running as a
monitored row). This plan does not propose hand-verifying all 219 gold ids
against the CR up front — that is the "verify wholesale" option Jon can pick
instead, if he'd rather not carry advisory-status gold at all.

## 6. Sequencing

`docs/plan-prompt-tuning.md:235` records Jon's ruling: *"RulesGuru-150
extension happens after this A/B."* That A/B (the 6+2-bullet prompt tuning
work) is complete — its results are written up in that same document. **This
gate has cleared.** Nothing blocks running either eval in §2 as of this
writing, beyond the ordinary cost/scheduling call in §7.

## 7. What this unlocks for other plans

RulesGuru-150 is the eval instrument two other pieces of work will need once
they're designed:

- **The rerank experiment.** `run_eval.py` already carries the constants for
  it (`RERANK_POOL = 50`, `RERANK_MODELS = ("rerank-2.5", "rerank-2.5-lite")`,
  a `rerank()` call already wired into the arm matrix) — a rerank A/B needs a
  question set large and stratified enough to show whether reranking helps
  or hurts by difficulty tier, which the 31-question set cannot resolve at
  the tier level (n=6-ish per tier if it were even labeled by tier, which it
  isn't). RulesGuru-150's 30-per-level design is what makes that breakdown
  possible. Not designed here.
- **The miss-partition diagnostic.** Any future analysis that wants to
  partition retrieval misses by cause (wrong vocabulary, wrong chunk
  granularity, genuinely absent from the corpus, etc.) needs more than 31
  data points to find a pattern rather than anecdote. RulesGuru-150's misses,
  once measured (§2a), are the population that diagnostic would partition.
  Not designed here.

Both are referenced, not designed, per this plan's scope.

## 8. Cost estimate

**Retrieval pass (2a), full 134-question run:**

- Embeddings: one Voyage API call per question per arm (`run_eval.py`'s
  docstring: "one Voyage API call per query" — BM25 and vector rankings
  fetched once, every other arm derived from those same two rankings, so the
  call count does not multiply per arm). 134 questions → 134 Voyage calls
  for the base pass, regardless of how many derived arms (BM25/vector/hybrid
  RRF/hybrid weighted/rerank) are reported from it.
- Rewrite calls, if the rewrite arms are included: one rewrite call per
  question per (model × n) cell in `REWRITE_MODELS × REWRITE_NS`
  (`run_eval.py`'s existing 3-model × 2-n grid) — but `rewrite_query()` is
  disk-cached (`KVCache("rewrite")`, keyed on prompt version per the module
  comment: *"editing either SYSTEM text changes what a cached entry actually
  means, so a version bump/change busts the cache automatically"*), so a
  **second run against an unchanged prompt version costs nothing** — only
  the first run per (question, model, n, prompt-version) tuple pays the API
  cost. Running the full existing rewrite grid against 134 new questions the
  first time is the expensive case; every re-run after that is cache hits.
- No generation model involved in the retrieval-only pass — recall@k is
  computed on chunk ids, not generated text.
- Net: modest, one-time cost dominated by embedding calls (Voyage, cheap per
  call) plus a first-time rewrite-grid cost if all rewrite arms are run; safe
  to run in full rather than sampling.

**Answer-quality pass (2b), full 150-question run:**

- Generation: one `claude-sonnet-5` call per question (`GEN_MODEL`,
  `answer.py:31`). `run_answer_eval.py`'s own docstring benchmarks 31
  questions at "well over 120s" (~4s+/question including rewrite) — scaling
  to 150 questions puts the generation step at roughly 10+ minutes wall
  time, consistent with `plan-rulesguru-import.md`'s own estimate ("~150
  generation calls — real money and >10 min"). This is a real Anthropic API
  cost per question, not cached — each question's phrasing is unique so
  there is no cache hit path for generation.
- Judging: one OpenRouter call to `gpt-5-mini` per answered question
  (`judge_rulesguru.py`'s `JUDGE_SLUG`), with a documented ≥2s rate-limit
  courtesy sleep on the RulesGuru fetch side (not the judge call itself,
  which has no stated rate limit here) — cheap per call, no caching, 150
  calls for a full pass.
- Net: 150 generation calls + 150 judge calls, real but bounded money, real
  wall time (>10 min) — this is why `plan-rulesguru-import.md` already
  scoped the full run as Jon-triggered rather than automatic/CI, and this
  plan does not change that call. A smoke slice (~5 questions, as the import
  plan's own verification section specifies) is the safe default for a
  first look; the full 150 is a deliberate, sized decision each time.

Neither pass touches a paid API from this document's own execution — the
above are estimates for the runs the plan proposes scheduling, not calls made
while writing it.

## 9. Non-goals

- No change to `evals/rulesguru.jsonl`, `rulesguru_raw.json`,
  `fetch_rulesguru.py`, or `judge_rulesguru.py`. All already built and
  correct for their stated purpose.
- No change to `questions.jsonl`, `cards.jsonl`, or any existing verdict
  file. The hand-curated 31-question set stays the primary regression suite;
  RulesGuru is additive, not a replacement.
- No hand-verification of all 219 gold ids against the CR as a precondition
  for using the set (§5.3 proposes advisory treatment instead) — that is
  offered as an option for Jon, not adopted here.
- No new rerank or miss-partition design (§7) — referenced, not designed.
- No merged single score across retrieval and answer-quality evals (§2).
- No change to the frozen judge's model, prompt, or grading criteria.
- No CI wiring — both passes stay manually triggered, per the existing
  import plan's own scoping.

## 10. What would change Jon's mind

- If RulesGuru's `match: "any"` semantics prove structurally unfair to the
  retriever (e.g. gold sets that are true synonyms of each other vs. gold
  sets where only one id is actually correct and the rest are noise) — that
  would argue for hand-auditing a level-stratified sample's `match`
  appropriateness before trusting the recall number, the same way
  `questions.jsonl` got a per-question `match` call.
- If the CR-resolution figure (all 219 ids resolving), re-run by someone
  with `data/raw/` present, comes back lower than 219/219 — that would mean
  real CR-version drift between RulesGuru's snapshot and this repo's, and
  the drift-counting logic `fetch_rulesguru.py` already has (per the import
  plan) would need to actually be exercised and reported, not assumed clean.
- If a level-stratified retrieval run shows recall falling off a cliff at
  Corner Case specifically (not gradually across levels) — that would argue
  for treating Corner Case as its own reporting category rather than folding
  it into a single "harder tiers" narrative, since a cliff and a slope imply
  different fixes.
- If the first full answer-quality run produces a high `unparsed_or_error`
  count (the judge's own summary field) — that would mean the judge prompt
  needs adjustment for RulesGuru's phrasing before the accuracy number can
  be trusted at all, independent of the bot's actual quality.

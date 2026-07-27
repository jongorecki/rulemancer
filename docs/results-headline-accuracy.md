# Results — measured accuracy on the full RulesGuru corpus

**Run 2026-07-27. First corpus-wide accuracy measurement this project has ever
made.** Everything before it was a projection extrapolated from 311 rows.

## The number

**85.88% on all 1,409 questions** (1,210 correct), 95% Wilson CI
**[83.96%, 87.60%]**.

By difficulty level:

| level | correct | accuracy | 95% CI | n |
|---|---|---|---|---|
| 0 | 199/207 | 96.14% | [92.6%, 98.0%] | 207 |
| 1 | 510/565 | 90.27% | [87.5%, 92.4%] | 565 |
| 2 | 342/406 | 84.24% | [80.4%, 87.5%] | 406 |
| 3 | 110/162 | **67.90%** | [60.4%, 74.6%] | 162 |
| Corner Case | 49/69 | 71.01% | [59.4%, 80.4%] | 69 |
| **all** | **1210/1409** | **85.88%** | **[83.96%, 87.60%]** | 1409 |

The monotonic decline from level 0 to level 3 is the substance. It independently
corroborates `docs/results-failure-taxonomy.md`, which found level 3 failing at
~6x the base rate on a separate 311-row sample. Corner Case (71.0%) sits nominally
above level 3 (67.9%), but with n=69 the intervals overlap heavily and that
ordering is **not** established.

## Exactly what was measured

Config, verified as recorded on all 1,409 answer rows (not as intended — as
stamped):

| field | value |
|---|---|
| model | `claude-opus-5` |
| effort | `low` |
| rewrite_version | `v2` |
| ruling_query_mode | `raw` |
| system_version | 3 |
| max_tokens | 32768 |
| reground | False |
| batch | True |
| prompts cache | `_prompts_rulesguru_full_v2raw.json`, sha256 `61bb33929f734b17…` |
| layers tool | **removed** (`f357c4a`) — did not exist at run time |

This is the shipped pipeline. Getting there required warming the v2 rewrite cache
with real Haiku calls ($1.90), because both existing prompt-cache builders
hardcode `rewrite_version=none` / `ruling_query_mode=union` and would have
produced a number labelled "production" that measured a different config. The
runner's config-stamp guard caught that attempt and refused it.

**Judge:** `openai/gpt-5-mini` (different vendor from the generator), 3-vote
majority, prompt digest `b54fbdb95565abf8`. 24 rows (1.70%) were 2-1 splits.

**Tools:** `tool_rounds` is null on every row — batch mode cannot run a tool loop.
This costs nothing measurable: `calculate_cost` (the only remaining tool) fired
**0 times in 311 rows** of prior live-path arms, so its base rate is zero.

## Error decomposition — the part that makes the figure defensible

A single percentage hides three separate error sources. All three were measured
tonight rather than assumed.

| source | magnitude | how measured |
|---|---|---|
| sampling | ±1.8pp | Wilson interval at n=1,409 |
| judge instability | ~2-4pp | `docs/results-judge-stability.md`: re-judging shifted the h2h hard arm 75.9% → 72.2% |
| judge false positives | 4.4% (CI to 10.9%) | `docs/results-judge-error-rate.md`, 90-row human sample |
| judge false negatives | 0%, CI [0%, 4.7%] | `docs/results-judge-false-negatives.md`, 77 rows hand-graded incl. a census of all 53 hard-level passes |

**Net direction: the figure is more likely an understatement than an
overstatement.** False positives (wrongly failing a correct answer) run at 4.4%
and pull the number down; false negatives (wrongly passing a wrong answer) measure
0% with a 95% upper bound of 4.7% and would pull it up. At point estimates they do
not cancel.

**So the honest phrasing is "roughly 86%, with a ±2pp sampling interval and a
further ~4pp of judge-instrument variance."** Quoting 85.88% as though the third
digit means something would be false precision.

## Refusals are not inflating this

The system declined to answer on **10 of 1,409 rows (0.71%)**, and 9 of those were
scored incorrect. Confidently-wrong answers: 190 rows (13.48%). 98.1% of answers
cite a CR rule.

That matters because the companion experiment
(`docs/results-rules86-placebo.md`) shows the system refusing on 90.7% of rows when
handed deliberately wrong rules. On the real corpus it almost always answers — so
85.88% is a genuine accuracy figure, not a refusal artifact. The two arms together
show the refusal behaviour is *conditional on the context being bad*, which is
exactly what it should be.

## Beat the projection, and why

The dashboard projected 82.8% [78.2%, 86.6%] from three arms. Actual: 85.88%,
**+3.1 points**, near the top of the projected interval. The projection was
extrapolated from arms running the OLD config; this run reproduces production's v2
rewrite, which retrieves on a rewritten query and produced measurably longer, more
relevant prompts (mean 18,394 chars vs ~11,900 in the old arms). The $1.90 of
Haiku rewrites bought config fidelity and, apparently, accuracy.

## Cost

| item | pool | cost |
|---|---|---|
| v2 rewrite warm-up (1,258 Haiku calls) | Anthropic | $1.90 |
| pilot, 5 stratified rows | Anthropic | $0.16 |
| generation, 1,409 rows, batched | Anthropic | **$43.61** |
| judging, 4,227 calls (3 votes) | OpenRouter | ~$13 (est.) |

$0.03095 per row batched. The batch discount halved it; the same run
synchronously would have been ~$87.

## What this does NOT establish

- **Not corpus-general.** RulesGuru questions are written by certified judges and
  are 99.4% card-interaction scenarios. This is accuracy on *that* distribution,
  not on arbitrary player questions.
- **Not human-validated at scale.** Only 32 rows in this project have ever carried
  a real human verdict, and all 32 came from rows the judge had already failed. The
  judge's own error rates are themselves estimates from small samples.
- **Not a live-path number.** Frozen prompts, no tool loop. Rewrite and ruling-mode
  parity were restored deliberately so the only remaining difference is the tool
  loop, whose base rate is zero — but no paired live-vs-frozen comparison has ever
  been run in this repo, so equivalence is argued, not measured.
- **Nothing about improvement.** This is one point estimate of the current
  pipeline. It cannot show that any change helps, because a 3-point improvement
  would sit inside judge instability.

## Reproduce

```
python evals/warm_rewrite_cache_v2.py                  # $ Haiku, cached after
python evals/build_rulesguru_full_prompts_v2raw.py     # $0, 26.4MB cache (gitignored)
python evals/run_answer_eval.py --questions evals/rulesguru_full_v2.jsonl \
  --prompts-cache evals/answers/_prompts_rulesguru_full_v2raw.json --batch \
  --out evals/answers/headline_full.json --model claude-opus-5 --effort low \
  --rewrite-version v2 --ruling-query-mode raw
python evals/judge_norules_control.py \
  --answers evals/answers/headline_full.json \
  --questions evals/rulesguru_full_v2.jsonl \
  --out evals/verdicts_headline_full_votes3.json --votes 3 --workers 8
```

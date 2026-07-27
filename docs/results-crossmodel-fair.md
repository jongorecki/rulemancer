# Results — the first fair cross-model comparison this project has run

**2026-07-27. `claude-opus-5` (effort low) vs `openai/gpt-5-mini`, answering
byte-identical prompts over the same 1,409 questions, graded by four judges from
three model families.**

Every previous cross-model number in this repo is confounded. This one is not, and
the difference is worth stating precisely.

## Why the earlier comparisons could not be used

From the parity audit run earlier this session:

- `rulesguru_sonnet` vs the opus arms share a question set but ran **different
  retrieval configs** (`rewrite_version` v2 vs none, `ruling_query_mode` raw vs
  union), and the sonnet arm's effort / max_tokens / system_version are recorded as
  `null` rather than confirmed equal.
- `h2h_gpt5mini` shares **no question set** with any opus arm, and was **judged by
  its own model family** — `report_h2h.py:15-19` says so itself: *"a LOSS here is
  strong evidence, a WIN is weak."*
- The prompts for those non-opus arms were **never persisted** (`prompts_cache:
  null`), so "same prompt" cannot be verified even in principle from what is on
  disk.

## What makes this one fair

Both models read from **one frozen prompt cache**,
`_prompts_rulesguru_full_v2raw.json`, sha256 `61bb33929f734b17…`, built at
production config (`rewrite_version=v2`, `ruling_query_mode=raw`, real retrieval,
full `Card data:` blocks, mean 19.29 retrieved rule ids per question). Same 1,409
questions, same reference answers, same judge prompt digest `b54fbdb95565abf8`,
3-vote majority throughout. **The only variable is the model.**

## The results

| judge | family | opus-5 low | gpt-5-mini | gap | rows |
|---|---|---:|---:|---:|---:|
| **gpt-5-mini, full corpus** | favours **gpt-5-mini** | **85.88%** [83.96, 87.60] | **70.05%** [67.61, 72.38] | **+15.8** | **1409** |
| Claude panel | favours **opus** | 87.3% [77.6, 93.2] | 68.1% [56.6, 77.7] | **+19.2** | 72 |
| deepseek-v3.2 | neutral | 87.3% [81.1, 91.7] | 70.0% [62.2, 76.8] | **+17.3** | 150 |
| gemini-2.5-flash-lite | neutral | 75.3% [67.9, 81.5] | 59.3% [51.3, 66.9] | **+16.0** | 150 |
| gpt-5-mini, subset | favours **gpt-5-mini** | 85.3% [78.8, 90.1] | — | — | 150 |

**Four judges, three model families, gaps of 15.8 / 16.0 / 17.3 / 19.2 — a spread
of 3.4 points.** Absolute levels vary considerably (gemini scores both arms ~12
points below deepseek), but the ranking and the magnitude do not move.

Two independent cross-checks worth noting:

- **deepseek's neutral read of the gpt-5-mini arm was 70.0% on 150 rows; gpt-5-mini's
  own family scored that arm 70.05% on all 1,409.** Different judge, different
  sample, agreeing to 0.05 points.
- **Per level, gpt-5-mini mirrors opus's curve one tier down**: 84.1 / 72.7 / 68.2 /
  54.9 / 52.2 against opus's 96.1 / 90.3 / 84.2 / 67.9 / 71.0. Same monotonic decline
  by difficulty, roughly 12-15 points lower throughout. It is not failing at one
  particular thing; it is uniformly weaker at the same things.

**The ranking is stable across every judge family tested.** opus-5 leads by 16 to
19 points regardless of who grades. Gemini scores both arms far lower in absolute
terms and still produces the same ordering with the same gap — a judge with a
different threshold but consistent ranking, which is exactly what a robustness
check should look like.

## Read the bias direction deliberately

This was committed to **before** the numbers came back:

- opus winning under the **gpt-5-mini** judge would be strong evidence (the judge's
  own family loses).
- gpt-5-mini winning under the **Claude panel** would be strong evidence (same
  logic, reversed).
- each model winning only under its own family's judge would mean *indistinguishable
  with these instruments*.

What happened: **opus won under the gpt-5-mini judge, on all 1,409 questions, by
15.8 points.** That is the strong-evidence case — the judge sharing a family with
the losing model still ranked it well behind. Both neutral judges agree within 1.5
points of that gap, and the Claude panel agrees at a slightly wider margin,
consistent with mild home-family favouritism in the direction bias predicts.

Every bracket points the same way. There is no judge in this set under which
gpt-5-mini is competitive.

**Caveat on the neutral judges, stated up front: they are UNVALIDATED.**
`judge_bakeoff.py` lists deepseek-v3.2 and gemini-2.5-flash-lite, and verdict files
from earlier runs exist, but the dashboard skips them all ("bare array, no summary")
and no agreement figure was ever recorded. They answer *"does the ranking flip
across judge families?"* — not *"which model is better."* Their agreement with each
other and with the Claude panel is what carries weight here, not either number
alone.

## The mechanism: refusals, not contested rulings

This is judge-independent, and it explains why the gap survives every grader.

| | `answered=False` | share |
|---|---:|---:|
| opus-5 | 10 / 1409 | **0.7%** |
| gpt-5-mini | 157 / 1409 | **11.1%** |

`answered` is the model's own structured-output field in both paths
(`run_openrouter_arm.py:220` reads `result.answer.answered`; `run_answer_eval.py`
uses the same field), so this is like-for-like self-reporting under one schema.

**gpt-5-mini declines roughly one question in nine, on prompts that contain the
retrieved rules and the full card data.** A decline scores as incorrect under every
judge, so a gap driven by refusals cannot be graded away — there is nothing for
judges to disagree about. That is why four judges from three families land within
3 points of each other on the size of the gap.

The Claude panel independently noticed this before the count was run: roughly a
third of gpt-5-mini's losses were outright refusals *"on questions it had the
material to answer — a pattern opus-5 never showed."*

**Methodological note:** a keyword regex for refusal phrases was tried and
discarded. It flagged 441 opus rows against 70 gpt-5-mini rows — the opposite
conclusion — because it matches hedging *inside* complete answers ("the context
doesn't include…") rather than actual declines. The structured field is the correct
instrument; the regex is recorded here only so nobody re-derives it and trusts it.

## Per-level (Claude panel, 72 rows — opus / gpt-5-mini)

| level | opus-5 | gpt-5-mini |
|---|---|---|
| 0 | 100% | 82% |
| 1 | 90% | 72% |
| 2 | 71% | 59% |
| 3 | 83% | 58% |
| Corner Case | 67% | 33% |

Both degrade with difficulty; gpt-5-mini's relative gap widens most at level 3 and
Corner Case. n is small per cell — treat as directional.

## Cost

| item | pool | cost |
|---|---|---|
| gpt-5-mini generation, 1,409 rows (16 parallel shards) | OpenRouter | $9.96 |
| earlier serial attempt (161 rows, preserved into the merge) | OpenRouter | $1.31 |
| deepseek + gemini judging, 1,800 calls | OpenRouter | ~$0.27 |
| Claude panel, 144 gradings | subscription | **$0** |
| opus-5 generation | Anthropic | already spent ($43.61, the headline run) |

The entire cross-model comparison cost about **$11.50**, because the expensive half
was already paid for by the headline run and the strongest single check was free.

## What this does not establish

- **Not a statement about gpt-5-mini in general.** It measures gpt-5-mini reading
  prompts built by and for a pipeline tuned around Claude models, including a
  system prompt it never saw during any tuning.
- **The refusal behaviour may be promptable.** An instruction tuned to discourage
  declining might close much of an 11.1% refusal rate. That is a real experiment and
  it has not been run.
- **The neutral judges are uncharacterised** (above).
- **Price does not follow list price.** `openai/gpt-5` lists at $1.25/$10 per M
  against opus-5's $5/$25 — nominally 2.5x cheaper. Measured on these prompts it
  costs **$0.032/row against opus's $0.031/row**: parity. Two effects erase the
  discount, and both are easy to miss when planning from a price table: opus ran
  through the **Batch API at 50% off**, and gpt-5 is a reasoning model whose
  thinking tokens bill as output. The genuinely cheaper options are an order of
  magnitude down (gpt-5-mini ~$0.008/row, deepseek-v3.2 ~$0.002/row), not in the
  middle of the market.

## Reproduce

```
python evals/draw_crossjudge_subset.py            # 150 stratified ids, seed 20260727
python evals/merge_gpt5mini_shards.py             # merge shards, stamp answer_gold, normalise `text`->`answer`
python evals/judge_norules_control.py --answers evals/answers/gpt5mini_fair_merged.json \
  --questions evals/rulesguru_full_v2.jsonl --out evals/verdicts_gpt5mini_fair_votes3.json \
  --votes 3 --workers 8
python evals/judge_norules_control.py --judge deepseek/deepseek-v3.2 ...
python evals/judge_norules_control.py --judge google/gemini-2.5-flash-lite ...
```

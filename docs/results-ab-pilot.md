# Results — retrieval A/B (pilot, then the full 120-row run)

> ## FINAL RESULT, n=120 paired — retrieval does not measurably help
>
> ```
> A  real retrieved CR rules                     66.7%   (120 rows)
> B  CR rules retrieved for a DIFFERENT question 63.3%   (120 rows)
>
> paired:  both right 68 | A only 12 | B only 8 | both wrong 32
>          discordant pairs: 20   ->   12-8 split, p ~= 0.5
> ```
>
> Swapping in the rules retrieved for an unrelated question costs **3.4 points**,
> which sits inside the measured 7-10% run-to-run noise floor. On 20 discordant
> pairs a 12-8 split is a coin flip. **This is the experiment the entire retrieval
> roadmap rested on, and it says the retrieved CR rules are close to inert.**
>
> The mechanism is visible in the grounding split: arm A cites CR rules on
> **97.5%** of rows, arm B on **22.5%**. The model plainly notices which rules it
> was handed — it just doesn't need them, and falls back to the card rulings.
>
> **The bound on this claim, stated plainly:** both arms retained the *correct*
> card oracle text and Scryfall rulings. So this measures the value of the
> retrieved CR rules **given correct card data**, not the value of retrieval in
> general. The honest conclusion is narrower than "retrieval is worthless": it is
> **"the CR-rules layer adds little on top of card data + rulings."** Which
> channel is actually carrying the answers is the follow-up experiment (arms R /
> K / Z, `_prompts_ab_placebo_rulings|carddata|all.json`).
>
> Everything below this box is the original 15-row pilot, kept because its cost
> model and its power analysis are what shaped the full run.

---

## The pilot (15 rows, 3 arms)

Ran 2026-07-26 against `docs/spec-retrieval-value-ab.md`, stage 1 of the staged
budget plan. **Spend: $3.36 generation + ~$0.15 judging, against a $4.55
estimate.** Account balance was ~$40; ~$36 remains.

Rows: 15 of the frozen 120-row set (`evals/ab_rows.jsonl`), 5 each from level 2,
level 3 and Corner Case. Judge `openai/gpt-5-mini`, prompt sha `b54fbdb955` —
the same judge as every published arm, so verdicts are comparable.

## Arms as actually run

| arm | rules block | effort | $/question |
|---|---|---|---|
| A | real retrieval | low | **$0.0630** |
| B | another question's retrieval (deranged placebo) | low | **$0.0648** |
| D | real retrieval | high | **$0.0960** |

**Arm C (layers tool off) was cancelled before spending** — see
`spec-retrieval-value-ab.md`. The `--prompts-cache` path makes a single
`messages.parse()` call with no `tools=` argument, so arms A and C would have
sent byte-identical requests. It would have cost ~$6 to measure run-to-run noise.

**Carry this caveat with every number below.** Because all three arms run through
the frozen-prompt path, none of them is the shipped pipeline: no tools, and
`ruling_query_mode=union` rather than the shipped `raw`. The *contrasts* are
clean, because those differences are held constant across arms. The absolute
accuracies are not the product's.

## Cost model: estimates were sound, and pessimistic where it mattered

| arm | estimated | actual | error |
|---|---|---|---|
| A | $0.060 | $0.0630 | +5% |
| B | $0.087 | $0.0648 | **−26%** |
| D | $0.102 | $0.0960 | −6% |

Arm B produced **no hedging inflation at all** — mean output 1,379 tokens against
arm A's 1,369. The worry that a model given useless context would ramble was
wrong. The standing lesson ("an arm's cost model does not transfer across arm
kinds") held for the *direction* of the risk being unknown, but here the estimate
erred safe.

Arm D roughly doubled output (1,369 → 2,692 tokens) for its 52% cost increase,
exactly as reasoning-effort pricing predicts.

## Results

```
arm A (real, low)      73.3%  (11/15)
arm B (placebo, low)   66.7%  (10/15)
arm D (real, high)     73.3%  (11/15)
```

### A vs B — the core question

```
both right         9      retrieval irrelevant on these rows
A right, B wrong   2      retrieval helped
A wrong, B right   1      placebo won
both wrong         3      retrieval cannot fix these

diff +6.7 pp — which is ONE row. Not a result.
```

### A vs D — does reasoning effort explain the oracle gap?

```
A right, D wrong   1
A wrong, D right   1
discordant         2      identical scores, 11/15 each
```

**Doubling reasoning effort bought nothing here**, at 52% more cost. Weak
evidence (n=15, 2 discordant pairs), but it points against effort explaining the
82.8% → 91.3% shipped-vs-oracle gap. If that holds, the gap really is about the
rules being handed in — which makes the retrieval question more live, not less.

## The finding that decides what happens next: discordance is 20%

Only 3 of 15 rows carried any information. Nine were right either way; three were
wrong either way. **Statistical power depends entirely on the discordant pairs,
not the row count.**

- At n=120 → ~24 discordant pairs. McNemar needs roughly **17 of 24** one way to
  reach p<0.05.
- To *detect* a genuine 2:1 effect at 80% power needs ~**68 discordant pairs ≈
  340 rows ≈ $44** of paired generation.

**That exceeds the entire account balance.** The experiment as specced cannot be
adequately powered with the money available. This is precisely what a pilot is
for, and it is better to know it for $3.36 than to discover it after $32.

What remains affordable:

| option | rows | cost | discordant | what it can conclude |
|---|---|---|---|---|
| 1 | finish the 120 | ~$14 | ~24 | a lopsided split (19-5) is conclusive; 14-10 is not |
| 2 | ~250 | ~$32 | ~50 | a null result meaningfully *bounds* the effect as small |
| 3 | stop | $0 | — | spend on the guard defect below instead |

## A product defect found for free along the way

**Arm B answered 15 of 15 questions** — every one, with a context block
containing nothing relevant to the question asked.

`contracts.py` documents the `answered` field as the low-confidence path: *"True
if the provided rules were sufficient to answer... False triggers the
low-confidence path: the bot says it can't answer from the rules it was given
rather than hallucinating. **This is the groundedness guard.**"*

Handed 100% irrelevant rules, **the guard never fired once**. The bot answered
from its own knowledge and cited the irrelevant rules it had been given.

This is a shipped-product defect, not a measurement artifact, and it is arguably
worth more than the A/B result it fell out of. It is also cheap to probe further:
the placebo cache already exists, so a larger placebo-only run measures the guard's
false-negative rate directly, with no second arm needed.

## Recommendation

**Option 1.** Finish the planned 120 rows for ~$14, keeping ~$22 in reserve.

The reasoning: after this session's review, a large retrieval effect looks
unlikely, so a cheap bounded answer beats an expensive uncertain one. And a
result that comes back flat is genuinely actionable — combined with the 55.6% of
rows that score 89.4% with zero gold in context, it would say plainly that
retrieval is not where the remaining accuracy lives.

**Do not run the $73-91 full corpus run.** Nothing learned today makes that a
better purchase than it was this morning, and two of the arms it would be
compared against have now been shown to differ from the shipped pipeline on axes
nobody had recorded.

---

## Batch API + prompt caching — measured, not assumed (2026-07-26)

**Batch API works and is worth using.** Validated end to end on a 2-row smoke
test: submitted, completed in **1 minute 47 seconds**, results collected, and a
re-run **attached to the existing batch rather than resubmitting** (the property
that stops a crashed poll from being billed twice). Row schema is identical to
the synchronous path, `usage` included. Cost halves: $0.123 -> $0.0615.

At our scale latency is not a real cost, so batch should be the default for any
`--prompts-cache` arm. It cannot be used for the live path (tool loop) or with
`--reground` (the re-ask depends on the first response); `run_answer_eval.py`
refuses both combinations loudly rather than falling back to synchronous, which
would silently produce a run believed to be half price.

**Prompt caching with batch is NET NEGATIVE for this workload. Do not enable it.**

Only the ~1,297-token system prompt is shared across rows -- user prompts share
16 characters, because the rules block and card data are per-question. Analysis
said this was worth ~9% with a break-even cache-hit rate of ~21.7% (below that,
the 1.25x write premium exceeds the 0.1x read saving). Measured on arm R, 120
rows, batched, `--cache-prompt` on:

```
rows with a cache hit:   7/120  =  6%      (break-even ~22%)
actual cost      $3.744
without caching  $3.631
caching cost us  +$0.113   (+3.1%)
```

The cause is documented and specific: a cache entry is readable only after the
first response begins streaming, so **N parallel requests sharing a prefix all
pay full price** -- none can read what the others are still writing. That is
exactly how batch dispatches. On the 2,818-row full corpus run, leaving caching
off avoids roughly $2.70 of pure waste.

Worth recording as a method note: the estimate said "~9% saving, some risk"; the
measurement said "6% hit rate, net loss." The empirical check cost $0.11 and was
folded into an arm being run anyway, rather than being discovered inside a $90
run.

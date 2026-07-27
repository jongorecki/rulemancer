# Judge stability: majority voting against gpt-5-mini's own noise

## The problem

Re-judging *identical* answers with the same judge model (`openai/gpt-5-mini`)
and the same prompt digest flips the verdict on a nontrivial slice of rows:

```
h2h hard    r1 75.9% -> r2 72.2%    4 of 54 rows flipped  (7.4%)
h2h easy    r1 92.0% -> r2 86.0%    5 of 50 rows flipped  (10.0%)
```

(source: `docs/results-adversarial-review.md`, `docs/results-failure-taxonomy.md`)

At accuracy figures in the 75-92% range, a 7-10% flip rate is comparable in
size to the entire failure set. A single judging pass is not a reproducible
number — re-running the exact same judge on the exact same answers can move
the headline accuracy several points in either direction. That makes a
single-pass number unsafe to put on a resume: it isn't clear a re-run would
reproduce it.

Separately, the project already tracks a **judge false-positive rate of
4.4% (95% CI 1.7%-10.9%)** against a human/reference-grader sample
(`docs/results-judge-error-rate.md`) — that number is about the judge being
*wrong* (systematic bias against a stricter grader), not about the judge
being *inconsistent with itself*. The two problems are different and need
different fixes.

## What was added: `--votes N`

`evals/judge_rulesguru.py` and `evals/judge_norules_control.py` (the
reference-answer judge path, which both call the shared
`judge_with_reason()`) gained an opt-in `--votes N` flag, default `1`
(unchanged default behaviour). `N > 1` judges each row independently `N`
times and takes the majority verdict, in parallel via `--workers`
(`ThreadPoolExecutor`, following the existing pattern in `judge_v5.py`).

Every individual vote is kept, per row, not just the majority winner:

```json
{
  "id": "rg2871",
  "verdict": "same",
  "votes": [
    {"verdict": "different", "reason": "..."},
    {"verdict": "same", "reason": "..."},
    {"verdict": "same", "reason": "..."}
  ],
  "tally": {"different": 1, "same": 2},
  "unanimous": false
}
```

The per-row vote spread is the evidence a majority-vote number is stable;
collapsing to just the winner would throw that evidence away. The summary
block adds `votes_per_row`, `unanimous_count`, `split_count`, `split_pct`,
and `split_ids`.

New helper: `judge_row_votes(question, reference, candidate, votes)` in
`evals/judge_rulesguru.py`, imported by `judge_norules_control.py`.

## Temperature

`judge_with_reason()`'s request body already pins `"temperature": 0`. It has
not been changed. That means the 7-10% flip rate measured above was already
happening **at temperature 0** — the source of the flips is not sampling
temperature, it's provider-side nondeterminism upstream of the model call
(OpenRouter backend routing, quantization variance across replicas, cache
effects, etc.). This matters for what majority voting can and cannot fix:
voting averages over that nondeterminism (each of the N calls is an
independent draw from the same noisy process), but it cannot make the
judge deterministic, and it cannot fix a bias that is *consistent* across
calls -- see "What this does not fix" below.

## Headline measurement: h2h_opuslow easy/hard, 3 votes, no new generation

**This is the number to quote.** The `l0_opuslow` arm (below, kept as
contrast) sits at 97% accuracy, where there is almost nothing contestable
for three judge calls to disagree about -- a low split rate there is close
to guaranteed and understates instability at any arm that actually matters
for a headline number. The h2h easy/hard arms are the *same two arms* whose
two-single-pass-run flip rates (10.0%, 7.4%) motivated this work in the
first place, and hard (75.9%) is the closer analog to a run expected to
land near ~83% accuracy.

Judged the existing `evals/answers/h2h_opuslow_easy_r1.json` (n=50) and
`evals/answers/h2h_opuslow_hard_r1.json` (n=54) with `--votes 3 --workers 6`
-- reusing already-generated answers, no new generation, no Anthropic calls.

```
.venv/Scripts/python.exe evals/judge_rulesguru.py \
  --answers evals/answers/h2h_opuslow_easy_r1.json \
  --questions evals/rulesguru_full.jsonl \
  --out evals/verdicts_h2h_opuslow_easy_r1_votes3.json \
  --votes 3 --workers 6

.venv/Scripts/python.exe evals/judge_rulesguru.py \
  --answers evals/answers/h2h_opuslow_hard_r1.json \
  --questions evals/rulesguru_full.jsonl \
  --out evals/verdicts_h2h_opuslow_hard_r1_votes3.json \
  --votes 3 --workers 6
```

(50 + 54) rows x 3 votes = 312 gpt-5-mini judge calls.

### Results

| | easy r1 single-pass | easy r1 majority-of-3 | hard r1 single-pass | hard r1 majority-of-3 |
|---|---|---|---|---|
| accuracy | 46/50 = 92.0% | 46/50 = 92.0% | 41/54 = 75.9% | 39/54 = 72.2% |
| unanimous (3/3) | -- | 49/50 (98%) | -- | 53/54 (98.1%) |
| split 2-1 | -- | 1/50 (2.0%) | -- | 1/54 (1.85%) |
| split row id(s) | -- | `rg6461` | -- | `rg4854` |

`rg6461` (easy): votes same, different, same -> majority same, matches the
old single-pass verdict (same). No net change on this row.

`rg4854` (hard): votes same, different, different -> majority **different**,
but the old single-pass verdict on this row was **same** -- the majority
flipped it relative to the recorded single-pass number.

### The number the split rate alone misses

Within-run split rate is not the whole instability picture. Comparing the
new majority verdict to the *old, independently-run single-pass verdict*,
row by row, on the hard arm:

```
rg1128:  old single-pass "same"  ->  new 3-vote majority "different"  (UNANIMOUS 3/3 in the new run)
rg4854:  old single-pass "same"  ->  new 3-vote majority "different"  (SPLIT 2-1 in the new run)
```

`rg1128` is the important one: all three votes in the new run **agreed**
with each other (unanimous), yet still landed on a different verdict than
the old single-pass call. A 2-1 split within one 3-vote batch is not the
only signature of instability -- an entire fresh batch of 3 can unanimously
land somewhere a prior single independent draw did not. With only 3 draws,
that is expected: at ~54 rows this is 2 events, too few to fit a precise
per-row noise model, but it is real and it moved the accuracy number.

- **Within-run split rate: 1/54 = 1.85%** (hard), 1/50 = 2.0% (easy).
- **Old-single-pass-vs-new-majority accuracy delta: 41/54 (75.9%) vs 39/54
  (72.2%) = 3.7 points, 2/54 rows (3.7%)** (hard); 0/50 rows (0%) (easy).

**Split rate scales with how contestable the arm is.** l0_opuslow (97%
accuracy) split at 0.48%; the h2h arms (72-92% accuracy, the two arms
whose two-run flip rate originally motivated this work) split at 1.85-2.0%
within-run, and showed a 3.7% cross-run accuracy shift on the harder,
lower-accuracy arm. A run landing near ~83% accuracy should expect
instability in the h2h range, not the l0 range.

### Honest residual instability figure

**For a run near ~75-85% accuracy, the honest number is ~2-4%, not 0.48%.**
Specifically:
- Within-run (2-1 split) instability: **~2%** (1.85% hard, 2.0% easy).
- Full old-vs-new instability, which also catches unanimous-but-shifted
  rows like `rg1128`: **up to ~3.7%** on the closer (hard, 75.9%) analog.

That is still a large improvement over the raw 7.4-10.0% two-single-pass
flip rate the problem started from -- majority voting roughly halves the
observed instability on this sample -- but it is nowhere near the ~0.5%
figure the l0 arm alone would suggest, and 0.5% should not be quoted as
"the" judge stability number for anything but a near-ceiling arm.

**Caveat on comparability:** n=50 and n=54 are small samples; 1-2 rows
moving the count is exactly the kind of small-sample noise this whole
exercise is trying to characterize, so treat "2-4%" as an order-of-magnitude
band, not a precise point estimate. A tighter number would need more votes
per row (N=5 or 7) and/or a larger contestable sample -- a natural follow-up,
out of scope for this pass under the spend ceiling.

## Contrast: `l0_opuslow` arm (97% accuracy) -- the easy case

Judged for comparison, same method, same day: `evals/answers/l0_opuslow.json`
(n=207, the best-covered current-config arm on disk) with `--votes 3
--workers 6` -> `evals/verdicts_l0_opuslow_votes3.json` (207 x 3 = 621 calls).

| | single-pass | majority-of-3 |
|---|---|---|
| accuracy | 201/207 = 97.10% | 201/207 = 97.10% |
| disagreement rows | rg102, rg1049, rg6547, rg6664, rg6743, rg6838 | same 6 rows |

Unanimous 206/207 (99.5%), split 2-1 on 1/207 (0.48%), `rg2871` (votes:
different, same, same -> majority same, matches old single-pass). No
cross-run shift on this arm.

**This 0.48% number is NOT the judge's general stability figure.** It is
what stability looks like on an arm so lopsided (97% accuracy) that almost
every row has an unambiguous verdict -- there's very little for repeat
votes to disagree about. Use the h2h-based ~2-4% figure above for any run
in the 75-92% range; reserve 0.48% for describing an arm that is itself
near-ceiling.

## What majority voting does NOT fix

Voting smooths over **provider-side nondeterminism** -- the noise that
made an identical rerun of a single-pass judge flip 7-10% of verdicts. It
does **not** touch **systematic judge bias**: if gpt-5-mini is
*consistently* wrong on some class of row (e.g. too lenient on a
particular ruling pattern, or missing a rules nuance every time), all N
votes will agree on the same wrong verdict, and majority voting reports
that wrong verdict as "unanimous" with full confidence. Unanimity is
evidence of *consistency*, not *correctness*.

That's what the project's existing 4.4% (CI to 10.9%) false-positive rate
against a reference/human grader is measuring, and majority voting does
nothing to move that number. Addressing systematic bias needs a
human-graded (or independent stronger-grader) sample compared row-by-row
against the judge's verdicts -- the kind of audit already run in
`docs/results-judge-error-rate.md` -- not more votes from the same judge.

## What this instrument is for now

Jon has since moved primary judging to a subscription-based Claude judge
panel (built and validated separately, against human-graded rows) --
subagent labor is free where OpenRouter credits are metered, and a
stronger grader is a better default instrument. That changes this
instrument's role: it is no longer the primary judge, it is the
**independent, different-vendor cross-check** on that panel.

That reframing is a genuine gain, not a demotion. A Claude panel grading
Claude-generated answers is a same-family judge -- it shares training data,
RLHF conventions, and blind spots with the system under test, so it can't
by itself rule out same-family bias inflating the headline number.
gpt-5-mini is a different vendor, different training pipeline, different
failure modes -- an outside reference point the Claude panel doesn't have
on its own.

Two things make it a *useful* cross-check rather than just a second
opinion:

1. **Verdicts are recorded per-row with stable ids** (`evals/verdicts_*_votes3.json`,
   one majority verdict + full vote tally per row id), so any row where the
   Claude panel and gpt-5-mini disagree can be looked up directly and
   compared, not just compared in aggregate.
2. **The residual instability figure (~2-4% on the h2h arms, the closer
   analog to a real headline run; 0.48% only on the near-ceiling l0 arm) is
   the noise floor.** When the panel and gpt-5-mini disagree on a row, the
   first question is "is this row one of gpt-5-mini's unstable ones, or a
   real difference of opinion between the two judges?" Rows in `split_ids`
   are direct candidates for "gpt-5-mini's own instability" (it split
   2-1 on that exact row). Rows gpt-5-mini was unanimous about are *usually*
   more likely a real cross-judge disagreement worth looking at -- but the
   hard-arm result above (`rg1128`: unanimous 3/3 in the new run, yet
   different from the old single-pass call) shows unanimity in one 3-vote
   batch is not proof the row is stable across independent runs. Treat
   unanimous-but-panel-disagrees rows as *probably* real disagreements, not
   *certainly* real ones, unless the arm is near-ceiling like l0.

## Files

- `evals/judge_rulesguru.py` -- added `judge_row_votes()`, `--votes`,
  `--workers` args (default path unchanged).
- `evals/judge_norules_control.py` -- same flag added, mirrors
  `judge_rulesguru.py`'s implementation via the shared helper.
- `evals/verdicts_h2h_opuslow_easy_r1_votes3.json` -- headline 3-vote
  measurement, easy arm (50 rows, every individual vote recorded).
- `evals/verdicts_h2h_opuslow_hard_r1_votes3.json` -- headline 3-vote
  measurement, hard arm (54 rows, every individual vote recorded).
- `evals/verdicts_l0_opuslow_votes3.json` -- contrast-only 3-vote
  measurement, near-ceiling arm (207 rows, every individual vote recorded).
  Do not quote this file's 0.48% split rate as the general judge stability
  figure.

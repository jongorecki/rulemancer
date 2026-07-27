# Results — CR rules retrieval is load-bearing, and the prior "inert" finding was a corpus artifact

**Run 2026-07-27. This result reverses the headline of `docs/results-channel-ablation.md`.**
That ablation concluded CR-rule retrieval was "~inert" (-3.3 points, p=0.50). It was
measured on a corpus that is 99.4% card-interaction questions. On card-free rules
questions, scrambling the retrieved rules collapses accuracy by **83.7 points**.

The rules were never inert. The card text was covering for them.

## The arms

Two arms over `evals/questions_rules86.jsonl` (86 card-free rules questions, 31
validated earlier + 55 drafted and blind-reviewed on 2026-07-26/27). Both arms
`claude-opus-5`, effort `low`, `rewrite_version=v2`, `ruling_query_mode=raw`, no
layers tool (removed in `f357c4a`), batched.

**The two prompts are byte-identical except inside the rules block.** Verified at
build time: first divergence at character offset 16, immediately after
`"Rules context:\n"`, and everything from `"\n\nQuestion:"` onward matches exactly,
including the system prompt. Placebo rules are those retrieved for a *different*
question in the same set — a seeded derangement (SEED=613) with no self-loops.
No row has a `Card data:` block; this set is genuinely card-free.

| arm | correct | accuracy | 95% CI (Wilson) |
|---|---|---|---|
| real rules | 85/86 | **98.84%** | [93.70%, 99.79%] |
| scrambled rules | 13/86 | **15.12%** | [9.05%, 24.16%] |

Judge: `openai/gpt-5-mini`, 3-vote majority. 2-1 splits: 1 row (real), 5 rows
(placebo). Measured judge instability at contestable accuracy is ~2-4 points
(`docs/results-judge-stability.md`), so an 83.7-point gap is not an instrument
artifact by any reading.

## The mechanism is REFUSAL, not error — and this is the more important finding

Accuracy alone badly misdescribes what happened.

| | real | placebo |
|---|---|---|
| declined to answer (`answered=False`) | 0 | **78 (90.7%)** |
| cited a CR rule | 86 (100%) | 27 (31.4%) |
| rows it attempted | 86 | 8 |
| correct among attempted | 85/86 = 98.8% | 5/8 = 62.5% |
| **confidently wrong** | 1 | **3 of 86 (3.5%)** |

Handed rules retrieved for an unrelated question, the system refuses and says why:

> `q001`: "I can't answer this from the rules provided. The context here contains
> no phasing rules at all (nothing from rule 702.25 on phasing, and nothing on
> whether a permanent phasing in counts as entering the battlefield)."

> `q003`: "The provided rules don't cover the storm ability at all, so I can't
> confirm from this context whether storm is a triggered ability..."

So the 83.7-point collapse is **70 honest declines scored as incorrect**, plus 3
genuine confabulations. Under deliberately corrupted retrieval the system produced
a confident wrong answer on **3.5% of rows** and refused on 90.7%. That is a
measured safety property, and it corroborates the prior session's finding that the
fabrication canary reads 0 on every arm.

## What this means, stated carefully

1. **CR rules retrieval is necessary for rules questions.** Not inert. The prior
   conclusion was true *of the card corpus* and false in general.
2. **The earlier result is best restated as "rules are redundant GIVEN card
   text."** Card oracle text on a card-interaction question already supplies most
   of what the retrieved rules would have said. Remove the cards and the rules
   become the whole answer.
3. **Wrong rules are worse than no rules, by a lot.** The earlier no-context
   control scored ~59.5%. Placebo here scores 15.1%. But the gap is refusal, not
   error — with no context the model answers from parametric knowledge; with
   *misleading* context it correctly declines to guess.
4. **The accuracy metric has an instrument defect: it conflates "refused" with
   "wrong."** A grounded rules bot that declines when it lacks the governing rule
   is behaving correctly. Scoring that identically to a confident error makes the
   system look roughly 6x worse than it is on this arm. **Verdicts should be
   three-way: correct / incorrect / declined.** Recommended follow-up, and it costs
   nothing because `answered` is already recorded per row.

## Caveats held honestly

- **One of the 3 "confident errors" looks like a judge false positive.** `q118`'s
  placebo answer states that "choose new targets" does not force any target to
  change, which matches CR 115.7d and the row's own reference answer. That would
  make the true confabulation count 2, not 3, and is consistent with the judge's
  measured 4.4% false-positive rate (`docs/results-judge-error-rate.md`).
- **n=86 is small.** The CI on the placebo arm spans 9.05%-24.16%. The direction
  and magnitude are unambiguous; the exact figure is not.
- **The real arm at 98.84% is near-ceiling**, which means this set cannot detect
  improvements to the real pipeline. It is a sensitive instrument for *damage*, not
  for gains. A harder card-free set would be needed to measure progress.
- **The 55 newly drafted rows were validated by blind adversarial review**, but by
  LLM reviewers grounded in the CR, not by certified judges. Every reviewer flag
  was checked against the CR text by hand and all four turned out to be reviewer
  error rather than draft error (see `b290fc5`), which is reassuring but not the
  same as human certification.
- **Same-family caveat does not apply here.** The judge is `openai/gpt-5-mini`, a
  different vendor from the generator.

## Reproduce

```
# prompts (production config, v2 rewrite + raw ruling mode)
python evals/build_rules86_real_prompts_v2raw.py
python evals/build_rules86_placebo_prompts_v2raw.py

# generation, batched
python evals/run_answer_eval.py --questions evals/questions_rules86.jsonl \
  --prompts-cache evals/answers/_prompts_rules86_real_v2raw.json --batch \
  --out evals/answers/rules86_real.json --model claude-opus-5 --effort low \
  --rewrite-version v2 --ruling-query-mode raw
# ...same with the placebo cache -> rules86_placebo.json

# judging, 3-vote majority
python evals/judge_norules_control.py --answers evals/answers/rules86_real.json \
  --questions evals/questions_rules86.jsonl \
  --out evals/verdicts_rules86_real_votes3.json --votes 3 --workers 6
```

Cost: **$3.49 Anthropic** (86 rows x 2 arms, batched: $1.91 real + $1.58
placebo), ~$1.60 OpenRouter for judging. The whole experiment that overturned a
published conclusion cost about five dollars.

## The lesson

The channel ablation's method was sound and its arithmetic was right. Its
conclusion was still wrong, because **an ablation can only tell you what a channel
contributes on the distribution you tested it on.** Rules looked inert on a corpus
where 99.4% of questions carry cards. The fix was not a better statistical test —
it was building the 86-question card-free set that let the same method ask the
question on a distribution where the answer could differ.

Previous sessions learned: *anything used as ground truth is an experiment
subject*; *you cannot know which part of a system does the work until you take it
away*. This session adds: **you cannot know what an ablation means until you run it
on more than one distribution.**

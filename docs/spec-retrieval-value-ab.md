# Spec — measuring what retrieval is actually worth (single-variable A/B)

**Status: DESIGN ONLY. Rule 0 — nothing runs until Jon rules on it.**
Written 2026-07-26 (session 11), following `docs/results-adversarial-review.md`.

## The question this answers

*Do the retrieved rules make the answers better, or does the model already know?*

Right now we cannot answer that. Not because the number is uncertain, but because
no experiment on disk isolates retrieval. Every arm we have changes two or more
things at once (review §3), so the 82.8% → 91.3% gap that motivates all retrieval
work cannot be attributed.

## The obstacle that shapes the whole design

The obvious experiment — run the shipped pipeline with the rules removed — **is
not possible.** `SYSTEM_V3` repeatedly instructs the model to answer only from
the provided rules and to decline (`answered=false`) when they are insufficient.
Hand it zero rules and it is built to refuse. That is precisely why
`build_norules_prompts.py` wrote a separate `CONTROL_SYSTEM` string, and that
decision was correct and well-documented.

But it means the no-rules control can never be a single-variable test against the
shipped pipeline. Removing the rules *forces* a prompt change.

**So we do not remove the rules. We corrupt them.**

## Design: the placebo arm

Keep every byte of the pipeline identical — same system prompt, same effort, same
tool set, same rules-block formatting, same number of rules. Change only **which**
rules go in the block.

| arm | rules block contains | everything else |
|---|---|---|
| **A — real** | the rules retrieval actually returned | shipped config, `effort=low` |
| **B — placebo** | the rules retrieved *for a different question* | identical to A |

Arm B is a true placebo: same count, same formatting, same distribution of rule
types and lengths, plausible-looking CR text — carrying no information about
*this* question. The prompt still has a populated rules block, so the decline
path never triggers and `SYSTEM_V3` stays untouched.

**Shuffled, not random.** Randomly sampled CR rules would differ in length and
character from real retrieval output and could tip the model off. Reusing another
question's retrieval block holds the distribution fixed exactly. Shuffle with a
fixed seed, derangement-checked so no row keeps its own block.

**A − B is the value of retrieval**, and nothing else differs.

## Two extra arms worth buying at the same time

Both answer live questions, both reuse the same rows and the same judging run, so
the marginal cost is only the generation.

**Arm C — layers tool off.** Jon: *"with opus, I'm curious how well things go
without the layers tool. I don't remember if the layers tool actually helps at
all."* Nobody knows, and the reason is structural: **every layers-off arm on disk
is `claude-sonnet-5` (`layers_slice0_base_layers_r1/r2/r3`) and every layers-on
arm is `claude-opus-5`.** The tool has never been toggled against a fixed model.
Arm C is arm A with `layers_tool=False` and nothing else changed.

Context for interpreting it: `resolve_layers` fires on **3 of 207 rows (1.4%)** in
the L0 arm, and only **5.4% of gold-bearing corpus rows** have any 613 rule in
gold. On the hard/layers-enriched sets it fires on ~85% of rows. So the tool is
either near-irrelevant corpus-wide or load-bearing on a narrow slice — and those
two possibilities have very different product implications.

**Arm D — effort=high.** Arm A with `effort=high`. This decomposes the headline
gap. Arm B of the derivability work (the 91.3% "ceiling") runs at `effort=high`
while the shipped pipeline runs at `effort=low`; arm D says how much of that
8.5-point gap is simply reasoning effort rather than retrieval quality.

## Row selection

**120 rows: 40 each from level 2, level 3, and Corner Case.**

Deliberately *not* corpus-representative. Levels 0 and 1 are 86.7% and 70.0%
confounded — the model answers them without rules, so they cannot show a
retrieval effect and would only dilute the signal. This estimates the effect
**where retrieval could matter**, and the writeup must say so rather than
implying a corpus-wide number.

Rules for the draw:
- Stratified random within level, fixed seed, spread across the file (not a
  prefix — that trap has fired twice in this project).
- Gold-bearing rows only (the 153 empty-gold rows cannot be scored).
- **Exclude the 8 rows in `evals/purerules.jsonl`** — that is the held-out set.
- Record the drawn ids to a frozen file before any call is made.

## Pre-registered decision rules

Written down **before** the run, because this project's recurring failure is
interpreting a number after seeing it.

| result | reading | what we do |
|---|---|---|
| A − B ≥ 15 points | retrieval is doing real work | fix retrieval; the roadmap is right |
| A − B 6-15 points | real but modest | retrieval is worth improving, not worth rebuilding around |
| A − B ≤ 5 points | **inside the noise floor** — retrieval is not measurably earning its place at these levels | stop optimising retrieval; the bottleneck is elsewhere |
| B > A | partial/irrelevant context actively harms | investigate distraction; consider retrieving less, or not at all when confidence is low |

That last row is a live possibility, not a formality: review §7 found that on hard
rows, partial gold coverage scored **31.0%** against **90.9%** for zero coverage,
replicated across three arms with gold-set size controlled.

For arm C: **if |A − C| ≤ 5 points, the layers tool is not paying for its
complexity** and should be considered for removal or for the redesign below.

## Power, honestly

The noise floor is real and large: two identical runs of the same config flipped
7.4% and 10.0% of rows (review §4).

This is a **paired** design — same question, same seed row set, one variable — so
the comparison is per-row (McNemar), not arm-mean against arm-mean. That is
substantially more powerful than the unpaired comparisons this project has been
making, because per-row noise partly cancels.

Even so: at n=120, a true effect below ~6 points will not be reliably
distinguishable. **The design can detect "retrieval matters a lot" and "retrieval
barely matters." It cannot resolve small effects, and no affordable run can.**
Stating that up front is the point.

## Cost

Rates from `rulesagent.pricing` (`claude-opus-5`, $5/MTok in, $25/MTok out,
freshness check clean). Token means from arms actually on disk.

| arm | mean in | mean out (est.) | $/question | 120 rows |
|---|---|---|---|---|
| A real | 6,400 | 1,100 | $0.060 | $7.20 |
| B placebo | 6,400 | 2,200 | $0.087 | $10.44 |
| C layers off | ~5,200 | 1,100 | $0.054 | $6.48 |
| D effort=high | 6,400 | 2,800 | $0.102 | $12.24 |

**Arm B and D output estimates are deliberately pessimistic.** The standing lesson
is that an arm's cost model does not transfer across arm kinds: removing rules
doubled-to-tripled output tokens, and output is 5x the price of input. A model
given useless context may hedge at length; a model at `effort=high` reasons
longer. Both are priced at the top of the plausible range.

```
generation (all four arms)      $36.36
judging (480 answers, gpt-5-mini)  ~$1.50
------------------------------------------
estimate                        ~$38
requested ceiling               $45
```

**Pilot checkpoint, mandatory.** Run **15 rows** (5 per level) through all four
arms first — about **$4.55**. Then stop and report: actual $/question per arm,
observed output-token inflation, and whether arm B's answers look like genuine
attempts rather than degenerate refusals. **No further spend without Jon's
go-ahead at that checkpoint.** If arm B's real cost exceeds the estimate by more
than 50%, the full run gets re-quoted before it proceeds.

**Cheaper fallback if the ceiling is too high:** arms A and B only, 120 rows —
about **$19** all-in. That still answers the core question. Arms C and D are
valuable but secondary.

## What must be recorded

Every row: the arm label, the exact rules block sent, which question the placebo
block was borrowed from, `system_version`, `effort`, `layers_tool`,
`ruling_query_mode`, token usage, and the new `prompt_supplied_rule_ids` field.
Answers land in `evals/answers/`, which is **not** gitignored and must not become
so — those files are the recorded evidence.

Judging uses `judge_rulesguru.py` with the existing judge and prompt
(`openai/gpt-5-mini`, sha `b54fbdb955`) so verdicts are comparable to every
published arm. Remember the judge is **one-directionally harsh** (7/7 human
corrections were "judge wrong → human right"), so all four arms are biased the
same way and the *difference* between arms is the robust quantity — which is
exactly what this design reads.

## Separate design question raised by Jon (not part of this spec)

If the layers tool survives arm C, its schema is incomplete. Verified against
`data/raw/MagicCompRules 20260619.txt`: the schema quotes 613.6 verbatim, 613.8a
in substance, and mentions 613.3 and 613.4a — but the tool reasons over the full
layer system, and **613.1 (the layer order), 613.2 (layer 1 sublayers), and 613.4
(layer 7 sublayers) carry the structure it depends on.** A tool asked to order
effects while holding only a fragment of the ordering rules is under-specified.

This is a real improvement and a **confound if bundled into arm C** — changing the
schema and toggling the tool in the same run reproduces the exact mistake this
whole spec exists to stop. Fix it after arm C reports, as its own change.

## Why this comes before the full run

The full run costs $73-91 and produces a corpus-wide accuracy figure on a corpus
that is 50-70% confounded, read through a 7-10% noise floor. It would give a
defensible headline number and would not tell us whether retrieval earns its
place. This costs roughly a quarter of that and answers the question the whole
roadmap depends on.

**Recommendation: run the pilot, then arms A and B at minimum. Hold the full run
until A − B is known.**

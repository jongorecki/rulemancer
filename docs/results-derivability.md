# Results — can the RulesGuru answers be derived from our gold?

**Corrected 2026-07-26 after human grading.** Three claims in the original
version are **withdrawn** — see [What is withdrawn](#what-is-withdrawn-and-why).
The headline moved from 90.0% to **93.3%**, and the "92.7% ceiling" no longer
exists as a measured quantity.

Jon's question, verbatim: *"I want to make sure we can derive the rulesguru
answers from the gold rules and rulings."*

## Provenance

Every number below is read from a named file, because this repo has already
shipped a results doc that disagreed with its own verdict file inside one commit.

| | |
|---|---|
| Questions | `evals/questions_rulesguru150_v3.jsonl` (150, stratified 30/level) |
| Arm B run | opus-5 effort high, prompt caching on, all card rulings (union mode), **no retrieval** |
| Auto verdicts | `evals/verdicts_derivability_B.json` (written 2026-07-26T00:17) |
| Human grading | `data/parsed/gold_audit_verdicts.json` (Jon, 2026-07-26T11:15) |
| Merged, published | `evals/verdicts_derivability_B_human.json` (2026-07-26T11:53) |
| Judge | `openai/gpt-5-mini`, prompt digest `b54fbdb95565abf8` |

**This accuracy names its judging run on purpose.** The judge is
nondeterministic — re-judging identical answers with the identical frozen prompt
flips roughly **1 verdict per 100 rows** and rewrites the reasoning prose every
time (`docs/results-easy-regression.md`). A digest pins the *prompt*, not the
*output*. Any figure here is one draw of the instrument.

## The answer: 93.3%

```
auto-judged                                   135/150 = 90.0%    $8.47
+ 5 judge false negatives overturned by Jon   140/150 = 93.3%   <- headline

  Level 0      30/30  100%        Level 3        26/30   87%
  Level 1      30/30  100%        Corner Case    25/30   83%
  Level 2      29/30   97%
```

Given roughly three rules (mean 3.25 gold chunks) plus the card rulings — no
search, no retrieval — the model reproduces the judge-authored answer about
nineteen times in twenty, degrading cleanly with difficulty.

The five overturned rows are `rg7215`, `rg549`, `rg1718`, `rg851`, `rg811`. On
each, **both answers say the same thing and the judge called it a
disagreement.** Jon on rg7215: *"IMPORTANT!!!!!!! they say the same thing. This
isn't a disagreement."* The judge's original verdict is preserved on every row in
the merged file, so these pairs remain available as material for measuring the
judge's false-negative rate.

## What the remaining 10 failures actually are

Jon graded all 15 auto-flagged rows in the batch-1 gold audit. The classes:

```
judge was wrong (overturned)   5   rg7215 rg549 rg1718 rg851 rg811
we were wrong                  5   rg494 rg713 rg1095 rg1208 rg842
gold was genuinely thin        2   rg241 (Jon supplied the CR chain) rg559
RulesGuru itself is wrong      2   rg6556 rg289
open rules question            1   rg5863 (which rule takes precedence)
```

Read as a range rather than a point, because two of the classes are arguments
about the reference answer rather than about the bot:

```
93.3%  140/150   as published — only Jon's approved overturns applied
94.7%  142/150   if the two wrong RulesGuru answers are scored our way
95.3%  143/150   additionally if the rg5863 precedence call goes our way
```

**93.3% is the number to quote.** The other two are stated so nobody
re-derives them later and reports them as a discovery; they depend on rulings
that have not been made. `rg5863` turns on whether `116.2f` ("only when you have
priority") or `702.62a` (suspend's own "if you could begin to cast this card"
wording) governs — Jon has asked whether WotC guidance settles it.

## What is withdrawn, and why

**1. The "gold was incomplete" category (4 rows) — withdrawn entirely.**
The original doc classified `rg7215`, `rg549`, `rg851`, `rg811` as rows where
the gold was missing something, on the evidence that arm C (same 15 questions,
gold **plus** production's retrieved top-15, $1.37) scored them correct. All four
are judge false negatives. Arm B had already answered them correctly.

Checked directly rather than inherited: arm C's four passes
(`evals/verdicts_derivability_C.json`) are exactly `rg7215`, `rg549`, `rg811`,
`rg851` — precisely four of the five rows Jon later overturned. **Arm C did not
measure retrieval closing a gap; it measured the judge changing its mind about
answers that were already right.** A re-judge that appears to show improvement,
on rows selected for having been judged wrong, is the shape of regression to the
mean, and that is the reading arm C now gets.

**2. The 92.7% ceiling — withdrawn.** It was `135 + the 4 incomplete rows`. The
category dissolved, so the arithmetic has no inputs. There is now **no measured
ceiling** for this eval. Producing one would need a fresh arm C over the
genuinely-thin rows, of which batch 1 found two (`rg241`, `rg559`) — too few to
support a ceiling claim.

**3. "Single-id rows are the risk group" — withdrawn.** The heuristic came from
noticing that two of those four rows had exactly one gold rule. Both are judge
false negatives, so the observation was about which rows the judge mishandles, if
anything, and not about thin gold. It should not be used to target further
auditing.

## What this changes for retrieval

The original conclusion — **retrieval is the bottleneck, not reasoning** —
survives, but the size of the gap has to be quoted on a like-for-like basis.

```
gold-only arm B, auto-judged                     90.0%
production (sonnet-5, retrieval finding)      ~75-82%   auto-judged
gap                                            8-15pp
```

**Compare auto to auto.** 93.3% is human-corrected; the production figures are
not. Since the same judge produced both, production's numbers are understated by
a similar few points, so subtracting a corrected number from an uncorrected one
would double-count the correction and inflate the gap. On a consistent auto
basis the gap is roughly **8-15 points**, down from the 11-18 originally
claimed, and still the largest single lever in the system. The retrieval branch
— multi-query, `REWRITE_N` 1->3, the diversity work — remains aimed at a real
target.

Corroborating this from the other direction: `rg241` is a case where **all four
CR rules in Jon's derivation are already in the index**, and multi-query moved
the key rule from rank 33 to rank 10. The gap there is multi-hop reach, not
missing content (see the handoff's retrieval section).

## Footnote — this arm's ruling citations are unusable

**The accuracy stands; the citations do not.** These prompts were built by
`evals/build_gold_prompts.py`, which called `build_prompt()` directly at a time
when card-ruling labels were applied inside `RulesAgent.answer()`. So the rulings
rendered as an unlabelled bullet list while the system prompt still instructed
the model to cite `[Card Name ruling #N]`. With no labels to copy the model
counted bullets **1-based**, and **every ruling citation in this arm is off by
one** — 83 of the 120 rows that cite a ruling carry at least one index past the
end of the card's list. Full investigation:
`docs/report-ruling-citation-offbyone.md`.

**This does not touch the 93.3%.** The judge compares answer text to the
reference answer; it never resolves a citation label. Spot-checked by hand, the
1-based reading lands on the *correct* ruling — the reasoning was right, the
index was wrong. CR rule citations (`[614.12]` and friends) are unaffected; those
labels were always real.

The labelling now happens inside `build_prompt()`, the boundary every prompt
builder shares, so a future builder cannot reintroduce this by not knowing it had
to (`label_rulings()`, guarded by `tests/test_ruling_labels.py`). **Jon's call,
2026-07-26: do not re-run arm B for the fix** — the accuracy is unchanged and the
re-run would cost about what arm B cost. Treat this arm's `citations` field as
unusable for analysis; use a post-fix arm instead.

## Limits of this number, stated plainly

- **A ceiling-ish figure, not a forecast.** Arm B ran opus-5 at effort high with
  the gold handed to it. Production runs opus-5 at effort low behind retrieval.
  93.3% is what the gold *supports* under favourable conditions.
- **One judging run of a nondeterministic judge.** ~1 flip per 100 rows means
  ±1-2 rows of wobble in the headline before anything real changes.
- **One grader, ungraded rows unexamined.** Only the 15 rows the judge flagged
  were human-graded. The judge's **false negatives among the 135 it passed have
  never been checked** — that is the reverse error, and it would push the true
  figure in the other direction. Measuring it is queued.
- **One draw of 150.** Mining is low-reproducibility (below) and generation is
  not temperature-pinned.
- **Measured against gold with the known conjunctive-grouping flaw** (adversarial
  review, 2026-07-26). That flaw affects *recall* scoring, not this experiment —
  arm B hands the model every gold id regardless of grouping — so these numbers
  are unaffected by it.

## Reproducibility caveat on the gold itself

A control run re-mined 50 already-mined questions under the original prompt. It
disproved the hypothesis it was built to test (prompt wording was worth 1 point,
not 8) and found something larger: two independent mining runs on identical
questions produce **identical gold on only 26% of rows, mean overlap 0.54, with 6
of 50 sharing no rules at all.** For any given question, "the gold" is largely
whichever draw happened to run. That is a property of the method, not of this
session; it applies to the original 150-row run too.

It does not undermine the result: whatever draw produced this gold, that gold
demonstrably supports the answers. But a different draw would produce a somewhat
different 93.3%.

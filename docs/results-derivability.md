# Results — can the RulesGuru answers be derived from our gold?

**Corrected twice on 2026-07-26. The second correction reinstated most of what the
first one withdrew.** The short version: arm B is **91.3%**, the "gold was
incomplete" category is **real** (3 rows), and the ceiling is **93.3%**. If you
read the version of this doc that withdrew those claims, it was wrong — see
[How this doc moved](#how-this-doc-moved-twice) for why, because the failure mode
is worth more than the numbers.

Jon's question, verbatim: *"I want to make sure we can derive the rulesguru
answers from the gold rules and rulings."*

## Provenance

| | |
|---|---|
| Questions | `evals/questions_rulesguru150_v3.jsonl` (150, stratified 30/level) |
| Arm B | opus-5 effort high, prompt caching on, all card rulings (union), **no retrieval** |
| Arm C | the 15 arm-B failures, re-run with gold **plus** production's retrieved top-15 |
| Auto verdicts | `evals/verdicts_derivability_B.json`, `evals/verdicts_derivability_C.json` |
| Human grading | `data/parsed/gold_audit_verdicts.json` (Jon, 2026-07-26) |
| Merged, published | `evals/verdicts_derivability_B_human.json` — 2 overturns applied |
| Judge | `openai/gpt-5-mini`, prompt digest `b54fbdb95565abf8` |

**The judge is nondeterministic** — re-judging identical answers with the identical
frozen prompt flips ~1 verdict per 100 rows. A digest pins the *prompt*, not the
*output*. Every figure here is one draw of the instrument.

## The answer: 91.3%

```
auto-judged                                  135/150 = 90.0%
+ 2 judge false negatives overturned by Jon  137/150 = 91.3%   <- headline

  Level 0      30/30  100%        Level 3        25/30   83%
  Level 1      30/30  100%        Corner Case    24/30   80%
  Level 2      28/30   93%
```

Given roughly three rules (mean 3.25 gold chunks) plus the card rulings — no
search, no retrieval — the model reproduces the judge-authored answer about nine
times in ten, degrading cleanly with difficulty.

The two overturned rows are **`rg1718`** and **`rg851`**. On `rg1718` the answers
agree on the case actually asked (a two-player game: zero cards) and ours adds a
multiplayer case. On `rg851` both say Lust for War ends up in the graveyard and
differ only on the mechanism — Jon's own note flags that ("303.4i is the operative
rule here"), and arm C's near-identical answer was judged `same`, which is what a
judge flip looks like.

## The 13 remaining failures

```
gold was INCOMPLETE   3   rg7215 rg549 rg811   -> failed on gold alone, CORRECT once retrieval was added
we were wrong         5   rg494 rg713 rg1095 rg1208 rg842
gold was thin         2   rg241 (Jon supplied the CR chain) rg559
RulesGuru is wrong    2   rg6556 rg289
open rules question   1   rg5863 (116.2f vs 702.62a precedence)
```

**The incomplete-gold category is a checked fact, not an inference.** On all three
rows arm C's answer matches the reference answer's bottom line, and arm B's
contradicts it:

| | gold | arm B (gold only) | arm C (gold + retrieval) |
|---|---|---|---|
| `rg7215` | Tapped | "enters **untapped**" ✗ | "enters **tapped**" ✓ |
| `rg549` | Any color | "produces **no mana**" ✗ | "any one **color**" ✓ |
| `rg811` | "but **no other abilities**" | keeps flying + vigilance ✗ | "does **not** have flying, vigilance, or the threshold ability" ✓ |

Jon adjudicated all three on 2026-07-26: **the gold is correct in each case.**

## The ceiling

```
arm B, gold as it stands              137/150 = 91.3%
+ repairing the 3 incomplete rows     140/150 = 93.3%   <- ceiling with perfect retrieval
beyond retrieval                       10/150 =  6.7%
```

**93.3% is the most this eval can score** however good retrieval gets. The 10
unreachable rows fail with the gold *and* everything retrieval would have
supplied: `rg1095 rg1208 rg241 rg289 rg494 rg559 rg5863 rg6556 rg713 rg842`.
They are reasoning failures, thin gold, or cases where the RulesGuru answer is
itself wrong — a class that is real and confirmed (three wrong RulesGuru answers
were found and corrected on 2026-07-25, `docs/gold-corrections.md`).

**Thin gold is a usable risk signal.** Two of the three incomplete rows had
exactly ONE gold rule (`rg7215` → `614.12`; `rg549` → `106.7`). Single-id rows
deserve a second look — a cheap heuristic for finding more.

## What this changes for retrieval

**Retrieval is the bottleneck, not reasoning**, and the incomplete-gold rows are
the direct evidence: three questions the model got *wrong* with gold alone and
*right* once retrieval supplied the missing rule.

```
gold-only arm B, auto-judged                     90.0%
production (sonnet-5, retrieval finding)      ~75-82%   auto-judged
gap                                            8-15pp
```

**Compare auto to auto.** 91.3% is human-corrected; the production figures are
not. The same judge produced both, so subtracting a corrected number from an
uncorrected one double-counts the correction. On a consistent auto basis the gap
is roughly **8-15 points** — still the largest single lever in the system.

Corroborating from the other direction: on `rg241` all four CR rules in Jon's
derivation are already in the index, and multi-query moved the key rule from rank
33 to rank 10. That gap is multi-hop reach, not missing content.

## How this doc moved, twice

Worth recording, because the mechanism generalises.

**v1 (correct).** Reported 90.0%, an incomplete-gold category of 4 rows, a 92.7%
ceiling, and the single-id heuristic.

**v2 (wrong).** Jon hand-graded the 15 flagged rows and marked 5 as "they say the
same thing." That was applied as a rescore, taking the headline to 93.3%, and
because 4 of those 5 were the incomplete-gold rows, the whole category was
withdrawn along with the ceiling and the heuristic. Arm C's passes were
reinterpreted as the judge changing its mind about answers that were already
right.

**v3 (this version).** On a second read, 3 of those 5 rows turn out to be flat
contradictions of the reference answer — opposite bottom lines, quoted in the
table above. Jon adjudicated: the gold is correct on all three. So they revert to
incorrect, the headline is 91.3%, and **the category, the ceiling and the
heuristic are all reinstated** — v1 was right.

**The lesson is not "the human grading was wrong."** It is that v2 took a human
label as ground truth and rewrote a published result on it *without checking the
label against the answer text* — the exact failure v2 itself was written to
correct in the judge. The instrument under audit changed from the LLM judge to
the human grader, and the audit skipped. **Anything used as ground truth is an
experiment subject, including a person.** The check that would have caught it
costs one minute: read the gold's first sentence next to ours.

## Limits of this number, stated plainly

- **A favourable-conditions figure, not a forecast.** Arm B ran opus-5 at effort
  high with the gold handed to it; production runs opus-5 at effort low behind
  retrieval.
- **One judging run of a nondeterministic judge.** ~1 flip per 100 rows means
  ±1-2 rows of wobble before anything real changes.
- **Only flagged rows were human-graded.** The judge's errors among the 135 it
  *passed* are measured separately and are non-zero — see
  `docs/results-judge-error-rate.md`, which puts an upper bound of ~4.4% on
  wrongly-passed rows. That pushes the true figure *down*, not up.
- **One draw of 150**, with mining known to be low-reproducibility (below).
- **Measured against gold with the known conjunctive-grouping flaw** (adversarial
  review, 2026-07-26). That affects *recall* scoring, not this experiment — arm B
  hands the model every gold id regardless of grouping.

## Footnote — this arm's ruling citations are unusable

**The accuracy stands; the citations do not.** These prompts were built by
`evals/build_gold_prompts.py`, which called `build_prompt()` at a time when
card-ruling labels were applied inside `RulesAgent.answer()`. The rulings rendered
as an unlabelled bullet list while the system prompt still demanded citations of
the form `[Card Name ruling #N]`, so the model counted bullets **1-based** and
**every ruling citation in this arm is off by one** — 83 of the 120 citing rows
carry at least one index past the end of the card's list. Full investigation:
`docs/report-ruling-citation-offbyone.md`.

This does not touch the accuracy: the judge compares answer text and never
resolves a citation label. CR rule citations (`[614.12]`) are unaffected — those
labels were always real. Labelling now happens inside `build_prompt()`, the
boundary every builder shares (`label_rulings()`, guarded by
`tests/test_ruling_labels.py`). **Jon's call: arm B is not re-run** — the
accuracy is unchanged and the re-run buys only citation data. Treat this arm's
`citations` field as unusable; use a post-fix arm.

## Reproducibility caveat on the gold itself

A control run re-mined 50 already-mined questions under the original prompt. It
disproved the hypothesis it was built to test (prompt wording was worth 1 point,
not 8) and found something larger: two independent mining runs on identical
questions produce **identical gold on only 26% of rows, mean overlap 0.54, with 6
of 50 sharing no rules at all.** For any given question, "the gold" is largely
whichever draw happened to run. That is a property of the method, not of this
session.

It does not undermine the result: whatever draw produced this gold, that gold
demonstrably supports the answers. But a different draw would produce a somewhat
different 91.3%.

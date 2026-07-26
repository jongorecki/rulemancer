# Results — can the RulesGuru answers be derived from our gold?

Run 2026-07-26 on all 150 questions of `evals/questions_rulesguru150_v3.jsonl`.
opus-5 at effort high, prompt caching on, all card rulings included (union mode).
Judged by the frozen instrument, digest `b54fbdb95565abf8` **unchanged**, so these
numbers sit on the same scale as every prior figure.

Jon's question, verbatim: *"I want to make sure we can derive the rulesguru
answers from the gold rules and rulings."*

## The answer: yes, 90%

```
Arm B — gold rules only, no retrieval          135/150 = 90.0%    $8.47

  Level 0      30/30  100%        Level 3        24/30   80%
  Level 1      30/30  100%        Corner Case    23/30   77%
  Level 2      28/30   93%
```

Given roughly three rules (mean 3.25 gold chunks) plus the card rulings — no
search, no retrieval — the model reproduces the judge-authored answer nine times
out of ten, degrading cleanly with difficulty.

## Splitting the 15 failures

Arm C re-ran only the 15 failures with gold PLUS production's retrieved top-15,
for $1.37. That distinguishes "the gold was missing something" from "nothing
would have helped".

```
gold was INCOMPLETE (passed once retrieval was added)   4
beyond retrieval  (failed even with gold + top-15)     11
```

| | |
|---|---|
| **rg7215** | level 2, gold was a single id (`614.12`) |
| **rg549** | level 3, gold was a single id (`106.7`) |
| **rg851** | Corner Case, 4 gold ids |
| **rg811** | Corner Case, 7 gold ids — a layers/timestamp question Jon had separately confirmed the bot got genuinely wrong |

Two of the four had exactly ONE gold rule. Thin gold is the risk factor, which
is a cheap heuristic for finding more: single-id rows deserve a second look.

## The ceiling

```
arm B, gold as it stands            135/150 = 90.0%
+ repairing the 4 incomplete rows   139/150 = 92.7%   <- ceiling with perfect retrieval
unreachable by any retrieval work    11/150 =  7.3%
```

**92.7% is the most this eval can ever score**, no matter how good retrieval
gets. The 11 unreachable questions fail with the gold AND everything retrieval
would have supplied: they are reasoning failures, or the RulesGuru answer itself
is wrong. That second class is real and confirmed — three wrong RulesGuru answers
were found and corrected on 2026-07-25 (`docs/gold-corrections.md`), so some of
these 11 are likely more of the same.

Unreachable: `rg241 rg494 rg713 rg559 rg1095 rg1718 rg6556 rg289 rg1208 rg5863 rg842`

## What this changes

**Retrieval is the bottleneck, not reasoning.** This is the first measurement
that separates them, and it inverts an assumption made earlier the same night —
that the layers/timestamp cluster meant reasoning was the weak link.

```
production today (sonnet-5, retrieval doing the finding)   ~75-82%
this ceiling (right rules in hand)                          ~92.7%
```

That gap is retrieval failure, and it is worth roughly **11-18 points**. So the
retrieval branch — multi-query, the `REWRITE_N` 1->3 decision, the diversity
work — is aimed at a real target after all.

## Limits of this number, stated plainly

- **A ceiling, not a forecast.** This ran opus-5 at effort high; production runs
  sonnet-5 at the API default effort. 90% is what the gold *supports* with a
  strong model, not what production would score.
- **Auto-judged only.** On the bucket-A grade, ~12% of the judge's flags proved
  to be judge errors and 3 were bad reference answers. True derivability is
  plausibly 92-93%, and the ceiling correspondingly higher.
- **One draw of 150.** Mining is known to be low-reproducibility (see below), and
  generation is not temperature-pinned.
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

It does not undermine the 90%: whatever draw produced this gold, that gold
demonstrably supports the answers. But a different draw would produce a somewhat
different 90%.

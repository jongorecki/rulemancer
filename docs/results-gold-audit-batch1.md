# Results — gold audit, batch 1 (the derivability 15)

Jon graded all 15 rows that the judge flagged as failures in derivability arm B.
**A third of them turned out to be the judge being wrong, not the bot.** That
finding forced a correction to `docs/results-derivability.md` and is the origin
of the queued work on judge false-negative rate.

## Provenance

| | |
|---|---|
| Rows | the 15 arm-B failures, assembled by `evals/build_gold_audit_input.py` |
| UI | `evals/build_grading_ui.py --verdicts gold-audit` (spec: `docs/spec-gold-audit-ui.md`) |
| Grader | Jon Gorecki, 2026-07-26 |
| Raw verdicts | `data/parsed/gold_audit_verdicts.json` (2026-07-26T11:15) |
| Merged into arm B | `evals/verdicts_derivability_B_human.json` (2026-07-26T11:53) |
| Judge under audit | `openai/gpt-5-mini`, prompt digest `b54fbdb95565abf8` |

Retrieval shown in the UI for these rows was a **probe against the current
index**, not what the run pulled — arm B ran with retrieval off by design. Every
probed row is labelled `retrieved_provenance: "probe"` so the panel cannot be
misread as a record of the run.

## The vocabulary

Batch 1 grades *who is wrong*, not *is the bot right*. That is the whole point:
these rows are pre-selected for having been called wrong, so the useful question
is which party made the error.

| Verdict | Meaning |
|---|---|
| `ours-wrong` | the bot's answer is genuinely incorrect |
| `rulesguru-wrong` | the reference answer is incorrect |
| `gold-incomplete` | the answer needs a rule the gold does not contain |
| `ambiguous` | the two answers do not actually conflict, or the rules do not settle it |

## The 15 rows

```
id        level         verdict            counted correct?
rg7215    2             ambiguous          yes   both answers say the same thing
rg549     3             ambiguous          yes   same
rg1718    3             ambiguous          yes   same
rg851     Corner Case   ambiguous          yes   same
rg811     Corner Case   ambiguous          yes   same
rg5863    Corner Case   ambiguous          no    open rules-precedence question
rg494     3             ours-wrong         no
rg713     3             ours-wrong         no
rg1095    3             ours-wrong         no
rg1208    Corner Case   ours-wrong         no
rg842     Corner Case   ours-wrong         no
rg241     2             gold-incomplete    no
rg559     3             gold-incomplete    no
rg6556    Corner Case   rulesguru-wrong    no
rg289     Corner Case   rulesguru-wrong    no

by class:  ambiguous 6   ours-wrong 5   gold-incomplete 2   rulesguru-wrong 2
by level:  L2 2   L3 6   Corner Case 7
```

> ⚠️ **CORRECTED 2026-07-26.** Five of the six `ambiguous` rows were initially
> approved as overturns, taking arm B to 140/150 (93.3%). On a second read,
> **three of those five contradict the reference answer outright** and Jon
> adjudicated the gold correct on all three. Only `rg1718` and `rg851` survive as
> overturns. **Arm B is 137/150 = 91.3%.** The class counts in the table above are
> the grading as originally recorded; the corrected reading is below.

```
corrected classes
  judge was wrong (overturned)   2   rg1718 rg851
  gold was incomplete            3   rg7215 rg549 rg811   <- arm B wrong, arm C right
  we were wrong                  5   rg494 rg713 rg1095 rg1208 rg842
  gold was thin                  2   rg241 rg559
  RulesGuru is wrong             2   rg6556 rg289
  open rules question            1   rg5863
```

## Finding 1 — the judge's false-negative rate is 2 in 15, not 5

**As first written this section said five, and it was wrong.** The correction
matters more than the original claim, so it leads.

Three of the five rows graded "they say the same thing" state the *opposite*
bottom line from the reference answer:

| | gold says | we said |
|---|---|---|
| `rg7215` | "Tapped." | "Minas Tirith enters **untapped**." |
| `rg549` | "Any color." | "Quirion Explorer produces **no mana**." |
| `rg811` | 4/4 black Frog "**but no other abilities**" | keeps "**flying, vigilance** … plus its **Threshold** ability" |

Jon adjudicated 2026-07-26: **the gold is correct in all three.** They revert to
incorrect. The surviving false negatives are `rg1718` (answers agree on the case
actually asked) and `rg851` (same end state, different mechanism — and arm C's
near-identical answer was judged `same`, which is what a flip looks like).

**What that reverses.** This section previously claimed the "gold was incomplete"
category in `docs/results-derivability.md` was an artefact — that arm C had
measured the judge changing its mind rather than retrieval closing a gap. The
opposite is true. Arm C's answers on those three rows match the gold's bottom
line where arm B's contradict it, so **retrieval genuinely fixed them.** The
category, the ceiling (now 93.3%) and the single-id heuristic are all reinstated.

**How the error happened, since it is the more useful finding.** A human label was
taken as ground truth and a published result was rewritten on it *without checking
the label against the answer text* — the exact failure this audit existed to
catch in the LLM judge. When the instrument under audit changed from the judge to
the grader, the auditing stopped. **Anything used as ground truth is an experiment
subject, including a person.**

**It remains unmeasured in the direction that matters more.** This audit only saw rows
the judge called *wrong*. Its false negatives among the **135 it passed have
never been checked**, and those would push the true figure down rather than up.
Combined with the ~1-flip-per-100-rows nondeterminism measured separately
(`docs/results-easy-regression.md`), the honest position is that the judge's
error bars are not yet known in either direction. That gates how much to trust
every accuracy number in this repo. Infrastructure for measuring it already
exists: `evals/opus_grader_calibration.py`,
`docs/plan-opus-grader-calibration.md`, `evals/judge_agreement_results.json`.

## Finding 2 — out-of-range ruling citations (3 of 15 rows) — INVESTIGATED, root cause found

On `rg1095`, `rg549` and `rg1718`, the bot cites ruling indices that do not
exist. Jon on `rg1095`: *"cited ruling #3 is out of range — Rescuer Sphinx has 3
rulings, #0-#2."*

**Full investigation: `docs/report-ruling-citation-offbyone.md`.** It corrects
this section in three ways, and the first was my error, written here before the
investigation ran:

- **It is not a product bug.** Production-path arms emit **0 out-of-range
  citations across 397 checked.** The defect is confined to
  `evals/build_gold_prompts.py`, so it affects the two derivability arms only.
- **It is much larger than 3 of 15.** In arm B, **83 of the 120 rows citing a
  ruling (69%)** carry at least one out-of-range citation.
- **Root cause:** the label-injection step lives in `RulesAgent.answer()`, not at
  the prompt-construction boundary. `build_gold_prompts.py` calls
  `build_prompt()` directly, so rulings render as an unlabeled bullet list while
  the system prompt still instructs the model to cite `[Card Name ruling #N]`.
  With no labels to copy, the model counts the bullets **1-based** — 341
  citations in arm B, not one of them `#0`, where the production arm's modal
  index *is* `#0`.

It does not invalidate the accuracy: the judge compares answer text, not citations.

## Finding 3 — card-name completeness may affect ruling retrieval

On `rg289`, Jon: *"This points to an issue we might be seeing in other rulings
where we need to make sure that the card is referred to by its full name. would
that have effected the answer here?"* Untested. Production derives card names via
`parse_card_refs()` on the question text, so a partial or informal name is a
plausible failure path into ruling lookup.

Related and already fixed in the same session: the grading UI's card panel had
been **empty for every RulesGuru row** because enrichment read the questions
file's `cards` field, which is `null` for all 150, instead of deriving names the
way production does. 0/0 cards became 40/40 with 184 rulings.

## Finding 4 — level-weighted scoring, requested and now ruled

Two notes asked for it. `rg842`: *"I wouldn't consider this one part of scoring
too strongly... it's more important that we get the level 3 questions right than
it is we get the corner cases right, but we should try for both."* `rg1208`:
*"major corner case. never would happen in game. not super important to me to get
right."*

**Jon's ruling: flat across L0-L3, Corner Case 0.5.** Spec is
`docs/spec-weighted-scoring.md`, which predates the ruling and still frames it as
a recommendation. Note that batch 1 is itself Corner-Case-heavy (7 of 15), which
is what surfaced the request.

## What batch 1 does not tell us

- **It is not a sample of the corpus.** These 15 rows were selected by the judge
  for being wrong, so class proportions here say nothing about the other 135.
- **One grader, one pass.** No second opinion, no re-grade for consistency.
- **`ambiguous` is doing two jobs.** Five rows mean "these answers agree"; one
  (`rg5863`) means "the rules do not settle it." Batch 2 should split that label
  — they lead to opposite actions, one a judge fix and one a rules question.

## Batch 2

The full-data rows: `rg1802`, `rg4440`, `rg5628` (missed by every arm of both
models in the easy-set regression check, so gold-error candidates) plus the
h2h/costbase rows. Build with `--provenance run` — those rows carry real
`retrieved_rule_ids`, so the panel flips to the green "retrieved by the run"
label instead of the probe label.

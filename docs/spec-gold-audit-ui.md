# Spec — gold-audit grading UI (batch 1: the derivability 15)

Design-only until Jon rules. Jon ruled 2026-07-26: build it, in batches, the 15
first, using the gold-audit vocabulary.

## What this is for

> **Outcome, added 2026-07-26 — the framing below has since been overturned by
> the very audit it specifies.** Batch 1 found that 5 of the 15 rows were **judge
> false negatives**, including all 4 of the "incomplete gold" rows. The
> unreachable/incomplete split in this section is what we believed when the
> screen was built, kept as-is because it is the input the build used. For what
> the rows turned out to be, read `docs/results-gold-audit-batch1.md`.

`docs/results-derivability.md` established that 11 of 150 questions are
**unreachable by any retrieval work** — hand the model the complete gold rules
and it still fails — and that 4 more had **incomplete gold** (they passed once
retrieval was added back). Those 15 rows are the strongest evidence we have that
the fault is in the *reference data*, not the bot.

That is a judgment call a human has to make, and it can't be made from a verdict
file. Making it needs the question, both answers side by side, the CR text of the
gold rules, what retrieval actually surfaces, and the official card rulings — on
one screen. This spec adds that screen.

The precedent it feeds: `docs/gold-corrections.md` established that **an official
card ruling outranks RulesGuru gold**, because that is objectively checkable.
Three answers were corrected on that basis. Showing the rulings is what makes the
exception applicable.

## The rows

Batch 1 is the 15 rows in `evals/answers/derivability_C_failures.json` — verified
against the file, not just the doc:

```
unreachable (11)   rg241 rg494 rg713 rg559 rg1095 rg1718 rg6556 rg289 rg1208 rg5863 rg842
incomplete gold (4) rg7215 rg549 rg851 rg811
```

Batch 2 (later, not this spec) is the full-data rows: the 3 that every easy-set
arm misses (`rg1802`, `rg4440`, `rg5628`) and suspect rows from the h2h/costbase
runs, which carry real `retrieved_rule_ids`.

## What the data can and cannot support

Checked before designing, because the panels make claims:

| Panel | Source | Status |
|---|---|---|
| Question, our answer, RulesGuru answer | `derivability_C_failures.json` (`question`, `answer`, `answer_gold`) | present |
| Gold rules + CR text | `gold`, `gold_text` | present, already rendered |
| Card info (per face) | `_load_card_data()` via `data/scryfall.db` | present, already rendered |
| Card rulings text | `_load_card_data()` | loaded today, rendered **only when cited** |
| Retrieved CR rules | `retrieved_rule_ids` | **absent — 0 of 15 rows** |

The retrieved set is absent by design, not by defect: derivability arm B was
gold-only, with retrieval switched off. That is what let it separate retrieval
failure from reasoning failure in the first place.

## Two labels that are load-bearing

Both new panels show something adjacent to what a reader will assume, so both are
labeled in the UI itself, not just here.

**1. The retrieved panel is a fresh probe, not run provenance.** Since these rows
retrieved nothing, the panel is filled by running retrieval *now*, against the
current index. That index has changed since those runs (10 questions repointed,
`606.5` added), so it answers "would retrieval find this today?" and NOT "what did
that run pull?" Every batch-1 row renders the label **"retrieved today (probe) —
not what the run pulled."** Batch 2 rows carry a real `retrieved_rule_ids` and
flip to **"retrieved by the run."** The flag is per row, so a mixed queue is
never ambiguous.

This matters because the repo's recurring defect is a number arriving with an
unchecked claim about how it was produced. An unlabeled retrieval panel would be
exactly that.

**2. The rulings panel is everything on file, not what the model saw.** No row
records which rulings `ruling_select` put into the prompt, so the panel shows all
Scryfall rulings for every card the question references, with cited ones marked.
Labeled **"all rulings on file for these cards (Scryfall) — not necessarily what
the model was shown."** This is the right material regardless: the reason to show
rulings is to apply the card-ruling-outranks-gold exception, which needs the
complete ruling list, not the model's subset.

## Verdict vocabulary

Batch-1 buttons replace correct/partial/wrong, which does not fit — every one of
these rows is an arm-B failure, so "ours was wrong" is already true by
construction. The open question is *who* is wrong:

```
RulesGuru answer wrong        the reference answer is incorrect
Gold incomplete or mis-cited  reference answer fine, gold rules don't support it
Our reasoning wrong           reference and gold are both fine
Ambiguous, both defensible    genuinely unclear or question is underspecified
```

Free-text note per row is kept, along with the existing keyboard shortcuts and
progress bar. Export stays the `{id, verdict, note}` shape so
`evals/harvest_grading_notes.py` keeps working untouched, but writes to
**`gold_audit_verdicts.json`** — a distinct filename, so a gold-audit export can
never be mistaken for or merged with an `answer_verdicts.json` answer-quality
export.

## Implementation

Approach: extend the single grading UI rather than fork one. The retrieved-rules
panel is not batch-1-specific — it is the fix for the largest actionable category
in `docs/grading-feedback-backlog.md` (**27 notes**, "rule/ruling TEXT not shown
though citations present"), and batch 2 needs it too. A fork would leave that
defect to be fixed in two places.

1. **`evals/build_gold_audit_input.py`** (new, small). Reads
   `derivability_C_failures.json`, runs the retrieval probe per question via
   `HybridRetriever.search()`, and writes rows carrying `retrieved_rule_ids` plus
   `retrieved_provenance: "probe"`. Card data and gold text resolution are reused
   from `build_grading_ui.py`, not reimplemented.

2. **`evals/build_grading_ui.py`** gains two things:
   - a **Retrieved** panel rendering ids to CR text through the existing
     `textMap`, with the per-row provenance label, and the same visible
     `(text not found as a chunk)` fallback the other panels use;
   - a `--verdicts {answer-quality,gold-audit}` switch selecting the button set
     and default export filename. Default stays `answer-quality`, so existing
     usage is unchanged.

3. **Output**: `data/parsed/gold_audit_15.html`.

## Testing

`build_grading_ui.py` has no tests today. This adds focused coverage for the new
behavior only, rather than retrofitting the whole 562-line file:

- retrieved ids resolve to CR text in the rendered payload;
- a missing chunk id renders the visible fallback rather than being dropped
  silently;
- `--verdicts gold-audit` emits the four gold-audit buttons and the
  `gold_audit_verdicts.json` default, and `answer-quality` still emits the
  original three;
- the provenance flag round-trips per row, so a mixed queue labels each row
  correctly.

Verify by rendering, per the standing rule: build the HTML, serve it, and look at
the page before calling it done. **Jon runs the app on port 8000 — never bind or
kill it.**

## Cost

15 query embeddings for the probe. Voyage, not Anthropic, so it cannot draw on
the API-credit pool the eval runs use. Generation cost: zero — no answers are
regenerated.

## Out of scope

No restyling (the existing dark theme, sticky header, progress bar and keyboard
shortcuts stay). No change to the existing answer-quality verdict flow. No change
to `answer.py`. No gold edits — this batch produces *judgments*, and any
correction is a separate ruled change, recorded the way
`docs/gold-corrections.md` records the previous three.

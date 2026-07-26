# Results — match-semantics gap on the full corpus

**In plain language, before any table:** every question's gold rules carry a
`match` field that says what counts as "retrieval found it" — `any` (one gold
rule is enough), `all` (every gold rule must show up), or `groups` (an
AND-of-ORs structure: several required steps, each of which may have its own
alternative phrasings). On the curated 150-question set
(`questions_rulesguru150_v3.jsonl`), someone actually made that call per
question — the three modes are all in use. On the full 1,409-question corpus
(`rulesguru_full_v2.jsonl`) and its 207-row L0 subset (`_l0_only.jsonl`),
every single row is `match: "any"`, with no other value ever used. That is not
1,409 individual judgements that one rule always suffices to answer the
question — it reads as an unset default that nobody has gone back to curate,
the same way a field left at its default value in code is not evidence anyone
considered it. On a row whose gold list has 10 required rules, `any` means
retrieval is scored as a full hit if it surfaces just one of them.

## What was measured

Computed directly from the three question files (`evals/questions_rulesguru150_v3.jsonl`,
`evals/rulesguru_full_v2.jsonl`, `evals/_l0_only.jsonl`), by reading every row's
`match` field and the length of its `gold` list. `_l0_only.jsonl` is a 207-row
subset of the full corpus (confirmed: every L0 id is also in the full corpus
file) — it is the arm currently running (see `evals/answers/`), not an
independent sample.

| file | rows | match distribution | rows with 2+ gold rules | share | mean size (multi-rule rows) | max size |
|---|---:|---|---:|---:|---:|---:|
| `questions_rulesguru150_v3.jsonl` (curated) | 150 | `groups`: 79, `any`: 55, `all`: 16 | 126 | 84.0% | 3.25 | 12 |
| `rulesguru_full_v2.jsonl` (full corpus) | 1,409 | `any`: 1,409 (100%) | 745 | 52.9% | 2.75 | 10 |
| `_l0_only.jsonl` (L0 subset, running arm) | 207 | `any`: 207 (100%) | 68 | 32.9% | 2.49 | 6 |

(The 150-set's multi-rule share and mean look higher than the full corpus
because it is stratified toward harder questions, not because the two files
disagree about anything.)

**Bottom line: the full corpus and its L0 subset carry no per-question match
curation at all.** Every row defaults to the loosest possible rule, and more
than half the full corpus (52.9%) has enough gold rules that the default
materially matters.

## What this affects, and what it does not

**Answer accuracy is not affected.** Verdicts come from an LLM judge
(`evals/judge_rulesguru.py:judge_with_reason`, `evals/judge_v5.py` and
siblings for other arms) that receives exactly three things: the question
text, the reference answer (`answer_gold`, human-written prose), and the
candidate's generated answer. It asks the judge for `same`/`different` on
whether the candidate reaches the same ruling as the reference. Neither the
gold rule ids nor the `match` field are passed to the judge, referenced in its
prompt, or read anywhere in that call. Confirmed by reading
`judge_with_reason`'s request body directly — it does not touch `q.gold` or
`q.match` at any point. So the 80.3% corpus-mix projection, the arm
accuracies, and the opus-vs-sonnet head-to-head in the metrics history are all
untouched by this finding.

**Every retrieval measurement is affected.** `evals/run_eval.py`'s
`gold_groups()` (line 158) turns `match: "any"` into a single OR-group
containing the whole flat gold list, and `hit_at()` (line 169) scores a hit
when **any** member of **every** group is present — with one group covering
all the gold ids, one incidental match is a full pass. This is the function
that produces recall, hit@k, and "context ok" everywhere those terms are
used, including `docs/results-retrieval-diversity.md` and
`docs/results-miss-partition.md`. Both are computed correctly *given* each
row's stated `match` — the bug is upstream, in what `match` was set to, not in
how it's consumed.

**Consequence for `docs/results-miss-partition.md` specifically:** its
accuracy-given-context-ok vs. accuracy-given-retrieval-miss conditionals are
not interpretable as retrieval-failure-vs-reasoning-failure, because "context
ok" itself is inflated on multi-rule rows. That doc already says as much for
the hard arm and traces it to the OR-group defect (its §0, §2, and the
`rg4023` worked example: 3 of 10 gold ids retrieved was enough to call a row
"context ok" under `any`, while the two rules that actually decided the
ruling were never retrieved). This doc generalizes that same observation from
the 150-set (where it could be checked against the OR-group re-pass) to the
full corpus (where the same shape of problem exists on more than half the
rows, at bigger multiplicity in the worst cases — max gold size 10 vs. 12 on
the 150-set, so comparable in severity, at 7x the row count).

## Relationship to the OR-group finding

`docs/results-orgroup-repass.md` re-checked the 150-set's 105 multi-member
`gold_groups` sub-groups (curated, `match: "groups"` rows) against CR text and
found 54 of them (43 rows) were a required chain wrongly encoded as an
"any one of these is enough" alternative. That is the identical logical
error this doc describes, at a **different scope**:

- **OR-group re-pass:** already-curated groups, on 150 questions, where the
  *shape* of the AND/OR structure was wrong in 54 of 105 places.
- **This finding:** the full 1,409-question corpus never received that
  curation step at all — 100% of it defaults to the single loosest mode,
  and 745 rows (52.9%) have enough gold rules for the default to matter.

An `any` match over a multi-rule gold list *is* a mis-encoded conjunction —
it is the same disease the OR-group re-pass diagnosed, just never
individually reviewed on 1,409 rows instead of caught and partly corrected on
150. The OR-group re-pass covered 105 groups across 75 of 150 questions; this
covers 745 rows across the full 1,409 — roughly 7x the row count, and with no
prior review pass of any kind (the 150-set at least had a first mining pass
that assigned real modes to 95 of 150 rows before the re-pass found errors in
it; the full corpus has never had that first pass).

## What it would take to fix

The OR-group re-pass is the working method, already proven at n=105: for each
multi-rule row, apply rule 6's test from `evals/gold_miner_prompt.md` — *"if
the retriever found ONLY this member and none of the others, would that step
of the answer be established? If no for any member, split the group"* —
against the actual CR text (`data/raw/MagicCompRules 20260619.txt`), plus a
Scryfall lookup where a group's classification hinges on a card's exact
wording. That pass classified each group as legitimate OR (26), mis-encoded
conjunction (54, mechanically splittable once classified), or needs-Jon (25,
genuinely a judgment call — padding vs. a real second step, or a suspicious
citation that doesn't belong at all).

Scaled to the full corpus:

- **Mechanical, free, no review needed:** the 664 rows with 0 or 1 gold rule
  (1,409 − 745) are already correctly scored under `any` — a single-item
  group and an `any` group with one member are the same thing. No action.
- **Not mechanical, but zero API spend:** classifying each of the 745
  multi-rule rows requires the same CR-grounded read the OR-group re-pass
  did — there is no shortcut that infers "required chain" vs. "alternative
  phrasing" from the ids alone. This is Claude Code subagent labor (grep the
  CR, check Scryfall's local cache, apply rule 6's test), the same "subscription,
  not credits" cost model the `or-group-repass` and `resume-mining` roadmap
  items already use. It is not a small task: 745 rows is roughly 7x the
  105-group pilot, and the pilot needed Jon's own judgment on 25 of 105 groups
  (24%) even with full CR grounding — a proportional share of the full corpus
  pass would still need his ruling on a few hundred rows.
- **Partly mechanical shortcuts that reduce, not eliminate, the review:**
  (1) sort the 745 rows by gold-list size descending so the worst offenders
  (mean 2.75, max 10) are reviewed first, since a bigger gold list is a bigger
  potential recall inflation per row; (2) the re-pass's own legitimate-OR
  cases were almost all one repeating pattern — a numbered CR rule paired
  with its own glossary entry, or a general clause paired with a
  card-type-specific restatement of the same clause (e.g. `106.12`/`106.12b`
  in the re-pass's own worked list) — rows whose gold ids share a CR section
  number to several decimal places are more likely to be that pattern and
  could be pre-tagged as candidate-legitimate for a faster confirm-only pass,
  rather than a full grounded read; neither heuristic removes the need for a
  human or subagent to check the CR text, it only orders and triages the
  work.
- **What doesn't need touching:** no canonical gold or question file changes
  as part of this documentation pass — this doc, like the OR-group re-pass,
  is a proposal surface. Any actual re-curation is a separate, explicitly
  approved pass, same as `evals/orgroup_repass_proposed_corrections.jsonl`
  was kept separate from the live question file until Jon ruled on it.

## Files

- This document: `docs/results-match-semantics.md`.
- Measured from: `evals/questions_rulesguru150_v3.jsonl` (150 rows),
  `evals/rulesguru_full_v2.jsonl` (1,409 rows), `evals/_l0_only.jsonl` (207
  rows) — read directly, counts and sizes recomputed in this session, not
  taken from any prior report.
- Judging path confirmed by reading `evals/judge_rulesguru.py`
  (`judge_with_reason`, lines ~88-124): the OpenRouter judge request body
  carries `question`, `reference` (`answer_gold`), and `candidate` only.
- Retrieval scoring confirmed by reading `evals/run_eval.py:158-177`
  (`gold_groups`, `hit_at`).
- Related: `docs/results-orgroup-repass.md` (the same defect, on the 150-set's
  already-curated `groups` rows), `docs/results-miss-partition.md` (the doc
  whose context-ok/retrieval-miss conditionals this finding un-interprets on
  the hard arm).
- No question file, gold file, or canonical data was modified to produce this
  document.

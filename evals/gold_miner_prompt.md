# Gold-miner prompt (canonical)

**This file is the instrument. Do not paraphrase it into a dispatch message.**
Dispatch by telling the agent to read this file and giving it a line range.

Why it exists: on 2026-07-25 the prompt lived only inside dispatch messages, and
it got silently reworded between batches 3 and 4 — the justification clauses
were trimmed off rules 1 and 3. Recovery against existing gold fell from a
68% mean (b01-b03) to 60% (b04-b09) across that boundary. Editing prose in a
prompt is editing a parameter of the experiment; a prompt that isn't
version-controlled will drift.

## Version history

| version | date | batches | change |
|---|---|---|---|
| v1 | 2026-07-25 | b01-b03 | initial, derived from commit `8b94ef5`'s recorded calibration rules |
| v1-trimmed | 2026-07-25 | b04-b09 | **accidental**: justification clauses dropped from rules 1 and 3. Do not reuse. |
| v2 | 2026-07-26 | b10+ | v1 text restored verbatim, plus rule 6 (the merge rule) from the adversarial review |

`b09_rerun` re-mines b09's exact questions under v1 to test whether the drift
was caused by the wording or by the questions.

## Known open defect this prompt does NOT yet fix

Batches b01-b09 were mined before rule 6 existed and contain conjunctive
OR-groups (see the adversarial review, 2026-07-26): 162 multi-member groups
across those batches, plus 105 in `questions_rulesguru150_v3.jsonl`. Jon has
held the v3 re-pass pending the drift result. Anything mined at v2 or later
should be clean; anything earlier needs a grouping re-pass before it is used to
score recall.

---

## THE PROMPT (everything below is verbatim; substitute only the line range and output filename)

You are mining CR retrieval gold for the Rulemancer eval at D:\Job_hunt\mtg-rules-bot. Work ONLY on lines {START}-{END} of `evals/_mine_remaining_blind.jsonl` (read exactly that slice with Read offset/limit; do NOT read the whole file).

Each row has: id, question, answer_gold (a correct answer written by a certified MTG judge), level, complexity.

YOUR TASK is tracing, not solving. The answer is already known to be correct. Work out which Comprehensive Rules chunks that answer actually rests on. Do not try to answer the question yourself.

HARD RULES (these come from a calibration pass against hand-labelled data — follow them exactly):

1. CLOSED VOCABULARY. Cite only ids that literally appear in `evals/_chunk_inventory.txt` (3,619 real chunk source_ids). Grep that file to check — never Read it whole. An id absent from it can never be retrieved, so it is worthless as gold. This is the single most important rule: a prior pass produced 19 unusable labels by citing folded parent rules like `702.16` instead of the child that actually carries the text.

2. STATES, not implies. Cite a rule only if it STATES the answer. A rule that merely relates to the topic is not gold.

3. NEVER DROP AN ALTERNATIVE. If two rules could each independently support the same step, keep BOTH as alternatives inside one group. Dropping one is pure recall loss.

4. DO NOT ADD A PARENT'S OTHER CHILDREN. If you cite `613.7a`, do not sweep in `613.7b`/`613.7c` unless each independently states part of the answer. Padding makes gold easier to hit rather than sharper, which corrupts the metric.

5. Ground every claim in the actual CR text at `data/raw/MagicCompRules 20260619.txt` (grep it). Never assert a rule's content from memory.

6. THE MERGE RULE — put two rules in the SAME group only if **each one alone fully licenses that step's claim**. A group means "any one of these suffices." If the answer needs rule A *and* rule B to make its point, they are consecutive links in a chain and belong in SEPARATE groups, not one.
   - Correct merge: `113.7a` and `608.2h` — either alone states the same fact.
   - Wrong merge: `613.4b` (sets power/toughness) with `613.4c` (modifies it) — different sublayers doing different jobs; retrieving one does not establish the other.
   - Wrong merge: `702.37a` (morph alternative cost) with `702.35a` (madness alternative cost) — the answer needs both to exist before "only one alternative cost" bites.
   - Test to apply out loud for every group with 2+ members: *"if the retriever found ONLY this member and none of the others, would that step of the answer be established?"* If no for any member, split the group.
   - This is the single most common error found by adversarial review: 5 of 9 sampled multi-member groups were conjunctive chains wrongly merged, which silently inflates recall.

MATCH MODE:
- `groups` (preferred when the answer has several distinct steps): gold_groups is a list of OR-groups; EVERY group must be satisfied, and any one id within a group suffices.
- `any`: one OR-group — any single id answers it.
- `all`: every id independently required, no alternatives.
- INVARIANT: `gold` must equal the flat union of `gold_groups`, in order.
- Emit `gold_groups` on EVERY row, including `any` rows (a single group containing the flat list). A missing key is a schema hole that structural checks skip.

OUTPUT. Append one JSON object per line to `evals/{OUTFILE}` (create it), shaped exactly like this real example:
{"id": "rg6328", "gold": ["601.2b", "118.9", "118.9a", "113.6d"], "match": "groups", "gold_groups": [["601.2b", "118.9", "118.9a"], ["113.6d"]], "rationale": "one or two sentences on why these rules and this grouping"}

If a question genuinely cannot be traced to any inventory id, still emit a row with "gold": [], "match": "any", "gold_groups": [[]], and a rationale saying why — do not silently skip it.

Before finishing, verify your own output: every id appears in _chunk_inventory.txt, gold == flat union of gold_groups on EVERY row, every row has a gold_groups key, and every multi-member group passes the rule-6 test. Fix any violations.

RETURN (this is all I want back, nothing else): one line of the form
`{TAG} | rows=<n> | modes any=<n>,groups=<n>,all=<n> | ids=<total> | inventory_violations=<n> | union_mismatches=<n> | multi_member_groups=<n>`
plus a second line listing any question ids you could not trace.

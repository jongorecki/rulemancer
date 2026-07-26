# Results — the same-prompt gold-mining stability number: 0.4867 mean overlap, not better than the 0.54 cross-prompt figure

Zero API spend. Two fresh mining passes over the same 50 questions, same
prompt (v2, current), run independently by two separate Claude Code
subagents on Jon's subscription — no Anthropic SDK call anywhere in this
work. Run A: `evals/gold_proposals_v2_stability_runA.jsonl`. Run B:
`evals/gold_proposals_v2_stability_runB.jsonl`. Analysis script:
`evals/_double_mine_stability_v2.py`. Per-row detail:
`evals/_double_mine_stability_v2_rows.json`. Neither canonical gold file nor
`docs/results-gold-stability.md` was touched.

This fills the gap that doc names explicitly: "same questions, same prompt,
mined twice ... does not exist on disk." It now does.

## 1. Questions

**Selection rule: reuse b09's exact 50 question ids.** Those are lines
401-450 of `evals/_mine_remaining_blind.jsonl` (`rg655` … `rg778`, confirmed
contiguous by direct lookup). This is the most comparable choice on offer —
it's the same 50 questions the 0.54 cross-prompt figure was measured on, so
the two numbers differ only in which prompt(s) produced them, not in which
questions were asked. No better reason turned up to deviate from it.

## 2. Prompt

**v2** — `gold_miner_prompt.md`, the version currently marked for b10+: "v1
text restored verbatim, plus rule 6 (the merge rule)." Both runs were
dispatched by telling the mining agent to read `gold_miner_prompt.md` in full
and execute the section literally titled "THE PROMPT" verbatim, substituting
only `{START}=401`, `{END}=450`, and the output filename — per that file's
own instruction not to paraphrase it into a dispatch message. Each run was a
separate Claude Code subagent (Sonnet) with no shared context, explicitly
told not to open the other run's output file, either b09 file, or this
project's results docs. Run A ran to completion before run B was dispatched,
so there was no window where a partially-written sibling file could leak
into the other run's directory listing.

Both agents' self-reported RETURN lines:

```
runA | rows=50 | modes any=38,groups=12 | ids=62 | inventory_violations=0 | union_mismatches=0 | multi_member_groups=0
runB | rows=50 | modes any=34,groups=16 | ids=68 | inventory_violations=0 | union_mismatches=0 | multi_member_groups=1
```

Both files independently validated after the fact (this session, not just
self-reported): 50 rows each, every row has `gold_groups`, `gold` equals the
flat union of `gold_groups` on every row in both files. No untraceable
question ids in either run.

## 3. The number, correctly attached

Mean per-question Jaccard overlap (`|A∩B| / |A∪B|` over gold rule-id sets)
across the 50 shared question ids, same-prompt replicate: **0.4867**.

## The shape of disagreement — order vs content

| category | rows | share |
|---|---|---|
| **Identical gold set** (same ids, any order) | 19 | 38.0% |
| — of which: fully identical (ids, group structure, list order all match) | 19 | 38.0% |
| — of which: same ids, only list order differs | 0 | 0.0% |
| — of which: same ids, `gold_groups` structure differs | 0 | 0.0% |
| **Genuinely different rule sets** | 31 | 62.0% |
| — of which: same *count* of ids, different members (substitution) | 18 | 36.0% |
| — of which: different *count* of ids (one run adds/drops an id) | 13 | 26.0% |
| — of which: share zero ids (`jaccard = 0`) | 19 | 38.0% |

Match-mode agreement (`any` / `all` / `groups`) is **38/50 = 76.0%** — the
identical figure the b09 pair produced, though the underlying mode splits
differ: run A picked `groups` 12/50 (24%), `any` 38/50 (76%); run B split
16/34 (32%/68%). Both runs stayed `any`-heavy; neither showed the b09 pair's
25/25 even split. Neither run produced any `all`-mode rows.

Jaccard distribution, same buckets as the existing doc:

```
jaccard = 0.00       19 rows  (38%)
jaccard = 0.01-0.34   5 rows  (10%)
jaccard = 0.34-0.99   7 rows  (14%)
jaccard = 1.00       19 rows  (38%)
```

Still bimodal, and more sharply so than the cross-prompt pair: 76% of rows
sit at one of the two extremes (0 or 1), only 24% in between.

## 4. Comparison to the 0.54 cross-prompt figure — and the confound that has to be named

**Same-prompt overlap (0.4867) is *lower* than the cross-prompt-plus-noise
figure (0.5407), not higher.** Read plainly, that says: rerunning the
identical v2 prompt on the identical 50 questions does not produce cleaner
agreement than the pair that also changed the prompt wording. The prompt
edit between v1-trimmed and v1 restored is **not** shown to be the dominant
driver of the 0.54 instability — whatever is making these two numbers close
(and this one is not even higher) is present with the prompt held perfectly
fixed. **The miner is noisy regardless of prompt wording**; that's the
supported reading, not "the prompt didn't matter at all" (see confound
below, which cuts against over-reading either number).

**The confound that has to be flagged, because it's real and it's large:**
this v2 pair produced much smaller average gold sets than the b09 pair did.

| pair | avg ids/question, run 1 | avg ids/question, run 2 | rows with a single-id gold set |
|---|---|---|---|
| b09 (cross-prompt, v1-trimmed vs v1) | 1.98 | 2.00 | 14/50, 12/50 |
| v2 (same-prompt, this run) | 1.24 | 1.36 | 38/50, 34/50 |

Jaccard on a 1-element set is mechanically binary — it can only land at 0 or
1, never in between. With 34-38 of 50 rows carrying single-id gold in this
pair (versus 12-14 of 50 for b09), the same-prompt distribution is
structurally pushed toward its two extremes regardless of how "stable" the
underlying reasoning actually is. That mechanically explains both ends
moving at once here: the higher exact-identical rate (38% vs 26%) *and* the
higher share-nothing rate (38% vs 12%) are both symptoms of smaller sets, not
independent evidence of more or less agreement. **The two mean-Jaccard
numbers are not a clean apples-to-apples comparison** — part of the gap
(direction unknown, size unknown) is this set-size artifact rather than a
real difference in how stable the miner is prompt-to-prompt versus
run-to-run.

That said, the set-size difference is itself worth sitting with rather than
explaining away: nothing about v2's wording should make gold sets smaller
(rule 6 only changes how already-cited ids get *grouped*, not how many get
cited — see `gold_miner_prompt.md` rule 6, which splits a wrongly-merged pair
into two groups without changing the flat union). So the smaller sets here
most plausibly reflect ordinary agent-to-agent variance in how aggressively
rule 3 ("never drop an alternative") gets applied — which is itself exactly
the kind of noise this experiment exists to surface, not an artifact
external to the question being asked.

**What this comparison does support:** the earlier doc's claim that 0.54
"almost certainly" reflects mostly-noise rather than mostly-prompt-drift is,
if anything, reinforced — a same-prompt rerun did not land meaningfully
above 0.54, and by the raw number came in below it. What it does **not**
support is a confident verdict on which of "prompt drift" or "pure noise" is
bigger, because this pair's smaller, more single-id-heavy gold sets make its
Jaccard mechanically prone to bimodal 0/1 outcomes in a way the b09 pair's
gold sets were not.

**Uncertainty, stated plainly:** this is one pair, 50 questions, mined once
each way. Both this pair and the b09 pair are single data points; neither
should be read as a stable estimate of "the" noise floor. A third or fourth
independent v2 replicate would be needed before treating either 0.4867 or
0.5407 as more than "in the same rough neighborhood, both mediocre."

## 5. Qualitative notes (grounded, not counted in the headline number)

- **`rg680`/`rg681`/`rg682` disagree in the same direction, three times in a
  row.** All three ask a variant of the same phylactery-counter timing
  question (different cards, same underlying issue). Run A cited `614.4` on
  all three; run B cited `614.17a` on all three. Grepping
  `data/raw/MagicCompRules 20260619.txt`: 614.4 is the general
  "replacement effects can't go back in time" statement; 614.17a is the same
  principle restated specifically for "can't" effects. Both runs were
  *internally consistent* with themselves across the three near-duplicate
  questions — this isn't random flicker, it's a systematic, reproducible
  preference for one of two rules that state closely related timing
  principles. That's a citation-granularity disagreement in the same family
  the original doc flagged (parent/child, sibling near-duplicates), not
  three independent coin-flips.
- **Run B's one multi-member group passes the rule-6 test on inspection.**
  `rg660` (`116.2b` + `702.37e`, "turning a permanent face up is a special
  action") — grepping the CR, either rule independently states that a
  permanent's turning face up is a special action, so the merge is correct
  under rule 6, not a repeat of the pre-rule-6 conjunctive-chain defect.
  Run A's zero multi-member groups mean rule 6 had nothing to violate there
  either. Consistent with the prompt note that v2 batches should be clean of
  that defect.

## Caveats

- **(a) One pair, 50 questions, N is thin.** Same limitation as the b09
  measurement; doesn't license treating 0.4867 as a stable estimate any more
  than 0.5407 was.
- **(b) Set-size confound stated in §4** is the single biggest reason not to
  over-read the direct 0.4867-vs-0.5407 comparison as "same-prompt noise
  exceeds prompt-drift-plus-noise" in a strong sense — it might, but this
  pair's mechanically bimodal Jaccard (from mostly single-id gold) means the
  comparison is noisier than the two point numbers alone suggest.
- **(c) Both runs are v2, clean of the pre-rule-6 conjunctive-OR defect** —
  unlike the b09 pair, which the canonical doc flags as pre-rule-6 on both
  sides. This is the first stability figure computed on gold that isn't
  carrying that known defect.
- **(d) Conditioned on the judge-authored answer**, same as every gold-mining
  pass under this spec (`docs/spec-cr-gold-mining.md` §2) — both runs were
  handed the correct answer and asked to trace it to CR ids, not to solve the
  question blind.
- **(e) Provenance of the b09 pair's mining agents (model, exact dispatch
  method) is not recorded in either b09 file** (`proposed_by` field is absent
  from both) — so a difference in agent thoroughness between "whatever
  produced b09" and "the two Sonnet subagents in this run" cannot be fully
  ruled out as a contributor to the set-size gap in §4, alongside genuine
  run-to-run noise.
- **(f) No git commit / push / checkout was performed**, and no canonical
  gold file was modified. The only new files are this doc, the two
  `gold_proposals_v2_stability_run{A,B}.jsonl` mining outputs, and the two
  `_double_mine_stability_v2*` analysis artifacts in `evals/`.
- **(g) This does not supersede or contradict `docs/results-gold-stability.md`.**
  That doc's 0.5407 figure, its framing as cross-prompt-plus-noise, and its
  hierarchy-aware-metric proposal all stand as written. This doc adds the
  measurement that one was missing; it does not revise it.

## What this doesn't cover

- A hierarchy-aware overlap metric (parent/child, sibling partial credit) —
  still proposed, not computed, in the original doc; the weights are Jon's
  call and nothing here changes that.
- Whether instability is worse on harder questions — `level`/`complexity`
  was not joined against overlap here, same reason as before (50 rows is
  thin to slice further).
- Any claim about which of run A / run B is "more correct" against
  human-authored gold. Not compared here.
- A third replicate, which would be needed to say anything sharper than
  "same rough neighborhood as 0.54" about the true noise floor.

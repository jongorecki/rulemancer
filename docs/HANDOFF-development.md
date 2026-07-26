# Handoff — both switches shipped, and the judge is the next bottleneck

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-26 session, which applied both approved switches, finished the easy-set
regression check, priced everything properly for the first time, built the
gold-audit grading UI and had Jon grade batch 1 — which found that a third of
the "failures" it was auditing were the judge being wrong, not the bot.**

Suite: **582 passed, exit 0.** Commits: `d95a461`, `2e9e2fc`, `dcadb4c`,
`86b5d27`, `2172d6e`, `e2ce15c`, `fba7227`, `b085417`, `3715826`.

---

## ⚠️ FIRST, UNLEARN THIS

**1. "11 questions are unreachable by any retrieval work" is wrong.** Jon graded
the 15 derivability failures. Five of them — `rg7215`, `rg549`, `rg1718`,
`rg851`, `rg811` — are rows where **the two answers say the same thing** and the
judge scored them as disagreements. His note on rg7215: *"IMPORTANT!!!!!!! they
say the same thing. This isn't a disagreement."* The real count of "we got this
wrong" is **5**, not 11.

**2. The entire "gold was incomplete" category dissolves.** All four rows
`results-derivability.md` classified that way (`rg7215`, `rg549`, `rg851`,
`rg811`) are judge false negatives. Arm B had already answered them correctly.
So the **92.7% ceiling** and the *"single-id rows are the risk group"* heuristic
— both derived from that category — must be withdrawn.

**3. The judge is nondeterministic.** Re-judging the same answers with the same
frozen instrument (`b54fbdb95565abf8`) flipped `rg6461` and moved sonnet easy r1
from 76.0% to 78.0%. Measured over both re-judged arms: **1 verdict flip per 100
rows, and 100/100 entries with different reasoning prose.** A published accuracy
must name its judging run.

**4. "opus-low is 23% cheaper" is only true of hard traffic.** Priced properly
(below), it is *more expensive* on easy questions until sonnet's intro pricing
ends 2026-08-31.

---

## WHAT SHIPPED

**Switch 1 — `GEN_MODEL` -> `claude-opus-5`** (`d95a461`). This needed **two**
edits, not the one the last handoff described. Production builds a bare
`RulesAgent(store)`, and `effort` defaults to `None`, so changing the model alone
would have shipped **opus at the API's default effort** — an unmeasured, costlier
arm that discards the cost argument the decision rests on. Added `GEN_EFFORT =
"low"` next to `GEN_MODEL`, applied at the API entry point rather than as the
library default so `answer.py`'s byte-identical-request-body contract (guarded by
`tests/test_prompt_identity.py`) survives and eval arms keep declaring effort
explicitly.

**Switch 2 — `REWRITE_N` 1 -> 3** (`86b5d27`), applied only after both sonnet
arms finished. `REWRITE_N` has no CLI override and is read off the module at
answer time, so flipping it while the queued r2 was pending would have given r2
three rewrites against r1's one and silently broken the regression check.
`GEN_MODEL` was safe to change mid-flight because every queued command passed
`--model` explicitly — verified by reading r2's first row back, not by assuming.

**This activated a dormant production path.** The RRF fusion branch in `answer()`
only runs when `REWRITE_N > 1`, so production retrieval now fuses several
rankings instead of taking one. That branch was exercised by retrieval evals,
never by production traffic.

**Gold-audit grading UI** (`2e9e2fc` spec, `dcadb4c` build). `--verdicts
gold-audit` swaps in a who-is-wrong vocabulary with its own localStorage key and
export name; a Retrieved panel renders the retrieved set with a per-row
provenance label. **It also fixed a silent bug: the card panel had been empty for
every RulesGuru row** — enrichment read the questions file's `cards` field, which
is `null` for all 150, while production derives names via `parse_card_refs()` on
the question text. 0/0 cards became 40/40 with 184 rulings.

---

## THE EASY-SET REGRESSION CHECK: no regression, opus-low wins

`docs/results-easy-regression.md`.

```
opus-5 effort low    r1 92.0%  r2 86.0%   mean 89.0%
sonnet-5 default     r1 78.0%  r2 74.0%   mean 76.0%   +13.0pp
paired r1 8-1,  paired r2 6-0
within-arm noise: opus 5/50, sonnet 6/50 (matches the hard set's 11%)
```

The gap is **larger** on easy questions (+13.0pp) than hard (+9.3pp), so the
overthinking-simple-questions failure this check existed to find runs the other
way. Opus's errors are a fixed core of three (`rg1802`, `rg4440`, `rg5628`, all
missed by every arm of both models — gold-error candidates for batch 2); sonnet
misses those plus six more.

## COST, PRICED PROPERLY (Jon caught this)

Reporting token ratios is not a cost result — opus costs more per token, so 3.2x
fewer output tokens does not establish which is cheaper.

```
per question        opus-5 low   sonnet @ intro   sonnet @ standard (9/1)
hard set (n=54)       $0.06445      $0.08571          $0.12856
                                    opus -24.8%       opus -49.9%
easy set (n=50)       $0.05153      $0.04724          $0.07086
                                    opus +9.1%        opus -27.3%
```

**Mechanism:** opus at `effort=low` emits a nearly constant ~1,200 output tokens
regardless of difficulty (1,211 hard / 1,178 easy); sonnet's scales with the
problem (7,184 / 3,763). All of opus's saving comes from capping output, so it is
worth more the harder the traffic. **Jon's ruling: keep the switch — "opus low is
the meta moving forward."**

`REWRITE_N` 1->3 costs **$0.00036/question** measured (under the $0.0005
estimate), ~0.6% of answer cost, and **does not inflate the prompt**: chunk count
is pinned at `TOP_K` by `rrf_fuse(rankings)[: self.k]`, and measured context
tokens are flat across n=1/3/5/8 (2,423 / 2,293 / 2,291 / 2,468).

---

## THE GOLD AUDIT (batch 1) — Jon's verdicts

`data/parsed/gold_audit_verdicts.json`, 15 rows: 6 ambiguous, 5 ours-wrong,
2 gold-incomplete, 2 rulesguru-wrong. Corrected accounting for arm B:

```
measured                                 135/150 = 90.0%
+ judge false negatives (5)                    -> 140 = 93.3%
+ RulesGuru wrong (rg6556, rg289)              -> 142 = 94.7%
+ rg5863 if the rules-precedence call goes ours-> 143 = 95.3%

genuinely ours-wrong: 5   rg494 rg713 rg1095 rg1208 rg842
genuinely gold-gap:   2   rg241 (Jon supplied the chain), rg559
```

**Other findings in his notes:**
- **Out-of-range ruling citations on 3 of 15 rows** (`rg1095`, `rg549`, `rg1718`)
  — the bot cites ruling indices that do not exist. Real product bug.
- **rg289**: card-name-completeness may affect ruling retrieval; worth checking
  whether partial names degrade matching.
- **Level-weighted scoring** requested, now ruled on (below).

---

## RETRIEVAL: rg241 proves the gap is multi-hop, not missing content

Jon asked whether cross-card ruling transfer (normalise card names to CARDNAME,
match near-identical ability text, reuse the other card's rulings) would help.
**Tested on the case that motivated it — and it would not have.** All four CR
rules in his derivation are already in the index:

```
vector-only probe (n=1):  303.4f rank 33   -> missed the top-15
production (n=3, RRF):    303.4f rank 10   -> retrieved
deep-fusion rank:  702.16c 103   614.12a 319   702.11b 571   614.1c 612
```

Multi-query moved the gold rule from rank 33 to 10 — **the most legible evidence
switch 2 has produced.** But `614.1c` / `614.12a` are unreachable *by
construction*: the derivation needs three hops (303.4f says the choice happens
"as" it enters -> 614.1c says "as" means a replacement effect -> 614.12a says
those choices happen before the event), and hops 2-3 have no resemblance to the
question. Question-side rewriting cannot reach them however good the rewrites.

**Jon already proposed the right fix, in his own q016 grading note:** one round
of clarifying queries against the rules — i.e. second-hop retrieval. Better
targeted than CARDNAME transfer. Park the transfer idea until the audit queue
shows failures that are genuinely "the explaining ruling lives on another card";
that count is currently 0 for 1.

**Cosine separation, load-bearing vs not** (proxy: cited by a judge-correct
answer): means 0.456 vs 0.339, gap +0.117 — real but overlapping (LB p10 0.384
sits below non-LB p90 0.455), so a score alone cannot classify. `COSINE_FLOOR =
0.38` keeps 92% of load-bearing and discards 72% of the rest; **leave it there**
(0.45 halves coverage). **Discard the rank statistic from that run — it was
circular** (`select_rulings` caps at TOP_N=5, so a cited ruling was necessarily
in the top 5), and the LB sample is truncated at the floor, so +0.117 is
optimistic.

**A cosine floor on CR chunks is a free local change** — `scores = embeddings @
qvec` is one in-process matmul; the only API call is embedding the query, which
happens either way. It would also cut the **38% chunk churn** multi-query
introduces (5.7 of 15 chunks differ vs n=1), because a weak rewrite currently
contributes 100 candidates to fusion unconditionally. Note switch 2 *removed* the
calibrated similarity signal at the fusion stage: RRF scores are
`sum(1/(60+rank))`, rank-derived, not thresholdable as confidence.

---

## RULED BY JON, NOT YET BUILT

**Level-weighted scoring: flat across L0-L3, Corner Case 0.5.** Spec is
`docs/spec-weighted-scoring.md`; the ruling came after it was written, so the
spec still presents it as a recommendation — **it is now decided.** Zero API
(re-scoring pass over `by_level_counts` already in every verdict file),
retroactive to all historical arms. Sensitivity: no conclusion flips under any
scheme; hard set moves ~2pp, easy set not at all. Key design facts already in the
spec: the v3 150 is stratified 30-per-level so weighting is a value judgment not
a bias fix; **only ratios matter** (two schemes differing by a scale factor are
the same scheme — this already fooled one sensitivity run); Corner Case is a
category, not the top rung of difficulty.

**Rescore the 5 judge-false-negative rows as correct.** Approved, **not applied.**

---

## NEXT SESSION, IN ORDER

1. ~~**Apply the 5-row rescore** and **correct `results-derivability.md`**.~~
   **DONE** `373c4aa`. Arm B is 93.3% (`evals/verdicts_derivability_B_human.json`,
   built by the new `evals/merge_human_verdicts.py`); all three claims withdrawn.
2. ~~**Write `docs/results-gold-audit-batch1.md`.**~~ **DONE** `373c4aa`.
   ⚠️ **The dangling-reference warning in this list was itself wrong** —
   `results-easy-regression.md` never referenced that file; it links
   `docs/spec-gold-audit-ui.md`, which exists. Checked with grep across the repo
   before acting. It *did* carry a stale "11 unreachable questions" reference,
   now corrected to 10 and pointed at the batch-1 results.
3. ~~**Build weighted scoring**~~ **DONE** `372965b`. `evals/weighted_score.py`
   + 53 tests. No conclusion flips; largest move 1.5pp. Suite 635.
4. ~~**Investigate out-of-range ruling citations**~~ **DONE** `ad53532`.
   **Not a product bug** — production is clean across 397 citations; the defect
   is in `evals/build_gold_prompts.py` and affects 69% of citing rows in
   derivability arms B/C. Root cause + recommended fix:
   `docs/report-ruling-citation-offbyone.md`. **Needs Jon's ruling** on (a) move
   labelling into `build_prompt()` vs patch the one caller, and (b) whether to
   re-run arm B (~$8.47) so its citations become usable data. No code changed.
5. ~~**Build the metrics-history view**~~ **DONE** `44c7852`.
   `evals/build_metrics_history.py` → `evals/metrics_history.html` (+ JSON).
   16 arms, 6 question sets, grouped by a question-id fingerprint so only
   genuinely comparable arms sit together; answers↔verdicts joins are verified
   by id-set match, not filename. **The decision number: a full run over the
   1,409 RulesGuru questions costs ~$72–104 in generation** at the shipped
   config. Retrieval config (TOP_K/TOP_N/COSINE_FLOOR) is *not* recorded per
   arm — the page says so rather than implying per-row history.
6. **Measure the judge's false-negative rate** on a sample of judged-"different"
   rows across arms. This gates how much to trust every accuracy number we own,
   including this session's. `evals/opus_grader_calibration.py`,
   `docs/plan-opus-grader-calibration.md`, and `evals/judge_agreement_results.json`
   are existing infrastructure for exactly this.
7. **Batch 2 of the gold audit** — the full-data rows (`rg1802`, `rg4440`,
   `rg5628` plus h2h/costbase). Build with `--provenance run`; those rows carry
   real `retrieved_rule_ids` and the panel flips to the green "retrieved by the
   run" label.
8. **Spec the cosine floor** (free at runtime, cuts churn, restores a calibrated
   signal) and **second-hop retrieval** (the multi-hop gap above).

Still open from before: double-mine for stability (0.54 run-to-run overlap),
re-pass v3's 105 conjunctive OR-groups, resume mining (809 rows).

---

## HOW JON WORKS (unchanged, load-bearing)

- **Explain things properly.** Define jargon at first use, lead with what a thing
  means, show a concrete example. He is a partner, not an observer.
- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until he rules.
- **USE SUBAGENTS** — *but this session's harness forbade the Agent tool unless
  Jon asked.* Say so immediately rather than absorbing the work inline.
- **Verify agents' claims yourself, and verify the right thing.** Structural
  verification is not quality verification.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR,
  Scryfall, or a live check. **Model facts and pricing via the claude-api skill**
  — this session's cost correction came from doing that instead of recalling.
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.** (A scratch `http.server` on 8942 may still be running from this
  session.)
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 5`.
  `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`.
- **Never pipe a long run through `| tail`**; **PowerShell `*>` buffers until
  exit**, so a running job's log looks dead — check the output artifact.

---

## THE LESSON TO CARRY

Previous sessions: *a value that looks like an identity but is really a position*
(the ruling-index bug), then *a claim inherited and repeated without being
checked* ("the same bucket").

This session: **a number is a snapshot of a file at a time, not a fact.** This
doc's predecessor recorded sonnet r1 at 76.0%. That number was read at 09:13 and
committed later — but the verdict file was rewritten at 10:05, so the commit
shipped a results doc and a verdict file **that disagreed with each other inside
the same commit.** Nobody edited the doc wrongly; the ground moved underneath a
number that had already been read.

The habit that catches it: when a number will be published, re-read it from the
file at the moment you write it down, and record what produced it — the run, the
timestamp, the instrument. This is the same discipline as the provenance labels
on the retrieved panel, applied to our own numbers instead of the model's.

The corollary, from the same finding: **an eval instrument is itself an
experiment subject.** The judge was treated as fixed because its prompt is
frozen — but frozen prompt does not mean deterministic output, and it does not
mean correct output. Both turned out false in the same afternoon.

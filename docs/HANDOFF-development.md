# Handoff — the session that found the measuring stick was bent

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-26 evening session. The previous handoff's headline belief was "retrieval
is the bottleneck." That is probably still true, but this session established
that we could not have known it, because every instrument used to measure
retrieval was broken — and roughly 60% of the eval corpus cannot detect a
retrieval change at all.**

Suite: **929 passed, exit 0**, verified with every eval arm stopped. **The "645
passing" figure in the prior handoff and in `CLAUDE.md` was ~280 tests stale** —
it had been carried forward unchecked across sessions.

Nothing was committed during the session; everything below landed in one
end-of-session commit.

---

## ⚠️ FIRST, UNLEARN THIS

**1. Answer accuracy and retrieval accuracy are two different instruments with
two different reliabilities.** Accuracy is judged by comparing our answer to the
reference answer — `judge_rulesguru.py` never reads `q.gold` or `q.match`.
Retrieval is judged by comparing retrieved ids to a mined gold rule set.
Everything found this session hit the second one. **Every published accuracy
number survives intact. Every published retrieval number does not.**

**2. ~60% of the corpus cannot measure retrieval.** A no-rules control arm (90
of a planned 150 rows, all five levels) answered questions with zero rules in
context. Corpus-weighted, **59.5%** of rows were answered correctly anyway —
those rows cannot detect whether retrieval helped. It is concentrated at the easy
end: L0 86.7%, L1 70.0%, L2 40.0%, L3 50.0%, Corner Case 30.0%. Retrieval work
must be evaluated on the hard subset; measuring it corpus-wide halves the signal.

**3. `hit_at()` has been over-crediting retrieval by roughly 3x.** The full
1,409-question corpus is `match: "any"` on **every single row**, and 745 rows
(52.9%) list 2+ gold rules (max 10). Finding 1 of 10 scored as complete success.
Real coverage on the hard arms is **17.4%** against a reported hit rate of 48.1%.

**4. 10.9% of the corpus has no gold rules at all** — 153 of 1,409, and **33% of
L0** (69 of 207). Reference answers are present on all of them, so accuracy still
scores; retrieval simply has nothing to match against.

**5. L0 is 97.1%, and that is not good news.** 201/207. But 86.7% of L0 is
answerable with no rules whatsoever, so the score reflects the model's own Magic
knowledge more than the pipeline's.

**6. An arm's cost model does not transfer to a different kind of arm.** Arm B's
$0.056/question did not predict the no-rules control's $0.104. Removing rules
shrinks input slightly but **doubles to triples output** (2.05x at L0, 2.37x at
L1, 2.59x at L2), and output is 5x the price of input. Estimate the expensive
side, not the cheap one.

**7. Sampling the front of a sorted file is not sampling.** A 10-question pilot
drawn from the head of the level-ordered question set hit only L0 and projected
$11.35 against an actual $15+. The same trap made the first 70 control rows
30xL0 + 30xL1 + 10xL2 and zero L3/Corner.

---

## WHAT SHIPPED

**Graded coverage metric** — `coverage_at()` / `coverage_from_ids()` in
`evals/run_eval.py`, `evals/backfill_coverage.py`, `tests/test_coverage_metric.py`
(24 tests). Flat fraction of gold ids retrieved, deliberately NOT routed through
`gold_groups()` — that function returns `[q.gold]` for `match:"any"`, which is why
the pre-existing `group_coverage()` in `run_retrieval_diversity.py:122` computes
`hit/1` and is boolean on 100% of the corpus. `hit_at()` and `gold_groups()` are
**byte-identical** to HEAD; coverage is reported alongside, never instead of.
Backfilled across all 21 arms with zero model calls.

**The inflation worklist** — the gap between `hit_at()` and coverage ranks rows
by how much the boolean flatters them. 282 rows have a positive gap; **158 exceed
0.5**, and those collapse to **38 distinct questions**. That is the curation
worklist, produced with no human judgement. `evals/coverage_backfill.json`.

**No-rules control arm** — `evals/answers/norules_control.json` (70) +
`_topup.json` (20), `docs/results-norules-control.md`. See point 2 above. Two
limitations that must travel with the number: it is 90 of a planned 150 (halted
deliberately, not failed), and its `system_version` differs from arm B's, so it
changes the system prompt as well as removing the rules. Not a clean
single-variable control.

**L0-only pipeline arm** — 207 questions, 97.1%, judge recorded, $11.71.
**The full-run projection moved from 80.3% [71.7-86.8%] at 85% coverage to
82.8% [78.2-86.6%] at 100% coverage.** The interval nearly halved and the
projection is no longer an extrapolation.

**OR-group re-pass** — `docs/results-orgroup-repass.md`,
`evals/orgroup_repass_proposed_corrections.jsonl`. Of 105 multi-member groups in
`questions_rulesguru150_v3.jsonl` (verified: 75 rows carry them): **26 legitimate
OR, 54 mis-encoded conjunctions, 25 needing judgement.** Up to 60 of 150 rows
would have gold restructured. Flat `gold` union unchanged, so derivability arms
are unaffected — this moves retrieval scoring only.

**OR-group resolution (only-one-in test)** —
`docs/results-orgroup-resolution.md`. Tested 21 of the 25 undecided groups (4
excluded because arm B fails those rows even with full gold). Raw verdict was 20
OR / 1 conjunction, but cross-checked against the control: **5 valid legitimate
ORs, 1 valid conjunction (`rg60`), 5 invalid because their row is confounded, 10
unknown because their row has no control data.** Note the asymmetry — the
confound manufactures false *passes*, never false failures, so the conjunction
verdict is robust and the OR verdicts are not.

**Match-semantics audit** — `docs/results-match-semantics.md`, plus a live
`crit` open item on the dashboard computed from the question files at build time.

**Miss-partition diagnostic** — `docs/results-miss-partition.md`. Its
conditionals are NOT interpretable as retrieval-vs-reasoning: 100% of "context
ok" rows on the hard arm were `match:"any"` with mean gold size 4.13, which is
why it shows the paradox of accuracy being lower with "context ok" (61.5%) than
without (89.3%). The 2x2 itself is sound; the label is not.

**CR update checker** — `scripts/check_cr_update.py` + 40 tests. Classifies
rules as unchanged/renumbered/edited/deleted/ambiguous by content fingerprint,
auto-fixes only renumbered ids and only with `--apply`. Self-test on the current
CR: `unchanged=3153, remaps=0, flags=0, exit 0`.

**Gold mining stability, both framings** — `docs/results-gold-stability.md`
(prompt drift: 0.5407 mean Jaccard, v1-trimmed vs v1 — NOT a stability figure)
and `docs/results-gold-stability-sameprompt.md` (same prompt twice under v2:
0.4867). **The miner is roughly half-reproducible with the prompt held fixed.**
Caveat: v2 mines 35% smaller gold sets than v1 on identical questions (mean
1.24-1.36 vs 1.98-2.00 ids, 68-76% singletons vs 24-28%), so the two Jaccards are
not directly comparable and the direction of that shift is unresolved.

**Pure-rules held-out set** — `evals/purerules.jsonl` (8 questions, loads
unmodified through `run_eval.load_questions()`), `evals/build_purerules_holdout.py`,
22 tests including two guards asserting neither harness's default `--questions`
path is the holdout file. `docs/spec-pure-rules-holdout.md` carries the open
decision on how big the set should get.

**Specs written and ruled on by Jon:** `docs/spec-coverage-metric.md` (shipped),
`docs/spec-gold-sufficiency.md` (approved, partially executed).
**Specs written and awaiting a ruling:** `docs/spec-cosine-floor.md`,
`docs/spec-stackexchange-rule-chains.md`.

**Two gold-audit batches** — `data/parsed/gold_audit_batch2.html` (20 rows,
selector rejected — built on `h2h_gpt5mini` disagreements, an arm scoring 52.8%
with no recorded judge) and `data/parsed/gold_audit_batch2_opuslow.html` (15
rows, **the one to grade**). The 15 are stable pipeline misses: judged wrong in
BOTH reps of the shipped config. `build_grading_ui.py` gained
`--audit-frame {oracle,pipeline-miss}` so the header describes the right
experiment; default stays `oracle` so batch 1 renders unchanged.

**README + hygiene** — the architecture diagram claimed `claude-sonnet-5`;
production is `claude-opus-5` at `effort=low` (`answer.py:34,54`). Quickstart
verified by actually running it. `evals/answers/` was briefly gitignored and that
was **reverted** — those 121 files are the recorded generations behind every
published accuracy (~$48 for the priced arms alone), `build_metrics_history.py`
reads them at line 79, and ignoring them puts them in reach of `git clean -Xdf`.

---

## THE STATE OF THE NUMBERS

```
full-run projection (shipped config)   82.8%  [78.2-86.6%]   $73-91   100% coverage
arm B (oracle, gold handed in)         91.3%  (137/150, human-verified)
ceiling with perfect retrieval         93.3%  (140/150)
L0-only pipeline arm                   97.1%  (201/207)

confounded fraction (corpus-weighted)  59.5%   <- rows that cannot measure retrieval
  L0 86.7% | L1 70.0% | L2 40.0% | L3 50.0% | Corner 30.0%

retrieval, hard arms:  hit_at() 48.1%   vs   coverage 17.4%
retrieval, easy arms:  hit_at() 44.7%   vs   coverage 29.6%
retrieval, L0:         hit_at() 39.9%   vs   coverage 30.8%  (138/207 scoreable)
```

Session API spend: **~$25** — L0 $11.71, control $9.70, OR-group $3.27 plus an
estimated $0.25-0.45 of judging.

---

## NEXT SESSION, IN ORDER — GOLD IS PRIORITY ONE

Jon's ruling: **figuring out the correct gold is the number one priority.** He
has also ruled out hand-grading at scale, so every step below has to be
machine-decidable or it does not qualify.

1. **Run the necessity (leave-one-out) test on the 38-question worklist.** Per
   `docs/spec-gold-sufficiency.md`, ~3.25 calls/row at arm B's rate. These are
   the rows where `hit_at()` most flatters retrieval, so they are where
   over-specified gold does the most damage. **Restrict to rows the control
   showed are NOT confounded** — on a confounded row the test cannot distinguish
   anything, which is exactly how the OR-group run lost 5 of its 21 verdicts.
2. **Extend the control to the remaining 60 rows** if the necessity work needs
   more rows validated. It is the gate on every other gold experiment's
   interpretability, which was not obvious until it retroactively decided which
   OR-group verdicts to keep.
3. **Fix the empty-gold rows** — 153 corpus-wide, 69 in L0. Nothing can measure
   retrieval on a row with no gold, and they are currently silently excluded from
   means rather than flagged.
4. **Rule on the 54+1 mis-encoded conjunctions** and apply them. Then re-run the
   coverage backfill; the retrieval numbers will move.
5. **Pilot the Stack Exchange rule chains** — `docs/spec-stackexchange-rule-chains.md`.
   10-15 usable chains from a 50-100 question pull at the sampled 50% yield. It is
   the only automated external source of conjunctive structure, which is what
   both the OR-group and match-mode defects are missing. Filter is Jon's: top
   answer must ALSO be the accepted answer, and it must cite specific numbered
   rules. Resolve citations four ways (by-number-content-agrees /
   by-number-content-DISAGREES / by-content-after-number-fails / unresolved) —
   17% of sampled citations were the dangerous middle case where the number still
   resolves but now means something else. Academy Ruins (`academyruins.com`,
   AGPL-3.0) is a real dated CR archive with diffs, which makes
   `check_cr_update.py`'s classifier reusable instead of fuzzy-matching quotes.
6. **Then decide the full run.** $73-91 at 82.8% [78.2-86.6%]. Cost was never the
   blocker and coverage no longer is. The open question is whether a corpus that
   is 60% confounded is the right thing to spend it on.

Still open from before: cosine floor (spec written, awaiting ruling), second-hop
retrieval, rerank-after-rewrite (needs re-scoping to the shipped n=3 path).

---

## HOW JON WORKS (load-bearing)

- **Explain things properly.** Define jargon at first use, lead with what a thing
  means, show a concrete example. He is a partner, not an observer.
- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until he rules.
- **Complete $0 work without asking.** His words: "we should always just complete
  these, especially if they don't use any AI. local compute is even better than
  free." But split the two kinds: local compute is genuinely free; "$0 in credits"
  means the labor is Claude's and only stays free on a subscription subagent.
- **Anything spending API credits gets an explicit ask**, however small, with a
  hard ceiling and a pilot checkpoint. Both cost gates fired usefully this
  session.
- **Verify agents' claims against the underlying data before relaying them.**
  This session that caught: a gold-audit row set selected from a 52.8%-accuracy
  arm, a wrong cache-coverage figure, a mislabeled stability number, a
  "pre-existing" test failure that was actually ours, and an OR-group result that
  was an artifact. Every one of them had sound arithmetic and a wrong sentence
  wrapped around it.
- **Subagent deliverables MUST land in the repo, not the session scratchpad.**
  $3.27 of completed OR-group work sat in a temp directory one session-end away
  from evaporating, and nothing would have flagged it.
- **Do not run the full pytest suite while an eval arm is running.** It races
  with `evals/answers/_progress/` and produces false failures. Two were chased
  this session.
- **Never assert an MTG or model fact from memory.** Ground in
  `data/raw/MagicCompRules 20260619.txt`, Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. For pricing import
  `rulesagent.pricing`; do not load the claude-api skill.
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.**
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON with
  `encoding="utf-8"` — the Windows cp1252 default fails on these files.
- Never pipe a long run through `| tail`; PowerShell `*>` buffers until exit so a
  running job's log looks dead. Check the output artifact.

---

## THE LESSON TO CARRY

Previous sessions: *a value that looks like an identity but is really a
position*; *a claim inherited without being checked*; *a number is a snapshot of
a file at a time*; *anything used as ground truth is an experiment subject,
including a person.*

This session: **an instrument that has never been tested is not a measurement, it
is an assumption with a number attached.**

Gold rule sets have been asserted by a miner and treated as truth from the moment
they were written. Nothing ever checked whether the listed rules were the ones a
question needs, whether they were all required or any one sufficed, whether the
miner would produce the same set twice, or whether the question needed rules at
all. Four separate defects, all downstream of that one omission, and all of them
invisible because the numbers they produced looked reasonable.

The corollary that cost the most today: **the confound in one experiment can
invalidate a different experiment that never mentioned it.** The OR-group test
was designed, costed, run and reported without anyone connecting it to the
control arm running in parallel — and the control turned out to decide which of
its verdicts were meaningful. When two experiments share a subject, they share
each other's confounds, whether or not the write-ups acknowledge it.

# Adversarial review — where the problems actually come from

Written 2026-07-26 (session 11), at Jon's request: *"we're answering a ton of
questions right, but not answering from the rules is a problem for a RAG."*

Every number below was recomputed from the files on disk during this review. No
model calls, no API spend. Where a number contradicts a published one, the
recomputation is shown so it can be checked.

**Plain-English summary of the verdict.** The bot is not making things up — when
it cites a rule, that rule was almost always genuinely in front of it. The real
problem is different and worse for a RAG: **on most questions the retrieved rules
aren't doing the work.** The model already knows the answer. And the deeper issue
is that our experiments were never built to tell those two situations apart, so
we cannot currently say what retrieval is worth.

---

## 1. The good news first: the bot is not inventing rule numbers

The contract in `contracts.py` says citations "must come from the chunks provided
in context, not outside knowledge." So counting citations that were never in
context measures how often the bot breaks its own grounding promise.

Across six arms running the shipped config (`l0_opuslow`, both h2h hard reps,
both h2h easy reps, `opus5_low_norewrite_costbase`):

```
rule-number citations         2,264
never present in context         17   (0.8%)
   of which CR 613 (layers)      16
```

Sixteen of the seventeen are CR 613 rules, which the `resolve_layers` tool and
the system prompt quote verbatim — so they were in front of the model, just not
via retrieval. **Effectively zero fabricated rule citations.**

> A trap worth recording: the first pass at this measured 40-46% ungrounded and
> was wrong. The `citations` field legitimately holds three different kinds of
> thing — rule numbers, glossary terms, and card/ruling labels like
> `Archive Trap ruling #2` — and only the first kind is a retrieval claim. Card
> and ruling citations arrive through the Scryfall/rulings channel, which never
> touches `retrieved_rule_ids`. Counting them as ungrounded rules manufactures a
> crisis that does not exist.

---

## 2. The real problem: retrieval mostly misses, and it mostly doesn't matter

Across all gold-bearing rows in the shipped-config arms (n=408):

```
mean gold coverage                24.8%
rows with ZERO gold in context      227  (55.6%)
accuracy on those zero rows       89.4%
correlation(coverage, correct)    r = +0.06
```

Retrieval fails to supply a single required rule on more than half the rows, and
the bot still gets ~9 in 10 of those right. Coverage and correctness are
essentially uncorrelated.

**That is the finding behind Jon's instinct.** The rules are being retrieved,
cited, and largely bypassed.

### The no-rules control reproduces, but with a much wider error bar

Recomputing the corpus-weighted confounded fraction from the 90 control rows and
the true corpus level distribution:

| level | correct / n | rate | corpus rows | weight |
|---|---|---|---|---|
| 0 | 26/30 | 86.7% | 207 | 14.7% |
| 1 | 21/30 | 70.0% | 565 | 40.1% |
| 2 | 4/10 | 40.0% | 406 | 28.8% |
| 3 | 5/10 | 50.0% | 162 | 11.5% |
| Corner Case | 3/10 | 30.0% | 69 | 4.9% |

**59.5%, 95% CI [48.6%, 70.5%].** The point estimate is exactly right. But 69% of
the corpus weight (levels 1 and 2) is carried by 40 rows, so the honest statement
is "somewhere between half and seven-tenths of the corpus is confounded," not
"60%." The sampling itself is sound — rows are spread through each level, not
taken off the front of the file.

---

## 3. NEW — no arm we have isolates retrieval. Not one.

This is the finding that most changes what to do next, and it is not in the prior
handoff. Pulled straight from the config fields recorded on each answer row:

| arm | rules in context | system_version | effort | ruling_query_mode | layers tool |
|---|---|---|---|---|---|
| shipped pipeline (l0, h2h, costbase) | ~19 | `3` | **low** | `raw` | **on** |
| no-rules control | 0 | `norules_control` | **high** | `union` | **off** |
| arm B "oracle" (91.3%) | gold handed in | `3` | **high** | `union` | on |

**In fairness to the control's design, which this review initially misread:** the
no-rules control was built as *"arm B minus rules"* (`build_norules_prompts.py`
§1), and against **arm B** it is well matched — same `effort=high`, same
`ruling_query_mode=union`. It differs from arm B on rules (intended),
`system_version` (unavoidable, see below), and `layers_tool` (unjustified). Its
separate system prompt was a considered, documented decision, not an oversight:
`SYSTEM_V3` instructs the model to answer only from the provided rules and to
decline when they are insufficient, which is exactly backwards for a control that
wants the model to try from its own knowledge.

**The problem is not the control's construction — it is what the control is being
used for.** The 59.5% confounded fraction was measured at `effort=high` against
arm B, and is then applied to the *shipped pipeline* (`effort=low`, `raw` query
mode, layers tool on) to decide whether the shipped full run is worth doing. A
confound rate measured under one configuration does not automatically transfer to
another.

**And arm B — the 91.3% number used as the "ceiling with perfect retrieval" — is
also `effort=high` while the shipped pipeline is `effort=low`.** So the headline
gap that motivates the entire "retrieval is the bottleneck" thesis:

```
shipped pipeline   82.8%   (effort=low)
arm B "oracle"     91.3%   (effort=high)   <- gap attributed to retrieval
```

...mixes retrieval quality with reasoning effort, and nothing on disk separates
them. The gap may be mostly retrieval. It may be substantially effort. **We do
not know, and no existing arm can tell us.**

### The layers tool has never been A/B'd either

Same pattern, found while answering Jon's question *"I don't remember if the
layers tool actually helps at all."* Every layers-off arm on disk
(`layers_slice0_base_layers_r1/r2/r3`) is `claude-sonnet-5`; every layers-on arm
is `claude-opus-5`. **The tool has never been toggled against a fixed model**, so
its value is unmeasured. For scale: `resolve_layers` fires on 3 of 207 rows (1.4%)
in the L0 arm, and only 5.4% of gold-bearing corpus rows have any 613 rule in
gold — but on the layers-enriched hard sets it fires on ~85% of rows.

### There is almost no paired data

Rows where the *same question* was answered both with and without rules:

| arm | paired rows | rules unneeded | rules helped | rules hurt |
|---|---|---|---|---|
| l0_opuslow | 30 | 25 | 4 | 1 |
| h2h hard r1 / r2 | 3 / 3 | 1 | 2 | 0 |
| costbase A | 4 | 2 | 2 | 0 |

About 40 paired rows exist, 30 of them level 0. Everything else is a comparison
of different questions answered under different configs.

---

## 4. The measurement floor is higher than most effects we've chased

Two identical runs of the same config, same questions:

```
h2h hard    r1 75.9%  ->  r2 72.2%    4 of 54 rows flipped  (7.4%)
h2h easy    r1 92.0%  ->  r2 86.0%    5 of 50 rows flipped  (10.0%)
```

**Any single-run difference smaller than roughly 6 points is indistinguishable
from noise.** The easy arm moved 6 points with nothing changed at all.

---

## 5. The judge is harsh in one direction only

Comparing the LLM judge's verdict to human review on the two arms that have both
(reading `final_correct`, not `verdict` — the human files preserve the judge's
original column and add their own):

| arm | judge | human | agreement | judge too harsh | judge too lenient |
|---|---|---|---|---|---|
| derivability B | 90.0% | 91.3% | 98.7% | 2 | **0** |
| costbase bucket A | 75.0% | 82.4% | 92.6% | 5 | **0** |

Seven corrections across 218 reviewed rows, **all in the same direction**. Every
judge-scored accuracy is a lower bound. Two consequences:

- Published accuracy numbers understate by roughly 1-7 points.
- The control was scored by the same harsh judge, so **the confounded fraction is
  understated too** — with human grading, more rows would be "right without
  rules," not fewer. The 60%-confounded problem is if anything worse than stated.

Human review also found the *reference answers* wrong on 2 rows and gold
incomplete on 2 more (~1.3%). RulesGuru is not a perfect oracle either.

---

## 6. A real bug in the coverage metric: the layers blind spot

`retrieved_rule_ids` records only what the retriever fetched. It does **not**
record rule text that arrives free in the prompt on every call.

**The mechanism is the tool schema descriptions, not the system prompt.** This
review's first pass got that wrong and the correction matters, because it changes
what the fix may credit. Verified by reading the actual constants in
`src/rulesagent/generate/answer.py`:

- `RESOLVE_LAYERS_TOOL` (4,592 chars, sent on every call when the tool is enabled,
  whether or not it ever fires) quotes **CR 613.6 verbatim** and 613.8a's criteria
  in substance, and references 613.3 / 613.4a.
- `CALCULATE_COST_TOOL` references 601.2f.
- `SYSTEM_V3` — the shipped prompt — quotes **no rule text at all**. Its single
  rule number appears only as a formatting example: *"Rules are labeled with their
  number in brackets, e.g. [104.3a]."* A bare number with no text is **not**
  supplied context and must not be credited as coverage. (The 613 quotations in
  `SYSTEM_VERSIONS['v3+613']` belong to a prompt version the shipped arms do not
  use.)

So the governing distinction is **quoted text vs bare reference**, and only the
former counts. Applying it strictly, the set of rules genuinely handed over free
is just **613.6 and 613.8a** (layers tool on), plus 611.3a under the unused
`v3+613` prompt. `601.2f` and `613.3`/`613.4a` are bare citations and were
excluded on the same principle as 104.3a.

**Fixed and verified this session.** `coverage_at()` / `coverage_from_ids()` now
accept a prompt-supplied set, generation records `prompt_supplied_rule_ids` per
row, and the backfill reports corrected and uncorrected side by side. Measured
across the same 408 rows, independently reproduced:

```
mean coverage, uncorrected   24.8%
mean coverage, corrected     29.4%   (+4.6 pp, 56 rows changed)
```

The entire correction lands on the layers-heavy arms (`h2h_opuslow_hard_*`
17.4% → 28.7%, `opus5_low_norewrite_costbase` 17.7% → 27.7%); L0 and both easy
arms do not move at all, because their gold never includes those two rules. That
asymmetry is itself the evidence the fix is doing what it claims.

> An earlier draft of this review put the correction at +6.5 pp (to 31.3%). That
> was computed with `104.3a` wrongly credited. **+4.6 pp is the verified figure.**

This explains part of the strangest result in this review:

**12 hard (L3/Corner) rows where retrieval returned nothing even in the same rule
family as gold, judged 100% correct.** Inspecting them: `rg126`-`rg131` are six
permutations of the same Blood Moon + Life and Limb layer puzzle, plus `rg7`,
`rg98`. Their gold is dominated by 613.x. The layers tool handled them. Coverage
called it a total miss.

Their gold is 613-heavy, and 613.8a is one of the ids the layers tool schema
supplies for free. So the pipeline had more than coverage credited it with —
though **not** the whole gold set, so this softens the anomaly rather than
dissolving it. The rest is still unexplained and belongs in the gold audit.

**Two secondary findings fall out of that:** the corpus contains near-duplicate
clusters (six rows for one interaction), so effective sample size is smaller than
row count; and any per-row metric that ignores tool-delivered context will
systematically under-credit the layers path.

**A third, raised by Jon and confirmed against the CR:** the layers tool schema is
under-specified for what it does. It quotes 613.6 and 613.8a, but the tool reasons
over the whole layer system, and `MagicCompRules 20260619.txt` puts the structure
it depends on in 613.1 (the layer order), 613.2 (layer 1 sublayers) and 613.4
(layer 7 sublayers) — none of which it carries. Fixing that is worth doing, but
**not in the same run as toggling the tool**, or it reproduces exactly the
multi-variable mistake this review is about.

---

## 7. "Full coverage scores 97.8%" is not evidence retrieval works

Breaking the coverage buckets down by how many gold rules the row actually has:

| bucket | n | mean gold-set size | rows with only 1 gold rule |
|---|---|---|---|
| zero coverage | 227 | 2.32 | 30.8% |
| partial | 136 | 3.60 | **0.0%** |
| full | 45 | 1.22 | **80.0%** |

**Stratified properly (shipped six arms, corrected coverage, n=408) the apparent
relationship disappears:**

| gold-set size | n | mean cov | zero (n / acc) | partial (n / acc) | full (n / acc) |
|---|---|---|---|---|---|
| 1 | 106 | 36.8% | 67 / **97.0%** | n/a — structural | 39 / **94.9%** |
| 2 | 143 | 26.6% | 78 / 84.6% | 54 / 100.0% | 11 / 72.7% |
| 3 | 76 | 28.5% | 27 / 81.5% | 48 / 83.3% | 1 / 100.0% |
| 4+ | 83 | 25.8% | 24 / 87.5% | 59 / 59.3% | 0 / — |

Read row 1: on single-gold-rule questions, retrieving the rule scores **94.9%**
and retrieving nothing scores **97.0%**. Full coverage is not better. The
headline "97.8% at full coverage" was composition, not effect.

A row with one gold rule can only ever be zero or full — never partial. So "full
coverage" is mostly single-rule questions (easy) and "partial" is mostly
multi-rule questions (hard). The apparent coverage-accuracy relationship is
substantially a difficulty artifact.

Restricting to multi-gold rows only, so partial is possible in both groups. **Both
the uncorrected numbers this review first published and the corrected ones after
the §6 fix landed:**

```
                      UNCORRECTED (first pass)          CORRECTED (§6 fix applied)
easy levels (0-2):  zero 85.9% (n=135) partial 86.9% (n=107)   zero 84.8% (n=125) partial 88.0% (n=117)
hard levels (3/CC): zero 90.9% (n= 22) partial 31.0% (n= 29)   zero 75.0% (n=  4) partial 59.1% (n= 44)
```

**The easy-level result survives and is solid.** On levels 0-2, retrieval
coverage makes no measurable difference — a 3-point gap across 242 rows, well
inside the 7-10% noise floor.

**The hard-level 60-point inversion does not survive, and this review was wrong
to headline it.** Once the layers-supplied rules are credited, most of those
"zero coverage" hard rows turn out to have had partial coverage all along: the
bucket collapses from n=22 to **n=4**. Four rows cannot support a finding. The
direction still points the same way, but that is now an observation about four
questions, not a result.

**The two findings were causally linked and nobody spotted it until both were
computed.** §6's measurement bug manufactured §7's anomaly. That is this
session's own instance of the standing lesson: *a confound in one experiment can
invalidate a different experiment that never mentioned it.* It happened again,
inside the review written to catch it happening.

What that leaves:

- **(a) Partial context distracts** — a known RAG failure mode, still possible,
  now with almost no evidence behind it here.
- **(b) Coverage is a proxy for obscurity** — reverse causation, equally live.

Observational data cannot separate them, and after the correction there is barely
enough data to try. **This strengthens rather than weakens the case for the
intervention in `docs/spec-retrieval-value-ab.md`:** the observational route is
exhausted.

Note also the hard pool is failure-enriched by construction — `build_h2h_set.py`
builds half the set from a previous model's misses, and its Corner Case rows are
miss-only. These rows were never representative.

---

## 8. Things that turned out fine (checked, so they can stop being suspected)

- **The rule index is complete.** All 738 distinct gold ids resolve to real chunks
  in `MagicCompRules 20260619.txt` (3,619 chunks). Zero rows have unretrievable
  gold. (An earlier inference in this review suggested 12.7% missing; that was
  computed from observed retrievals rather than the index, and was wrong.)
- **One judge, one judge prompt.** Every relevant arm was scored by
  `openai/gpt-5-mini` at prompt sha `b54fbdb955`. No cross-judge contamination.
- **Control sampling is spread, not a prefix.** Selected rows span each level's
  full range; the head-of-file trap did not recur here.

---

## 9. Root cause

Three layers, outermost first.

**The eval corpus is largely not rules-dependent.** RulesGuru questions skew
toward things a strong model already knows. Half to seven-tenths of rows are
answerable with no rules at all. Even a perfect measurement would have little
signal to read.

**Gold was never validated.** Coverage and `hit_at()` measure agreement with a
label a miner asserted. When a hard row shows zero coverage and a correct answer,
we cannot tell whether the gold is wrong, the rules were unnecessary, or another
channel supplied them. (This session found the third case is real and unmeasured.)

**The deepest one: nothing in the system separates "the pipeline was right" from
"the model was right."** Every arm changes several variables at once, paired data
barely exists, run-to-run noise is 7-10%, and the judge is one-directionally
harsh. The RAG's contribution has never been measured — it has been *inferred*
from comparisons that do not isolate it.

That is why the bot answers well and the rules aren't doing the work: **we have
been optimising a component whose value we never instrumented.**

---

## 10. What to do, in order

### Free (local compute, zero credits) — no approval needed

1. ~~**Record tool-supplied and prompt-quoted rule ids on the answer row**, then
   re-run `backfill_coverage.py`.~~ **DONE this session.** Coverage 24.8% → 29.4%
   (§6). Drift-guard test added so editing a prompt or tool schema fails loudly
   rather than silently changing what counts as retrieved.
2. **Stratify every retrieval metric by gold-set size.** Unstratified
   coverage-vs-accuracy is a difficulty artifact (§7).
3. ~~**Publish a config matrix on the dashboard.**~~ **DONE this session.** 19
   arms × 9 config axes, columns where arms disagree highlighted, columns where
   they agree muted. This is the discipline fix for §3 — it makes an uncontrolled
   comparison hard to publish by accident. 8 of the 9 axes differ across arms;
   `show_rewrite` is the only one every arm agrees on.
4. **Report a noise floor next to every accuracy number** (§4), so effects under
   ~6 points are visibly inside the error bar.
5. **Flag the 153 empty-gold rows** explicitly instead of silently dropping them.
6. **Detect near-duplicate question clusters** and report effective sample size.

### Costs credits — needs an explicit ask with a ceiling

7. **The one experiment that answers Jon's question: a true single-variable
   paired A/B.** Same rows, same `system_version`, same `effort=low`, layers tool
   on in both — the only difference being retrieved rules present vs absent.
   ~100 rows stratified by level. Nothing we have measures this, and everything
   downstream depends on it. **This should come before the full run.**
8. Necessity (leave-one-out) on the 38-row worklist, restricted to
   non-confounded rows — as the handoff already planned.
9. **Highest-yield gold audit target found this review:** the 22 hard rows with
   zero gold coverage that were judged correct, minus the 613/layers cluster
   explained in §6. On those, either the gold is wrong or the question needs no
   rules, and both answers are valuable.

### Recommendation on the full run

**Hold it.** $73-91 buys a corpus-wide accuracy number on a corpus that is
50-70% confounded, measured with a 7-10% noise floor and a one-directionally
harsh judge. It would produce a defensible headline figure and would not move the
question of whether retrieval earns its place. Item 7 costs far less and actually
answers it.

---

## The lesson

Previous sessions: *an instrument that has never been tested is not a
measurement, it is an assumption with a number attached.*

This one is the next turn of the same screw: **an experiment that changes more
than one thing at a time cannot attribute its result, no matter how clean the
number looks.** The control differed on four axes; the oracle ceiling differed on
reasoning effort. Both produced numbers that were quoted, compared, and built on.
Neither can support the comparison it was used for.

The fix is not more arms. It is recording the config diff between any two arms at
the moment they are compared, and refusing the comparison when the diff has more
than one row in it.

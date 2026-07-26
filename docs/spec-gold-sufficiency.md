# Spec — gold sufficiency: turning "is this gold good enough" into a measurement

**Status: unruled.** Rule 0 applies — this is design only, nothing below is built.

## The idea, with the proof already sitting on disk

Every question in this repo's eval sets carries a **gold** rule list: the CR
sections a miner asserts are needed to answer it. Nobody has ever checked that
assertion directly — "is this the right set of rules" has always been a
judgment call, made by reading CR text next to a question and deciding whether
it looks right (that's exactly what the OR-group re-pass did, by hand, for 105
groups; `docs/results-orgroup-repass.md`).

But the repo already contains the machine to check it, because one of the
eval harness's arms does something stronger than judge an answer: it hands the
model **nothing but the candidate gold** — no retrieval, no search, just those
rules and the card rulings — and scores whether the answer it produces matches
the reference. If the model gets it right from *only* those rules, that is a
direct, positive proof that the set is **sufficient**: nothing else was in the
room when the right answer came out. This isn't a new experiment to design —
it's arm B of the derivability run, already executed and already published:
`evals/verdicts_derivability_B_human.json`, 137/150 = 91.3%, documented in
`docs/results-derivability.md`. This spec names that arm as a *general-purpose
sufficiency test* and designs the two things it doesn't already do on its
own: telling a real gap apart from an unlucky answer, and checking whether
gold is not just enough but has anything extra it didn't need.

**Concrete worked example**, so "sufficiency" isn't abstract. `rg7215`'s gold
is one rule, `614.12`. Handed only that rule, arm B answered "enters
**untapped**." The reference answer is "enters **tapped**." That's a failure
— but by itself it doesn't say *why*. The same row, re-run with retrieval
added on top of the same gold (`evals/verdicts_derivability_C.json`, arm C),
answered "enters **tapped**" correctly, because retrieval supplied a rule
`614.12` alone didn't contain. That side-by-side — fails alone, passes with
one more rule added, and the added rule is the reason — is what turns "gold
looks thin" from a suspicion into a checked fact. That's the whole method:
run the model on a candidate set, and use a second condition (more rules, a
repeat, a different model) to tell you what a failure actually means.

## 1. The test is one-way — and how a failure gets triaged instead of assumed

**Success proves sufficiency. Failure proves nothing on its own.** A "correct"
verdict has exactly one explanation: the model produced the reference answer
from the candidate rules and nothing else, so those rules were enough. A
"wrong" verdict has at least four:

1. **Gold is genuinely incomplete** — the true positive this test exists to
   catch (`rg7215`, `rg549`, `rg811`).
2. **Reasoning failure** — the rules were enough, the model just got the
   inference wrong (`docs/results-miss-partition.md`'s `rg614`, `rg776`,
   `rg4023` are exactly this shape, just measured with retrieval present
   instead of gold-only).
3. **Judge error** — the judge is nondeterministic (`docs/results-
   derivability.md`: "~1 flip per 100 rows... a digest pins the *prompt*, not
   the *output*") and has a measured non-zero false-fail rate
   (`docs/results-judge-error-rate.md`, cited in the derivability doc as an
   upper bound of ~4.4% on wrongly-passed rows — the false-fail direction is
   the same instrument, not separately bounded here, but the same order of
   magnitude applies).
4. **The reference itself is wrong** — already a confirmed, non-hypothetical
   category (`docs/results-derivability.md`'s "RulesGuru is wrong": `rg6556`,
   `rg289`).

A test that can't fail cleanly is not a test — this is the part of the design
that has to be explicit, not the part to gloss past. Proposed triage, cheapest
check first:

- **Step 0 — re-judge, don't re-run.** Re-score the existing transcript with a
  fresh judge call. If the verdict flips, that's judge noise, not a gold
  problem. Cost: one judge call, no model call, effectively free relative to
  everything below.
- **Step 1 — repeat the row.** Re-run the same gold-only prompt 2 more times
  (3 total) at the same model/effort. If the answer is wrong the same way all
  three times, that rules out one-off sampling variance — the model isn't
  flip-flopping, it's consistently landing somewhere the candidate rules don't
  support (or consistently making the same mistake despite them).
- **Step 2 — add retrieval back (arm C) on just this row.** Two outcomes,
  and they mean different things:
  - **Passes, citing a rule outside the candidate gold set** — direct,
    checked proof of incompleteness. This is exactly how `rg7215`/`rg549`/
    `rg811` were confirmed, not inferred.
  - **Still fails, or passes citing only rules already in the candidate
    set** — incompleteness is *not* demonstrated. The likelier explanation is
    reasoning failure (category 2) or a bad reference (category 4), and the
    row should go to a human read (Jon) rather than being logged as a gold
    gap on the strength of one bad arm-B answer.
- **Step 3 (stronger signal, use when Step 2 is ambiguous) — cross-model
  check.** Run the same gold-only prompt on a different model family. If a
  different model succeeds where the first one failed, that's evidence
  against "gold is incomplete" and for "that specific model has a blind spot
  here" — a shared failure across unrelated architectures is much harder to
  explain as one model's quirk. This is the second signal the design brief
  asked for, offered as an escalation, not a default, because it doubles the
  run's cost for a check that's only needed when repetition and retrieval
  didn't already settle it.

**The load-bearing rule:** insufficiency is only *logged* as insufficiency
once Step 2 (or Step 3) produces the positive signature — retrieval supplying
material the candidate set lacked, and that material being the reason the
answer changed. Everything short of that stays labeled "unresolved failure,"
not "gold gap."

## 2. The confound that has to be named first, not last: parametric knowledge

**The model already knows Magic.** Opus-5 was trained on a large slice of the
public internet, which includes rules forums, wikis, and almost certainly the
Comprehensive Rules themselves. A gold-only arm cannot, by construction,
distinguish "the model derived this from the three rules I handed it" from
"the model already knew the answer before it read the rules I handed it, and
the rules were decoration." If the second thing is common, this whole test is
measuring the model's prior, not the gold set's quality — a bad gold set could
look perfectly sufficient for the wrong reason, and the test would never show
it. This is the single biggest threat to the method's validity.

**Detection: a no-rules control arm.** Run the identical 150 questions with
*no rules attached at all* — strip the system prompt's "answer only from the
following rules" framing, give the model just the question, and score against
the same reference with the same judge. This is arm B with the one variable
that matters set to zero.

What the comparison tells you, row by row:

- **Control wrong, arm B right** — clean evidence the gold rules did the
  work. This is what a *validly* sufficient gold set looks like.
- **Control right, arm B right** — the row is confounded. Arm B's "pass"
  doesn't distinguish gold from prior; the candidate set looks sufficient but
  the test can't tell you it was gold that made it so.
- **Control right, arm B wrong** — a stranger case worth flagging on sight:
  the model does *worse* with the candidate rules in front of it than
  without them. That's a real signal too — either the rules are actively
  misleading, or attention gets pulled toward a distractor.
- **Control wrong, arm B wrong** — uninformative for this question either
  way; falls back to the Section 1 triage.

**A corpus-level confound rate** — the fraction of arm B's 137 passes where
the control *also* passes — is the number to report, not just anecdotes.
If it's high (say, most of the 100-level rows, where MTG's public-facing rules
content is densest), the 91.3% headline needs an asterisk: "sufficient
*and distinguishable from prior knowledge* on only N of 137." If it's low,
the 91.3% stands largely uncontested.

**Cost.** The control arm is *cheaper* per row than arm B, not just equal —
there's no gold-chunk text and no card-ruling block in the prompt, so input
tokens drop. Lacking a token breakdown for arm B's actual calls, the honest
move is to price the control at arm B's own per-question rate as a
**conservative upper bound** (see Section 4) rather than invent a token count
for a leaner prompt that hasn't been built yet. Running the control on the
full 150-row set costs at most **$8.47** (arm B's own figure, restated as a
ceiling); a stratified sample sized to match whatever necessity sample gets
picked costs proportionally less. Given how central this confound is, running
it on the *whole* 150 rather than a slice is the one place in this spec where
the full-corpus cost is small enough ($8.47, already spent once on arm B
itself) that sampling isn't worth the loss of coverage.

## 3. The mirror test: necessity (leave-one-out)

Sufficiency asks "is this enough." The mirror question is "is any of it
unneeded" — drop one gold rule, re-run gold-only, and see if the answer
survives without it. If it does, that rule wasn't doing anything for *this*
question; the gold is over-specified for it.

This matters now, not as a hypothetical: `docs/results-miss-partition.md`
found 90 of 202 scored rows (across four production arms) where the model
answered correctly **without the flagged gold rule ever appearing in
context** — the "miss, correct" cell. That's a different experiment
(production retrieval missing gold, not an oracle arm dropping it on
purpose), but it's the same shape of finding pointing the same direction:
gold rule lists may routinely carry more than a given question needs.

**Design.** For a question with gold set `G = {r1, ..., rk}`, run gold-only
`k` times, each time with exactly one `ri` removed (`G \ {ri}`). The `k=full`
case is arm B itself — already run, zero incremental cost, that data point is
reused as the baseline. If the answer stays correct with `ri` removed, `ri`
was not necessary for this question (over-specification, at least for this
row). If it flips to wrong, `ri` was carrying real weight.

**Combinatorics — and why it's linear, not exponential, by design.** The
textbook way to find the *truly* minimal sufficient subset is to test every
non-empty subset of `G` and keep the smallest one that still passes — the
power set, `2^k - 1` runs. That's the honest expensive version: for the
`rg4023`-sized row in `docs/results-derivability.md` (10 gold ids), it's
**1,023 runs for one question.** Leave-one-out is the cheap approximation:
test only the `k` subsets of size `k-1`, one rule dropped at a time. That's
linear in `k`, and it's not an ad-hoc shortcut — it's exactly the manual test
`evals/gold_miner_prompt.md`'s rule 6 already applies by hand to OR-groups
("if the retriever found ONLY this member and none of the others, would that
step of the answer be established?"). LOO automates that same test instead of
inventing a new one.

**What LOO can miss, stated plainly.** It tests each rule's necessity *given
all the others are present*. It cannot catch a case where no single rule is
individually necessary but some smaller *combination* is required (dropping
either of two rules alone still leaves enough support, because each
compensates for the other) — that needs the full power-set test to catch,
and at the cost above, it isn't worth chasing except as a follow-up on a row
LOO already flagged as interesting.

**Cost for a stated sample.** Derivability's own corpus statistic — mean 3.25
gold chunks per question (`docs/results-derivability.md`) — is the right `k`
to use, since it's the same question set and the same arm shape. Per-row LOO
cost: `3.25 calls x $0.05647/call ≈ $0.184/row` (see Section 4 for the
per-call basis). Two concrete samples:

- **General sample, n=20 multi-rule rows** drawn from the 137 rows arm B
  already scored correct (necessity is only meaningful against a
  known-sufficient baseline — there's nothing to test on a row that already
  failed sufficiency). `20 x 3.25 ≈ 65 calls ≈ $3.67`.
- **Targeted sample: the 25 needs-Jon OR-groups** (Section 5) — cheaper and
  higher-value; costed separately there.

## 4. Costs, from `rulesagent.pricing`, not guessed

Per the task constraint, no `claude-api` skill load — everything below comes
from `rulesagent.pricing.rate()`/`cost_usd()` plus the one number already
published.

```
>>> from rulesagent import pricing
>>> pricing.rate("claude-opus-5")
(5.0, 25.0)          # $/MTok, input/output — static, no scheduled change
>>> pricing.check_freshness()
[]                    # cache confirmed current as of this doc
```

Arm B's own figure is the empirical anchor: **$8.47 / 150 = $0.05647 per
question** (`docs/HANDOFF-development.md`, cited at
`evals/build_metrics_history.py`'s `armb-rerun` roadmap entry). That number
already reflects opus-5 effort-high pricing on this corpus's actual token
mix (gold rules + card rulings + prompt-cache reads on the shared system
prompt) — reusing it rather than re-deriving from scratch avoids guessing a
token count for calls that haven't been made yet.

| Arm | Per-call basis | Per-row cost | Sample | Sample cost |
|---|---|---|---|---|
| Sufficiency (arm B) | measured, 150 calls | $0.05647 | 150 (**already run**) | $8.47 (sunk) |
| Failure triage, Step 1 (repeat x2) | same rate, no new context | $0.1129/row | 13 remaining failures | $1.47 |
| Failure triage, Step 2 (arm C re-run) | arm C already exists for these rows | $0 (reuse) | 13 rows | $0 |
| Necessity (LOO), general sample | $0.05647/call x mean 3.25 calls | $0.184/row | 20 rows | $3.67 |
| Necessity (LOO), needs-Jon OR-groups | $0.05647/call x ~2.04 members/group | ~$0.115/group | 25 groups (51 member-drop calls, see §5) | $2.88 |
| Parametric-knowledge control | ≤ arm B rate (conservative; true cost is lower, shorter prompt) | ≤ $0.05647/row | 150 (full corpus, see §2) | ≤ $8.47 |

**Total for the recommended first pass** (needs-Jon necessity + a 20-row
general necessity sample + the 13-row failure triage + the full-corpus
control, which Section 2 argues shouldn't be sampled down): roughly
**$2.88 + $3.67 + $1.47 + $8.47 ≈ $16.49** — about twice arm B's own cost, for
three separate questions arm B alone can't answer: which gold is thin, which
gold is fat, and how much of the whole thing is prior knowledge in a trench
coat.

## 5. Sample selection — where to spend the first dollar

Three candidate populations, and a specific argument for ordering them:

1. **The 25 needs-Jon OR-groups** (`docs/results-orgroup-repass.md`) — highest
   priority. See Section 6 below for why: this is the one population where
   the test's *output* is a direct answer to a question already blocking a
   human, not just a data point.
2. **Multi-rule rows, general sample (n=20)** — where match semantics broke
   (`docs/results-miss-partition.md`: `match: "any"` over a multi-part gold
   list inflates "context ok," and the reversal on hard/bucketA questions —
   lower accuracy *with* gold present than without — is the headline finding
   there). Rows with 2+ gold rules are exactly where a leave-one-out check
   has something to remove; single-rule rows (like `rg7215`) have nothing to
   drop and should be excluded from this sample by construction.
3. **Rows behind published numbers** — the derivability doc's ceiling
   (`rg7215`, `rg549`, `rg811`, already resolved) and its 10 "beyond
   retrieval" rows (`rg1095 rg1208 rg241 rg289 rg494 rg559 rg5863 rg6556
   rg713 rg842`) — these matter because they sit directly under the quoted
   93.3% ceiling; a repetition/cross-model triage pass here (Section 1)
   would either shore up that number or surface a correction, and either
   outcome is worth having before it's cited further.

**A triangulation bonus, worth building into whichever sample is drawn:**
where a row appears in *both* the miss-partition "miss, correct" set (right
without gold, from a live retrieval arm) and passes this spec's leave-one-out
test without one of its gold rules (right without that rule, from the oracle
arm), that's the same conclusion reached two independent ways — the strongest
version of an over-specification finding this design can produce, and cheap
to check for once both datasets exist.

## 6. Can this shrink Jon's queue — the 25 needs-Jon OR-groups

**Yes, mechanically, for the scoring-relevant question — with one caveat.**

`docs/results-orgroup-repass.md`'s rule 6 test is, verbatim: *"if the
retriever found ONLY this member and none of the others, would that step of
the answer be established? If no for any member, split the group."* That is
already a sufficiency/necessity statement about individual OR-group members —
it was just answered by a human reading CR text instead of by running the
model. The exact same test, automated: for OR-group `{m1, m2}` inside a row's
full gold set `G`, run gold-only twice — once with `G` minus `m2` (only `m1`
from the group, plus every other required rule in `G`), once with `G` minus
`m1`. Score against the reference, same judge as arm B.

- **Both variants pass** → each member independently carries the question —
  matches "(a) legitimate OR," confirmed by behavior, not just by reading.
- **Only one variant passes** → the other member was necessary, not an
  alternative — matches "(b) mis-encoded conjunction," and the split rule 6
  already prescribes is now demonstrated, not asserted.
- **Neither passes** → both members together were needed, or something
  outside this group is also missing — inconclusive on its own, escalate via
  Section 1's triage.

Counting the 25 needs-Jon groups from the doc's own listing: 24 are 2-member
and one (`rg6475`'s `701.19a/614.8/701.19b` group) is 3-member — **51
member-drop calls total** (a handful of rows in the doc's prose don't spell
out member ids explicitly; those are assumed 2-member, the dominant shape
everywhere else in that document, so this is an estimate built from the
doc's own text, not a fresh recount of the underlying corrections file).
51 calls x $0.05647 ≈ **$2.88** to mechanically test all 25.

**The caveat:** this resolves the *scoring question* — is member M necessary
for retrieval credit, yes or no — for essentially all 25, which is exactly
what feeds `gold_groups()`/`hit_at()` and gates the intersection/union
decision in Section 7. It does **not** fully resolve the *narrative* question
some of the 25 were flagged for — `docs/results-orgroup-repass.md`'s own
example, `rg60` (`702.26k` states the scenario outright; `702.26b` is true
background that "adds nothing the specific rule doesn't already cover") —
where the behavioral test (drop `702.26b`, does the answer survive) will very
likely say "yes, drop it," the same verdict a legitimate-OR case gets. The
model test can tell you a member is dispensable; it can't tell you *whether*
that's because it's a genuine independent alternative or because it's padding
text that happened to rephrase the necessary rule. For the scoring decision
that gates Section 7, that distinction doesn't matter — dispensable is
dispensable either way. For the handful of rows where Jon might want the
narrative distinction preserved in the gold's documentation (not just its
scoring), a short human read of the model-flagged dispensable members is
still worth doing — but that's a much smaller, cheaper read than re-deriving
all 25 groups from CR text by hand, which is the queue item this test
removes.

## 7. What this gates: intersection or union for consensus mining

`docs/HANDOFF-development.md`'s "double-mine" work (roadmap id `double-mine`,
`evals/build_metrics_history.py`) found that two independent mining runs on
identical questions agree on only 26% of rows, mean overlap 0.54. Once
consensus mining (running the miner N times and combining) is built, it has
to pick one of two combination rules, and they pull in opposite directions:

- **Take the intersection** (keep only rules every run agreed on) — the
  right call if gold tends to be **over-specified**: individual runs each add
  some rule the others didn't need, and agreement is the filter that removes
  padding.
- **Take the union** (keep every rule any run found) — the right call if gold
  tends to be **under-specified**: individual runs each miss something real,
  and pooling coverage is what fixes it.

**Current indirect evidence leans toward over-specification being the more
common failure, but it's indirect on both counts and this test is what would
make it direct.** The incompleteness rate measured so far is low and confirmed
by name (3/150 = 2%, `rg7215`/`rg549`/`rg811`). The over-specification
signal is larger but not yet measured the same way: 54/105 OR-groups were
mis-encoded conjunctions (a related but different defect — wrong *structure*,
not proven-unnecessary *content*), and 90/202 miss-partition rows were
answered correctly without gold ever being retrieved (a production-retrieval
artifact, not a controlled drop-one-rule test). **Neither of those is the
necessity test itself** — they're the reason to expect what Section 3's
leave-one-out sample would show, not a substitute for running it. Once the
necessity sample from Section 3/6 actually runs, its over-specification rate
versus the (already-measured) 2% incompleteness rate is the number that
decides this: if over-specification clears incompleteness by a wide margin,
intersection is the evidence-backed default; if they turn out closer than
expected, union deserves a second look before it's ruled out.

## Explicitly out of scope

- Building consensus mining itself (`double-mine` roadmap item) — this spec
  only supplies the evidence that gates its intersection-vs-union choice.
- Re-running arm B for citation correctness (`armb-rerun` roadmap item,
  already separately proposed and already `open`) — orthogonal to
  sufficiency; that item is about label offsets, not the sufficiency
  question.
- Modifying `evals/questions_rulesguru150_v3.jsonl` or any canonical gold —
  every arm above reads gold, none writes it.
- Running the power-set (full minimality) necessity test — priced above at
  1,023 calls for a 10-rule row and rejected on cost; LOO is the recommended
  approximation.
- Judge error rate itself — measured separately
  (`docs/results-judge-error-rate.md`); this spec only uses that figure as an
  input to Section 1's triage, it doesn't re-measure it.

## Open decisions for Jon

1. **Whether to run the parametric-knowledge control on the full 150 now** —
   recommended in Section 2 given its centrality to validity, at $8.47
   (upper-bound pricing) — versus starting with a smaller stratified sample
   and expanding only if the confound rate looks high.
2. **Which necessity sample to run first** — the 25 needs-Jon OR-groups alone
   ($2.88, directly actionable against Jon's queue) versus adding the general
   20-row sample in the same pass ($3.67 more) for a corpus-wide
   over-specification estimate to weigh against the 2% incompleteness rate in
   Section 7.
3. **Whether a dispensable-but-possibly-narrative-worthy member (the `rg60`
   shape in Section 6) gets a short human read even after the model test
   calls it dispensable**, or whether "dispensable" is treated as fully
   decided once the behavioral test says so.
4. **Cross-model escalation (Section 1, Step 3)** — build it now as part of
   this pass, or hold it until a specific ambiguous row actually needs it.

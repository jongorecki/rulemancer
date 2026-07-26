# Results — miss-partition diagnostic: retrieval miss vs. reasoning failure

**Design doc:** `docs/plan-miss-partition-diagnostic.md` (DRAFT, awaiting Jon's
review at time of writing). Its definitions are used as-is: *context ok* means
the question's gold requirement (respecting `match`/`gold_groups`, via the
project's own `gold_groups()`/`hit_at()` rule in `evals/run_eval.py:158-177`)
was satisfied by the chunks actually placed in the generator's context;
*retrieval miss* means it wasn't. The plan's Candidate-A/Candidate-B split
(§4.1) is moot for this run: the answer rows in scope already carry a
structured `retrieved_rule_ids` field (the plan's own recommended fix, since
built), so no prompt-string slicing was needed. This is a read-only pass over
existing files — no model calls, no new eval run.

## The split, in plain language, before any table

On the **easy** half of the shipped h2h arms, this is not close: every single
miss is a retrieval miss. Across both easy runs, zero rows have the gold rule
in context and still get marked wrong. When the model has the rule, it uses it
correctly, 100% of the time (n=21 both runs). All the wrongness on easy
questions happens when gold wasn't in context.

On the **hard** half and on **bucketA** (a different retrieval config, kept
separate), the picture flips, and the flip is the headline: rows where gold
was in context are answered *correctly less often* than rows where gold was
missing (roughly 58-63% accuracy with gold present vs. 85-89% accuracy without
it, per arm below). That is backwards from the naive expectation, and it is
not a small effect — 10 to 12 rows per arm are context-ok-but-wrong. Some of
that is genuine reasoning failure (three worked examples below). But a real
chunk of it is an artifact of how "context ok" gets computed today: these are
multi-part questions scored under `match: "any"`, so a single incidentally-
retrieved rule id is enough to mark the whole question "context ok" even when
6 of 7 actually-needed rules are missing. `rg4023` below is a clean case of
exactly that. The corrected-semantics pass (next section) confirms this isn't
speculation, on the small slice where it could be checked directly.

## 1. THE SPLIT — current semantics (`hit_at()` as implemented today)

Per-arm 2x2, computed by testing each row's own `match`/`gold` against its
`retrieved_rule_ids` (full assembled context, not a k-cutoff — the plan's §5
rank-in-window question is out of scope here since the diagnostic asks
presence, not rank) and crossing that against the judge verdict
(`same`=correct, `different`=wrong; no `partial` value exists in these judge
files). Rows with empty `gold` are excluded and reported separately — they
cannot be scored "present" or "absent" (same blocker the plan names for
`cards.jsonl`, here showing up in 3/50 rows of each easy run, 0 elsewhere).

| arm | n scoreable | context-ok + correct | context-ok + wrong | miss + correct | miss + wrong | empty-gold (excluded) |
|---|---:|---:|---:|---:|---:|---:|
| h2h_opuslow_easy_r1 | 47 | 21 | **0** | 22 | 4 | 3 |
| h2h_opuslow_easy_r2 | 47 | 21 | **0** | 19 | 7 | 3 |
| h2h_opuslow_hard_r1 | 54 | 16 | **10** | 25 | 3 | 0 |
| h2h_opuslow_hard_r2 | 54 | 15 | **11** | 24 | 4 | 0 |
| **4-arm total** | **202** | **73** | **21** | **90** | **18** | **6** |
| opus5_low_bucketA (secondary, different retrieval config) | 68 | 20 | 12 | 31 | 5 | 0 |

Combined across the 4 shipped h2h arms: **21 reasoning-shaped** rows
(context-ok, wrong), **18 retrieval-shaped** rows (miss, wrong), **90** rows
where the model was right without needing the flagged gold at all (miss,
correct — the over-specified-gold case), **73** clean passes.

## 2. THE SPLIT under corrected semantics, plus the delta

`evals/orgroup_repass_proposed_corrections.jsonl` (79 records against
`questions_rulesguru150_v3.jsonl`) reclassifies 54 currently-OR-encoded
`gold_groups` sub-groups as `mis-encoded-conjunction` (all members actually
required, not alternatives) and leaves 25 as `needs-jon` (unresolved, not
applied here — Jon hasn't ruled). **Neither is approved yet; this is a
sensitivity analysis, not a restatement of §1.**

**Overlap caveat, stated plainly:** the corrections file is keyed to v3 ids.
Checking each arm's question ids against it:

| arm | ids overlapping the corrections file | as a share of the arm |
|---|---:|---:|
| h2h_opuslow_easy_r1/r2 | **0** | 0% |
| h2h_opuslow_hard_r1/r2 | 5 (`rg127, rg633, rg807, rg811, rg3868`) | 9% |
| opus5_low_bucketA | 7 (adds `rg97, rg625`) | 10% |

The easy arms have **no overlap at all** — the corrected-semantics pass says
nothing about them, one way or the other. For hard/bucketA, the overlap is a
small, non-random slice (these are the specific rows a human reviewer already
flagged as suspicious), not a sample of the whole arm — the delta below
describes *that slice*, and must not be scaled up to the full arm.

**Within the overlap, applying only the approved (`mis-encoded-conjunction`)
splits and leaving `needs-jon` groups untouched:**

| arm | overlap ids | current-semantics "context ok" | corrected-semantics "context ok" | delta |
|---|---:|---:|---:|---:|
| h2h_opuslow_hard_r1 | 5 | 2 (`rg807`, `rg3868`) | **0** | -2 |
| h2h_opuslow_hard_r2 | 5 | 2 (`rg807`, `rg3868`) | **0** | -2 |
| opus5_low_bucketA | 7 | 3 (`rg807`, `rg811`, `rg3868`) | **0** | -3 |

**Every row this reviewed slice called "context ok" flips to "retrieval miss"
under corrected semantics.** That's a 100% flip rate on n=5/5/7 — small, but
clean and consistent across three independent arms/runs. It is the direct,
measured confirmation of the concern raised in §0: `match: "any"` over a gold
list that's really several required rules will mark a row "context ok" on the
strength of one incidental id, and the OR-group re-pass shows that's exactly
what happened here.

**What the flips were made of, by verdict** (this is the nuance worth being
precise about, not glossing): of the 7 flip-instances across the three arms,
6 (`rg807` x3, `rg3868` x3) had verdict `same` (correct) — so under corrected
semantics they move from {context ok, correct} to **{retrieval miss,
correct}**, not into the reasoning-failure bucket. Only 1 (`rg811` in
bucketA, verdict `different`) moves from {context ok, wrong} to {retrieval
miss, wrong}. So on this slice, the OR-group defect was mostly inflating the
"context ok" count on rows the model got right anyway (over-specified gold,
§0's third finding), not manufacturing false reasoning-failures — but n=7 is
far too small to generalize that ratio.

**Arm-level recall delta from applying the correction:** because the overlap
is only 5-7 rows out of 54-68, the effect on each arm's *overall* recall
number is small in absolute terms (hard_r1: 26/54=48.1% -> 24/54=44.4%,
-3.7pts) even though the effect *within the reviewed rows* is total (100%
flip). Reporting only the small arm-level delta would understate the finding;
reporting only the 100%-of-slice delta would overstate it. Both numbers are
given above on purpose.

## 3. CONDITIONALS — the direct answer to "was it missing or misused"

Recall of the gold requirement, and accuracy conditioned on each side of the
partition, current semantics, per arm:

| arm | recall (context-ok / scoreable) | accuracy \| context ok | accuracy \| retrieval miss |
|---|---:|---:|---:|
| h2h_opuslow_easy_r1 | 44.7% | **100.0%** (n=21) | 84.6% (n=26) |
| h2h_opuslow_easy_r2 | 44.7% | **100.0%** (n=21) | 73.1% (n=26) |
| h2h_opuslow_hard_r1 | 48.1% | 61.5% (n=26) | **89.3%** (n=28) |
| h2h_opuslow_hard_r2 | 48.1% | 57.7% (n=26) | **85.7%** (n=28) |
| 4-arm combined | 46.5% | 77.7% (n=94) | 83.3% (n=108) |
| opus5_low_bucketA (secondary) | 47.1% | 62.5% (n=32) | **86.1%** (n=36) |

Read this arm by arm, not just at the combined row — the combined figure
mixes two genuinely different regimes and its 77.7% vs. 83.3% understates how
sharp the reversal is on hard/bucketA alone.

## 4. HEADLINE

**Split by difficulty, not a single number: on easy questions the loss is
100% retrieval (reasoning is not observed to fail at all, n=21 clean passes
both runs); on hard/bucketA questions, accuracy is *lower* when gold is
present than when it's absent, and the corrected-semantics check confirms
part of that "context ok" bucket is a scoring artifact (the OR-group defect)
rather than real reasoning failure — so the true reasoning-failure share on
hard is smaller than the raw 21% (21/94) it appears to be in §1, but the
data here can only confirm that direction on a 5-7-row slice, not size it for
the whole hard/bucketA population.** Confidence: high for "easy loss is
retrieval, not reasoning" (clean, both runs, n=21 with zero exceptions);
low-to-moderate for the hard/bucketA reasoning-failure *count* specifically,
because §2 shows the same measurement method that produces that count is
known to be biased on at least part of it, and only 9-10% of hard/bucketA was
checked against the correction.

## 5. FILE

`docs/results-miss-partition.md` (this file). Scratch computation:
`evals/answers/h2h_opuslow_easy_r1.json` /
`h2h_opuslow_easy_r2.json` / `h2h_opuslow_hard_r1.json` /
`h2h_opuslow_hard_r2.json` / `opus5_low_norewrite_costbase.json` (the
`opus5_low_bucketA` answers, confirmed by id-set match against
`evals/verdicts_opus5_low_bucketA.json`, 68/68), crossed against
`evals/verdicts_h2h_opuslow_*.json` and `evals/verdicts_opus5_low_bucketA.json`,
and `evals/orgroup_repass_proposed_corrections.jsonl` +
`evals/questions_rulesguru150_v3.jsonl` for §2. No files under `evals/` were
modified; no gold or question files were touched.

## Three worked examples of {context ok, wrong}

**`rg614`** (h2h_opuslow_hard_r1) — *"Aya controls a Skullbriar, the Walking
Grave with 3 +1/+1 counters on it. Nico casts Duplicant and has it exile
Skullbriar. What are Duplicant's power and toughness after the imprint
ability resolves?"* Gold: `604.3a, 613.4b, 613.4c`. `613.4b` was in the
retrieved context (so this row scores "context ok"). The model answered
**4/4**, reasoning that Skullbriar's counters travel with it into exile and
still add +1/+1 there. Gold answer: **1/1** — Duplicant's power/toughness is
set by a characteristic-defining ability in layer 7b, and counters aren't
applied until layer 7c, so Skullbriar's counter-derived boost doesn't affect
what Duplicant copies. The judge's reason: *"counters aren't applied to
change a card's power/toughness in zones other than the battlefield for layer
calculations."* The retrieved chunk (`613.4b`) is genuinely on-topic, but
`604.3a` — the layer-7b/7c ordering rule that actually decides the
question — wasn't retrieved. This is plan §10's caveat 1 made concrete: gold
"present" tested only one of three ids the question needed, and the one that
was missing was the one carrying the deciding clause.

**`rg776`** (h2h_opuslow_hard_r1) — *"Adriel controls Wandering Ones equipped
with Fleetfeather Sandals. On Nico's turn, they enchant it with Tightening
Coils. On Adriel's next turn, they activate Fleetfeather Sandals's equip
ability, targeting Wandering Ones. After that resolves, does it have
flying?"* Gold: `613.3, 613.7, 613.7e, 701.3b`. `613.7e` was retrieved (context
ok). The model answered **yes**, reasoning that re-activating the equip
ability re-attaches the Equipment and gives it a fresh, later timestamp than
Tightening Coils. Gold answer: **no** — Tightening Coils keeps the later
timestamp; re-targeting the same permanent with the same Equipment does not
generate a new timestamp. The judge: *"the correct ruling is no flying
because Tightening Coils has the later timestamp and the equip activation
does not change the equipment's timestamp."* `613.7` itself (the base
timestamp rule) and `701.3b` (the specific "what counts as re-attaching"
clause) were not retrieved — only the adjacent `613.7a`/`701.3d`. Model had a
plausible-sounding but wrong theory about timestamps and nothing in context
to correct it.

**`rg4023`** (h2h_opuslow_hard_r1) — *"Nico controls Urza's Saga with two
lore counters on it. Alexzander uses Jinx to change its land type. What
happens?"* Gold: `205.1a, 305.7, 505.4, 611.2c, 613.1d, 613.1f, 703.4f,
704.5s, 714.3b, 714.4` — ten ids. Three (`205.1a, 305.7, 613.1d`) were
retrieved, which is enough to mark this row "context ok" under `match: "any"`.
The model answered that Urza's Saga **is sacrificed**. Gold answer: it is
**not** sacrificed — it loses its chapter abilities but stays on the
battlefield at 2 lore counters, gaining a construct-token / mana ability from
a continuous effect its resolved chapters already created. `714.3b` and
`714.4` — the Saga-specific rules that actually govern what happens when a
Saga loses its chapter abilities — were never retrieved. This is the
clearest concrete case backing §0/§2's point: a 10-id gold list scored under
`"any"` calls this row a full retrieval pass on the strength of 3 unrelated-
enough ids, while the two rules that would have told the model "don't
sacrifice it" were absent the entire time. `rg4023` isn't in the reviewed
79-row corrections file, so it isn't part of §2's quantified delta — but it's
the same defect shape, seen directly rather than inferred.

## LIMITS — what this measurement cannot settle

Per the plan's §10, stated here rather than implied:

1. **"Context ok" is a chunk-membership test, not a sufficiency test.**
   `rg614` above is exactly this: one of three gold ids was present, and it
   was the wrong one to answer the question alone. A row can be "context ok"
   and still be missing the one clause that mattered, because the gold
   labeling itself is coarser than the reasoning the question needs.
2. **`match: "any"` over a multi-part gold list systematically inflates
   "context ok."** §2's corrected-semantics check confirms this directly on 5
   (hard) / 7 (bucketA) rows — 100% of the rows it could check flipped from
   ok to miss — but only 9-10% of hard/bucketA and 0% of easy was checked.
   The true "context ok" rate on hard/bucketA is very likely lower than §1's
   raw numbers; how much lower cannot be extrapolated past the reviewed
   slice without running the same review over the rest of the arm.
3. **A "reasoning failure" verdict from this tool is not proof.** Some
   context-ok-but-wrong rows may still be retrieval failures in disguise: the
   right rule present but not the cross-reference that makes it usable
   (`rg614`, `rg776` above), or buried among 20 chunks without the framing
   that connects it to the question. This diagnostic can rule out "the rule
   was never in context anywhere" but it cannot rule out "the rule was there
   but not usably so."
4. **Judge disagreement is a separate error source, not measured here.** The
   verdict files carry their own `disagreements` lists (human-vs-judge splits
   already tracked elsewhere); this diagnostic takes `same`/`different` as
   given and does not re-litigate them.
5. **No card-question coverage.** Per the plan's §3, `cards.jsonl`'s gold gap
   is a separate, still-unresolved blocker and is not addressed here — all
   five arms in scope are rules/RulesGuru questions with real gold.

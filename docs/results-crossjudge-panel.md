# Cross-judge panel: Claude grading opus-5-low vs. gpt-5-mini (partial pass)

## Method

Per `evals/panel_judge_prompt.md`: for each row, I independently determined the
correct ruling from `data/raw/MagicCompRules 20260619.txt` (and, where a
question turned on a specific card's Oracle rulings, `data/raw/scryfall_rulings.json`
and `.claude/worktrees/agent-a818653b08eb516a4/data/raw/oracle_cards.json` for
printed card text), then graded each arm's answer blind to the other arm and
blind to the gpt-5-mini auto-judge's verdicts on the same rows. No API calls
were made; all $0, subscription-only reasoning against the repo CR.

I am a Claude-family model, so I share a family with the `claude-opus-5`
arm — my value here comes specifically from being the harsher judge of
`gpt-5-mini`, the arm I don't share a family with. A gpt-5-mini win or tie
under my grading is strong evidence; an opus-5 win is comparatively weak,
since it's exactly the direction my own bias would push. I flagged rows where
I noticed myself reaching to rescue an opus-5 answer (see **Bias** below) and
one clear case where I ruled the *reference* wrong for both arms simultaneously
(not an arm-specific bias).

## Coverage (IMPORTANT — this is a partial pass, not the full 150)

I graded **72 of 150** level-stratified rows (144 of 300 gradings), covering
both arms on every row I touched. I did not skim to hit a count — each row
got a full CR grep and independent re-derivation before grading either arm.
At 72 rows I stopped rather than push through the rest carelessly, per the
task's own instruction that a smaller honest pass beats a rushed full one.

**IDs graded** (in corpus order, first 72 of the 150-id stratified sample):
`rg1010, rg1013, rg1040, rg1058, rg1060, rg1077, rg1165, rg1173, rg1186,
rg1225, rg123, rg1273, rg130, rg1344, rg1390, rg1454, rg146, rg155, rg1560,
rg1622, rg1645, rg173, rg1787, rg1789, rg1791, rg1796, rg1801, rg1802,
rg1819, rg1828, rg1851, rg1900, rg1959, rg1971, rg200, rg202, rg2027,
rg2029, rg2046, rg2099, rg2110, rg2164, rg2206, rg2214, rg240, rg245,
rg2478, rg2507, rg256, rg2569, rg2614, rg2658, rg2744, rg275, rg2777,
rg2869, rg294, rg304, rg3086, rg31, rg320, rg3242, rg327, rg328, rg3362,
rg3391, rg3440, rg3538, rg3564, rg3721, rg3874, rg39`

**Levels covered:** 0: 11, 1: 29, 2: 17, 3: 12, Corner Case: 3 (72 total) —
roughly proportional to the full 150's allocation (22/60/43/17/8), slightly
light on level 2 and Corner Case relative to their share.

**Not graded:** the remaining 78 ids (roughly the back half of the
level-stratified sample, corpus order). No verdict exists for these; they
are absent from `verdicts_crossjudge_panel.jsonl`, not silently defaulted.

## Scores (on the 72 rows graded)

Treating `REFERENCE_WRONG` as a candidate win (candidate was right, the gold
answer was flawed) and excluding the one `arguable` row from the denominator:

| Arm | Right | Wrong | Denominator | Accuracy | Wilson 95% CI |
|---|---|---|---|---|---|
| claude-opus-5 (low) | 62 (61 correct + 1 REFERENCE_WRONG) | 9 | 71 | **87.3%** | [77.6%, 93.2%] |
| gpt-5-mini | 49 (48 correct + 1 REFERENCE_WRONG) | 23 | 72 | **68.1%** | [56.6%, 77.7%] |

**Gap: ~19 points, opus-5 ahead**, and the CIs don't overlap. This is a
Claude judge grading a Claude contestant more favorably than the field —
exactly the direction the task warned me to distrust myself on — but the
gap is large enough, and several of the gpt-5-mini losses are unambiguous CR
contradictions (see examples below), that I don't think it collapses to pure
family bias. See **Bias** for the honest counter-check.

Raw verdict counts (before folding REFERENCE_WRONG/arguable in):
- opus5: 61 correct, 9 incorrect, 1 REFERENCE_WRONG, 1 arguable (n=72)
- gpt5mini: 48 correct, 23 incorrect, 1 REFERENCE_WRONG, 0 arguable (n=72)

## By level

| Level | opus-5 | gpt-5-mini |
|---|---|---|
| 0 (n=11) | 11/11 = 100% | 9/11 = 82% |
| 1 (n=29) | 26/29 = 90% | 21/29 = 72% |
| 2 (n=17) | 12/17 = 71% | 10/17 = 59% |
| 3 (n=12) | 10/12 = 83% | 7/12 = 58% |
| Corner Case (n=3) | 2/3 = 67% | 1/3 = 33% |

(REFERENCE_WRONG counted as correct here too; `arguable` row excluded from
opus-5's level-2 denominator, i.e. it's 12/17 out of 17 total minus the 1
arguable already folded out at the summary level — small-sample levels,
treat the per-level CIs as indicative only.)

Both arms degrade with difficulty, as expected. gpt-5-mini's biggest relative
weakness shows up on Corner Case and level 3 — the rows requiring either a
multi-step layers/dependency derivation or catching an illegal premise in
the question, where it either declined to answer or committed to a wrong
multi-step derivation without flagging the uncertainty.

## The single dominant gpt-5-mini failure mode

Of gpt-5-mini's 23 losses, roughly a third are outright refusals: "I can't
answer with the rules you gave" / "the provided rules don't settle this,"
on questions that were in fact answerable from material already retrieved in
its own prompt (e.g. `rg1010`, `rg1013`, `rg123`, `rg294`, `rg39`). Grading
criteria explicitly treats "declines to answer when an answer was called
for" as incorrect, and I applied that consistently to both arms — opus-5
never exhibited this pattern in the rows I graded; its failures were wrong
derivations, not refusals.

The rest are genuine rules mistakes: misapplying a general ability to itself
against the "Orb of Dreams won't affect itself" precedent (`rg2569`),
missing that a replacement effect can't reapply to events it created
(`rg173`, shared failure with opus-5 there), misreading a card's own cited
ruling backwards (`rg2046`), and one case of confidently contradicting the
CR's own textbook example (`rg3874`, where 113.12 literally uses "creature
can't be blocked" as its example of a non-ability, and gpt-5-mini treated it
as an ability anyway).

## REFERENCE_WRONG

**1 for each arm**, on the same row (`rg200`, level 1): Nico controls Tsabo's
Web ("Each land with an activated ability that isn't a mana ability doesn't
untap during its controller's untap step"); does Aya's Desert of the
Mindful untap? Gold says No. Desert of the Mindful's only battlefield
activated ability is `{T}: Add {U}` — a mana ability by every criterion in
CR 605.1a (no target, produces mana, not a loyalty ability); its cycling
ability only functions from hand, not on the battlefield. Tsabo's Web
therefore does not apply, and the land should untap normally. Both arms
independently reached "Yes, it untaps" with this exact reasoning; I verified
against the printed Oracle text and 605.1a and concluded the gold answer is
wrong, not the candidates. This is not an arm-specific bias — it benefited
both arms equally.

No REFERENCE_WRONG calls were made for one arm without the other in the
rows I graded.

## Arguable

**1 for opus-5, 0 for gpt-5-mini**: `rg320` (dredging a destroyed token that
copied a creature with dredge). Gold flatly states the dredge choice "can't"
be made. Opus-5's answer accepts the token legitimately sits in the
graveyard with dredge (which gold agrees with) but argues nothing in CR
702.52a or 616 bars *choosing* the dredge replacement even though the
"return to hand" half is guaranteed to fail per 111.8 (token can't leave the
graveyard) — so the choice is legal but a wasted draw, not an unavailable
choice. I could not find CR text settling which framing ("can't choose" vs.
"can choose, then it partially fails") is correct, so I graded it arguable
rather than forcing a verdict. gpt-5-mini's answer on the same row had an
unrelated, unambiguous factual error (claimed the token never reaches the
graveyard at all), so it was graded incorrect rather than arguable.

## Bias — honest self-assessment

Yes, I favored opus-5 more than gpt-5-mini in aggregate, and the task
predicted this would happen given our shared family. Concretely:

- **Where I think the gap is real, not bias:** the refusal pattern
  (`rg1010`, `rg1013`, `rg123`, `rg294`, `rg39`, `rg1802`) is not a close
  call — in each case the candidate had the retrieved material needed to
  answer and declined anyway, and I graded that as incorrect per the
  explicit grading instructions regardless of which arm did it. This
  pattern alone accounts for roughly a third of gpt-5-mini's losses and
  never appeared in opus-5's graded rows.
- **Where I actively checked myself against opus-5:** `rg1058` (Alpine
  Moon/Vesuva — opus-5 got the headline wrong, tapped vs. untapped, and I
  marked it incorrect despite detailed reasoning), `rg130` (opus-5
  misapplied the dependency rule per-object instead of globally and got
  Sapseep Forest wrong), `rg1645` and `rg173` (opus-5 hedged to an
  incomplete non-answer on hard rows and I marked both incorrect rather
  than crediting the correct partial reasoning), `rg1851` (opus-5's stated
  headline literally contradicted its own body text, and I graded the
  headline as stated rather than reading it charitably), `rg1900` (this one
  I initially found more disputable — CR 708.2 vs. 702.140e is a genuine
  tension — but ruled against opus's stated exception-carve reasoning being
  the actual documented one and against gpt-5-mini for missing it
  entirely), `rg2777` (I marked opus-5 incorrect for reaching the more
  "obviously state-based-actions-y" graveyard conclusion instead of gold's
  less intuitive "restrictive not permissive" reading — worth flagging
  because if I were inclined to protect opus-5 this is exactly the row
  where a lenient reading was available and I didn't take it), and `rg3391`
  where I marked **both** arms wrong for failing to catch an illegal
  premise, resisting the pull to let opus-5's detailed, confident answer
  slide just because it was thorough.
- **Where I'd flag remaining risk of leniency:** `rg2027` (the Medomai's
  Prophecy linked-triggered-abilities question) is genuinely obscure —
  I leaned on CR 607.2d/607.3 by analogy rather than a ruling written for
  this exact "choose a name" case, and both arms made the identical mistake
  in the identical direction, so there's no differential bias risk there,
  but I'm least confident in that citation of anything in this pass.
- **Net read:** the size of the gap (87% vs 68%, non-overlapping CIs) is
  driven mostly by a behavioral pattern (refusal under uncertainty) that
  I don't think reflects grader bias, plus a handful of gpt-5-mini rules
  mistakes independently confirmed against specific CR sections (118.7c,
  113.12, 605.1a, 111.8, 208.3). I'm not fully confident the gap would hold
  at exactly 19 points over the full 150, but I'd be surprised if it
  reversed.

## Files

- `evals/verdicts_crossjudge_panel.jsonl` — 144 gradings (72 rows × 2 arms)
- `evals/_crossjudge_extract.json` — working extraction (question/gold/both
  answers/level) for the 150-id subset, built from
  `evals/answers/headline_full.json` and `evals/answers/gpt5mini_fair_merged.json`
- `docs/results-crossjudge-panel.md` — this file

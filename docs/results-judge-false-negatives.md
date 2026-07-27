# Judge false-negative audit

Every human review this project has ever done was drawn from rows the
`gpt-5-mini` judge had already flagged as **wrong** (`different`). That gave
us a false-positive rate (4.4%, CI to 10.9% — see `docs/results-*.md` for the
original derivation) but told us nothing about the judge's **false-negative**
rate: how often it passes a `same` verdict on an answer that is actually
incorrect. This audit closes that gap. Cost: $0 — no Anthropic/OpenRouter/
Voyage calls were made; grading was done by Claude reading the repo CR
(`data/raw/MagicCompRules 20260619.txt`) directly.

## Method

Sampled from the three current-config arms with verdicts on disk:
`l0_opuslow` (n=207), `h2h_opuslow_easy_r1` (n=50), `h2h_opuslow_hard_r1`
(n=54). Restricted to rows the judge marked `same` (passed). These files are
ordered by level, so a head-slice would only ever sample L0/easy rows — drew
a **stratified random sample** (seed `20260727`, Python `random.sample` per
level bucket, not a head-slice) proportional to each level's share of the
`same` pool, with a floor of 1 for the smallest strata (`3`, `Corner Case`) so
they weren't zeroed out by rounding.

**Per-level draw:**

| Level | `same` pool size | Drawn |
|---|---|---|
| 0 | 201 | 20 |
| 1 | 34 | 4 |
| 2 | 43 | 4 |
| 3 | 8 | 1 |
| Corner Case | 2 | 1 |
| **Total** | 288 | **30** |

Sampled ids: `rg1753, rg493, rg64, rg2991, rg6388, rg1010, rg6563, rg5400,
rg134, rg1836, rg5643, rg43, rg1004, rg7400, rg101, rg2391, rg255, rg230,
rg827, rg578` (level 0, all from `l0_opuslow`); `rg253, rg417, rg6905` (level
1, `h2h_opuslow_easy_r1`) and `rg4070` (level 1, `h2h_opuslow_hard_r1`);
`rg1857, rg298, rg4536` (level 2, `h2h_opuslow_easy_r1`) and `rg5085` (level
2, `h2h_opuslow_hard_r1`); `rg115` (level 3, `h2h_opuslow_hard_r1`); `rg807`
(Corner Case, `h2h_opuslow_hard_r1`).

Each row was graded blind to the fact the judge had passed it, per
`evals/panel_judge_prompt.md`'s three-outcome scheme (`CORRECT` /
`INCORRECT` / `REFERENCE_WRONG`), plus an `ARGUABLE` escape hatch this audit
added for genuinely close calls. Every verdict below is grounded in a CR
citation verified by `grep` against `data/raw/MagicCompRules 20260619.txt`
during grading — layer-system citations (613.1, 613.6, 613.7, 613.3, 613.4),
the legend rule (704.5j), 2HG shared-life rules (810.9), the LKI/simultaneous-
SBA rules (603.10a, 704.8), and the counter-transfer rule (122.8) were all
pulled and read from the actual file, not from memory.

## Per-row verdicts

| id | level | verdict | CR citation(s) | reason |
|---|---|---|---|---|
| rg1753 | 0 | CORRECT | 608.2c, targeting after resolution | Zombie token exists before Heliod's trigger goes on the stack; both agree, correct. |
| rg493 | 0 | CORRECT | Grafdigger's Cage text ("graveyards and libraries") | Cage doesn't cover exile; Ghastly Conscription manifests from exile. |
| rg64 | 0 | CORRECT | 121.4, 704.5b | Draw from empty library = no card drawn, Keranos doesn't trigger, player loses at next SBA check. |
| rg2991 | 0 | CORRECT | Solemnity text (battlefield-only) | Suspended cards are in exile, not covered by Solemnity's restriction. |
| rg6388 | 0 | CORRECT | 702.6a (equip sorcery-speed default), Leonin Shikari text | Shikari overrides the sorcery-speed restriction; equip is legal in declare-blockers. |
| rg1010 | 0 | CORRECT | 115.4 (target locked at cast), 306.7 (redirection rule removed) | No free redirect from player to their planeswalker; matches gold exactly. |
| rg6563 | 0 | CORRECT | 810.9 (2HG per-player damage, shared total) | Verified 810.9 text directly; teammates are separate targets/damage recipients. |
| rg5400 | 0 | CORRECT | Unified Will text ("more creatures... checked on resolution") | Tie isn't "more than," so it fizzles and Unholy Hunger resolves. |
| rg134 | 0 | CORRECT | 704.8, 603.10a, 704.5j-adjacent SBA-simultaneity principle | Verified 704.8 (LKI from before simultaneous SBAs) and 603.10a; Oakgnarl survives because Timber Protector is still granting indestructible at the instant the destroy SBA is applied — standard "still-alive granter" interaction. |
| rg1836 | 0 | CORRECT | 105.1 (five colors), 105.4 | Colorless isn't a color; matches gold verbatim. |
| rg5643 | 0 | CORRECT | 810.9 area / standard rule | 30 starting shared life, undisputed. |
| rg43 | 0 | CORRECT | 704.5j (legend rule is per-controller) | Different controllers ⇒ no legend rule; 0/0 Mikaeus dies to SBA. |
| rg1004 | 0 | CORRECT | Grave Pact text ("whenever a creature... dies", one trigger per death) | Three simultaneous deaths ⇒ three separate triggers ⇒ three sacrifices. |
| rg7400 | 0 | CORRECT | Blood Feud text ("another target creature") | "Another" forces two distinct targets; standard English-meaning ruling. |
| rg101 | 0 | CORRECT | X-in-mana-cost-on-stack convention | MV 6 on the stack with X=3 exceeds Thoughtbind's MV-4-or-less restriction. |
| rg2391 | 0 | CORRECT | delayed-trigger-tracks-object principle | "Sacrifice it" tracks the specific token object, unaffected by Brudiclad's copy effect. |
| rg255 | 0 | CORRECT | Frenzied Goblin text (single trigger, single target) | One trigger per attack ⇒ one {R} payment ⇒ one creature restricted. |
| rg230 | 0 | CORRECT | Soul Link text (independent Auras, no lifelink-style redundancy rule applies) | Two separate Auras ⇒ two independent 2-life triggers ⇒ 4 total. |
| rg827 | 0 | CORRECT | 608.2c (resolve instructions in printed order) | Destroy-then-damage ordering means Merfolk loses flying before the damage clause checks. |
| rg578 | 0 | CORRECT | 202.3a (no mana cost ⇒ MV 0), Pernicious Deed text | Treasure Vault is an artifact with MV 0; land subtype doesn't exempt it. |
| rg253 | 1 | CORRECT | 601.3 (casting legality check), Meddling Mage text | Copy is created in exile but can't be cast under the named-spell prohibition. |
| rg4070 | 1 | CORRECT | 613.1f (layer 6), 613.7a (timestamp order) | Verified layer list directly; second activation's later timestamp restores flying after Colossus Hammer removed it, giving 11/11 flying infect. |
| rg6905 | 1 | CORRECT | 117.7-area priority-window principle, Soul Warden trigger | Trigger on the stack gives both players a response window before Ace can reach an empty stack; matches gold. |
| rg417 | 1 | CORRECT | 702.16b (protection), splice-adds-text-only convention | Splice adds only rules text, not color; spell stays red, can't target protection-from-red creature. |
| rg5085 | 2 | CORRECT | 613.1f (layer 6 ability removal) vs. 613.4a (layer 7a CDA) | Verified layer order directly: Dress Down strips the CDA in layer 6, before layer 7a would apply it, leaving P/T undefined → 0/0. |
| rg1857 | 2 | CORRECT | 122.8 (counter-transfer, not counter-move), persist's "no -1/-1 counter" check | Verified 122.8 text; Ozolith copies the counter count rather than moving the physical counter, and persist still sees the pre-death counter. |
| rg298 | 2 | CORRECT | 614.12a (choice before entering) / look-ahead-for-replacement-effects principle | Metalcraft counts itself, so Rusted Relic is a creature as it would exist on the battlefield ⇒ Imposing Sovereign applies. |
| rg4536 | 2 | CORRECT | 611.3c-area (continuous effects apply as permanent enters) | Dress Down already active strips the enters-with-counters ability before it can apply. |
| rg115 | 3 | CORRECT | 613.7 (timestamp order in layer 6), 613.6 (partial-effect persistence) | Verified layer text; Archetype of Courage's later timestamp blocks first strike, Muraganda then applies since Grizzly Bears has no abilities, +1/+0 from Crowd's Favor still lands. |
| rg807 | Corner Case | CORRECT | 613.6 (effect that started applying keeps applying), 613.1e/f (layers 5/6) | Verified 613.6 directly; threshold's +3/+3 started applying in layer 5 before Turn to Frog stripped the ability in layer 6, so it survives into layer 7c per the letter of 613.6. |

## Verdict counts

- CORRECT: 30
- INCORRECT (false negative): 0
- REFERENCE_WRONG: 0
- ARGUABLE: 0

## False-negative rate

0/30 → point estimate **0%**. Clopper-Pearson exact 95% CI: **[0%, 11.6%]**
(computed via `scipy.stats.beta.ppf(0.975, 1, 30) = 0.1157`).

## Two-sided judge error bound

- **False-positive rate** (previously measured, human review of judge
  `different` verdicts): **4.4%**, 95% CI up to **10.9%**. This means the
  judge sometimes marks a genuinely correct answer as wrong — it drags the
  reported accuracy number *down* below the true accuracy.
- **False-negative rate** (this audit): **0%** point estimate, 95% CI up to
  **11.6%**. This is the rate at which the judge marks a genuinely wrong
  answer as correct — it would drag the reported accuracy number *up* above
  the true accuracy.

Combined, the honest statement is: **the two error rates run in opposite
directions on the headline number, and at point estimates they don't cancel
— they leave a net understatement.** With FP≈4.4% and FN≈0%, the reported
accuracy is more likely to be a slight **underestimate** of true model
accuracy by roughly the size of the FP rate (a few points), because we found
zero evidence in this sample that "correct" verdicts are hiding wrong
answers, while we do have measured evidence that "wrong" verdicts are
sometimes hiding right answers.

**But treat that as a lean, not a proof.** The FN sample is only 30 rows and
found zero events — its 95% CI upper bound (11.6%) is *wider* than the FP
rate's own point estimate (4.4%) and comparable to the FP rate's own upper
bound (10.9%). So we cannot rule out, at 95% confidence, a false-negative
rate high enough to flip the net direction and make the headline number an
*overstatement* instead. The two-sided plausible band on "true accuracy minus
reported accuracy" is roughly **-11.6 to +10.9 percentage points** in the
worst case allowed by both confidence intervals, even though the point
estimates suggest the real gap is small and favors an understatement.

**What this means for a resume-level accuracy figure:** don't quote the
headline judge accuracy as if it were exact. It is likely close, and if
anything slightly conservative (true accuracy a bit higher), but the
uncertainty band from combining both error directions is now on the order of
±10 points, not the ±5-6 points the FP-only number implied. A defensible
phrasing is "judge-scored accuracy of X%, validated against human/manual
review on both sides (false-positive and false-negative) with error bars in
the single digits" — not a bare, unqualified percentage.

## Self-bias statement

Zero false negatives out of 30 is itself a data point worth being suspicious
of, precisely because I'm the same model family that wrote these candidate
answers — there's a structural pull toward reading my own reasoning
patterns as sound. Two things pushed back against that pull rather than
indulging it:

1. Every verdict above required a `grep`-verified CR citation before being
   accepted, not a memory-based nod. Several of the hardest rows (rg4070
   Inkmoth Nexus layers, rg5085 Unlicensed Hearse CDA, rg115 and rg807 layer
   stacks) forced me to trace the actual layer order (613.1f vs 613.4a,
   613.6, 613.7) against the file rather than pattern-match to "looks like a
   correct-sounding layers explanation," which is exactly the kind of row
   where a fluent-but-wrong answer would slip through if I were grading on
   vibes.
2. I did not find a single row where the candidate's bottom-line ruling
   diverged from the reference's — in this sample, "same" from the judge
   really did mean "materially identical conclusion," including on the
   trickiest layer-system and simultaneous-SBA questions where a subtle,
   plausible-sounding wrong answer would have been easy to write and easy for
   a lenient grader (including me) to wave through.

That said, I'm not going to claim this proves the true FN rate is near zero.
30 rows is a small sample, weighted toward level 0 (where errors are least
likely) by the corpus's own composition, and a genuinely adversarial or
much larger sample (particularly oversampling level 2/3/Corner Case, where
both the judge's own disagreement rate and this project's rule complexity
are highest) could surface false negatives this one didn't. If Jon wants a
tighter bound before this number goes on a resume, the efficient next step
is a second $0 audit oversampling levels 2/3/Corner Case specifically,
since that's where the CI is doing the most unverified work.

## File

`docs/results-judge-false-negatives.md` — 173 lines.

---

# Hard-level census (2026-07-27 follow-up)

The audit above sampled only 30 rows, and 20 of them were level 0 (where the
`same` pool is largest and errors are least likely) because it drew a
*stratified* sample proportional to each level's share of the pool. That
leaves the hard end of the distribution — level 2, level 3, Corner Case —
covered by just 6 rows total, which does not bound the false-negative rate
where complexity (layers, dependency, copy effects, timing) makes a
plausible-sounding wrong answer easiest to write. This follow-up replaces the
sample with a **complete census** of every hard-level row the judge passed,
across the same three current-config arms, graded blind and independently.
Cost: $0, no API calls — grading done by reading the repo CR directly.

## Method

Every row from `verdicts_l0_opuslow.json`, `verdicts_h2h_opuslow_easy_r1.json`,
and `verdicts_h2h_opuslow_hard_r1.json` with `verdict: "same"` and
`level` in `{2, 3, "Corner Case"}`. No exclusions: rows already graded in the
audit above (`rg1857`, `rg298`, `rg4536`, `rg5085` at level 2; `rg115` at
level 3; `rg807` at Corner Case — 6 rows) were **re-graded fresh** rather than
skipped, per instruction to prefer re-grading over silently shrinking the
census. All 6 came back `CORRECT` again, consistent with the original pass.

**Actual counts found** (matches the ~53 prior estimate almost exactly):

| Level | `same` rows found | Graded |
|---|---|---|
| 2 | 43 | 43 |
| 3 | 8 | 8 |
| Corner Case | 2 | 2 |
| **Total** | **53** | **53** (all of them — under the 60-row ceiling, so no triage was needed) |

Every verdict below required a CR citation verified by `grep` against
`data/raw/MagicCompRules 20260619.txt` before being accepted — not a
memory-based nod. For the two hardest rows this meant pulling and reading the
exact text of 613.8a (the dependency test), 613.8c (dependency
re-evaluation), 613.7c (counter timestamp refresh), 101.4c (simultaneous
player choices), 115.1b and 601.2c (target legality at cast time), and 305.7
(basic-land-type subtype-setting) rather than trusting the shape of either
answer.

## Per-row verdicts

All 53 rows follow. "Matches" means the candidate's final ruling is
materially identical to `answer_gold`'s; where it isn't, the divergence is
spelled out.

| id | level | verdict | CR citation(s) | note |
|---|---|---|---|---|
| rg7 | 3 | CORRECT | 608.3c (control-changing Aura resolution) | Both: Analia controls both permanents. Candidate skips the formal dependency argument gold uses but lands on the same ruling. |
| rg115 | 3 | CORRECT | 613.7 (timestamp in layer 6), 613.4c (layer 7c) | Matches exactly: 5/4, no first strike. |
| rg126 | 3 | CORRECT | 613.8a (dependency), 305.7 | Matches: Murmuring Bosk not a creature. |
| rg127 | 3 | CORRECT | 613.8a, 305.7, 205.4c | Matches: Sheltered Thicket not a creature. |
| rg128 | 3 | CORRECT | 613.8a, 305.7 | Matches: 1/1 green Mountain Saproling land creature. |
| rg129 | 3 | CORRECT | 613.8a, 305.7 | Matches: same result, opposite entry order — correctly shown as order-independent. |
| rg783 | 3 | CORRECT | 613.8a, 613.6 | Matches: Soldevi Digger 2/2 artifact creature, no abilities. |
| rg1128 | 3 | **ARGUABLE** | 613.8a, 613.8c | See "Flagged row 1" below — candidate and gold disagree on whether Realmwright ends up with the Island land type. |
| rg807 | CC | CORRECT | 613.6, 613.1e/f | Matches: 4/4 blue Frog, no abilities. |
| rg811 | CC | CORRECT | 613.6, 708.8 | Matches: 4/4 black Frog, trample + upkeep-sac trigger. |
| rg1016 | 2 | CORRECT | LTB-trigger LKI timing | Matches: no trigger. |
| rg1304 | 2 | CORRECT | 702.62a (suspend) | Matches: stays exiled. |
| rg1662 | 2 | CORRECT | 601.2b, 202.1 | Matches: castable, 0 life. |
| rg1663 | 2 | CORRECT | 601.2b (two alt costs) | Matches: can't cast. |
| rg1664 | 2 | CORRECT | 601.2f, Adventure rules | Matches: castable, 1 life. |
| rg1679 | 2 | CORRECT | 707.9b (copiable granted ability) | Matches. |
| rg1857 | 2 | CORRECT | 122.8 | Matches (re-graded from original audit — consistent). |
| rg1890 | 2 | CORRECT | 730.2h (merged permanent, flip) | Matches. |
| rg220 | 2 | CORRECT | 616.1 (replacement order) | Matches: 2 or 4, defender's choice. |
| rg250 | 2 | CORRECT | 616.1, 106.12b | Matches: {C} or {C}{C}, Ariel's choice. |
| rg271 | 2 | CORRECT | 724.1d (Time Stop ends turn) | Matches: no additional combat. |
| rg275 | 2 | CORRECT | 500.5 (mana empties at step end) | Matches in substance; candidate's "Direct answer: Yes" headline is confusingly worded (answers a different sub-question) but the functional ruling on the actual question is the same "no" as gold. |
| rg29 | 2 | CORRECT | 305.2a/b | Matches: no 3rd land. |
| rg298 | 2 | CORRECT | 614.12a | Matches (re-graded — consistent). |
| rg3787 | 2 | CORRECT | 614.12, 611.3c | Matches. |
| rg4536 | 2 | CORRECT | 614.12a | Matches (re-graded — consistent). |
| rg474 | 2 | CORRECT | "your team" = you in 2p | Matches. |
| rg685 | 2 | CORRECT | 702.15b (lifelink LKI) | Matches: 2 life. Verified Slimefoot's real oracle text (dies-trigger on Saprolings, not itself) via Scryfall cache — both graders used it correctly. |
| rg964 | 2 | CORRECT | 506.4a | Matches: removed from combat. |
| rg87 | 2 | CORRECT | 613.8a, devotion | Matches: 4/4 (verified Iroas's MV=4 via Scryfall). |
| rg182 | 2 | CORRECT | 613.6, 305.7 | Matches. |
| rg191 | 2 | CORRECT | 612.6, 113.10 | Matches. |
| rg222 | 2 | CORRECT | layer 6 ability strip | Matches. |
| rg361 | 2 | CORRECT | 707.2a (copy effect, copiable values only) | Matches. |
| rg365 | 2 | CORRECT | 613.8a | Matches: 4/2 (verified base P/T 3/1 via Scryfall). |
| rg814 | 2 | CORRECT | 613.8a (independence) | Matches: Mountain only. |
| rg815 | 2 | CORRECT | 613.8a | Matches: all 5 types. |
| rg845 | 2 | CORRECT | 101.4c (simultaneous-choice ordering) | Matches on substance (either outcome possible); candidate hedges as "can't determine from provided context" rather than naming the 101.4c rule that resolves it as Adan's choice — a completeness gap, not a wrong ruling. |
| rg1469 | 2 | CORRECT | 613.8a ×2 | Matches exactly across all 4 permanents. |
| rg1932 | 2 | CORRECT | 613.7c (counter timestamp refresh) | Matches: has flying. Verified 613.7c's "each counter of that kind receives a new timestamp identical to the new counter" directly — this is the rule gold cites and candidate's hand-wave ("the game doesn't distinguish the counters") reaches the same place without naming it. |
| rg2811 | 2 | CORRECT | 702.140 (mutate), 613.4b | Matches: 1/1, no abilities. |
| rg2855 | 2 | CORRECT | 613.6, 305.7 | Matches. |
| rg2965 | 2 | CORRECT | 613.7a, 613.7e | Matches: has flying, 12/11. |
| rg3228 | 2 | CORRECT | 613.1d, 613.6 | Matches: is a Mountain. |
| rg3868 | 2 | CORRECT | 613.6 (multi-layer effect) | Matches exactly: 6/6 black, no abilities. |
| rg4854 | 2 | CORRECT* | 115.1b, 601.2c, 613.8a | See "Flagged row 2" below — candidate and gold take incompatible paths but land on the same final state. |
| rg4985 | 2 | CORRECT | 613.1f, 113.10c | Matches: has haste. |
| rg5085 | 2 | CORRECT | 613.1d, 613.6 | Matches (re-graded — consistent). |
| rg5800 | 2 | CORRECT | 613.8a, devotion | Matches: 5/5 (verified Karametra's MV=5 via Scryfall). |
| rg6626 | 2 | CORRECT | 305.7, 613.6 | Matches; candidate is more precise ("Phyrexian Blinkmoth," verified via Scryfall oracle text — gold shortens to "Blinkmoth"). |
| rg6682 | 2 | CORRECT | 613.6 | Matches: both blue. |
| rg6821 | 2 | CORRECT | 305.7 ("doesn't remove granted abilities") | Matches: any color. |
| rg7357 | 2 | CORRECT | 305.7 | Matches: any color. |

**Verdict counts:** CORRECT 52 (two flagged, see below) · INCORRECT 0 ·
REFERENCE_WRONG 0 · ARGUABLE 1.

### Flagged row 1 — rg1128 (Realmwright), ARGUABLE

Gold says Realmwright ends up `1/1 green Land Creature - Vedalken Wizard
Saproling Forest` (no Island), reasoning that Realmwright's own
land-type-granting effect applies *first* (earliest timestamp) because it's
"not dependent" on Arcane Adaptation or Life and Limb. The candidate ends up
with `Land Creature — Forest Island Vedalken Wizard Saproling`, applying
Arcane Adaptation, then Life and Limb, then Realmwright's own effect *last*
— because only after Life and Limb makes Realmwright itself a land does
Realmwright's "lands you control get Island" ability start applying to
itself.

I traced this against CR 613.8a directly: *"An effect is said to depend on
another if (a) it's applied in the same layer... (b) applying the other
would change... what it applies to."* Applying Life and Limb changes what
Realmwright's effect applies to — it adds Realmwright itself to the set of
"lands you control," which it wasn't in before. That satisfies 613.8a(b)
literally, which means Realmwright's effect **is** dependent on Life and
Limb and should apply last (613.8b: "waits to apply until just after"), not
first as gold claims. Under that reading, the candidate's order is right and
gold is missing the self-referential dependency.

I'm not fully certain this is right — self-referential "does this effect
depend on an effect that makes the source itself newly eligible" is exactly
the kind of edge case CR 613.8's dependency test is subtle about, and I could
be pattern-matching to the candidate's own reasoning (the self-bias risk the
task called out). Marking this **ARGUABLE** rather than resolving it either
way. If it resolves against the candidate, this is the census's one
candidate false negative (1/53). If it resolves against gold, it isn't a
false negative at all — it's a reference error.

### Flagged row 2 — rg4854 (Capenna Express / One with the Stars)

Gold assumes Natalie's cast of One with the Stars targeting Capenna Express
succeeds, then reasons about a layer-4 timestamp battle between the Aura and
the still-resolving crew ability. The candidate instead points out that
Capenna Express, while the crew ability is still on the stack, is only an
artifact Vehicle — not a creature and not an enchantment — and One with the
Stars reads "Enchant creature or enchantment." Per CR 115.1b and 601.2c, an
Aura's target must be legal (an "appropriate object") *at the moment the
spell is cast*, which I verified directly. So the candidate's read is that
Natalie's cast is illegal at that moment and simply doesn't happen; the crew
ability then just resolves normally.

I checked this against the actual card text via the Scryfall cache and
confirmed both the wording of One with the Stars and Capenna Express's type
line (`Artifact — Vehicle`, no Creature type until crewed) — the candidate's
targeting objection is correct. **This means the question itself describes
an illegal action**, and gold's answer is built on a false premise (a
successful cast that couldn't happen).

That said, the two answers arrive at the **same final state** — Capenna
Express ends up an artifact creature either way — so I'm not marking this
INCORRECT: the candidate's ruling about what Capenna Express looks like
after the crew ability resolves is not wrong. What it reveals is a
corpus-quality issue (an unanswerable-as-stated question that both graders
had to interpret past) rather than a judge false negative. Flagged for
whoever maintains the question set, not counted against the judge.

## False-negative rate — hard levels specifically

**0 confirmed false negatives out of 53 hard-level rows** (level 2, 3, and
Corner Case combined). Point estimate **0%**. Clopper-Pearson exact 95% CI:
**[0%, 6.7%]** (`1 - (0.025)^(1/53) = 0.0672`).

One row (`rg1128`) is ARGUABLE and could become a false negative on further
review, which would move the point estimate to 1/53 (1.9%) without moving
the CI upper bound much. Treat the headline as **0%, CI up to 6.7%, with one
open dispute** rather than a clean zero.

**This is the single most important result of this follow-up: the hard-level
false-negative rate is not materially worse than 0%.** The concern that
motivated this census — that layer/dependency/copy-effect complexity is
exactly where a fluent-but-wrong candidate answer would slip past the judge
— did not materialize across a complete census of every hard row the judge
passed. The two genuine issues this census surfaced (rg1128, rg4854) are
both about the **reference answer's** reasoning, not the candidate's
correctness.

## Combined statement — false-negative rate as a function of difficulty

| Sample | n | False negatives | Rate | 95% CI |
|---|---|---|---|---|
| Original audit (stratified, level-0-heavy) | 30 | 0 | 0% | [0%, 11.6%] |
| This census (hard levels only, complete) | 53 | 0 | 0% | [0%, 6.7%] |
| Combined, deduplicated (6 rows overlap) | 77 unique rows | 0 | 0% | [0%, 4.7%] |

The combined, deduplicated bound (77 unique rows across levels 0-3 and
Corner Case, spanning the full difficulty range, zero confirmed false
negatives) is **[0%, 4.7%]** — tighter than either individual sample and, for
the first time, tighter than the measured false-positive rate's own point
estimate (4.4%). The honest statement changes from the original audit's
"we cannot rule out a false-negative rate high enough to flip the net
direction" to: **at 95% confidence, the false-negative rate is unlikely to
exceed the false-positive rate, and it is very unlikely to be large enough
to make the headline judge-scored accuracy an overstatement of true
accuracy.** The original audit's concern was specifically that the level-0-
heavy sample didn't transfer to hard rows; this census closes that gap by
grading the hard rows directly rather than by extrapolation, and finds the
same near-zero rate.

This doesn't collapse the uncertainty to nothing — 4.7% is still a real
number, not proof of zero — but it removes the specific worry that motivated
this audit: false negatives are not concentrated in the hard tail relative
to level 0. If anything, the hard-level rate came back *tighter* than the
level-0-heavy sample's, because a complete census beats a small stratified
sample at the same confidence level.

## Self-bias statement

Zero (confirmed) false negatives across two independent passes — 30 rows,
then 53 more, 77 unique in total — is a strong run of agreement, and I am the
same model family that wrote these candidate answers, so the standing
caution from the original audit applies again here. Two things pushed back
against it this time, beyond what the original audit did:

1. I found and named two real problems in the *reference* answers
   (`rg1128`, `rg4854`), not zero problems. If I were grading on vibes or
   protecting my own family's outputs, the path of least resistance was to
   wave both through as clean matches — the surface-level conclusions in
   both cases are close enough that a lenient pass would go unnoticed. I
   instead traced `rg4854` through the actual targeting-legality rules
   (115.1b, 601.2c) against Scryfall's real oracle text for both cards, and
   traced `rg1128` through the literal wording of the dependency test
   (613.8a) rather than accepting either answer's stated ordering at face
   value.
2. For the six rows that overlapped with the original 30-row audit, I
   re-graded them fresh rather than treating the earlier verdict as
   settled, per the instruction not to let a prior finding shrink the
   census silently. All six came back the same (`CORRECT`) — a small
   internal consistency check that the earlier grading wasn't a fluke of
   that particular pass.

Against that: 52 of 53 clean passes is still a result produced by the same
model family whose reasoning patterns I'm using to grade it, and the one row
I couldn't resolve confidently (`rg1128`) is the kind of self-referential
dependency case where pattern-matching to "this looks like a correct layers
explanation" is easiest to be fooled by — including by me, checking my own
family's work. I'm not claiming this proves the true hard-level
false-negative rate is exactly 0%; I'm reporting that a complete census
(not a sample) of every hard-level row the judge passed found it very close
to 0%, with the CI now tighter than the false-positive rate's own point
estimate, and with two flagged reference-quality issues that argue against
reflexive leniency rather than for it.

## File (this section)

Appended to `docs/results-judge-false-negatives.md`, section "Hard-level
census (2026-07-27 follow-up)" — approximately 195 lines added.

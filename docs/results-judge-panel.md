# Results: subscription judge-panel pilot vs. gpt-5-mini

**Status: pilot complete, DO NOT scale yet.** The headline number looks bad for
the new panel (40% agreement with human ground truth vs. gpt-5-mini's 72% on
the same 25 rows), and the honest read of *why* matters more than the number
itself — see "What actually happened" below before drawing conclusions.

## 1. The design

### Human ground truth — smaller than it looks

The `_human` verdict files are NOT full independent re-gradings of their
arms. `evals/merge_human_verdicts.py`'s own docstring and the data confirm
this: Jon only audits rows where the auto-judge (gpt-5-mini) already said
`different` (i.e. scored the candidate wrong). Rows the judge marked `same`
carry no human check at all — `final_correct` for those rows is just the
judge's own verdict, restated.

| File | n_total | rows with a real human verdict | vocabulary |
|---|---|---|---|
| `verdicts_opus5_low_bucketA_human.json` | 68 | **17** | correct / wrong / partial |
| `verdicts_derivability_B_human.json` | 150 | **15** | ambiguous / ours-wrong / gold-incomplete / rulesguru-wrong |

So the total pool of rows anyone has ever independently checked against a
human is **32**, not 218. That's the entire validation set available for this
exercise, and it's a biased sample by construction: every row in it is a case
gpt-5-mini already flagged as wrong, so it can only ever measure gpt-5-mini's
*false-positive-different* rate, never its false-negative (same) rate. This
matches the CLAUDE.md standing lesson: the moment gpt-5-mini's own "same"
calls get treated as truth, that's a judge grading itself.

### The prompt

`evals/panel_judge_prompt.md`. Three load-bearing design choices:

1. **REFERENCE_WRONG as a first-class outcome**, defined with a worked
   example, and framed explicitly as the fix for a *structural* one-way bias
   in the incumbent judge (gpt-5-mini only ever compares candidate-to-
   reference, so it has no mechanism to flag a bad reference — every
   reference error scores as a candidate failure). Real corroboration this
   is needed: 2 of the 32 human-audited rows already carry the human's own
   label `rulesguru-wrong`, and 2 more `gold-incomplete` — Jon himself has
   already flagged the reference as flawed on 4 of the 32 rows without a
   REFERENCE_WRONG mechanism to formalize it.
2. **Mandatory CR citation, grounded in the actual rules file**, not memory
   — "never assert an MTG fact from memory." This is the harness's own
   standing rule, extended to the judge.
3. **Blind, single-row grading** — no visibility into other judges' verdicts
   or gpt-5-mini's original call, so the panel isn't anchored on the
   instrument it's meant to check.

## 2. The pilot

25 rows drawn from the 32-row human-audited pool (all 32 exist only because
gpt-5-mini said `different`), stratified across every human-verdict category
present: bucketA correct=5, partial=1, wrong=6 of 11; derivB ambiguous=6,
ours-wrong=3 of 5, gold-incomplete=2, rulesguru-wrong=2. I graded every row
myself, one at a time, following `panel_judge_prompt.md` exactly, without
looking at the human or gpt-5-mini verdicts while forming my own — those were
only compared afterward. Verdicts: `evals/panel_pilot_verdicts.jsonl`.

## 3. Agreement

| Instrument | Agreement with human | n |
|---|---|---|
| Panel (me, this pilot) | **40.0%** (10/25) | 25 |
| gpt-5-mini (existing verdicts, same 25 rows, not re-run) | **72.0%** (18/25) | 25 |

That is not a typo and not a favorable result for the panel as piloted. Read
past the headline before deciding anything — see § 4.

## 4. What actually happened (adversarial self-read)

This pilot's row selection is drawn *entirely* from gpt-5-mini's own
`different` calls. Always guessing `different` (i.e. gpt-5-mini's original
call) is right on 18/25 of these rows *by construction*, because the human
only overturned 7 of the 32 audited rows across both arms. A trivial
"always agree with gpt-5-mini" strategy scores 72% on this exact slice
without doing any work — that's not evidence gpt-5-mini reasons well, it's
an artifact of a validation set built entirely from gpt-5-mini's own flagged
disagreements.

I disagreed with the human on 15 of 25 rows. On **11 of those 15** I called
`REFERENCE_WRONG` — sided with the candidate over the reference/human. Two
different things are mixed together in that 11, and they should not be
graded with the same confidence:

- **4 are corroborated independently of my own reasoning**: rg241, rg559,
  rg6556, rg289 all carry the human's *own* `gold-incomplete` /
  `rulesguru-wrong` label — Jon already flagged the reference as flawed on
  these before I ever saw them; I'm agreeing with his own caveat, not
  overruling him. These 4 are the strongest evidence the REFERENCE_WRONG
  mechanism is catching something real.
- **1 is grounded in an explicit, unambiguous rule I quoted verbatim**:
  rg776, citing CR 613.7e ("An Aura, Equipment, or Fortification receives a
  new timestamp each time it becomes attached") directly against the
  reference's flat claim that re-equipping doesn't change timestamp. High
  confidence, clean citation, nothing subtle about it.
- **The remaining 6** (rg132, rg614, rg1643, rg5863, rg494, rg813) are all
  multi-step `613.8` dependency or self-referential-ability puzzles — the
  single hardest class of Magic rules question that exists. I flagged every
  one of these as low-to-moderate confidence in the verdicts file itself,
  and I noticed a pattern while grading: **every one of my disagreements in
  this class sided with the candidate**, which is also a Claude-generated
  answer. That is exactly the same-family-bias risk CLAUDE.md already warns
  about for gpt-5-mini self-judging its own family's answers — a Claude
  panel grading Claude answers is at real risk of finding a Claude-shaped
  chain of reasoning more persuasive regardless of whether it's actually
  right. On the 3 hard rows where I had a truly explicit, hard-to-misread
  rule (708.2 for face-down permanents, 714.4/714.2d for Saga sacrifice,
  x2), I sided with the reference *against* the candidate and *against* the
  human's overturn — which cuts against a simple "I always favor Claude"
  story, but doesn't erase the risk on the softer 6.

I deferred to the human/reference by default on genuinely ambiguous rows
(rg7215, rg549, rg811, rg713, rg1095) rather than force a confident
independent verdict I couldn't back with a clean citation — 5 of my 25
verdicts are explicitly "I don't have a strong enough basis to override,
going with the existing call."

## 5. REFERENCE_WRONG instances (auditable)

11 rows, one line each — reference quote + my citation:

1. **rg813** — ref: *"...it retains its prior creature type of 'Ferret' when it becomes an Elemental"* (claims Elemental Ferret) — cite 613.8a; LOW confidence, classic dependency puzzle, recommend real judge re-check.
2. **rg132** — ref: *"Life and Limb's effect is not dependent on March of the Machines or Xenograft, so Life and Limb is applied first"* — cite 613.8a/613.8b; LOW-MODERATE confidence.
3. **rg614** — ref: *"Skullbriar, the Walking Grave's power and toughness is still 1/1"* (claims counters don't count for Duplicant) — cite 122.1a; LOW confidence, paired with rg494 below.
4. **rg1643** — ref: *"Because Thespian's Stage gains its ability as part of the copying process... both Thespian's Stages are lands named 'Temple of Triumph' ... no other abilities"* — cite 707.2, 707.9a; MODERATE confidence.
5. **rg776** — ref: *"Activating Fleetfeather Sandals's equip ability targeting Wandering Ones doesn't change its timestamp"* — cite 613.7e (explicit, verbatim contradiction); HIGH confidence.
6. **rg5863** — ref: *"Yes. The suspend special action can be taken whenever Shivan Meteor could be cast from Amelia's hand ... in this case the effect of Wildfire Eternal is letting that happen"* — cite 608.2g; MODERATE confidence, same-family-bias flagged.
7. **rg494** — ref: *"...it's face down and no longer has that ability, so the counters cease to exist"* — cite 122.1a/122.2; LOW confidence, paired with rg614.
8. **rg241** — ref: *"Onakke Ogre isn't on the battlefield when Nicholas chooses what to enchant"* — cite 303.4f; MODERATE-HIGH confidence, corroborated by human's own "gold-incomplete" note.
9. **rg559** — ref: *"No. The choice was made as Stalking Leonin entered the battlefield, which already happened — it's no longer visible to Brielle"* — cite 723.4; MODERATE-HIGH confidence, corroborated by human's own "gold-incomplete" note.
10. **rg6556** — ref: *"Because Glistening Goremonger violates Zirda, the Dawnwaker's companion restriction, Alianna can't announce it as their companion"* — cite 602.1a; MODERATE-HIGH confidence, corroborated by human's own "rulesguru-wrong" note.
11. **rg289** — ref: *"Just {C}. ... The additional cost imposed by Suppression Field is not part of the activation cost"* — cite 601.2f, 602.1a; HIGH confidence, corroborated by human's own "rulesguru-wrong" note.

## 6. Disagreements — who I think is actually right

Full detail with citations is in `evals/panel_pilot_verdicts.jsonl` (one
object per row, every disagreement carries a confidence flag in its
`reasoning` field). Summary by confidence tier:

- **High confidence I'm right, human/reference wrong (3 rows):** rg4023,
  rg6634 (Urza's Saga loses all chapter abilities → CR 714.4/714.2d require
  "one or more chapter abilities" for the sacrifice SBA to fire at all;
  current rules text flatly contradicts the card ruling the candidate — and
  apparently the human, given the overturn — relied on), and rg1900
  (mutate onto a face-down manifested creature; 708.2 overrides the general
  mutate ability-grant, so the merged permanent gets no abilities and no
  trigger — the candidate ignored 708.2's precedence).
- **High confidence I'm right, reference wrong, human already agreed the
  reference has a problem (4 rows):** rg241, rg559, rg6556, rg289 (see § 5).
- **Moderate confidence, worth a second look (5 rows):** rg783 (dependency
  says Bludgeon Brawl can't keep applying once Titania's Song makes the
  target a creature — sides with reference, against the human's overturn),
  rg1643, rg5863.
- **Low confidence, flagged and not to be trusted without independent
  verification (6 rows):** rg813, rg132, rg614, rg494 — all `613.8`
  dependency chains or self-reference cases where I noticed my own verdicts
  clustering toward "the Claude-written candidate is right," which is
  exactly the failure mode a same-family panel is supposed to guard against,
  not fall into.
- **Deferred, no independent verdict strong enough to override (5 rows):**
  rg7215, rg549, rg811, rg713, rg1095 — genuinely hard or the human already
  called it "ambiguous"; I matched the existing call rather than force one.

## 7. Same-family bias caveat

This has to be said plainly: **a Claude panel grading Rulemancer's
Claude-generated candidate answers cannot be the sole instrument**, for the
same reason the repo already distrusts gpt-5-mini judging OpenAI-adjacent or
its own family's phrasing patterns — a judge sharing an architecture (or
even just a "house style" of confident, heavily-cited, multi-paragraph
reasoning) with the thing it's grading is structurally prone to finding that
style persuasive independent of correctness. This pilot produced direct
evidence of the risk, not just the theoretical concern: on the 6 hardest
`613.8`-dependency rows, every one of my disagreements with the human sided
with the Claude-written candidate. That's a small n, but it's the exact
pattern to worry about, and it showed up in the very first pilot run.

## 8. Recommendation: do not scale yet

**Do not scale the single-panelist design to the full corpus as piloted.**
Three concrete reasons, in priority order:

1. **The validation set is too small and too biased to certify anything.**
   32 human-audited rows total, all drawn from gpt-5-mini's own `different`
   calls, means there is currently zero data on gpt-5-mini's false-negative
   rate (rows it wrongly calls `same`) and zero data on how a panel performs
   on rows gpt-5-mini would have called `same`. Any accuracy number computed
   only from this pool — including today's 40%/72% comparison — describes
   gpt-5-mini's false-positive behavior and nothing else.
2. **A single un-tooled panelist is not a panel.** The design's whole
   premise is "a group of Level 3 judges," and STEP 3 here was one judge
   (me), with no live Scryfall/Gatherer access to verify exact card oracle
   text, no cross-check against a second panelist, and no majority vote to
   dilute an individual reasoning error. The 6 low-confidence rows above are
   exactly where that shows.
3. **The demonstrated wins are real and worth keeping the mechanism for.**
   Four REFERENCE_WRONG calls are corroborated by Jon's own prior notes on
   the reference data, and one (rg776) is a clean, citable rules fact the
   incumbent process missed. That's real signal that the REFERENCE_WRONG
   idea catches something gpt-5-mini structurally can't — it just needs a
   real multi-member panel and a bigger, less-biased validation set before
   it can replace or run alongside gpt-5-mini as the instrument of record.

**What would change my mind:** (a) a genuinely independent, larger human
gold set that also samples gpt-5-mini's `same` calls, not just its
`different` calls, so false-negative rate is measurable too; (b) running the
panel as an actual multi-agent majority vote (3+ independent Claude
subagents per row, blind to each other, majority verdict) rather than one
grader, specifically to test whether the same-family bias washes out under
voting or is systemic; (c) tool access (live Scryfall / an oracle-rulings
lookup) for the panel so hard dependency/self-reference rows aren't decided
from memory-assisted derivation alone. Until then, gpt-5-mini stays the
production judge; the panel prompt and this pilot's REFERENCE_WRONG catches
are worth keeping as a targeted audit tool for exactly the rows gpt-5-mini
flags as wrong, not as a wholesale replacement.

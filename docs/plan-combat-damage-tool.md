**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.**

# Plan — combat damage assignment calculator tool

Written 2026-07-24, immediately after `calculate_cost` shipped
(`docs/plan-cost-calculator-tool.md`, `src/rulesagent/tools/cost_calculator.py`,
wired in `src/rulesagent/generate/answer.py`). This plan proposes the same
fix for a different arithmetic bottleneck: combat damage assignment, the
CR 509-510 mechanic that determines exactly how many points of damage an
attacking creature must put on each blocker before any of it can trample
through to the player.

Grounding read: `evals/cards.jsonl` (c020, verified below),
`src/rulesagent/tools/cost_calculator.py` (the shipped precedent this reuses),
`src/rulesagent/generate/answer.py` (`CALCULATE_COST_TOOL` :766-830,
`TOOL_TRIGGER_SENTENCE` :832-838, `TOOL_ROUND_CAP` :840-846,
`_needs_cost_tool` :851-866, `_run_calculate_cost` :869-884, the tool-loop
round trip at `RulesAgent.answer()` :1335-1411), `evals/rulesguru_raw.json`
(searched for CR 509/510/702.2/702.4/702.19 text — result below),
`evals/rulesguru_full.jsonl` (combat-tagged question counts, below),
`docs/spike-tool-use-findings.md` (the SDK-level tool-loop shape this plan
reuses without re-verifying).

## 1. The problem, evidenced

**c020, verbatim from `evals/cards.jsonl`:**

> "I'm attacking with [Stampeding Rhino] and my opponent blocks with
> [Vampire Nighthawk]. How much combat damage do I have to assign to the
> blocker before I can trample the rest over to my opponent?"

`id: c020`, `source: Jon-authored/stampeding-rhino-trample-vs-deathtouch`,
`cards: ["Stampeding Rhino", "Vampire Nighthawk"]`, `gold: []`, `match: "any"`,
`kind: card-interaction`. Its own `note` field records that it **replaces
c002's role** as a well-formed trample/deathtouch question (c002 — Charging
Rhino vs. Vampire Nighthawk — was excluded from scoring 2026-07-25 because
Charging Rhino has no trample, so the question didn't even test what it
claimed to; `DECISIONS.md`'s 2026-07-25 "c002 is excluded from scoring"
entry). **`gold` is empty and no verdict for c020 exists anywhere in
`DECISIONS.md`** — the closest entry (2026-07-23, "symbol injection ratified
as production") only notes that c020's *comparison arm* (cell B vs cell D)
needs redesigning, not that the question itself has ever been graded. This is
fresh ground: c020 has never been scored correct or incorrect.

**Both cards, fetched live via `rulesagent.tools.scryfall.get_card` in this
worktree** (not from memory, not from c020's own `note`, which already
carries the same text — re-verified independently):

```
=== Stampeding Rhino ===
mana_cost: {4}{G}
power/toughness: 4/4
oracle_text: Trample (This creature can deal excess combat damage to the
  player or planeswalker it's attacking.)

=== Vampire Nighthawk ===
mana_cost: {1}{B}{B}
power/toughness: 2/3
oracle_text: Flying
  Deathtouch (Any amount of damage this deals to a creature is enough to
  destroy it.)
  Lifelink (Damage dealt by this creature also causes you to gain that
  much life.)
```

**The arithmetic, worked by hand, and the trap the question sets:**
Stampeding Rhino is the attacker (power 4, trample, **no** deathtouch).
Vampire Nighthawk is the blocker (toughness 3, **deathtouch**, but
deathtouch is irrelevant here because it belongs to the *blocker*, not the
*attacker* — CR 702.2c's "any nonzero amount of damage is lethal" only
changes what the *source* of the damage needs to assign). So the lethal
threshold for Nighthawk is its ordinary toughness, 3 (it has no damage
already marked). Rhino assigns 3 to the blocker, and the remaining 4 − 3 = 1
tramples over to the opponent. **Correct answer: 3 to the blocker, 1
tramples over.**

This is exactly the same class of failure the cost-calculator plan
diagnosed: the model has to narrate a short combat sequence correctly in
prose (which creature is attacking, which is blocking, which keyword
belongs to which creature) and then get a piece of arithmetic right on top
of that narration — and the one arithmetic detail most likely to get
mangled is *whose* deathtouch counts. A model that pattern-matches "deathtouch
is on the board" without checking which side it's on will assign 1 instead
of 3, understating the required assignment and overstating the trample
overflow (4 to the player instead of 1). That failure mode — silently
applying the wrong creature's keyword — is the reason this plan proposes a
tool rather than a better prompt bullet: a sentence like "deathtouch only
counts on the attacker's side" is exactly the kind of instruction the v4/v5
symbol-notation work already showed doesn't reliably survive multi-step
reasoning (`docs/plan-cost-calculator-tool.md` §1).

## 2. Scope, drawn tightly

**Computes**, for one combat-damage step:

- Given an attacker (power, and keywords `trample`/`deathtouch`/
  `first_strike`/`double_strike`) and a list of blockers (each with
  toughness, damage already marked, and — recorded but never consulted for
  this computation, see the guard in §5 — its own `deathtouch` flag), plus
  an explicit assignment order when there is more than one blocker: the
  **minimum lethal damage** the attacker must assign to each blocker, in
  order, before any remaining power can go anywhere else.
- The **trample overflow** to the defending player/planeswalker, if and only
  if the attacker has trample and every blocker in the order has already
  been assigned its lethal minimum.
- What happens to leftover power when the attacker does **not** have
  trample: CR 510.1c requires *all* combat damage to be assigned among the
  blocking creatures — none evaporates and none reaches the player. The tool
  surfaces this as a distinct `leftover_power_no_trample` figure (dumped on
  the last blocker in the order) rather than quietly folding it into
  "trample," so a no-trample question never gets a trample-shaped answer by
  accident.
- Lethal-damage math that accounts for **deathtouch on the attacker only**
  (CR 702.2c: any nonzero amount of damage from a deathtouch source is
  lethal for assignment purposes) and for damage the blocker is already
  carrying (`toughness - damage_marked`, floored at 0).
- **First strike / double strike**, scoped as a *single-step* computation:
  the caller tells the tool which combat-damage step it's computing
  (`first_strike` or `regular`), and the tool returns `deals_damage_this_step:
  false` — not a guessed zero folded silently into the assignment — when the
  attacker doesn't have the keyword that would let it deal damage in that
  step. A double-strike attacker calls the tool twice (once per step); the
  second call's `damage_marked` on each blocker carries forward whatever the
  first call assigned, exactly like the real game state between the two
  damage steps. The tool does not sequence the two calls itself — same
  "caller supplies the classification, tool does the arithmetic" split
  `calculate_cost` already uses for cost modifiers (§2 there).

**Refuses to compute — explicitly, not silently:**

- **Banding** (CR 702.21-shaped configurations). Banding damage assignment
  is not lethal-damage-per-blocker-in-order at all — the attacking player
  (for creatures with banding) or defending player (for creatures *blocked
  by* a band) divides damage among the band as they choose, a completely
  different rule. The tool detects this only in the sense that it never
  claims to model it: a banding question is out of scope by definition, and
  the model is told not to call this tool for one.
- **Fighting** (CR 701.12-shaped "fight" effects, e.g. `Prey Upon`,
  `Ram Through`). Fighting deals damage simultaneously between two creatures
  outside of combat, unrelated to attackers/blockers/trample — it is a
  plausible confusable for a model given the surface similarity ("creature A
  deals damage to creature B"), and rulesguru's own tag vocabulary keeps
  `Fight` and `Combat` as separate tags (§6), which is corroborating
  evidence this is a real distinction, not a pedantic one. Refused.
- **Unusual replacement/prevention effects** — "prevent all combat damage,"
  "damage can't be prevented," damage redirection, or any card in play whose
  oracle text modifies how combat damage is dealt rather than how much is
  assigned. The tool computes assignment amounts only; it has no model of
  replacement effects and must not silently assume none apply.
- **Non-combat damage** — burn spells, activated-ability damage, damage from
  a triggered ability — is out of scope; this tool touches only the CR
  509-510 assignment step.
- **Indestructible is deliberately NOT special-cased.** It was considered
  and excluded on purpose, not missed: per CR 510.1c/702.2c, "lethal damage"
  for *assignment* purposes is defined purely from toughness and marked
  damage, regardless of whether the creature would actually be destroyed by
  it. Indestructible changes what happens *after* damage is dealt (state-based
  destruction), not the assignment arithmetic itself — so the tool computes
  the same lethal amount whether or not a blocker is indestructible, and
  that is correct, not an omission. Flagged here the way the cost tool
  flagged its Un-set-symbol decision (`docs/plan-cost-calculator-tool.md`
  §2), so a future reader doesn't "fix" it into a bug.

A tool that silently mis-assigns is worse than a model doing its best in
prose — same standing rule the cost calculator plan set (§2 there), restated
here because it's the whole justification for the refuse-list being longer
than the compute-list.

## 3. The interface

### 3a. Reuse, not rebuild

Every piece of machinery this needs already exists and already shipped for
`calculate_cost`:

- The tool-use round trip itself — `client.messages.parse(tools=...,
  output_format=Answer)`, reissued each round, no separate "tools-off final
  call" — is proven in production (`answer.py`:1356-1409, spike-verified
  per `docs/spike-tool-use-findings.md`).
- `TOOL_ROUND_CAP = 3` (`answer.py`:840) already caps a confused model's
  looping; this tool reuses the same cap rather than inventing a second one.
- `self.last_tool_calls` (`answer.py`:1150/1349/1411) already gives
  telemetry visibility into every tool invocation and result on an attempt;
  a combat-tool call is just another entry in the same list, distinguished
  by `name == "combat_damage_assignment"` (or whatever the registered tool
  name ends up being) vs. `name == "calculate_cost"`.
- `_run_calculate_cost`'s dispatch pattern (`answer.py`:869-884 — catch
  everything, return `{"ok": False, "error": ...}`, never let a tool crash
  take down the whole generation call) is the pattern a
  `_run_combat_assignment` dispatcher would follow exactly.

This tool **registers alongside** `calculate_cost` — a second entry in the
`tools=[...]` list passed to `messages.parse`, a second module under
`src/rulesagent/tools/` (proposed: `combat_calculator.py`, pure Python, no
LLM, no I/O, mirroring `cost_calculator.py`'s own docstring discipline of
quoting every rule it relies on rather than asserting from memory), and a
second dispatch branch in the same `for block in response.content` loop
(`answer.py`:1389-1399) keyed on `block.name`. Nothing about the round-trip
machinery, the round cap, or the `messages.parse` call shape needs to
change — this is additive to a proven seam, not a new one.

### 3b. Proposed tool declaration

```
{
  "name": "combat_damage_assignment",
  "description": "Given one attacking creature (power, and whether it has
    trample/deathtouch/first strike/double strike) and the creature(s)
    blocking it (toughness, damage already marked, assignment order when
    there is more than one), computes the exact minimum-lethal damage
    assignment per blocker and any trample overflow to the defending
    player, for ONE combat damage step at a time, per CR 509-510. Does NOT
    decide which creatures are attacking/blocking, what keywords they have,
    or which combat damage step applies -- identify that from the card
    data and question first, then call this only for the assignment
    arithmetic. Refuses (returns ok:false) rather than guessing on banding,
    fighting, non-combat damage, or damage-replacement effects -- do not
    call this tool for those. Never state a combat damage assignment or
    trample amount without calling this tool when more than one blocker,
    or an attacker/blocker keyword (trample, deathtouch, first strike,
    double strike), is in play.",
  "input_schema": {
    "attacker": {
      "power": int (>=0),
      "trample": bool, "deathtouch": bool,
      "first_strike": bool, "double_strike": bool
    },
    "blockers": [
      {"id": str, "toughness": int (>0), "damage_marked": int (>=0),
       "deathtouch": bool}
    ],
    "assignment_order": [str, ...] | null,   # blocker ids; required when
                                              # len(blockers) > 1
    "step": "single" | "first_strike" | "regular"
  }
}
```

Output, success:

```
{"ok": true,
 "deals_damage_this_step": bool,
 "assignments": [{"blocker_id": str, "assigned": int,
                   "lethal_amount_used": int, "note": str}, ...],
 "leftover_power_no_trample": int,
 "trample_to_player": int,
 "total_assigned": int,
 "steps": [str, ...]}
```

Output, refusal: `{"ok": false, "error": "...", "reason_code":
"banding"|"fight"|"replacement_effect"|"non_combat_damage"|
"malformed_input"}` — same discipline as `calculate_cost`'s `{"ok": False,
"error": ...}` (`cost_calculator.py`:154-156, 168-180), extended with a
`reason_code` because this tool's refuse-list (§2) is long enough that the
model benefits from a machine-checkable reason, not just prose, when
deciding whether to fall back to hedged text.

The `steps` trace follows `calculate_cost`'s own precedent exactly
(`cost_calculator.py`'s `steps` list, `answer.py`'s citation of it as the
guard against laundering a wrong number into an unexplained total) — one
line per blocker assignment plus a line for the trample/leftover
disposition, so the model's prose can cite the tool's own reasoning instead
of re-deriving it.

### 3c. The trigger — additive, deterministic, mirrors `_needs_cost_tool`

`_needs_cost_tool` (`answer.py`:851-866) is the pattern to copy exactly, not
just the spirit of it: a narrow regex-and-symbol-presence check over
`_card_symbol_text(cards) + question`, returning a plain bool, gating a
second `tools=[...]` entry and a second system-prompt sentence onto the same
call **only when it fires**. A proposed `_needs_combat_tool(question,
cards)` would fire when **both**:

1. A combat-damage shape is present in the question text — a
   trample/first-strike/deathtouch/double-strike keyword string, or a
   "block"/"blocks"/"blocked by" phrase, appears in the cards' oracle text
   or the question; **and**
2. A "how much damage" question shape is present — a regex over the
   question text (`\bhow much (combat )?damage\b`, or "damage do I have to
   assign," matching c020's own phrasing) — narrow on purpose, same
   trade-off `_needs_cost_tool`'s docstring already states explicitly
   (`answer.py`:857-862): *"a false negative just means the model does the
   arithmetic in prose as it does today (no regression); a false positive
   costs one extra system sentence + tool schema on that call."*

Both conditions being required (not just "combat present") keeps the
trigger narrow the same way `_needs_cost_tool` requires both `{X}` AND a
cost-change phrase, not just one. This is deliberately **additive** to the
existing gate, not a replacement or a merge: `use_cost_tool` and (proposed)
`use_combat_tool` are independent booleans, each attaching its own tool
entry to the same `extra_kwargs["tools"]` list and its own system sentence,
so a question that trips only one trigger pays only for that one tool's
schema tokens, and the non-tool path for every other question stays exactly
as byte-identical as it is today (`answer.py`:756-765's stated requirement,
which this plan inherits unchanged).

**The emerging tool-selection concern.** With two tools in play, a question
that trips both triggers (imagined case: a combat question with a mana-cost
comparison layered on, e.g. an X-cost pump spell in a trample fight) hands
the model two schemas at once and requires it to call the right one for
each sub-computation, not conflate them. This design keeps that safe for
now specifically *because* the triggers are independent and deterministic
rather than a single "pick a tool" decision handed to the model cold — each
tool still only appears when its own narrow, unrelated-to-the-other
condition fires, so the two-tools-at-once case stays rare by construction,
not by the model's judgment. That said, this is flagged as a real concern
that gets harder with a third tool, not solved — no router, no
tool-selection heuristic beyond "both narrow triggers happened to fire," is
proposed here. Worth a dedicated look once a third tool is on the table.

### 3d. Open items (mirrors `docs/plan-cost-calculator-tool.md` §10's honesty about what isn't settled)

1. Whether `assignment_order` should be required strictly, or inferred
   when there's exactly one blocker (almost certainly the latter — trivial,
   but not decided here).
2. Whether a double-strike attacker's two required calls (first-strike step,
   then regular step) should be nudged by a second trigger-adjacent system
   sentence ("call this again for the regular-damage step, carrying forward
   `damage_marked`") or left to the model's own multi-turn tool-use
   judgment, same as `calculate_cost`'s open item about nesting inside the
   retry loop (`docs/plan-cost-calculator-tool.md`§3d) — not designed here.
3. `TOOL_ROUND_CAP = 3` was sized for `calculate_cost`'s one-call use case
   (`answer.py`:840-846 sizing note). A double-strike combat question
   plausibly needs 2 tool calls in one attempt (first-strike step, regular
   step) plus the terminal Answer turn = 3 rounds, right at the cap with no
   slack for a retry within the same attempt. Whether the cap needs raising
   once both tools can coexist is flagged, not resolved.
4. Exact regex for the "how much damage" question shape (§3c) needs
   calibrating against more than c020 alone before it ships — one example
   is not enough to tune a regex any more than it's enough to validate a
   feature (§6).

## 4. Where the inputs come from

- **Attacker power, blocker toughness, keywords**: already fetched and
  already shown to the model today, the same way `calculate_cost`'s base
  cost already rides on `_format_cards`'s existing card-header emission
  (`docs/plan-cost-calculator-tool.md` §4). `tools/scryfall.py`'s
  `_face_from_json` already carries `power`/`toughness` per face
  (confirmed live above: Stampeding Rhino 4/4, Vampire Nighthawk 2/3), and
  oracle text carries the keyword abilities verbatim. No new fetch.
- **Which creature is attacking, which is blocking, and the assignment
  order**: this is the combat-tool analog of `calculate_cost`'s "which
  effects apply and what kind" scope exclusion (§2 there) — it lives in the
  question's prose ("I'm attacking with X... blocks with Y") and, per §2 of
  this plan, is never inferred by the tool itself. The model reads it from
  the question the same way it already does today; the tool receives it
  pre-identified.
- **Damage already marked on a blocker**: zero for a fresh single-step
  question like c020; non-zero only carries meaning across a two-step
  first-strike/double-strike sequence (§2), supplied by the model from its
  own first-call result, not fetched from anywhere new.

## 5. The honest failure mode

1. **Wrong-side keyword application** — the exact trap c020 sets (§1): a
   model attaches the *blocker's* deathtouch to the lethal-amount
   calculation instead of checking whether the *attacker* has it. **Guard:**
   the tool's input schema only reads `attacker.deathtouch` for the
   lethal-amount computation; `blockers[].deathtouch` is accepted and
   echoed back in the trace (so a misclassification is visible, same
   auditability posture as `calculate_cost`'s trace guard, §5.1 there) but
   is structurally incapable of affecting the assignment math, because the
   function never reads it for that purpose. This does not prevent the
   model from calling the tool with `attacker.deathtouch: true` when it
   shouldn't be (that's a classification error the tool can't catch,
   exactly like `calculate_cost` can't catch a mislabeled modifier kind,
   §5.1 there) — it prevents the *arithmetic* from silently reading the
   wrong field even when the classification going in is correct.
2. **Order omitted or wrong on a multi-blocker question.** CR 509.2/510.1c
   makes the attacking player's chosen order load-bearing — get it backwards
   and the minimum-lethal amounts land on the wrong creatures. **Guard:**
   `assignment_order` is a required field once `len(blockers) > 1`; the tool
   returns a structured `malformed_input` refusal rather than guessing an
   order (e.g. list order) when it's missing.
3. **Step mismatch** — asking for the `first_strike` step against a plain
   attacker with neither keyword. **Guard:** `deals_damage_this_step: false`
   is returned explicitly rather than a same-shaped-as-normal zero result,
   so the model's prose can't accidentally read a legitimate "no damage this
   step" as "the attacker dealt zero damage" in the final combat outcome.
4. **Prose drifts from the tool's own output** — same class of risk
   `calculate_cost`'s plan flagged (§5.3 there): the tool returns 3-to-
   blocker/1-tramples-over and the model's `Answer.text` says something
   else anyway. **Guard:** identical proposal — an eval-time check (not
   runtime) that the numbers in `Answer.text` match the last
   `combat_damage_assignment` result on that turn, logged the same way as
   the cost tool's equivalent guard, never silently retried.
5. **Malformed/impossible input** (negative power, zero-length blockers
   list, an assignment order that doesn't match the blocker ids given) —
   fails loud with a structured refusal, never a best-effort number, same
   standing rule as `calculate_cost`'s §5.5 and `cost_calculator.py`'s own
   validation functions.

## 6. Verification — c020 is one question, and it has no prior verdict

Say this as plainly as the cost-calculator plan said it about c014 (§6
there): **c020 has never been graded.** It is not a regression check against
a known-good answer; it's a fresh question this tool would be scored against
for the first time, by Jon, whenever this ships. n=1 on a never-scored
question is a weaker starting position than c014 had (c014 at least had two
full prompt programmes' worth of failed-attempt evidence behind it,
`docs/plan-cost-calculator-tool.md` §1) — which makes a real validation set
even more necessary here, not less.

**`evals/rulesguru_full.jsonl`, checked directly (1,409 rows total):**

Combat-tagged-question counts by literal tag string present in the file's
own tag vocabulary — checked directly rather than assumed, because most of
the tag names named in the task brief **do not exist** as tags in this
dataset:

- `Combat`: **92** rows.
- `Damage`: **96** rows.
- `Fight` (the CR 701.12 fighting mechanic, distinct from combat — see §2's
  refusal): **2** rows.
- `Fighting`, `Blocking`, `Trample`, `Deathtouch`, `First Strike`, `Double
  Strike` — **none of these exist as tags anywhere in the file.** The
  dataset's tag vocabulary is coarser than the mechanic-level granularity
  this feature targets; there is no way to pull "just the trample questions"
  or "just the deathtouch questions" by tag alone.
- Union of `Combat` OR `Damage` OR `Fight` (deduplicated): **164** rows.
  `Combat` and `Damage` overlap on 26 rows.
- Of that 164-row union, **151** carry non-empty `gold`.

**Recommendation, flagged as Jon's call, not settled here:** the 164-row
`Combat`/`Damage`/`Fight` union (151 with gold) is the closest available
proxy to a combat-damage validation set, but it is a **coarser** instrument
than `calculate_cost`'s 8-row mana-cost-math slice
(`docs/plan-cost-calculator-tool.md` §6) — it will include plenty of combat
questions with no assignment-arithmetic component at all (first-strike
timing questions, "does this creature survive combat" questions with no
trample/deathtouch in play, etc.), so a real validation pass would need a
second filter — reading the 164 rows' `question` text for actual
assignment-shaped content (trample overflow, deathtouch lethal-amount,
multi-blocker ordering) — that this plan has not done, the same way §3d's
open item #4 flags that the trigger regex itself isn't tuned yet either.
Both of those are one pass of real work, not a design decision, and both are
left for the build.

**Beyond rulesguru**, c002 (frozen, excluded from scoring but still run and
judged per `DECISIONS.md`'s 2026-07-25 entry) and c020 together give a
paired before/after on the exact mechanic this tool targets, the same way
`calculate_cost`'s plan used c002/c004/c011/c012/c014/c015 as a paired
cost-math baseline (§6 there) — with the caveat that c002 is explicitly
**not** to be un-excluded or restored to scoring by this work; it stays
frozen evidence, per Jon's own 2026-07-25 ruling.

## 7. Non-goals

- No multi-tool agentic loop beyond what already exists — one more narrow
  tool (`combat_damage_assignment`), registered alongside `calculate_cost`,
  not a general combat simulator.
- No banding support (§2) — CR 702.21's damage-division rules are a
  different mechanic entirely and are refused, not modeled.
- No support for fighting (CR 701.12), non-combat damage, or
  damage-replacement/prevention effects (§2) — all explicit refusals.
- No sequencing of first-strike/double-strike's two calls on the tool's own
  behalf (§3d #2) — the model drives that, same as it drives everything
  else about *which* effects apply, per §2's scope line.
- No OpenRouter/gpt-5-mini tool-use support — inherits the same deferral
  `calculate_cost`'s plan already recorded (§3d/§7 there), unless that
  changes independently of this feature.
- No un-excluding c002 from scoring, and no rewriting of c020's `gold` field
  or any other eval question/verdict as part of this plan — grading c020 is
  Jon's call, made after this ships, not before.

## 8. What would change Jon's mind

- **Base-rate evidence this is rare.** If the 164-row union (§6), once
  actually read for assignment-shaped content, turns out to contain only a
  handful of genuine trample/deathtouch/multi-blocker questions, the
  added-round-trip cost on every query that trips the trigger may not be
  worth it — the same ROI question `calculate_cost`'s plan raised (§8
  there).
- **Evidence the bottleneck is misclassification, not arithmetic.** If c020
  (and whatever real validation slice gets built from §6) still miss after
  this ships because the model keeps handing the tool the wrong side's
  deathtouch or the wrong assignment order, rather than the tool computing
  the wrong thing from correct inputs, that shows the actual gap is
  rules-judgment about *whose* keyword applies — a retrieval/prompt problem,
  not an arithmetic one — closing this line of work the same way the
  cost-calculator plan's own §8 describes for its own feature.

## 9. Demo/articulation note

This is the second time the same failure shape has shown up: the model can
narrate a combat or cost sequence correctly in prose and still land on the
wrong number, because the actual bottleneck is a small piece of exact
arithmetic buried inside rules-defined bookkeeping, not missing knowledge.
The fix is the same fix both times — stop asking a language model to do that
arithmetic token-by-token and hand the deterministic sub-computation to a
function while the model keeps doing what it's actually good at, identifying
which rule and which effect apply. Two independent instances of "found a
recurring class of failure, built a deterministic tool for the
sub-computation, kept the model as orchestrator" is a stronger story than
one, because it shows the pattern generalizes rather than being a one-off
fix for a single eval question.

## 10. Open items (compiled from above)

1. `assignment_order` required-vs-inferred for the single-blocker case
   (§3d #1) — trivial, not decided.
2. Double-strike two-call sequencing: model-driven vs. a nudging system
   sentence (§3d #2) — not designed.
3. `TOOL_ROUND_CAP` sizing once a double-strike combat question and the cost
   tool can both be in play (§3d #3) — flagged, not resolved.
4. The "how much damage" trigger regex (§3c) needs calibration beyond c020
   alone (§3d #4, §6) — one example is not enough to tune it.
5. CR 509.2, 510.1c, 510.5, 702.2c, 702.4, 702.19 text was searched for
   directly in this worktree's only available rules-grounding source
   (`evals/rulesguru_raw.json`'s `citedRules`, the same source
   `cost_calculator.py`'s own docstring uses for 601.2f) and **none of the
   six were found** — `data/raw/MagicCompRules*.txt` is absent from this
   worktree entirely. **CR text not available in this worktree — grounding
   deferred to build.** This plan's rule numbers and their described effects
   (deathtouch's 1-damage lethal threshold, trample's after-lethal
   overflow, the attacking player's chosen multi-blocker order, the
   two-step first/double-strike split) are stated from well-established
   Magic rules knowledge, consistent with how the actual game resolves
   combat, but **not verified against quoted CR text in this session** the
   way 601.2f and Trinisphere's ruling were verified for the cost tool —
   flagged honestly rather than pasted from memory as if grounded. Whoever
   builds this should paste the real CR 509-510/702.2/702.4/702.19 text
   from a worktree that has `data/raw/MagicCompRules*.txt` before writing
   `combat_calculator.py`'s docstring, the same discipline
   `cost_calculator.py`'s docstring already models.
6. A real validation slice from the 164-row rulesguru union needs a second,
   read-the-question-text pass to isolate actual assignment-shaped
   questions from the coarser `Combat`/`Damage`/`Fight` tag union (§6) —
   not done here.

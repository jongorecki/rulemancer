# Plan — layer-system resolver tool (CR 613)

**STATUS: DESIGN ONLY. Rule 0 — nothing here gets built until Jon reviews and
rules.** No source file has been touched. No tool code exists.

Written 2026-07-24 on `master`. Every CR quotation below is pasted verbatim from
`data/raw/MagicCompRules 20260619.txt`; every card's oracle text was fetched live
via `rulesagent.tools.scryfall.get_card`. Nothing in this document is asserted
from memory — the combat plan's §11 caught three wrong CR citations that had been
written from memory, so this plan quotes first and reasons second.

---

## 0. The verdict up front

Jon's ruling in `DECISIONS.md` set the bar: *"a layers plan that can't scope a
deterministic sub-computation the tool can own... if layer resolution can't be
made deterministic and bounded, it isn't tool-shaped and the slot reopens."*

**It is tool-shaped — but not for the reason a "layers calculator" sounds like it
would be.** The arithmetic in a layers question is trivial (`1/1` base, `+3/+3`,
`+2/+2` → `6/6`); a tool that existed only to add those numbers would not be worth
a round trip. The deterministic thing worth owning is **stateful ordering
bookkeeping under CR 613.6** — the rule that an effect which has *started* to
apply keeps applying in later layers even after the ability generating it is
removed.

That matters because of what the four regrade misses actually show. sonnet made
**the same CR 613.6 mistake on three of the four** (rg3868, rg807, rg811), each
time *after* correctly narrating the layer assignments, the timestamps, and the
rule itself. In rg3868 it even applied 613.6 correctly to colour in step 3 and
then contradicted itself on power/toughness in step 4, in the same answer. That
is the exact cost-calculator pattern — *narrates it right, then botches the
mechanical part* — and it is a failure mode that a resolver engine cannot have,
because in an engine the effects are a list ordered by `(layer, sublayer,
timestamp)` and removing an ability in layer 6 does not delete pending entries
from that list. **613.6 holds by construction; you would have to write extra code
to get it wrong.**

I hand-traced the proposed engine against all four seeds (§3b.5). It produces the
gold answer for rg3868, rg807, and rg811. It does **not** fix rg633, and I am not
going to pretend otherwise — rg633 fails on a *dependency judgment* (§1.3), which
the tool takes as input and can never second-guess.

**Base rate, which is what shelved combat: 51 genuinely resolver-shaped questions**
in the 1,409-row corpus, after hand-reading every one of the 68 that cite a CR 613
rule. Combat's equivalent number was **7**. That is 7× the volume on the weakest
difficulty tier, and it clears the shelve-it threshold in §8.4 by a wide margin
(§1.4).

Two things I want Jon to rule on before any code is written, both in §8: the
**conditional-applicability design** (§3a, option A vs B — this is the one real
scope fork) and whether the tool must first beat a **one-line prompt bullet**
control arm (§6.1), which is a much cheaper fix that might capture most of the
same win.

---

## 1. The problem, evidenced

### 1.1. The failure is the same bug, three times

I read the four failed answers myself (`evals/answers/rulesguru_answers.json`);
this was not delegated. Below is what sonnet actually said versus gold.

**rg3868** — *Muraganda Petroglyphs + Wayward Angel (7+ cards in graveyard) +
Humility. "What are Wayward Angel's characteristics?"*
Gold: **black 6/6, no abilities.** sonnet: **black 3/3, no abilities.**

sonnet's step 4, verbatim:

> Once the threshold ability is gone, none of its not-yet-applied effects (the
> +3/+3 boost, which is a layer 7c effect) can occur, since the source ability no
> longer exists by the time layer 7 is reached.

That is a direct contradiction of CR 613.6. And sonnet had already used the
opposite (correct) principle one step earlier, in step 3:

> Layer 5 (color) is calculated before layer 6 (abilities) in the fixed layer
> order, so the color already locked in during layer 5 is not retroactively undone
> when the threshold ability is stripped in layer 6

Same answer, same rule, two opposite applications. Everything else in that answer
is right: the layer assignments, the timestamps, the 604.3a reasoning about why
threshold is not a CDA, and even the Muraganda conditional. It loses on
bookkeeping alone.

**rg807** — *Wayward Angel (7+ in graveyard) + Turn to Frog.*
Gold: **4/4 blue Frog, no abilities.** sonnet: **1/1 blue Frog, no abilities.**

Identical error:

> The +3/+3 bonus, however, is a power/toughness-modifying effect computed after
> abilities are removed, so once Threshold itself has been stripped by "loses all
> abilities," the +3/+3 no longer applies

**rg811** — *the same two cards, but Wayward Angel is manifested, Turn to Frog
resolves on the face-down permanent, then it is turned face up.*
Gold: **4/4 black Frog with trample and the upkeep trigger and nothing else.**
sonnet: **4/4 black Frog with flying, vigilance, trample, the upkeep trigger, and
threshold.**

Different surface, same class of error — this time treating a continuous effect as
a one-shot snapshot:

> Turn to Frog's "loses all abilities" only stripped what existed at the time it
> resolved (nothing, since it was face down)

CR 611.3a is the rule it missed:

> 611.3a A continuous effect generated by a static ability isn't "locked in"; it
> applies at any given moment to whatever its text indicates.

Turn to Frog's effect keeps removing abilities every time the layer system runs.
Because it has the earlier timestamp (Wayward Angel got a *new* one on turning
face up, CR 613.7f), layer 6 goes: remove-all first (killing flying and
vigilance), *then* threshold grants trample and the trigger. sonnet got the
timestamps right and the persistence wrong.

**rg807 and rg811 are the single best evidence in the corpus.** They are the same
two cards with the same effects; the *only* thing that differs is relative
timestamp order, and the gold answers diverge on both colour and abilities. That
is a pure ordering computation with a card-identical control.

### 1.2. Why this is not "the model just needs to know the rule"

It does know the rule. rg3868 states 613.6's principle correctly for colour before
violating it for P/T. The knowledge is present and the *application* is
inconsistent across a multi-step walk it is holding in prose. That is precisely
the class of work a deterministic engine removes rather than teaches.

### 1.3. rg633 is a different failure and the tool does not fix it

*Alijah controls Badlands and Conversion, then casts Magus of the Moon. What
colour(s) can Badlands tap for?*
Gold: **only {R}.** sonnet: **only {W}.**

Oracle text (fetched live): Conversion — *"All Mountains are Plains."* Magus of the
Moon — *"Nonbasic lands are Mountains."* Badlands — *"Land — Swamp Mountain."*

Both effects are layer 4. Gold applies them in timestamp order (Conversion first →
Plains, then Magus → Mountain). sonnet instead asserted a **dependency**, applying
Magus first, and got the reverse answer. Under CR 613.8a the dependency does not
exist here: Badlands is *already* a Mountain by its printed type, so applying
Magus does not change whether Conversion applies to it.

sonnet flagged its own gap, verbatim:

> the specific rule governing how to order two effects that are 'dependent' on each
> other... wasn't included in the rules text I was given, so my ordering above is
> inferred from...

So rg633 is **two** problems: a retrieval miss on CR 613.8, and a dependency
judgment the model then got wrong. **A resolver engine cannot fix either.**
Dependency is model-declared input; the engine will faithfully compute the wrong
answer from a wrong declaration. The one honest mitigation is that the tool
*description* carries 613.8a verbatim, which guarantees the rule text is in context
at the moment it is needed — a retrieval effect, not a computation, and it should
be claimed as nothing more than that.

**Scoring the seed set honestly: 3 of 4 fixed, 1 of 4 not.**

### 1.4. Base rate — the number that shelved combat

Counted directly over `evals/rulesguru_full.jsonl` (1,409 rows; 1,256 carry gold),
streamed, never read into context raw. Then **every one of the 68 CR-613-citing
rows was hand-read and bucketed** — the same haircut discipline that took combat
from 164 tagged rows to 7 real ones.

| | Rows | |
|---|---|---|
| Cite any CR 613 rule | 68 | 4.8% of gold-bearing rows |
| — **bucket A, COMPUTE** (asks for a final characteristic) | **51** | the target set |
| — bucket B, order-only | 1 | rg7752, "what layer does X apply in" |
| — bucket C, incidental 613 cite | 16 | legality / SBA / combat outcome |
| Cite CR 611 | 33 | |
| Cite CR 612 | 3 | |
| *(combat, for comparison — plan-combat-damage-tool.md §11.2)* | *7* | *0.5%* |

Difficulty split of the 68: level 2 → 39, level 3 → 15, level 1 → 9, Corner Case → 5.

The four seeds are all inside the 613-citing set, so **citation filtering finds the
known failures** — no blind spot in the proxy.

Two figures from the sub-rule breakdown that bear directly on design:

- **`613.8a` is cited by 17 rows and `613.8b` by 9 — dependency appears in roughly a
  quarter of the target set.** That is not a rare corner. It means the plan's
  decision to take dependency as *model-declared input* (§2, §5.2) is load-bearing on
  a quarter of the questions, not a footnote. rg633 is the representative failure.
- **`613.6` is cited by only 4 rows**, yet it is the rule sonnet broke three times out
  of four. Gold under-cites it because it is a *procedural* rule rather than a
  question-defining one. This is a real caution about using gold citations to
  estimate where the value is: the highest-value rule in this tool is nearly invisible
  in the citation data.

**Caveat kept on the record:** 51 is still a small slice (3.6% of the corpus), and 29
of the 68 cite a 613 rule and nothing else — a chunk of the value is narrow
"two-effects-collide" puzzles rather than everyday coverage. A separate check found
11 more rows that are genuine final-P/T computations tagged with more specific rules
(CDAs, counters) instead of 613, so 51 is a floor rather than a ceiling — but most of
those are single-mechanism arithmetic with no cross-layer conflict, so I am not
counting them toward the target set.

---

## 2. Scope, drawn tightly

The tool is `resolve_layers`. It is pure Python, no LLM, no I/O, no network, no
card lookup — the same discipline as `cost_calculator.py`.

**What it owns.** Given a base characteristics object and a list of continuous
effects that the *caller* has already identified and assigned to layers, it applies
them in CR 613 order and returns the resulting characteristics plus a per-step
trace.

**What it never does — the boundary, stated as hard refusals:**

- **Never reads oracle text.** It does not know what a card says.
- **Never decides which layer an effect belongs to.** That is the model's job, and
  the model is empirically good at it (§1.1 — it got layers right on all four
  seeds, including the sublayer split).
- **Never decides whether a dependency exists.** CR 613.8a's three-part test needs
  effect semantics. `depends_on` is model-supplied or absent (§3a).
- **Never assigns timestamps.** Model-supplied relative integers.
- **Never translates results into game consequences.** For rg633 it returns *"land
  subtypes: [Mountain]"*; it does not say *"taps for {R}"* — that is CR 305.6
  card-rules territory and stays with the model.
- **Never assigns a verdict or grades anything.**

**Layers in v1 scope:** 2 (control), 4 (type), 5 (colour), 6 (abilities), 7a/7b/7c/7d
(P/T).

**Layers deliberately out of v1 scope**, each with a named consequence:

| Out | CR | Consequence of excluding |
|---|---|---|
| Layer 1a/1b — copy effects, face-down | 613.2a–c, 708.2 | Caller supplies `base` as the already-settled **copiable values**. rg811's face-down phase is handled by the model computing the post-turn-face-up base and the new timestamp (613.7f) before calling. Verified sufficient in the §3b.5 trace. |
| Layer 3 — text-changing | 612, 613.1c | Rare. A text-changing effect in play means the model must not call the tool; the schema has no slot for it, so a mis-call is a validation refusal, not a silent wrong answer. |
| 613.8c — dependency re-evaluation after each application | 613.8c | The engine resolves the dependency graph **once** per layer, not after each application. Re-evaluation requires *inferring* new dependencies mid-walk, which needs semantics the engine does not have. Refuses-vs-guesses: v1 documents this and the trace flags when any `depends_on` was supplied at all, so a case that needed re-evaluation is visible rather than silent. |
| 613.10 — continuous effects on players | 613.10 | Out. Player-level effects (e.g. protection granted to a player) are not object characteristics. |
| 613.11 — continuous effects on game rules | 613.11 | Out. Explicitly points at 601.2f, which is `calculate_cost`'s territory already. |

**Non-CDA note:** the engine implements 613.3's "CDAs first, then everything else
in timestamp order" and 613.4a's layer 7a via an `is_cda` boolean the caller
supplies. It does not apply CR 604.3a's five-criterion test itself. Grounding, so
the schema description can quote it rather than paraphrase:

> 604.3a A static ability is a characteristic-defining ability if it meets the
> following criteria: (1) It defines an object's colors, subtypes, power, or
> toughness; (2) it is printed on the card it affects, it was granted to the token
> it affects by the effect that created the token, or it was acquired by the object
> it affects as the result of a copy effect or text-changing effect; (3) it does not
> directly affect the characteristics of any other objects; (4) it is not an ability
> that an object grants to itself; and (5) it does not set the values of such
> characteristics only if certain conditions are met.

(Criterion 5 is why Wayward Angel's threshold ability is *not* a CDA — sonnet got
this right unprompted in rg3868 step 1.)

---

## 3. The interface

### 3a. The schema

The caller decomposes each ability into one or more **effect parts**, grouped under
a shared `source_id`. The grouping is what makes CR 613.6 computable — the engine
needs to know that the layer-5 colour change and the layer-7c pump come from *the
same ability*.

```python
resolve_layers(
    base: dict | None,
    effects: list[dict] | None = None,
) -> dict
```

`base` — the object's copiable values, post-layer-1:

```json
{
  "name": "Wayward Angel",
  "card_types": ["Creature"],
  "supertypes": [],
  "subtypes": ["Angel", "Horror"],
  "colors": ["W"],
  "abilities": ["Flying", "Vigilance", "Threshold - ... gets +3/+3, is black, has trample, and has \"At the beginning of your upkeep, sacrifice a creature.\""],
  "power": 4,
  "toughness": 4,
  "controller": "A"
}
```

`effects` — a flat list of parts. Each part:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique part id, e.g. `"e1c"`. |
| `source_id` | string | The **ability** this part comes from. Parts sharing a `source_id` are one ability split across layers per CR 613.6. |
| `layer` | enum | One of `"2"`, `"4"`, `"5"`, `"6"`, `"7a"`, `"7b"`, `"7c"`, `"7d"`. |
| `timestamp` | integer ≥ 0 | Relative order only. Equal timestamps are a refusal, not a coin flip. |
| `is_cda` | bool | Feeds 613.3 / 613.4a ordering. |
| `depends_on` | list[string] \| null | Part ids this part depends on, per 613.8a. Model-declared only. |
| `dependency_reason` | string \| null | **Required whenever `depends_on` is non-empty.** Forces the model to articulate the 613.8a test rather than assert an ordering (this is the rg633 mitigation, §1.3). |
| `operation` | object | The typed operation, below. |
| `applies_if` | object \| null | Conditional applicability — **see the fork below.** |
| `cite` | string | CR/oracle cite, mirroring `calculate_cost`'s `cite` field. |

`operation` is a closed union, one shape per layer:

```
layer 2   {"kind": "set_controller", "value": "<player>"}
layer 4   {"kind": "set_types",    "card_types": [...], "subtypes": [...], "supertypes": [...]}
          {"kind": "add_types",    "card_types": [...], "subtypes": [...], "supertypes": [...]}
          {"kind": "remove_types", "card_types": [...], "subtypes": [...], "supertypes": [...]}
layer 5   {"kind": "set_colors", "value": ["W","U","B","R","G"] subset}
          {"kind": "add_colors", "value": [...]}
layer 6   {"kind": "add_abilities",        "value": ["Trample", ...]}
          {"kind": "remove_abilities",     "value": [...]}
          {"kind": "remove_all_abilities"}
          {"kind": "cant_have_abilities"}
layer 7a  {"kind": "cda_pt",   "power": int, "toughness": int}
layer 7b  {"kind": "set_pt",   "power": int, "toughness": int}
layer 7c  {"kind": "modify_pt","power": int, "toughness": int}    # signed; counters use this
layer 7d  {"kind": "switch_pt"}
```

Any `operation.kind` used in the wrong layer is a refusal. This is deliberate — a
`set_pt` declared in layer 7c is a model error that would otherwise produce a
plausible wrong number.

**⚠️ THE ONE REAL SCOPE FORK — `applies_if` (Jon rules, §8.1).**

rg3868 needs Muraganda Petroglyphs (*"Creatures with no abilities get +2/+2"*) to
apply *only if* the object has no abilities — and whether it does is not known until
after layer 6 has run. The model cannot pre-compute that input without already
having done the engine's job. Three ways out:

- **Option A — static boolean.** `applies_if` is just `true`/`false`, decided by the
  model. Smallest schema. But it makes the model simulate layers 1–6 in its head to
  fill in the field, i.e. it re-introduces the exact reasoning the tool exists to
  remove. sonnet *did* get this right in rg3868, so A is not fatal — it is fragile.
- **Option B (recommended) — a closed predicate enum**, evaluated against live state
  at the moment of application:
  `{"has_no_abilities": true}` · `{"has_ability": "Flying"}` · `{"has_color": "W"}` ·
  `{"has_type": "Artifact"}` · `{"has_subtype": "Frog"}` · `{"power_gte": 4}`.
  Six predicates, a fixed enum, no expression language, no nesting. It handles
  rg3868's Muraganda *and* CR 613.5's own worked example (Honor of the Pure —
  *"White creatures you control get +1/+1"* — which is `{"has_color": "W"}`), which
  is the single most common shape in the whole layer system.
- **Option C — two tool calls**, model reads the trace and re-calls. Rejected: it
  spends a second tool round on every conditional question and pushes straight into
  the `TOOL_ROUND_CAP` question (§3d).

**I recommend B, capped hard at those six predicates, plus the `expect` field
below.** B makes the tool correct on 613.5's canonical example by construction, where
A gets it right only when the model happens to guess right.

**The silent-gating problem, and why it makes B *safer* than A rather than riskier.**
The obvious objection to B is that a mis-declared predicate silently gates an effect
out, producing a coherent, fully-traced, wrong answer. That objection is right about
the failure and wrong about which option is exposed to it. Under **A there is nothing
to cross-check** — the model asserts a boolean and the engine takes it. Under B the
engine independently evaluates the condition against real state, which means the
engine and the model *can disagree*, and a disagreement is a countable signal. Four
mechanisms turn the silent skip into a loud one:

1. **The trace records non-applications, not just applications**, with the evaluated
   reason and the state checked against:
   ```json
   {"layer": "7c", "skipped": "e3a",
    "why": "applies_if {\"has_no_abilities\": true} evaluated FALSE",
    "state_checked": {"abilities": ["Flying"]}}
   ```
2. **A top-level `skipped_count` / `skipped` list.** A nested trace entry gets skimmed
   past; a top-level counter does not.
3. **An `expect` boolean on `applies_if`** — the model declares what it expects the
   predicate to evaluate to. Engine/model disagreement returns a **warning**, not a
   refusal (the engine is right; the model's expectation was the wrong thing):
   ```
   "warnings": ["e3a: expected to apply, but at layer 7c the object had
                 abilities ['Flying'], so it was skipped"]
   ```
   This is the mechanism A structurally cannot have, and it doubles as the validation
   instrument: a high disagreement rate means the predicate vocabulary is wrong, and
   that shows up before shipping rather than after.
4. **Telemetry** — skip and warning data rides in the existing `last_tool_calls`
   channel, the same posture the repo already took for the rg6636 word-salad case
   (`last_uncited_success`): monitorable, not silently trusted.

**Honest limit:** these make the failure *visible*, not *correct*. The model can read
the warning and ignore it. But a measurable mismatch rate is a categorically better
position than an invisible one, and it is measurable from Slice 2 onward with no API
call. If Jon prefers the smaller surface, A remains a legitimate v1 and §9 Slice 2 is
sequenced so B can be added later without reshaping the schema — but A forfeits
mechanism 3 permanently.

**Return shape** mirrors `cost_calculator`'s tagged dict exactly:

```json
{"ok": true,
 "result": {"card_types": [...], "supertypes": [...], "subtypes": [...],
            "colors": [...], "abilities": [...], "power": 6, "toughness": 6,
            "controller": "A"},
 "trace": [{"layer": "5", "applied": "e1a", "why": "timestamp 1",
            "state_after": {"colors": ["B"]}},
           {"layer": "7c", "applied": "e1c", "why": "CR 613.6 - source ability e1 was removed in layer 6 but had already applied in layer 5, so it continues",
            "state_after": {"power": 4, "toughness": 4}}],
 "warnings": [],
 "skipped_count": 0,
 "skipped": [],
 "dependencies_declared": false}
```

and on any malformed input: `{"ok": false, "error": "<string>"}`. It never raises
for an input-shape problem and never returns a best-effort number.

The `trace` is not decoration. It is how a wrong *input* becomes debuggable instead
of invisible, and it is what the model reads back when its own narration disagrees
with the result.

### 3b. The algorithm

```
LAYER_ORDER = ["2", "4", "5", "6", "7a", "7b", "7c", "7d"]

state = copy(base)
started = {}          # source_id -> earliest layer index at which any part applied
removed_at = {}       # source_id -> layer index at which the ability was removed

for i, layer in enumerate(LAYER_ORDER):
    parts = [p for p in effects if p.layer == layer]

    # CR 613.3 / 613.4a: CDAs first, then everything else.
    # CR 613.7:  within each group, timestamp order.
    # CR 613.8b: a part waits until after all its declared dependencies;
    #            a dependency loop falls back to timestamp order.
    ordered = order_parts(parts)

    for p in ordered:
        if not is_active(p, i):      # CR 613.6 gate, below
            continue
        if not predicate_holds(p.applies_if, state):   # Option B only
            continue
        state = apply(p.operation, state)
        started.setdefault(p.source_id, i)
        if p.operation.kind in ("remove_all_abilities", "remove_abilities"):
            record_removals(removed_at, p, i)
```

**The CR 613.6 gate — the load-bearing 8 lines.** Grounding first:

> 613.6. If an effect should be applied in different layers and/or sublayers, the
> parts of the effect each apply in their appropriate ones. If an effect starts to
> apply in one layer and/or sublayer, it will continue to be applied to the same set
> of objects in each other applicable layer and/or sublayer, even if the ability
> generating the effect is removed during this process.

```
def is_active(part, layer_index):
    r = removed_at.get(part.source_id)
    if r is None:            return True     # never removed
    if r > layer_index:      return True     # removed later than now
    s = started.get(part.source_id)
    return s is not None and s <= r          # started before/at removal -> continues
```

Read that against §1.1. `started[source] <= removed_at[source]` is exactly the
distinction sonnet failed to hold three times. And note the *converse* is handled
too: an ability whose only part is in layer 7c, removed in layer 6, never started —
so it correctly does **not** apply. That asymmetry is why this is a real rule and
not just "ignore removals."

**Refusals** (all `{"ok": false, "error": ...}`, never a guess): duplicate part ids;
two parts in the same layer with the same timestamp and no dependency between them;
`operation.kind` illegal for its `layer`; `depends_on` naming a part in a different
layer (CR 613.8a criterion (a) forbids it); `depends_on` non-empty with no
`dependency_reason`; unknown predicate key; `set_pt`/`modify_pt` with non-integer
values; an unknown colour or layer token.

**613.8b, grounded**, since the ordering code implements it literally:

> 613.8b An effect dependent on one or more other effects waits to apply until just
> after all of those effects have been applied. If multiple dependent effects would
> apply simultaneously in this way, they're applied in timestamp order relative to
> each other. If several dependent effects form a dependency loop, then this rule is
> ignored and the effects in the dependency loop are applied in timestamp order.

Worth flagging for honesty: **CR 613.8 carries no worked example anywhere in the
rules text** (checked — 613.4d, 613.5, 613.6 and 613.9 all have Examples; 613.8a/b/c
have none). The least-illustrated part of the layer system is also the part this
tool refuses to reason about. Those two facts are consistent, and both point the
same way: dependency stays model-declared.

### 3b.5. Hand-traced against the seeds

I ran the algorithm above by hand on all four. Card text fetched live, not recalled.

**rg3868** — base: white 4/4 Angel Horror, abilities `[Flying, Vigilance,
Threshold]`. Effects: `e1` = Wayward Angel's threshold (ts 1) → `e1a` L5
`set_colors [B]`, `e1b` L6 `add_abilities [Trample, upkeep-sac]`, `e1c` L7c
`modify_pt +3/+3`. `e2` = Humility (ts 2) → `e2a` L6 `remove_all_abilities`, `e2b`
L7b `set_pt 1/1`. `e3` = Muraganda (ts 3) → `e3a` L7c `modify_pt +2/+2`,
`applies_if {"has_no_abilities": true}`.

| Layer | Applied | State after |
|---|---|---|
| 5 | e1a | colors `[B]`; `started[e1] = L5` |
| 6 | e1b (ts 1) | abilities += Trample, upkeep-sac |
| 6 | e2a (ts 2) | abilities `[]`; `removed_at[e1] = L6` |
| 7b | e2b | 1/1 |
| 7c | e1c (ts 1) | **active**: started L5 ≤ removed L6 → +3/+3 → **4/4** |
| 7c | e3a (ts 3) | predicate `has_no_abilities` true → +2/+2 → **6/6** |

→ **black 6/6, no abilities. Matches gold.**

**rg807** — `e1` WA threshold (ts 1) as above; `e2` Turn to Frog (ts 2) → L4
`set_types subtypes [Frog]`, L5 `set_colors [U]`, L6 `remove_all_abilities`, L7b
`set_pt 1/1`.
L4 → Frog. L5 → `[B]` then `[U]` = blue. L6 → grant, then remove-all → `[]`. L7b →
1/1. L7c → e1c active (started L5 ≤ removed L6) → **4/4**.
→ **4/4 blue Frog, no abilities. Matches gold.**

**rg811** — identical effects, **timestamps swapped**: Turn to Frog ts 1, Wayward
Angel ts 2 (it received a new timestamp on turning face up, CR 613.7f).
L4 → Frog. L5 → `[U]` then `[B]` = **black**. L6 → remove-all first (Flying and
Vigilance die), then grant → `[Trample, upkeep-sac]`. L7b → 1/1. L7c → +3/+3 →
**4/4**.
→ **4/4 black Frog with trample and the upkeep trigger, nothing else. Matches
gold.**

rg807 and rg811 differ in the payload by **one integer each**. Both land on gold.
That is the demonstration.

**rg633** — `e_conv` Conversion (ts 1) L4 `set_types subtypes [Plains]`; `e_magus`
Magus (ts 2) L4 `set_types subtypes [Mountain]`. No dependency declared → timestamp
order → Plains, then Mountain → **subtypes `[Mountain]`**, which is gold. But if the
model declares `depends_on: ["e_magus"]` on `e_conv` as it did in prose, the engine
dutifully applies Magus first and returns `[Plains]` — **gold missed.** The engine is
correct either way; the *input* decides. Honest result: **not fixed** (§1.3).

### 3c. The trigger — and a finding that kills the obvious approach

The combat plan's §11.3 is the cautionary tale: a trigger regex calibrated against
a single founding example hit **1 of 8** real corpus questions. So this trigger was
checked against all 51 bucket-A questions before being proposed, and the check
returned something worth stating loudly.

**Rules vocabulary is absent from layers questions.** Over all 1,409 questions:

| Pattern in question text | Rows |
|---|---|
| `\blayer\b` | **1** — and it is rg7752, the *bucket-B* order-only row. **Zero of the 51.** |
| `\btimestamp\b` | **0** |
| `\bdepend(s\|ency)\b` | **0** |
| `\bcontinuous effect` | **0** |

**62 of the 68 CR-613 rows match no keyword pattern at all.** The vocabulary lives
in `answer_gold`, never in the question. So the intuitive trigger — look for layers
words — would fire on essentially nothing. That branch is deleted, not tuned.

What the bucket-A questions actually say is **characteristic readouts**, in far more
surface forms than the four seeds suggested (verbatim from the survey):

> "is [X] a creature? If so, what are its power and toughness" · "what are the
> characteristics of [X]" · "What will [X]'s P/T be" · "does [X] have flying" ·
> "what color(s) of mana can [X] tap for" · "what land types does [X] have" · "What
> does [X] look like?" · "What is [X]?" · "will the created token be legendary" ·
> "Will [creature] have [ability]" · "What are the types and subtypes of [X]"

And one explicit trap: **"What happens?" appears in bucket A *and* bucket C.** It
cannot disambiguate on question text alone, so it is not a branch.

**Proposal — two conjuncts, mirroring `_needs_cost_tool`'s own shape** (which
requires both an `{X}` symbol *and* a cost phrase before firing):

```python
# Conjunct 1: the question asks for a characteristic readout.
_LAYERS_READOUT_RE = re.compile(
    r"\bcharacteristics\b"
    r"|\b(?:power and toughness|p/t)\b"
    r"|\bis\b.{0,40}?\ba creature\b"
    r"|\b(?:does|do|will)\b.{0,40}?\bhave\b"
    r"|\bwhat\b.{0,20}?\b(?:land )?(?:types?|subtypes?|colou?rs?)\b"
    r"|\bcolou?r\(s\)\b"
    r"|\btap\b.{0,25}?\bfor\b"
    r"|\blook like\b"
    r"|\bbe legendary\b",
    re.IGNORECASE | re.DOTALL,
)

# Conjunct 2: at least ONE loaded card carries continuous-effect-shaped static
# text. (Threshold was >= 2 as originally proposed; RULED down to >= 1 by Jon
# 2026-07-24 after calibration -- see "CALIBRATION RESULT" below.)
_CONTINUOUS_EFFECT_RE = re.compile(
    r"gets?\s*[+-]\d+/[+-]\d+"
    r"|\b(?:base power and toughness|loses? all abilities|can't have)\b"
    r"|\b(?:becomes?|are|is)\b.{0,30}?\b(?:creature|land|artifact|enchantment)s?\b"
    r"|\bhave\b.{0,20}?\bbase\b"
    r"|\b(?:are|becomes?|is)\b.{0,30}?\b(?:Mountains?|Islands?|Swamps?|Forests?|Plains)\b",
    re.IGNORECASE | re.DOTALL,
)

def _needs_layers_tool(question: str, cards: list[Card]) -> bool:
    if not _LAYERS_READOUT_RE.search(question):
        return False
    hits = sum(1 for c in cards if _CONTINUOUS_EFFECT_RE.search(_oracle_all_faces(c)))
    return hits >= 1
```

Conjunct 2 is doing the real work. Conjunct 1 alone is far too wide — *"does X have
flying"* is an ordinary Magic question shape that appears constantly in questions
with no continuous effects in them at all. Conjunct 2 is what makes this a layers
detector rather than a "characteristics" detector, and it is available at trigger
time because the loaded oracle text is already in hand (`_needs_cost_tool` scans it
the same way).

### CALIBRATION RESULT (measured 2026-07-24) — the original proposal FAILED

Measured against the bar this section set (**≥60% bucket-A recall, <10% non-layers
firing**). Buckets re-derived and persisted this time, to
`evals/_layers_buckets.json` (A=54, B=1, C=13; the earlier hand-count was
51/1/16 — the A set here is slightly *more* inclusive, so recall is measured against
a marginally harder denominator, not a flattering one). Script:
`evals/calibrate_layers_trigger.py`. False-positive rates below are over the **full**
1,341-row non-layers pool, not a 100-row sample.

| Variant | Bucket-A recall | Non-layers firing | Bar |
|---|---|---|---|
| As originally written above | 11/54 = **20.4%** | 0% | **FAIL** |
| + `gets?` typo fix | 17/54 = 31.5% | 0% | FAIL |
| + land-subtype alternative | 29/54 = 53.7% | ~0% | FAIL |
| **+ threshold `>= 1` (SHIPPED)** | **42/54 = 77.8%** | **5.1%** (adversarial 5.3%) | **PASS** |

Three distinct causes, and only the third was a design question:

1. **`get\s*` never matched singular `"gets +N/+N"`** — a one-character bug. The
   pattern was written against Muraganda Petroglyphs (*"Creatures with no abilities
   get +2/+2"*, plural) and never tested against a single-object pump. It therefore
   missed **Wayward Angel**, a card in this document's own §3b.5 hand-traces. Worth
   11 points. Fixed above.
2. **Land-type-changing effects were invisible.** The type alternation required
   `are`/`is`/`becomes` *followed* by creature/land/artifact/enchantment, but these
   effects name basic land **subtypes**: *"Nonbasic lands are Mountains."* That
   silently excluded **Blood Moon** and **Magus of the Moon**, which between them
   appear in roughly ten of the 43 original misses and are the most common layer
   cards in the corpus — plus the blue analogues **Harbinger of the Seas** (*"Nonbasic
   lands are Islands"*), **Stormtide Leviathan** and **Khod, Etlan Shiis Envoy**
   (*"All lands are Islands"*). Grounded against the local Scryfall store: 226 cards
   carry land-type-changing text and the added alternative covers all real
   type-changers (the only non-matches are Domain cards that *count* basic land types
   rather than change them). Worth another 22 points. Fixed above.
3. **The `>= 2` threshold was structurally wrong for bucket A.** Its dominant shape is
   *one* continuous effect plus the object it modifies, and that object is usually a
   vanilla target with no continuous-effect text at all — Dryad Arbor, Skeletal Snake,
   Raugrin Triome, Inkmoth Nexus. Requiring two loaded modifier cards excluded them by
   construction. **Fixing causes 1 and 2 alone still failed at 53.7%**, so this was
   the binding constraint, not the regex quality.

**Jon's ruling (2026-07-24): relax the threshold to `>= 1`.** His reasoning: a single
continuous effect can still produce a genuine layer interaction against the object's
own characteristics (Dryad Arbor under a type-changer; the Blood Moon family). He
also directed that the blue *"nonbasic lands are Islands"* family be covered, which
cause 2 above does. On the pre-named fallback: *"classification is more durable and
something we should do when it makes sense"* — so **roadmap item 5 (question
classification) stays the intended long-term answer**, and this trigger is the
shipping-now mechanism, not a claim that regexes are the right end state.

The cost asymmetry supports the looser threshold: a false negative is a
non-regression (the model answers in prose as it does today), while a false positive
costs one tool round trip and a refusal the model can ignore. At 5.1% measured over
the whole corpus, that is cheap.

**Note for Slice 4:** the pseudocode above reads `_oracle_all_faces(c)`, not
`c.oracle_text`. Oracle text on this project's `Card` contract is per-face
(`Card.faces[i].oracle_text`); the top-level field happens to carry a joined value
today, but the faces union is the contract-correct read and is what was measured.

### 3d. Wiring into `answer.py` — four must-fixes, not three

The handoff and `DECISIONS.md` both name three `use_cost_tool` gates. **There is a
fourth, and it is worse than the other three.** All line numbers verified against
`src/rulesagent/generate/answer.py` at HEAD.

*(Note: the handoff writes the path as `answer.py`; the real path is
`src/rulesagent/generate/answer.py`.)*

1. **`:1452`** — `if use_cost_tool and is_last_round:` sets
   `tool_choice: {"type": "none"}`. A layers-only trigger skips this and
   **reinherits the cap-exhaustion bug `1dfe6d4` just fixed.**
2. **`:1475`** — `if use_cost_tool and getattr(response, "stop_reason", None) ==
   "tool_use":` gates entry into the round-trip continuation. A layers-only call
   returning `tool_use` falls through to `break` with the tool never executed and
   `parsed_output` of `None` — a silently wasted round.
3. **`:1507`** — `if use_cost_tool: self.last_tool_calls = ...`. Layers calls would
   be invisible to telemetry.
4. **`:1486-1488` — the dispatch loop has no `block.name` branch at all:**

   ```python
   for block in response.content:
       if getattr(block, "type", None) == "tool_use":
           result = _run_calculate_cost(block.input)
   ```

   It calls `_run_calculate_cost` **unconditionally** on any `tool_use` block,
   because there has only ever been one tool. Register a second and every
   `resolve_layers` call gets fed to the cost calculator, which returns
   `{"ok": false, "error": ...}` about a missing `base_cost` — a wrong-but-plausible
   tool_result handed back to the model. This is the highest-risk item in the whole
   build and it is *not* in the combat plan's §11.4 list.

Fixes 1–3 are one boolean each (`use_cost_tool` → `use_any_tool`, computed once as
`use_cost_tool or use_layers_tool`). Fix 4 is a name branch:

```python
_TOOL_DISPATCH = {
    "calculate_cost": _run_calculate_cost,
    "resolve_layers": _run_resolve_layers,
}
...
handler = _TOOL_DISPATCH.get(block.name)
result = handler(block.input) if handler else {
    "ok": False, "error": f"unknown tool: {block.name!r}"}
```

Also needed: `extra_kwargs["tools"]` becomes a built list rather than the hardcoded
`[CALCULATE_COST_TOOL]`, and `TOOL_TRIGGER_SENTENCE` becomes per-tool so a layers
question does not get the cost tool's instruction sentence appended.

**`TOOL_ROUND_CAP` — I disagree with the handoff's assumption, with evidence.**
The handoff says the cap "likely needs raising." For *combat* that was forced:
double-strike needs two **sequentially dependent** calls (§11.4), and there are only
two tool-capable rounds. **Layers is a one-call use case** — the whole point is that
a single resolution answers the question. Current sizing:

```python
TOOL_ROUND_CAP = 3   # answer.py:840
```

giving rounds 0 and 1 tool-capable and round 2 forced-answer. A layers question uses
round 0 to call and round 1 to answer, never touching round 2. Even a self-correcting
second call fits. A layers+cost co-fire fits in one round when independent (§11.4
finding 1), and a *sequentially dependent* layers→cost chain is not a shape I can
construct — layers resolves characteristics, cost resolves 601.2f mana, and neither
needs the other's output.

I recommended leaving it at 3 for v1. **Jon ruled to raise it to 4 (§8.3)** — that
is the number to build. Rounds 0–2 become tool-capable and round 3 is the
forced-answer round. Slice 4 makes the change; Slice 5 measures whether the extra
round is used.

---

## 4. Where the inputs come from

The model builds the payload from what it already has, and the seeds show it can:

- `base` — printed characteristics from **oracle text via Scryfall**, already in
  context on every card question. This is the same data the strategy note says the
  model actually answers from.
- `layer` / sublayer per part — the model's own reading. **Empirically reliable:** all
  four seeds have correct layer assignments in the prose, including rg3868's split of
  one ability across 5/6/7c and rg811's 7b-before-7c sublayer note.
- `timestamp` — from the scenario's stated order of events, plus CR 613.7a–n for the
  special cases. sonnet got these right on all four, including rg811's face-up
  re-timestamp.
- `source_id` grouping — the new ask. The model must recognise that one ability
  producing three effects is *one* source. Wayward Angel's threshold is the canonical
  case and sonnet already described it as a single ability with three consequences.
- `depends_on` / `dependency_reason` — the weak input (§1.3, §5.2).

**The tool's own description is a delivery vehicle for CR 613.6 and 613.8a.** Both
get quoted verbatim in the schema description, which puts them in context precisely
when a layers question is being answered — the thing rg633's retrieval failed to do.

---

## 5. The honest failure mode

### 5.1. This tool is confidently wrong in a way `calculate_cost` is not

`calculate_cost`'s payload is thin: a base cost and a few `{kind, amount, cite}`
triples. If the model mislabels one, the number is off and usually obviously so.

**`resolve_layers`'s payload is most of the reasoning.** A mis-assigned layer, a
flipped timestamp, or a wrong `source_id` grouping produces a *fully coherent, fully
traced, wrong* answer that the model will then present with more confidence than its
own prose would have carried. That is a genuine regression risk and it did not exist
for the cost tool. It is the strongest argument against building this, and it is why
§6.2 measures **regressions on currently-passing questions**, not just fixes.

Mitigations, none of them complete: the `trace` makes the failure inspectable; the
refusal list (§3b) catches structurally impossible payloads rather than computing
them; equal timestamps refuse instead of tie-breaking; and under option B the
`expect`/warning mechanism (§3a) surfaces predicate mistakes as countable
disagreements.

Worth naming the asymmetry that limits all of them: a **structurally impossible**
payload gets refused, but a **structurally valid, semantically wrong** one gets
computed faithfully. Layer assignment, timestamp order and `source_id` grouping all
fall in the second category — the engine has no way to know a plausible layer is the
wrong layer. That is the irreducible residue, and the regression arm is the only
instrument that measures it.

### 5.2. Dependency is the soft spot

rg633 already demonstrated the model asserting a dependency that CR 613.8a does not
support. The engine will honour it. `dependency_reason` forces articulation and
makes the error visible in telemetry; it does not prevent it.

And this is not a corner: **17 of the 68 CR-613 rows cite 613.8a and 9 cite 613.8b**
(§1.4). Roughly a quarter of the target set turns on a dependency judgment the tool
takes on faith. So the realistic ceiling here is not "fixes layers questions" — it
is "fixes the ordering-and-persistence half, and is neutral-to-harmful on the
dependency half." §6.2's regression arm is what tells us which way that quarter
moves.

### 5.3. Schema-size risk

The cost tool's schema is one nested object plus a small array. This one is a list of
objects with a union-typed `operation` and (under option B) a predicate object.
Larger schemas raise the malformed-call rate. The `{"ok": false, "error": ...}`
contract handles this gracefully — the model sees the error and re-calls — but that
costs a round, which is the second reason §3d's cap analysis matters.

### 5.4. Scope creep is the standing temptation

Every excluded case in §2's table will look like "just one more operation kind."
Layer 1 copy effects especially. **The v1 line holds until measured otherwise.**

---

## 6. Verification

### 6.1. The control arm — run this first, it is nearly free

**Three of the four misses are one rule: CR 613.6.** Before building anything, the
cheapest possible intervention is a single system-prompt bullet quoting 613.6 and
611.3a. If that alone recovers rg3868/rg807/rg811, the tool has to justify itself
against *that* baseline, not against today's.

I think the prompt bullet will partially work and be unreliable — sonnet already
*knew* 613.6 in rg3868 and still violated it mid-answer, which is the signature of a
consistency failure rather than a knowledge gap, and prompts do not fix consistency
failures the way engines do. But that is a hypothesis, and it is cheap to test:
one prompt variant, the same four questions, a handful of reps.

**RULED (Jon, 2026-07-24): the tool must TIE OR BEAT the control arm.** Not
strictly beat.

The reasoning corrects something I had backwards. I had written that if the prompt
bullet recovers all three, the plan should close and the free win be taken. That was
too generous to the control arm, because **the two interventions do not carry
symmetric risk**:

- A **system-prompt bullet applies to every question in the corpus.** It is a global
  change, and it can regress questions that have nothing to do with layers.
- The **tool only fires when triggered** (§3c). Its blast radius is bounded to
  questions that trip both conjuncts.

So a tie is genuinely enough to prefer the tool: same win, smaller blast radius.

**Consequence for the measurement:** the control arm is *not* free and does not get
to skip the regression check. Slice 0 measures the prompt variant on the four seeds
**and** on a non-layers regression sample. Slice 5 does the same for the tool
(§6.2). Both arms report win-rate *and* regression, and they are compared on both
numbers — not on the seed recoveries alone.

**Recommendation: still run the control arm as Slice 0, before Slice 1.** Its value
is now diagnostic rather than a kill switch: if a bullet recovers all three, the
613.6 failure is a prompting problem and the tool's job gets easier to size; if it
does not, that confirms §1.2's read that this is a consistency failure rather than a
knowledge gap.

### 6.2. The real test set

Four seeds is not a test set — the cost plan made the same admission about c014 and
the combat plan about c020.

- **Unit tests (no API, no cap dependency):** the four seed traces from §3b.5 as
  exact expected outputs, plus CR 613.4d's three switch examples and 613.5's two
  examples, all of which are verbatim in the rules text and are free, authoritative
  test vectors. Plus every refusal in §3b. **These run today** — the API cap does not
  touch them.
- **Live arm (blocked until 2026-08-01 or Jon raises the cap):** the COMPUTE bucket
  from §10 item 1, tool-on vs tool-off, same judge (`judge_bakeoff` + gpt-5-mini,
  **frozen, never reworded**).
- **Regression arm, non-negotiable given §5.1:** the currently-*passing* layers
  questions, tool-on. A tool that fixes 3 and breaks 3 is not a win, and this is the
  measurement combat's plan would also have needed.

Grading verdicts are Jon's. The tool routes and ranks; it never assigns a verdict.

### 6.3. Evidence discipline

Aggregate before claiming a rate; a single favourable run is not a rate. Long runs
use `PYTHONUNBUFFERED=1` plus a log file, never `| tail` (it masks the exit code).

---

## 7. Non-goals

- Not a general Magic rules engine. No stack, no priority, no state-based actions, no
  zone changes, no combat.
- Not a card-text parser. Never infers an effect from oracle text.
- Not a dependency analyser (§2, §5.2).
- Not a replacement for the model's reasoning — it is the bookkeeping the reasoning
  hands off.
- Does not touch the retrieval side. The rewriter/coverage question stays separate.
- Does not translate characteristics into game consequences (rg633's "taps for {R}").

---

## 8. What Jon rules on

**8.1. `applies_if` — RULED (Jon, 2026-07-24): option B**, the six-predicate enum,
with the four anti-silent-gating mechanisms from §3a shipping alongside it in Slice
2. Option A is off the table. Nothing further to rule on here.

**8.2. Control arm — RULED (Jon, 2026-07-24): tie or beat.** The tool must match or
exceed the §6.1 prompt-bullet arm, not strictly beat it, because the prompt bullet is
a global change with its own regression exposure while the tool's blast radius is
bounded to triggered questions. Both arms now carry a regression measurement (§6.1,
§6.2). Nothing further to rule on here.

**8.3. `TOOL_ROUND_CAP` — RULED (Jon, 2026-07-24): raise it to 4.** I had
recommended leaving it at 3 (reasoning and the combat contrast in §3d); Jon ruled to
raise it. Proceeding with 4.

At 4 the loop runs rounds 0–3, giving **3 tool-capable rounds plus a forced-answer
round** (round 3 is `is_last_round` and carries `tool_choice: {"type": "none"}`).
For layers that is one call plus two rounds of slack — headroom for a self-correcting
re-call after reading the trace, and for a layers/cost sequential chain if one ever
turns out to exist. The cost is the one named in §3d: a pathological loop burns one
more full API call — the most expensive one, since the message list has grown — before
the forced round stops it.

The `1dfe6d4` cap-exhaustion guard is unaffected by the change: the forced-answer
round is keyed to `TOOL_ROUND_CAP - 1`, so it moves with the cap rather than being
pinned to round 2. Raising the number does not reopen that bug.

**Slice 5's round-usage histogram is the retrospective check** — if the extra round
goes unused across the 51-row run, that is evidence for dropping back to 3 later; if
it gets consumed, the ruling was right and there is data saying so.

**8.4. The base-rate gate is CLEARED.** I set the threshold at ~15 COMPUTE-bucket
questions before the count landed, specifically so it could not be rationalised
after the fact. It came back at **51**. Combat's was 7. Nothing to rule on here —
recording it so the bar is visible.

**What would change my mind on the whole plan:** the control arm (6.1) recovering all
three 613.6 misses reliably; a regression arm showing the payload's fragility (§5.1)
costing more than the fixes gain; or the §3c trigger missing its calibration bar,
which would mean the tool can be right and still never fire.

---

## 9. Build slices (only after Jon rules)

TDD throughout. One commit per slice on `master`, heredoc message, `Co-Authored-By:
Claude Opus 4.8` trailer. Python is `.venv/Scripts/python.exe`,
`PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`. Jon runs the app on port 8000 —
never bind or kill it. **No agent runs `git add -A` or `git add .`; every commit
stages named paths only.**

**Slice 0 — the control arm (§6.1).** No tool code. One prompt variant with 613.6 +
611.3a quoted, run on the four seeds *and* on a non-layers regression sample, several
reps, aggregated. Blocked on the API cap. Per the §8.2 ruling this is no longer a
kill switch — it is the baseline the tool must tie or beat on **both** win-rate and
regression.

**Slice 1 — the pure engine, layers 4/5/6 only.**
Create `src/rulesagent/tools/layer_resolver.py`, `tests/test_layer_resolver.py`.
Module docstring quotes CR 613.1a–g, 613.3, 613.6, 613.7 verbatim from
`data/raw/MagicCompRules 20260619.txt` — the citations get pasted from this
document's quotations, never retyped from memory. Tagged-dict return, no raises.
First failing test is rg811's layer-6 ordering (remove-all at ts 1, then grant at
ts 2, expecting `[Trample, upkeep-sac]` and *not* Flying/Vigilance) — it is the one
that isolates ordering with nothing else moving.

**Slice 2 — layer 7a–7d and the 613.6 gate.** The `is_active` gate from §3b, then
the four seed traces from §3b.5 as exact expected outputs, then CR 613.4d's three
switch examples verbatim. Under option B, `applies_if` lands here **together with all
four anti-silent-gating mechanisms** (§3a): skip entries in the trace, top-level
`skipped_count`/`skipped`, the `expect` field and its disagreement warning, and the
telemetry hook. They are not a later hardening pass — a predicate without its skip
signal is the exact failure mode the mechanisms exist to prevent, so they ship in the
same commit. Tests must include a deliberate expectation mismatch asserting a warning
is emitted and `ok` stays `true`.

**Slice 3 — 613.8b dependency ordering + the full refusal list (§3b).** Includes the
loop-falls-back-to-timestamp case, which 613.8b states and the CR never illustrates.

**Slice 4 — wiring.** The `RESOLVE_LAYERS_TOOL` schema dict, `_needs_layers_tool`,
`_run_resolve_layers`, and **all four `answer.py` fixes from §3d in one commit** —
they are one atomic change and splitting them ships a broken intermediate state.
Tests extend `tests/test_cost_tool_loop.py`'s scripted-fake-client pattern; a test
asserting a `resolve_layers` block does **not** reach `_run_calculate_cost` is
mandatory (fix 4). No live API call anywhere in this slice.

**Slice 5 — live validation (§6.2).** Blocked on the API cap. Tool-on vs tool-off
over the 51-row COMPUTE bucket, plus the regression arm, compared against Slice 0's
control arm on **both** win-rate and regression (§8.2 ruling). Frozen judge. Also
record, free with this run, the **round-usage histogram** — how many layers attempts
consume both tool-capable rounds. That is the measurement that settles §8.3: near
zero means `TOOL_ROUND_CAP = 3` is right; a meaningful share reaching the forced
round with an unfinished tool sequence means raise it, with data rather than
assumption.

Slices 1–4 are fully unblocked by the API cap. Slices 0 and 5 are not.

---

## 10. Open items

1. ~~COMPUTE-bucket classification~~ — **DONE.** 51 of 68 (§1.4). Gate cleared (§8.4).
2. ~~Trigger calibration~~ — **DONE, and it initially FAILED.** The trigger as
   originally written scored **20.4%** bucket-A recall against a 60% bar. Two pattern
   defects (`gets?`, land subtypes) and **Jon's ruling to relax the threshold to
   `>= 1`** bring it to **77.8% recall at 5.1% firing over the full 1,341-row
   non-layers pool — PASS**. Full table, causes and ruling in §3c "CALIBRATION
   RESULT". Buckets persisted to `evals/_layers_buckets.json` so this never has to be
   re-derived. **Slice 4 is unblocked.** Roadmap item 5 (question classification)
   remains the durable answer per Jon, to be done when it makes sense.
3. ~~`applies_if` fork~~ — **RULED: option B** with the four anti-silent-gating
   mechanisms (§8.1). Lands in Slice 2.
4. ~~Does the tool have to beat the control arm?~~ — **RULED: tie or beat** (§8.2).
   Both arms now carry a regression measurement. The control-arm *result* is still
   blocked on the API cap.
5. **613.8c non-implementation** (§2) — documented limitation; revisit only if the
   COMPUTE bucket shows real cases needing mid-walk re-evaluation.
6. **rg1268** was listed as a possible fifth seed. It is **not** a layer-system
   question: its gold cites `205.1b`, `611.1`, `712.17` — no 613 rule at all — and
   the crux is that a transforming double-faced permanent is not a new object
   (CR 712.17). Excluding it, and noting it here so it does not get re-added later.

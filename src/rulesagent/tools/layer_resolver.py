"""Deterministic layer-system resolver -- Slice 2 (docs/plan-layer-system-tool.md).

Pure Python, no LLM, no I/O, no network, no card lookup -- the same discipline
as tools/cost_calculator.py. Given a base characteristics object and a list of
already-classified, already-layer-assigned continuous-effect parts, applies
them in CR 613 order and returns the resulting characteristics plus a
per-step trace. This module never decides which layer an effect belongs to,
never assigns a timestamp, and never decides whether a dependency exists --
those are the CALLER's job (plan Sec 2).

**Slice 2 adds** layer 2 (control) and layers 7a-7d (power/toughness) to
Slice 1's layers 4/5/6, plus three load-bearing mechanisms:

1. The CR 613.6 `is_active` gate -- an ability whose effect has *started* to
   apply keeps applying in later layers even after the ability generating it
   is removed, but an ability that has *not yet* started never begins if it
   is removed first. Grounding, pasted verbatim from
   `data/raw/MagicCompRules 20260619.txt`:

    613.6. If an effect should be applied in different layers and/or
    sublayers, the parts of the effect each apply in their appropriate
    ones. If an effect starts to apply in one layer and/or sublayer, it
    will continue to be applied to the same set of objects in each other
    applicable layer and/or sublayer, even if the ability generating the
    effect is removed during this process.

   Implemented exactly per plan Sec 3b:

       def is_active(part, layer_index):
           r = removed_at.get(part.source_id)
           if r is None:            return True     # never removed
           if r > layer_index:      return True     # removed later than now
           s = started.get(part.source_id)
           return s is not None and s <= r          # started before/at removal -> continues

   The converse matters as much as the forward case: an ability whose only
   part is in a later layer, whose source is removed earlier and never
   started, correctly does NOT apply (`s is None` fails the final check).

2. `applies_if` -- CR 613.5 conditional applicability, **option B** (Jon's
   ruling, plan Sec 8.1): a closed six-predicate enum, evaluated against LIVE
   state at the moment of application, no expression language, no nesting:
   `has_no_abilities`, `has_ability`, `has_color`, `has_type`, `has_subtype`,
   `power_gte`.

3. The four anti-silent-gating mechanisms (plan Sec 3a), shipped in this same
   slice alongside the predicates rather than as later hardening:
   (a) the trace records every non-application, with the evaluated reason
       and the state checked against; (b) a top-level `skipped_count` /
   `skipped` list, so a nested trace entry cannot be skimmed past;
   (c) an `expect` boolean on `applies_if` -- engine/model disagreement
       produces a **warning**, not a refusal, because the engine's
       computation is correct and it is the model's expectation that was
       wrong; (d) the return dict carries `warnings` / `skipped_count` /
       `skipped` at the top level so a caller (`answer.py`, Slice 4) can log
       them -- this module does not itself do any logging or telemetry.

613.1g, extending Slice 1's 613.1 quotation to the layer this slice adds:

    613.1g Layer 7: Power- and/or toughness-changing effects are applied.

613.4, the sublayer-and-ordering rule for layer 7 (mirrors 613.3's role for
layers 2-6, quoted in the Slice 1 docstring below):

    613.4. Within layer 7, apply effects in a series of sublayers in the
    order described below. Within each sublayer, apply effects in
    timestamp order. (See rule 613.7.) Note that dependency may alter the
    order in which effects are applied within a sublayer. (See rule
    613.8.)

    613.4a Layer 7a: Effects from characteristic-defining abilities that
    define power and/or toughness are applied. See rule 604.3.

    613.4b Layer 7b: Effects that set power and/or toughness to a specific
    number or value are applied. Effects that refer to the base power
    and/or toughness of a creature apply in this layer.

    613.4c Layer 7c: Effects and counters that modify power and/or
    toughness (but don't set power and/or toughness to a specific number
    or value) are applied.

    613.4d Layer 7d: Effects that switch a creature's power and toughness
    are applied. Such effects take the value of power and apply it to the
    creature's toughness, and take the value of toughness and apply it to
    the creature's power.
    Example: A 1/3 creature is given +0/+1 by an effect. Then another
    effect switches the creature's power and toughness. Its new power and
    toughness is 4/1. A new effect gives the creature +5/+0. Its
    "unswitched" power and toughness would be 6/4, so its actual power and
    toughness is 4/6.
    Example: A 1/3 creature is given +0/+1 by an effect. Then another
    effect switches the creature's power and toughness. Its new power and
    toughness is 4/1. If the +0/+1 effect ends before the switch effect
    ends, the creature becomes 3/1.
    Example: A 1/3 creature is given +0/+1 by an effect. Then another
    effect switches the creature's power and toughness. Then another
    effect switches its power and toughness again. The two switches
    essentially cancel each other, and the creature becomes 1/4.

613.5, two worked examples this module is checked against directly (the
Honor of the Pure example is CR 613.5's own canonical `applies_if` shape --
`{"has_color": "W"}` -- and the Gray Ogre example proves 7b always applies
before 7c regardless of relative timestamp/resolution order):

    613.5. The application of continuous effects as described by the
    layer system is continually and automatically performed by the game.
    All resulting changes to an object's characteristics are
    instantaneous.
    Example: Honor of the Pure is an enchantment that reads "White
    creatures you control get +1/+1." Honor of the Pure and a 2/2 black
    creature are on the battlefield under your control. If an effect then
    turns the creature white (layer 5), it gets +1/+1 from Honor of the
    Pure (layer 7c), becoming 3/3. If the creature's color is later
    changed to red (layer 5), Honor of the Pure's effect stops applying to
    it, and it will return to being 2/2.
    Example: Gray Ogre, a 2/2 creature, is on the battlefield. An effect
    puts a +1/+1 counter on it (layer 7c), making it 3/3. A spell
    targeting it that says "Target creature gets +4/+4 until end of turn"
    resolves (layer 7c), making it 7/7. An enchantment that says
    "Creatures you control get +0/+2" enters the battlefield (layer 7c),
    making it 7/9. An effect that says "Target creature becomes 0/1 until
    end of turn" is applied to it (layer 7b), making it 5/8 (0/1, with
    +4/+4 from the resolved spell, +0/+2 from the enchantment, and +1/+1
    from the counter).

**Ability-source bookkeeping for the 613.6 gate.** To know whether a
source's ability was "removed" (for the purposes of `is_active`), this
module tracks which currently-present ability TEXT was contributed by which
`source_id` -- populated whenever an `add_abilities` part actually adds new
text, and (so an ability printed on the object itself, not granted by any
part in this call, can also be tracked as "removed") pre-seeded at
initialisation as `{text: text for text in base.abilities}`. That pre-seed
is inert unless a part's `source_id` is deliberately written to match one of
the object's own printed ability strings -- the natural convention for "this
part comes from the same printed ability that also grants this text".
When a `remove_abilities` / `remove_all_abilities` / `cant_have_abilities`
part applies, every currently-tracked source whose text is stripped gets
`removed_at[source] = this layer's index`. A source that never contributes
(or is never pre-seeded with) any tracked ability text -- e.g. Muraganda
Petroglyphs' land-based static ability in rg3868 -- is never marked
"removed"; its conditional applicability is governed entirely by
`applies_if`, which is the correct CR reading (that ability was never one of
the creature's own abilities to begin with, so nothing ever strips it).

**Still out of Slice 2** (see plan Sec 9, Slice 3): CR 613.8 dependency
ordering. A part carrying a non-empty `depends_on` is still refused, for the
same reason as Slice 1 -- this module cannot yet compute the CR 613.8b
wait-until-after ordering, and applying such a part in plain timestamp order
instead would be a silent wrong answer.

    613.8a An effect is said to "depend on" another if (a) it's applied in
    the same layer (and, if applicable, sublayer) as the other effect; (b)
    applying the other would change the text or the existence of the first
    effect, what it applies to, or what it does to any of the things it
    applies to; and (c) neither effect is from a characteristic-defining
    ability or both effects are from characteristic-defining abilities.
    Otherwise, the effect is considered to be independent of the other
    effect.

Refuses rather than guesses: malformed/missing `base`, an unknown layer
token, an `operation.kind` illegal for its declared layer, a non-integer
timestamp (bool is explicitly rejected), two parts in the same layer sharing
a timestamp (never tie-broken), a duplicate part `id`, an unknown colour
token, a malformed `applies_if` (wrong shape, unknown predicate key, wrong
value type for its predicate), and a present-and-non-empty `depends_on`
(Slice 3 feature). All of these return `{"ok": False, "error": "..."}` --
this module never raises for an input-shape problem and never produces a
best-effort characteristics object it can't stand behind.
"""

from __future__ import annotations

import json

_VALID_COLORS = ("W", "U", "B", "R", "G")

# The full CR 613.1 layer enum. Slice 2 resolves all of them.
_LAYER_ORDER = ["2", "4", "5", "6", "7a", "7b", "7c", "7d"]
_KNOWN_LAYERS = tuple(_LAYER_ORDER)
_LAYER_INDEX = {layer: i for i, layer in enumerate(_LAYER_ORDER)}

_LAYER_OPERATION_KINDS = {
    "2": {"set_controller"},
    "4": {"set_types", "add_types", "remove_types"},
    "5": {"set_colors", "add_colors"},
    "6": {"add_abilities", "remove_abilities", "remove_all_abilities", "cant_have_abilities"},
    "7a": {"cda_pt"},
    "7b": {"set_pt"},
    "7c": {"modify_pt"},
    "7d": {"switch_pt"},
}

# Ability-removing operation kinds that feed the CR 613.6 removed_at
# bookkeeping. cant_have_abilities is included alongside the plan's named
# pair (remove_all_abilities, remove_abilities) because it clears the
# object's abilities exactly like remove_all_abilities does (Slice 1
# docstring, CR 113.11) -- an ability wiped by "can't have abilities" must
# gate later-layer continuations the same way an ability wiped by
# "remove all abilities" does, or 613.6 would silently not apply to it.
_ABILITY_REMOVING_KINDS = ("remove_abilities", "remove_all_abilities", "cant_have_abilities")

_PREDICATE_KINDS = (
    "has_no_abilities",
    "has_ability",
    "has_color",
    "has_type",
    "has_subtype",
    "power_gte",
)

_TYPE_CATEGORY_FIELDS = ("card_types", "subtypes", "supertypes")

_BASE_LIST_FIELDS = ("card_types", "supertypes", "subtypes", "abilities")


def _is_nonneg_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_str_list(v: object) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _validate_base(base: object) -> str | None:
    """Returns an error string, or None if base is well-formed."""
    if base is None:
        return "no base provided -- nothing to resolve layers against"
    if not isinstance(base, dict):
        return f"base must be an object, got {type(base).__name__}"
    for field in _BASE_LIST_FIELDS:
        if field not in base:
            continue
        v = base[field]
        if not _is_str_list(v):
            return f"base.{field} must be a list of strings, got {v!r}"
    if "colors" in base:
        colors = base["colors"]
        if not _is_str_list(colors):
            return f"base.colors must be a list of strings, got {colors!r}"
        for c in colors:
            if c not in _VALID_COLORS:
                return f"base.colors has an unknown color token {c!r} (expected one of {_VALID_COLORS})"
    return None


def _validate_operation(layer: str, operation: object) -> str | None:
    if not isinstance(operation, dict):
        return f"operation must be an object, got {type(operation).__name__}"
    kind = operation.get("kind")
    legal_kinds = _LAYER_OPERATION_KINDS.get(layer, set())
    if kind not in legal_kinds:
        return (
            f"operation.kind {kind!r} is not legal for layer {layer!r} "
            f"(expected one of {sorted(legal_kinds)})"
        )

    if kind in ("set_types", "add_types", "remove_types"):
        for field in _TYPE_CATEGORY_FIELDS:
            if field not in operation:
                continue
            v = operation[field]
            if not _is_str_list(v):
                return f"operation.{field} must be a list of strings, got {v!r}"
        return None

    if kind in ("set_colors", "add_colors"):
        value = operation.get("value")
        if not _is_str_list(value):
            return f"operation.value must be a list of colors, got {value!r}"
        for c in value:
            if c not in _VALID_COLORS:
                return f"operation.value has an unknown color token {c!r} (expected one of {_VALID_COLORS})"
        return None

    if kind in ("add_abilities", "remove_abilities"):
        value = operation.get("value")
        if not _is_str_list(value):
            return f"operation.value must be a list of strings, got {value!r}"
        return None

    if kind == "set_controller":
        value = operation.get("value")
        if not isinstance(value, str) or not value:
            return f"operation.value must be a non-empty string, got {value!r}"
        return None

    if kind in ("cda_pt", "set_pt", "modify_pt"):
        for field in ("power", "toughness"):
            v = operation.get(field)
            if not _is_int(v):
                return f"operation.{field} must be an integer, got {v!r}"
        return None

    # remove_all_abilities / cant_have_abilities / switch_pt: no further
    # fields required.
    return None


def _validate_applies_if(applies_if: object) -> str | None:
    """Returns an error string, or None if applies_if is well-formed.
    `None` (omitted / null) is always well-formed -- it means no predicate."""
    if applies_if is None:
        return None
    if not isinstance(applies_if, dict):
        return f"applies_if must be an object, got {type(applies_if).__name__}"

    if "expect" in applies_if:
        expect = applies_if["expect"]
        if not isinstance(expect, bool):
            return f"applies_if.expect must be a boolean, got {expect!r}"

    predicate_keys = [k for k in applies_if if k != "expect"]
    if len(predicate_keys) != 1:
        return (
            f"applies_if must have exactly one predicate key (one of "
            f"{_PREDICATE_KINDS}), got {predicate_keys!r}"
        )
    key = predicate_keys[0]
    if key not in _PREDICATE_KINDS:
        return (
            f"applies_if has an unknown predicate key {key!r} (expected one "
            f"of {_PREDICATE_KINDS})"
        )
    value = applies_if[key]
    if key == "has_no_abilities":
        if not isinstance(value, bool):
            return f"applies_if.has_no_abilities must be a boolean, got {value!r}"
    elif key in ("has_ability", "has_type", "has_subtype"):
        if not isinstance(value, str) or not value:
            return f"applies_if.{key} must be a non-empty string, got {value!r}"
    elif key == "has_color":
        if value not in _VALID_COLORS:
            return (
                f"applies_if.has_color has an unknown color token {value!r} "
                f"(expected one of {_VALID_COLORS})"
            )
    elif key == "power_gte":
        if not _is_int(value):
            return f"applies_if.power_gte must be an integer, got {value!r}"
    return None


def _validate_part(p: object) -> str | None:
    if not isinstance(p, dict):
        return f"each effect part must be an object, got {type(p).__name__}"

    part_id = p.get("id")
    if not isinstance(part_id, str) or not part_id:
        return f"part.id must be a non-empty string, got {part_id!r}"

    source_id = p.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        return f"part {part_id!r}: source_id must be a non-empty string, got {source_id!r}"

    layer = p.get("layer")
    if layer not in _KNOWN_LAYERS:
        return f"part {part_id!r}: unknown layer token {layer!r} (expected one of {_KNOWN_LAYERS})"

    timestamp = p.get("timestamp")
    if not _is_nonneg_int(timestamp):
        return f"part {part_id!r}: timestamp must be a non-negative integer, got {timestamp!r}"

    is_cda = p.get("is_cda", False)
    if not isinstance(is_cda, bool):
        return f"part {part_id!r}: is_cda must be a boolean, got {is_cda!r}"

    applies_if_err = _validate_applies_if(p.get("applies_if"))
    if applies_if_err:
        return f"part {part_id!r}: {applies_if_err}"

    depends_on = p.get("depends_on")
    if depends_on:
        if not isinstance(depends_on, list) or not all(isinstance(x, str) for x in depends_on):
            return f"part {part_id!r}: depends_on must be a list of part ids, got {depends_on!r}"
        return (
            f"part {part_id!r}: depends_on is not yet supported -- Slice 2 does not "
            f"implement CR 613.8b dependency ordering (see docs/plan-layer-system-tool.md "
            f"Sec 9, Slice 3). Leave depends_on empty/null for this slice."
        )

    cite = p.get("cite", "")
    if not isinstance(cite, str):
        return f"part {part_id!r}: cite must be a string, got {type(cite).__name__}"

    return _validate_operation(layer, p.get("operation"))


def _apply_type_op(state: dict, operation: dict) -> None:
    kind = operation["kind"]
    for field in _TYPE_CATEGORY_FIELDS:
        if field not in operation:
            continue
        values = operation[field]
        if kind == "set_types":
            state[field] = list(values)
        elif kind == "add_types":
            current = state[field]
            for v in values:
                if v not in current:
                    current.append(v)
        elif kind == "remove_types":
            state[field] = [v for v in state[field] if v not in values]


def _apply_color_op(state: dict, operation: dict) -> None:
    kind = operation["kind"]
    value = operation["value"]
    if kind == "set_colors":
        state["colors"] = list(value)
    elif kind == "add_colors":
        current = state["colors"]
        for c in value:
            if c not in current:
                current.append(c)


def _apply_ability_op(state: dict, operation: dict, blocked: list[bool]) -> None:
    kind = operation["kind"]
    if kind == "add_abilities":
        if blocked[0]:
            return  # CR 113.11: an effect can't add an ability the object can't have.
        current = state["abilities"]
        for a in operation["value"]:
            if a not in current:
                current.append(a)
    elif kind == "remove_abilities":
        remove = set(operation["value"])
        state["abilities"] = [a for a in state["abilities"] if a not in remove]
    elif kind == "remove_all_abilities":
        state["abilities"] = []
    elif kind == "cant_have_abilities":
        state["abilities"] = []
        blocked[0] = True


def _apply_control_op(state: dict, operation: dict) -> None:
    state["controller"] = operation["value"]


def _apply_pt_op(state: dict, operation: dict) -> None:
    kind = operation["kind"]
    if kind in ("cda_pt", "set_pt"):
        state["power"] = operation["power"]
        state["toughness"] = operation["toughness"]
    elif kind == "modify_pt":
        state["power"] = (state["power"] or 0) + operation["power"]
        state["toughness"] = (state["toughness"] or 0) + operation["toughness"]
    elif kind == "switch_pt":
        state["power"], state["toughness"] = (state["toughness"] or 0), (state["power"] or 0)


def _order_parts(parts: list[dict]) -> list[dict]:
    """CR 613.3/613.4: characteristic-defining abilities first, then
    everything else, each group in CR 613.7 timestamp order."""
    cdas = sorted((p for p in parts if p.get("is_cda", False)), key=lambda p: p["timestamp"])
    others = sorted((p for p in parts if not p.get("is_cda", False)), key=lambda p: p["timestamp"])
    return cdas + others


def _is_active(source_id: str, layer_index: int, started: dict, removed_at: dict) -> bool:
    """CR 613.6 gate -- plan Sec 3b, pasted through unchanged from the
    approved pseudocode (renamed to take source_id/layer_index directly
    rather than a whole part, since that is all it needs)."""
    r = removed_at.get(source_id)
    if r is None:
        return True  # never removed
    if r > layer_index:
        return True  # removed later than now
    s = started.get(source_id)
    return s is not None and s <= r  # started before/at removal -> continues


def _predicate_kind_and_value(applies_if: dict) -> tuple[str, object]:
    key = next(k for k in applies_if if k != "expect")
    return key, applies_if[key]


def _predicate_holds(applies_if: dict | None, state: dict) -> bool:
    if applies_if is None:
        return True
    key, value = _predicate_kind_and_value(applies_if)
    if key == "has_no_abilities":
        return (len(state["abilities"]) == 0) == value
    if key == "has_ability":
        return value in state["abilities"]
    if key == "has_color":
        return value in state["colors"]
    if key == "has_type":
        return value in state["card_types"]
    if key == "has_subtype":
        return value in state["subtypes"]
    if key == "power_gte":
        return state["power"] is not None and state["power"] >= value
    raise AssertionError(f"unreachable predicate kind {key!r} -- should have been refused by _validate_applies_if")


def _predicate_repr(applies_if: dict) -> str:
    key, value = _predicate_kind_and_value(applies_if)
    return json.dumps({key: value})


def _predicate_state_snapshot(applies_if: dict, state: dict) -> dict:
    key, _ = _predicate_kind_and_value(applies_if)
    if key in ("has_no_abilities", "has_ability"):
        return {"abilities": list(state["abilities"])}
    if key == "has_color":
        return {"colors": list(state["colors"])}
    if key == "has_type":
        return {"card_types": list(state["card_types"])}
    if key == "has_subtype":
        return {"subtypes": list(state["subtypes"])}
    if key == "power_gte":
        return {"power": state["power"]}
    raise AssertionError(f"unreachable predicate kind {key!r} -- should have been refused by _validate_applies_if")


def resolve_layers(base: dict | None, effects: list[dict] | None = None) -> dict:
    """Apply a list of caller-classified, caller-layer-assigned continuous
    effect parts to `base` in CR 613 order, for all eight layers/sublayers
    (2, 4, 5, 6, 7a, 7b, 7c, 7d -- see the module docstring for the Slice 2
    boundary: CR 613.8 dependency ordering is still Slice 3). Never raises on
    bad input; returns {"ok": False, "error": "..."} instead.

    base: {"name": str, "card_types": [str], "supertypes": [str],
           "subtypes": [str], "colors": [str], "abilities": [str],
           "power": int|None, "toughness": int|None, "controller": str|None}
          -- the object's copiable values, post-layer-1 (plan Sec 3a).
    effects: flat list of effect parts (plan Sec 3a table):
          {"id": str, "source_id": str,
           "layer": "2"|"4"|"5"|"6"|"7a"|"7b"|"7c"|"7d",
           "timestamp": int (>=0), "is_cda": bool,
           "depends_on": list[str]|None, "dependency_reason": str|None,
           "operation": {...},
           "applies_if": {<one of the six predicate keys>: ..., "expect": bool|None}|None,
           "cite": str}
          A non-empty `depends_on` is refused in this slice (Slice 3
          feature). `None`/omitted is treated as [].

    Returns on success:
      {"ok": True,
       "result": {"card_types": [...], "supertypes": [...],
                   "subtypes": [...], "colors": [...], "abilities": [...],
                   "power": ..., "toughness": ..., "controller": ...},
       "trace": [{"layer": str, "applied": part_id, "source_id": str,
                   "why": str, "state_after": {...}}, ...],
       "warnings": [str, ...],
       "skipped_count": int,
       "skipped": [{"id": part_id, "layer": str, "why": str}, ...],
       "dependencies_declared": bool}
    and on any malformed input: {"ok": False, "error": "..."}.
    """
    err = _validate_base(base)
    if err:
        return {"ok": False, "error": err}

    effects = effects or []
    if not isinstance(effects, list):
        return {"ok": False, "error": f"effects must be a list, got {type(effects).__name__}"}

    # dependencies_declared would flag any part that named a dependency, but
    # _validate_part below refuses any non-empty depends_on outright (Slice 2
    # does not implement CR 613.8b ordering), so a truthy declaration never
    # reaches a successful return in this slice. Always False for now;
    # Slice 3 makes this field meaningful.
    dependencies_declared = False
    seen_ids: set[str] = set()
    for p in effects:
        err = _validate_part(p)
        if err:
            return {"ok": False, "error": err}
        part_id = p["id"]
        if part_id in seen_ids:
            return {"ok": False, "error": f"duplicate part id: {part_id!r}"}
        seen_ids.add(part_id)

    # CR 613.7 refusal: two parts in the same layer/sublayer sharing a
    # timestamp are never tie-broken.
    for layer in _LAYER_ORDER:
        parts_in_layer = [p for p in effects if p["layer"] == layer]
        seen_ts: dict[int, str] = {}
        for p in parts_in_layer:
            ts = p["timestamp"]
            if ts in seen_ts:
                return {
                    "ok": False,
                    "error": (
                        f"layer {layer!r}: parts {seen_ts[ts]!r} and {p['id']!r} share "
                        f"timestamp {ts} -- CR 613.7 orders by timestamp and this cannot "
                        f"be tie-broken"
                    ),
                }
            seen_ts[ts] = p["id"]

    state = {
        "card_types": list(base.get("card_types", [])),
        "supertypes": list(base.get("supertypes", [])),
        "subtypes": list(base.get("subtypes", [])),
        "colors": list(base.get("colors", [])),
        "abilities": list(base.get("abilities", [])),
        "power": base.get("power"),
        "toughness": base.get("toughness"),
        "controller": base.get("controller"),
    }

    trace: list[dict] = []
    warnings: list[str] = []
    skipped: list[dict] = []
    abilities_blocked = [False]  # mutable cell for CR 113.11 cant_have_abilities

    # CR 613.6 bookkeeping.
    started: dict[str, int] = {}          # source_id -> earliest layer index it applied at
    removed_at: dict[str, int] = {}       # source_id -> layer index its ability was stripped at
    # Which source_id contributed which currently-present ability text.
    # Pre-seeded from base so a part whose source_id matches one of the
    # object's own printed abilities is trackable even though nothing in
    # `effects` ever "added" that text (see module docstring).
    ability_source: dict[str, str] = {text: text for text in state["abilities"]}

    for layer in _LAYER_ORDER:
        idx = _LAYER_INDEX[layer]
        parts_in_layer = [p for p in effects if p["layer"] == layer]
        ordered = _order_parts(parts_in_layer)
        for p in ordered:
            part_id = p["id"]
            source_id = p["source_id"]
            operation = p["operation"]

            if not _is_active(source_id, idx, started, removed_at):
                why = (
                    f"CR 613.6 gate: source ability {source_id!r} was removed at layer "
                    f"{_LAYER_ORDER[removed_at[source_id]]!r} and had not started applying "
                    f"at any earlier layer, so it does not begin applying here"
                )
                trace.append({
                    "layer": layer, "skipped": part_id, "source_id": source_id,
                    "why": why,
                    "state_checked": {k: (list(v) if isinstance(v, list) else v) for k, v in state.items()},
                })
                skipped.append({"id": part_id, "layer": layer, "why": why})
                continue

            applies_if = p.get("applies_if")
            predicate_result = _predicate_holds(applies_if, state)

            if applies_if is not None:
                expect = applies_if.get("expect")
                if expect is not None and expect != predicate_result:
                    warnings.append(
                        f"{part_id}: expected applies_if {_predicate_repr(applies_if)} to "
                        f"evaluate to {expect}, but at layer {layer!r} it evaluated to "
                        f"{predicate_result} against live state"
                    )

            if not predicate_result:
                why = f"applies_if {_predicate_repr(applies_if)} evaluated FALSE"
                trace.append({
                    "layer": layer, "skipped": part_id, "source_id": source_id,
                    "why": why,
                    "state_checked": _predicate_state_snapshot(applies_if, state),
                })
                skipped.append({"id": part_id, "layer": layer, "why": why})
                continue

            if layer == "2":
                _apply_control_op(state, operation)
                state_after = {"controller": state["controller"]}
            elif layer == "4":
                _apply_type_op(state, operation)
                state_after = {k: list(state[k]) for k in _TYPE_CATEGORY_FIELDS}
            elif layer == "5":
                _apply_color_op(state, operation)
                state_after = {"colors": list(state["colors"])}
            elif layer == "6":
                kind = operation["kind"]
                if kind in _ABILITY_REMOVING_KINDS:
                    if kind == "remove_abilities":
                        remove_set = set(operation["value"])
                        removed_texts = [a for a in state["abilities"] if a in remove_set]
                    else:  # remove_all_abilities / cant_have_abilities
                        removed_texts = list(state["abilities"])
                    _apply_ability_op(state, operation, abilities_blocked)
                    for text in removed_texts:
                        src = ability_source.pop(text, None)
                        if src is not None:
                            removed_at.setdefault(src, idx)
                else:  # add_abilities
                    before = set(state["abilities"])
                    _apply_ability_op(state, operation, abilities_blocked)
                    for a in state["abilities"]:
                        if a not in before:
                            ability_source[a] = source_id
                state_after = {"abilities": list(state["abilities"])}
            else:  # 7a / 7b / 7c / 7d
                _apply_pt_op(state, operation)
                state_after = {"power": state["power"], "toughness": state["toughness"]}

            r = removed_at.get(source_id)
            if r is not None:
                why = (
                    f"CR 613.6 -- source ability {source_id!r} was removed at layer "
                    f"{_LAYER_ORDER[r]!r} but had already applied at layer "
                    f"{_LAYER_ORDER[started[source_id]]!r}, so it continues "
                    f"(timestamp {p['timestamp']})"
                )
            elif p.get("is_cda"):
                why = f"CDA (CR 613.3), timestamp {p['timestamp']}"
            else:
                why = f"timestamp {p['timestamp']}"
            if applies_if is not None:
                why += f"; applies_if {_predicate_repr(applies_if)} evaluated TRUE"

            trace.append({
                "layer": layer,
                "applied": part_id,
                "source_id": source_id,
                "why": why,
                "state_after": state_after,
            })
            started.setdefault(source_id, idx)

    result = {
        "card_types": state["card_types"],
        "supertypes": state["supertypes"],
        "subtypes": state["subtypes"],
        "colors": state["colors"],
        "abilities": state["abilities"],
        "power": state["power"],
        "toughness": state["toughness"],
        "controller": state["controller"],
    }

    return {
        "ok": True,
        "result": result,
        "trace": trace,
        "warnings": warnings,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "dependencies_declared": dependencies_declared,
    }

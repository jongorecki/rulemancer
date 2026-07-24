"""Deterministic layer-system resolver -- Slice 1 (docs/plan-layer-system-tool.md).

Pure Python, no LLM, no I/O, no network, no card lookup -- the same discipline
as tools/cost_calculator.py. Given a base characteristics object and a list of
already-classified, already-layer-assigned continuous-effect parts, applies
them in CR 613 order and returns the resulting characteristics plus a
per-step trace. This module never decides which layer an effect belongs to,
never assigns a timestamp, and never decides whether a dependency exists --
those are the CALLER's job (plan Sec 2).

**Slice 1 scope only.** Layers 4 (type), 5 (colour) and 6 (abilities). Every
CR quotation below is pasted verbatim from
`data/raw/MagicCompRules 20260619.txt`, never retyped from memory -- a
previous plan in this repo shipped three wrong CR citations that way.

613.1, grounding the layer system itself:

    613.1. The values of an object's characteristics are determined by
    starting with the actual object. For a card, that means the values of
    the characteristics printed on that card. For a token or a copy of a
    spell or card, that means the values of the characteristics defined by
    the effect that created it. Then all applicable continuous effects are
    applied in a series of layers in the following order:

    613.1a Layer 1: Rules and effects that modify copiable values are
    applied.

    613.1b Layer 2: Control-changing effects are applied.

    613.1c Layer 3: Text-changing effects are applied. See rule 612,
    "Text-Changing Effects."

    613.1d Layer 4: Type-changing effects are applied. These include
    effects that change an object's card type, subtype, and/or supertype.

    613.1e Layer 5: Color-changing effects are applied.

    613.1f Layer 6: Ability-adding effects, keyword counters,
    ability-removing effects, and effects that say an object can't have an
    ability are applied.

    613.1g Layer 7: Power- and/or toughness-changing effects are applied.

613.3, the within-layer ordering rule this module implements for layers 4-6:

    613.3. Within layers 2-6, apply effects from characteristic-defining
    abilities first (see rule 604.3), then all other effects in timestamp
    order (see rule 613.7). Note that dependency may alter the order in
    which effects are applied within a layer. (See rule 613.8.)

613.7, the timestamp rule that breaks ties within each CDA/non-CDA group:

    613.7. Within a layer or sublayer, determining which order effects are
    applied in is usually done using a timestamp system. An effect with an
    earlier timestamp is applied before an effect with a later timestamp.

604.3a, quoted because `is_cda` is a caller-supplied boolean that feeds
613.3's ordering directly -- this module does not run the five-criterion
test itself, the caller does:

    604.3a A static ability is a characteristic-defining ability if it
    meets the following criteria: (1) It defines an object's colors,
    subtypes, power, or toughness; (2) it is printed on the card it
    affects, it was granted to the token it affects by the effect that
    created the token, or it was acquired by the object it affects as the
    result of a copy effect or text-changing effect; (3) it does not
    directly affect the characteristics of any other objects; (4) it is not
    an ability that an object grants to itself; and (5) it does not set the
    values of such characteristics only if certain conditions are met.

613.6 is quoted here for context on why layers 2 and 7a-7d are OUT of this
slice (see below), even though this module does not implement it yet:

    613.6. If an effect should be applied in different layers and/or
    sublayers, the parts of the effect each apply in their appropriate
    ones. If an effect starts to apply in one layer and/or sublayer, it
    will continue to be applied to the same set of objects in each other
    applicable layer and/or sublayer, even if the ability generating the
    effect is removed during this process.

**What this slice deliberately does NOT implement** (see plan Sec 9, Slice
2/3):

- Layer 2 (control) and layers 7a-7d (power/toughness). A part whose
  `layer` names one of these is a known-but-unsupported layer token and is
  refused, distinctly from an unknown layer token entirely -- see
  `_KNOWN_LAYERS` / `_SUPPORTED_LAYERS` below.
- The CR 613.6 `is_active` gate (an ability's effect continuing to apply in
  a later layer/sublayer after the ability itself is removed). Slice 1's
  layers (4, 5, 6) never need it in isolation -- 613.6 only matters when an
  ability's parts span *multiple* layers and one of them is removed before
  a later one runs, which requires 7a-7d to observe. It ships in Slice 2.
- `applies_if` (CR 613.5 conditional effects, the Option-B predicate enum).
  A part carrying a non-null `applies_if` is REFUSED in this slice with a
  "not yet supported" error, rather than silently ignored -- silently
  ignoring a predicate would produce a coherent, fully-traced, WRONG answer
  for exactly the reason plan Sec 3a's silent-gating discussion warns
  about. Ships in Slice 2.
- CR 613.8 dependency ordering. A part carrying a non-empty `depends_on` is
  likewise REFUSED rather than silently honoured or silently ignored, for
  the same reason: this module cannot compute the CR 613.8b wait-until-after
  ordering yet, and applying such a part in plain timestamp order instead
  would be a silent wrong answer. `depends_on: null` / `[]` is accepted
  (nothing to order). Grounding, so the choice is auditable:

    613.8a An effect is said to "depend on" another if (a) it's applied in
    the same layer (and, if applicable, sublayer) as the other effect; (b)
    applying the other would change the text or the existence of the first
    effect, what it applies to, or what it does to any of the things it
    applies to; and (c) neither effect is from a characteristic-defining
    ability or both effects are from characteristic-defining abilities.
    Otherwise, the effect is considered to be independent of the other
    effect.

    613.8b An effect dependent on one or more other effects waits to apply
    until just after all of those effects have been applied. If multiple
    dependent effects would apply simultaneously in this way, they're
    applied in timestamp order relative to each other. If several
    dependent effects form a dependency loop, then this rule is ignored and
    the effects in the dependency loop are applied in timestamp order.

  Ships in Slice 3. The top-level `dependencies_declared` field is computed
  honestly regardless -- see `resolve_layers`'s docstring -- but because a
  truthy declaration is refused outright in this slice, it is always
  `False` on any `ok: True` result for now.
- `cant_have_abilities` (in scope for this slice, but the plan's own
  operation table gives it no `value` field, unlike `add_abilities` /
  `remove_abilities`). This module treats it as CR 113.11's general form --
  the object can't have ANY ability, not a single named one:

    113.11. Effects can stop an object from having a specified ability.
    These effects say that the object "can't have" that ability. If the
    object has that ability, it loses it. It's also impossible for an
    effect or keyword counter to add that ability to the object. ...

  Applying it clears the object's current abilities and blocks every later
  `add_abilities` part in the same layer-6 pass of this call from adding
  anything (matching "it's also impossible ... to add that ability"). A
  targeted single-ability variant (e.g. "can't have flying" specifically)
  would need a `value` field the plan's schema does not give this
  operation kind in v1; that is a real limitation, not an oversight, and
  is left for a later slice if the corpus ever needs it.

Refuses rather than guesses: malformed/missing `base`, an unknown or
not-yet-supported layer token, an `operation.kind` illegal for its declared
layer, a non-integer timestamp (bool is explicitly rejected -- same
strictness as cost_calculator's `_is_nonneg_int`), two parts in the same
layer sharing a timestamp (never tie-broken), a duplicate part `id`, an
unknown colour token, and a present-and-non-empty `applies_if` or
`depends_on` (Slice 2 / Slice 3 features). All of these return
`{"ok": False, "error": "..."}` -- this module never raises for an
input-shape problem and never produces a best-effort characteristics object
it can't stand behind.
"""

from __future__ import annotations

_VALID_COLORS = ("W", "U", "B", "R", "G")

# The full CR 613.1 layer enum, vs. the subset this slice actually resolves.
_KNOWN_LAYERS = ("2", "4", "5", "6", "7a", "7b", "7c", "7d")
_SUPPORTED_LAYERS = ("4", "5", "6")
_LAYER_ORDER = ["4", "5", "6"]  # processing order for this slice

_LAYER_OPERATION_KINDS = {
    "4": {"set_types", "add_types", "remove_types"},
    "5": {"set_colors", "add_colors"},
    "6": {"add_abilities", "remove_abilities", "remove_all_abilities", "cant_have_abilities"},
}

_TYPE_CATEGORY_FIELDS = ("card_types", "subtypes", "supertypes")

_BASE_LIST_FIELDS = ("card_types", "supertypes", "subtypes", "abilities")


def _is_nonneg_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


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

    # remove_all_abilities / cant_have_abilities: no further fields required.
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
    if layer not in _SUPPORTED_LAYERS:
        return (
            f"part {part_id!r}: layer {layer!r} is not yet supported -- Slice 1 only "
            f"resolves layers {_SUPPORTED_LAYERS} (see docs/plan-layer-system-tool.md Sec 9)"
        )

    timestamp = p.get("timestamp")
    if not _is_nonneg_int(timestamp):
        return f"part {part_id!r}: timestamp must be a non-negative integer, got {timestamp!r}"

    is_cda = p.get("is_cda", False)
    if not isinstance(is_cda, bool):
        return f"part {part_id!r}: is_cda must be a boolean, got {is_cda!r}"

    applies_if = p.get("applies_if")
    if applies_if:
        return (
            f"part {part_id!r}: applies_if is not yet supported -- Slice 1 does not "
            f"implement CR 613.5 conditional predicates (see docs/plan-layer-system-tool.md "
            f"Sec 9, Slice 2). Omit it or set it to null for this slice."
        )

    depends_on = p.get("depends_on")
    if depends_on:
        if not isinstance(depends_on, list) or not all(isinstance(x, str) for x in depends_on):
            return f"part {part_id!r}: depends_on must be a list of part ids, got {depends_on!r}"
        return (
            f"part {part_id!r}: depends_on is not yet supported -- Slice 1 does not "
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


def _order_parts(parts: list[dict]) -> list[dict]:
    """CR 613.3: characteristic-defining abilities first, then everything
    else, each group in CR 613.7 timestamp order."""
    cdas = sorted((p for p in parts if p.get("is_cda", False)), key=lambda p: p["timestamp"])
    others = sorted((p for p in parts if not p.get("is_cda", False)), key=lambda p: p["timestamp"])
    return cdas + others


def resolve_layers(base: dict | None, effects: list[dict] | None = None) -> dict:
    """Apply a list of caller-classified, caller-layer-assigned continuous
    effect parts to `base` in CR 613 order, for layers 4 (type), 5 (colour)
    and 6 (abilities) only -- see the module docstring for the full Slice 1
    boundary. Never raises on bad input; returns
    {"ok": False, "error": "..."} instead.

    base: {"name": str, "card_types": [str], "supertypes": [str],
           "subtypes": [str], "colors": [str], "abilities": [str],
           "power": int|None, "toughness": int|None, "controller": str|None}
          -- the object's copiable values, post-layer-1 (plan Sec 3a).
          `power`/`toughness`/`controller`/`name` pass through untouched in
          this slice; no layer 7 or layer 2 operations exist yet to touch
          them.
    effects: flat list of effect parts (plan Sec 3a table):
          {"id": str, "source_id": str, "layer": "4"|"5"|"6",
           "timestamp": int (>=0), "is_cda": bool,
           "depends_on": list[str]|None, "dependency_reason": str|None,
           "operation": {...}, "applies_if": None, "cite": str}
          `applies_if` and a non-empty `depends_on` are refused in this
          slice (see module docstring). `None`/omitted is treated as [].

    Returns on success:
      {"ok": True,
       "result": {"card_types": [...], "supertypes": [...],
                   "subtypes": [...], "colors": [...], "abilities": [...],
                   "power": ..., "toughness": ..., "controller": ...},
       "trace": [{"layer": str, "applied": part_id, "source_id": str,
                   "why": str, "state_after": {...}}, ...],
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
    # _validate_part below refuses any non-empty depends_on outright (Slice 1
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

    # CR 613.3 refusal: two parts in the same layer sharing a timestamp are
    # never tie-broken.
    for layer in _SUPPORTED_LAYERS:
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
    abilities_blocked = [False]  # mutable cell for CR 113.11 cant_have_abilities

    for layer in _LAYER_ORDER:
        parts_in_layer = [p for p in effects if p["layer"] == layer]
        ordered = _order_parts(parts_in_layer)
        for p in ordered:
            operation = p["operation"]
            if layer == "4":
                _apply_type_op(state, operation)
                state_after = {k: list(state[k]) for k in _TYPE_CATEGORY_FIELDS}
            elif layer == "5":
                _apply_color_op(state, operation)
                state_after = {"colors": list(state["colors"])}
            else:  # layer == "6"
                _apply_ability_op(state, operation, abilities_blocked)
                state_after = {"abilities": list(state["abilities"])}

            why = f"CDA (CR 613.3), timestamp {p['timestamp']}" if p.get("is_cda") else f"timestamp {p['timestamp']}"
            trace.append({
                "layer": layer,
                "applied": p["id"],
                "source_id": p["source_id"],
                "why": why,
                "state_after": state_after,
            })

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
        "dependencies_declared": dependencies_declared,
    }

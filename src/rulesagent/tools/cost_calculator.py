"""Deterministic mana-cost / mana-value calculator (docs/plan-cost-calculator-tool.md).

Pure Python, no LLM, no I/O. Computes the exact resulting cost from a base
mana cost plus a list of already-classified cost-modifying effects (each
supplied by the CALLER as reduction / increase / floor_total -- this module
never decides which effects apply or what kind they are; that judgment call
belongs to the rules-RAG pipeline, per the plan Sec 2).

Two things ground the arithmetic here, both quoted rather than asserted from
memory (data/raw/MagicCompRules*.txt is absent in this environment -- see the
note at the bottom of this docstring):

1. CR 601.2f -- the general cost-calculation-order rule. Quoted verbatim from
   evals/rulesguru_raw.json's own `citedRules["601.2f"]["ruleText"]` entry
   (checked into this repo, sourced from the real Comprehensive Rules):

     "The player determines the total cost of the spell. Usually this is
     just the mana cost. Some spells have additional or alternative costs.
     Some effects may increase or reduce the cost to pay, or may provide
     other alternative costs. ... The total cost is the mana cost or
     alternative cost (as determined in rule 601.2b), plus all additional
     costs and cost increases, and minus all cost reductions. If multiple
     cost reductions apply, the player may apply them in any order. If the
     mana component of the total cost is reduced to nothing by cost
     reduction effects, it is considered to be {0}. It can't be reduced to
     less than {0}. Once the total cost is determined, any effects that
     directly affect the total cost are applied. Then the resulting total
     cost becomes 'locked in.'"

   This settles the order: additions/increases, THEN reductions (floored at
   {0} generic), THEN "any effects that directly affect the total cost."

2. Trinisphere's OWN ruling #0 (fetched live via tools/scryfall.get_card, not
   from memory -- see docs/report-cost-calculator-tool.md for the pasted
   oracle_text) is what that last CR sentence means for a card-specific cost
   floor -- the plan searched the CR text for a general "costs at least N"
   mechanism and found none beyond 601.2f's own {0} floor (plan Sec 1/7):

     "To determine the total cost of a spell, start with the mana cost or
     alternative cost you're paying, add any cost increases, then apply any
     cost reductions. Finally, apply Trinisphere's effect if the mana
     component of the spell's cost is less than three mana. The mana value
     of the spell remains unchanged, no matter what the total cost to cast
     it was."

So this module's order is: (1) increase/additional-cost modifiers raise the
generic component; (2) reduction modifiers lower the generic component,
floored at 0; (3) a floor_total modifier (Trinisphere-style -- supplied by
the CALLER, never derived here) raises the total back up to its minimum,
last, if the total is still under it. Mana value is computed from the BASE
cost + resolved {X} only and is never changed by any modifier -- straight
from Trinisphere's own ruling above ("mana value ... remains unchanged").

Refuses rather than guesses: malformed input (negative amounts, an unknown
modifier kind, a non-numeric/missing base cost, an unresolved {X}) returns a
structured {"ok": False, "error": ...} -- this module never raises for an
input-shape problem and never produces a best-effort number it can't stand
behind (plan Sec 2, Sec 5.5).
"""

from __future__ import annotations

_COLOR_KEYS = ("W", "U", "B", "R", "G", "C")
_MODIFIER_KINDS = ("increase", "reduction", "floor_total")


def _is_nonneg_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_pos_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _validate_base_cost(base_cost: object) -> str | None:
    """Returns an error string, or None if base_cost is well-formed."""
    if base_cost is None:
        return "no base_cost provided -- nothing to compute a cost from"
    if not isinstance(base_cost, dict):
        return f"base_cost must be an object, got {type(base_cost).__name__}"
    generic = base_cost.get("generic", 0)
    if not _is_nonneg_int(generic):
        return f"base_cost.generic must be a non-negative integer, got {generic!r}"
    x_coefficient = base_cost.get("x_coefficient", 0)
    if not _is_nonneg_int(x_coefficient):
        return f"base_cost.x_coefficient must be a non-negative integer, got {x_coefficient!r}"
    colored = base_cost.get("colored", {}) or {}
    if not isinstance(colored, dict):
        return f"base_cost.colored must be an object, got {type(colored).__name__}"
    for k, v in colored.items():
        if k not in _COLOR_KEYS:
            return f"base_cost.colored has an unknown symbol {k!r} (expected one of {_COLOR_KEYS})"
        if not _is_nonneg_int(v):
            return f"base_cost.colored[{k!r}] must be a non-negative integer, got {v!r}"
    return None


def _validate_modifier(m: object) -> str | None:
    if not isinstance(m, dict):
        return f"each modifier must be an object, got {type(m).__name__}"
    kind = m.get("kind")
    if kind not in _MODIFIER_KINDS:
        return f"modifier kind must be one of {_MODIFIER_KINDS}, got {kind!r}"
    amount = m.get("amount")
    if not _is_pos_int(amount):
        return f"modifier amount must be a positive integer, got {amount!r}"
    cite = m.get("cite", "")
    if not isinstance(cite, str):
        return f"modifier cite must be a string, got {type(cite).__name__}"
    return None


def _cost_string(generic: int, colored: dict[str, int]) -> str:
    """A human-readable `{N}{G}{G}`-style rendering for the steps trace."""
    parts = []
    if generic:
        parts.append(f"{{{generic}}}")
    for c in ("W", "U", "B", "R", "G", "C"):
        parts.extend([f"{{{c}}}"] * colored.get(c, 0))
    return "".join(parts) if parts else "{0}"


def calculate_cost(
    base_cost: dict | None,
    modifiers: list[dict] | None = None,
    x_values: list[int] | None = None,
) -> dict:
    """Compute the exact resulting cost (and mana value) for a base mana
    cost plus a list of already-classified modifiers, per CR 601.2f and (for
    a floor_total modifier) the ordering a card's own ruling establishes --
    see the module docstring. Never raises on bad input; returns
    {"ok": False, "error": "..."} instead.

    base_cost: {"generic": int, "colored": {"W"|"U"|"B"|"R"|"G"|"C": int},
                "x_coefficient": int} -- the number of {X} symbols in the
                printed cost (0 if there is none).
    modifiers: list of {"kind": "increase"|"reduction"|"floor_total",
                "amount": int (>0), "cite": str}. Applied in this fixed
                order regardless of list order: all increases, then all
                reductions (each individually floored at 0 generic -- CR
                601.2f: "the player may apply them in any order," which
                only matters among reductions), then floor_total last.
    x_values: required (non-empty, non-negative ints) when
                base_cost.x_coefficient > 0 -- there is no way to resolve a
                cost containing {X} without being told which value(s) to
                evaluate. Ignored (a single X=None result) when
                x_coefficient == 0.

    Returns {"ok": True, "results": [...]} on success, one entry per x value
    (or a single entry with "x": None when there is no {X}):
      {"x": int|None, "generic": int, "colored": {...}, "total_mana": int,
       "mana_value": int, "cost_string": str, "steps": [str, ...]}
    """
    err = _validate_base_cost(base_cost)
    if err:
        return {"ok": False, "error": err}
    modifiers = modifiers or []
    for m in modifiers:
        err = _validate_modifier(m)
        if err:
            return {"ok": False, "error": err}

    generic0 = base_cost.get("generic", 0)
    colored = {k: v for k, v in (base_cost.get("colored") or {}).items() if v}
    colored_total = sum(colored.values())
    x_coefficient = base_cost.get("x_coefficient", 0)

    if x_coefficient > 0:
        if not x_values:
            return {
                "ok": False,
                "error": (
                    "base_cost has an {X} coefficient but no x_values were "
                    "supplied -- cannot resolve X without being told which "
                    "value(s) to evaluate"
                ),
            }
        for x in x_values:
            if not _is_nonneg_int(x):
                return {"ok": False, "error": f"x_values must be non-negative integers, got {x!r}"}
        xs: list[int | None] = list(x_values)
    else:
        xs = [None]

    results = []
    for x in xs:
        x_contrib = (x * x_coefficient) if x is not None else 0
        generic = generic0 + x_contrib
        base_total = generic + colored_total
        steps = [
            f"Base cost ({'X=' + str(x) if x is not None else 'no {X}'}): "
            f"{_cost_string(generic, colored)} ({base_total} total)"
        ]

        for m in modifiers:
            if m["kind"] == "increase":
                generic += m["amount"]
                cite = f" ({m['cite']})" if m.get("cite") else ""
                steps.append(
                    f"Increase +{m['amount']} generic{cite} -> "
                    f"{_cost_string(generic, colored)} ({generic + colored_total} total)"
                )

        for m in modifiers:
            if m["kind"] == "reduction":
                before = generic
                generic = max(0, generic - m["amount"])
                applied = before - generic
                cite = f" ({m['cite']})" if m.get("cite") else ""
                floor_note = " [hit the {0} generic floor]" if applied < m["amount"] else ""
                steps.append(
                    f"Reduction -{m['amount']} generic, floored at {{0}}{cite}: "
                    f"reduced by {applied}{floor_note} -> "
                    f"{_cost_string(generic, colored)} ({generic + colored_total} total)"
                )

        total = generic + colored_total
        for m in modifiers:
            if m["kind"] == "floor_total":
                cite = f" ({m['cite']})" if m.get("cite") else ""
                if total < m["amount"]:
                    bump = m["amount"] - total
                    generic += bump
                    total = m["amount"]
                    steps.append(
                        f"Floor: total cost can't be less than {m['amount']}{cite}: "
                        f"total was {total - bump}, raised generic by +{bump} -> "
                        f"{_cost_string(generic, colored)} ({total} total)"
                    )
                else:
                    steps.append(
                        f"Floor: total cost can't be less than {m['amount']}{cite}: "
                        f"total {total} already meets it, no change"
                    )

        # Mana value is fixed by the BASE cost + resolved X and is never
        # changed by a cost increase/reduction/floor -- Trinisphere's own
        # ruling #0 states this explicitly (module docstring point 2).
        mana_value = base_total

        results.append({
            "x": x,
            "generic": generic,
            "colored": colored,
            "total_mana": total,
            "mana_value": mana_value,
            "cost_string": _cost_string(generic, colored),
            "steps": steps,
        })

    return {"ok": True, "results": results}

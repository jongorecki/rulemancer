# Tests for the deterministic cost/mana-value calculator
# (docs/plan-cost-calculator-tool.md, src/rulesagent/tools/cost_calculator.py).
#
# Every expected number in the Trinisphere and c014 cases below is
# hand-derived in the plan-review report against:
#   - CR 601.2f (evals/rulesguru_raw.json citedRules["601.2f"]["ruleText"]):
#     total = base + increases - reductions (mana floored at {0}), THEN
#     "any effects that directly affect the total cost."
#   - Trinisphere's own ruling #0 (fetched live via tools.scryfall.get_card,
#     see docs/report-cost-calculator-tool.md): apply increases, then
#     reductions, THEN Trinisphere's floor; mana value never changes.
#   - Awaken the Woods' real Scryfall data: mana_cost {X}{G}{G}, cmc 2.0
#     (X=0 on the stack contributes 0, matching this module's mana_value).

from rulesagent.tools.cost_calculator import calculate_cost


def _one(result: dict) -> dict:
    """A calculate_cost() call with exactly one result -- unwrap it."""
    assert result["ok"] is True, result
    assert len(result["results"]) == 1
    return result["results"][0]


# --- Basic arithmetic, no modifiers -----------------------------------------


def test_plain_cost_no_modifiers():
    # {2}{U}{U}: 2 generic + 2 blue = 4 total, mana value 4.
    r = _one(calculate_cost(base_cost={"generic": 2, "colored": {"U": 2}, "x_coefficient": 0}))
    assert r["x"] is None
    assert r["generic"] == 2
    assert r["colored"] == {"U": 2}
    assert r["total_mana"] == 4
    assert r["mana_value"] == 4
    assert r["cost_string"] == "{2}{U}{U}"


def test_zero_cost_is_valid_not_refused():
    # A genuine {0} cost (e.g. Ornithopter's like) is real, not "nothing to
    # compute" -- only a *missing* base_cost is refused (see below).
    r = _one(calculate_cost(base_cost={"generic": 0, "colored": {}, "x_coefficient": 0}))
    assert r["total_mana"] == 0
    assert r["mana_value"] == 0
    assert r["cost_string"] == "{0}"


# --- Single modifiers --------------------------------------------------------


def test_single_reduction_lowers_generic_only():
    # {1}{G}{G} with a "costs {1} less" reduction -> {G}{G}, colored untouched.
    r = _one(calculate_cost(
        base_cost={"generic": 1, "colored": {"G": 2}, "x_coefficient": 0},
        modifiers=[{"kind": "reduction", "amount": 1, "cite": "test reduction"}],
    ))
    assert r["generic"] == 0
    assert r["colored"] == {"G": 2}
    assert r["total_mana"] == 2
    assert r["mana_value"] == 3  # base cost's mana value is unaffected by the reduction


def test_reduction_cannot_go_below_zero_generic():
    # CR 601.2f: "It can't be reduced to less than {0}." Generic is already
    # 0 -- a {1} reduction applies no further effect, colors untouched.
    r = _one(calculate_cost(
        base_cost={"generic": 0, "colored": {"G": 2}, "x_coefficient": 0},
        modifiers=[{"kind": "reduction", "amount": 1, "cite": "test"}],
    ))
    assert r["generic"] == 0
    assert r["total_mana"] == 2
    assert any("hit the {0} generic floor" in s for s in r["steps"])


def test_single_increase_raises_generic():
    # {2}{U} with a "costs {2} more" increase -> {4}{U}.
    r = _one(calculate_cost(
        base_cost={"generic": 2, "colored": {"U": 1}, "x_coefficient": 0},
        modifiers=[{"kind": "increase", "amount": 2, "cite": "test increase"}],
    ))
    assert r["generic"] == 4
    assert r["total_mana"] == 5
    assert r["mana_value"] == 3  # unaffected


def test_floor_total_raises_generic_when_under():
    # A floor of 3 on a cost that computes to {G}{G} (2 total) bumps generic
    # up by 1 -- Trinisphere's own shape with no other modifiers involved.
    r = _one(calculate_cost(
        base_cost={"generic": 0, "colored": {"G": 2}, "x_coefficient": 0},
        modifiers=[{"kind": "floor_total", "amount": 3, "cite": "floor effect"}],
    ))
    assert r["generic"] == 1
    assert r["total_mana"] == 3
    assert r["mana_value"] == 2  # floor never changes mana value


def test_floor_total_no_change_when_already_met():
    r = _one(calculate_cost(
        base_cost={"generic": 2, "colored": {"G": 2}, "x_coefficient": 0},
        modifiers=[{"kind": "floor_total", "amount": 3, "cite": "floor effect"}],
    ))
    assert r["total_mana"] == 4  # already >= 3, unchanged
    assert any("already meets it" in s for s in r["steps"])


# --- Ordering: increases, then reductions, then floor last ------------------


def test_increase_and_reduction_apply_in_that_order():
    # Order matters when both are present: {2}{R} + increase 1 -> {3}{R};
    # then reduction 2 -> {1}{R}. If reduction ran first it would be
    # {0}{R} then +1 = {1}{R} too here (coincidence of these numbers), so
    # use amounts where order changes the floor interaction instead.
    r = _one(calculate_cost(
        base_cost={"generic": 0, "colored": {"R": 1}, "x_coefficient": 0},
        modifiers=[
            {"kind": "reduction", "amount": 1, "cite": "reduce"},
            {"kind": "increase", "amount": 1, "cite": "increase"},
        ],
    ))
    # Increase applied first: 0 -> 1. Reduction applied second: 1 -> 0
    # (not floored, since 1 - 1 = 0 exactly). If reduction had run first
    # (0 -> floored at 0) then increase (0 -> 1), generic would be 1
    # instead of 0 -- this pins that increases-before-reductions is what
    # actually runs, per CR 601.2f's own listed order.
    assert r["generic"] == 0
    assert r["total_mana"] == 1


def test_worked_example_from_system_prompt_cost_math_bullet():
    # The existing SYSTEM_V4/V4NL worked example: {1}{G}{G} (3 total), a
    # "costs {1} less" effect -> {G}{G} (2 total); a total-cost floor of 3
    # also applies -> back to 3 (typically {1}{G}{G} again).
    r = _one(calculate_cost(
        base_cost={"generic": 1, "colored": {"G": 2}, "x_coefficient": 0},
        modifiers=[
            {"kind": "reduction", "amount": 1, "cite": "spells cost {1} less"},
            {"kind": "floor_total", "amount": 3, "cite": "total-cost floor of 3"},
        ],
    ))
    assert r["generic"] == 1
    assert r["colored"] == {"G": 2}
    assert r["total_mana"] == 3
    assert r["cost_string"] == "{1}{G}{G}"


# --- {X} handling -------------------------------------------------------------


def test_x_coefficient_requires_x_values():
    result = calculate_cost(base_cost={"generic": 0, "colored": {"G": 2}, "x_coefficient": 1})
    assert result["ok"] is False
    assert "x_values" in result["error"]


def test_x_values_multiple_results_no_modifiers():
    result = calculate_cost(
        base_cost={"generic": 0, "colored": {"G": 2}, "x_coefficient": 1},
        x_values=[0, 1, 2],
    )
    assert result["ok"] is True
    xs = {r["x"]: r for r in result["results"]}
    assert xs[0]["total_mana"] == 2
    assert xs[1]["total_mana"] == 3
    assert xs[2]["total_mana"] == 4
    assert xs[2]["mana_value"] == 4


# --- THE TRINISPHERE FLOOR CASE (Jon's explicit requirement) ----------------
# Awaken the Woods {X}{G}{G} (real Scryfall mana_cost, cmc 2.0), an
# opponent's untapped Trinisphere ("costs three mana to cast instead" when
# the mana component would be less than three), and a green-spell "costs
# {1} less" effect (c014's own setup, evals/cards.jsonl). Expected numbers
# match c014's `note` field verbatim: "X=0 costs 3 for zero tokens... cast
# for the largest X whose post-reduction cost is still <=3, never X=0" --
# hand-derived here as X=2 (cost 3, 2 tokens) beats X=3 (cost 4).


def test_trinisphere_floor_case_full_table():
    result = calculate_cost(
        base_cost={"generic": 0, "colored": {"G": 2}, "x_coefficient": 1},
        modifiers=[
            {"kind": "reduction", "amount": 1, "cite": "permanent makes green spells cost {1} less"},
            {"kind": "floor_total", "amount": 3, "cite": "Trinisphere: costs three mana to cast instead"},
        ],
        x_values=[0, 1, 2, 3],
    )
    assert result["ok"] is True
    xs = {r["x"]: r for r in result["results"]}

    # X=0: base {G}{G} (2 total) -> reduction can't touch generic (already
    # 0) -> Trinisphere floor bumps total to 3. Zero tokens created.
    assert xs[0]["total_mana"] == 3
    assert xs[0]["mana_value"] == 2
    assert xs[0]["cost_string"] == "{1}{G}{G}"

    # X=1: base {1}{G}{G} (3 total) -> reduction takes generic to 0 (2
    # total) -> Trinisphere floor bumps back to 3. One token.
    assert xs[1]["total_mana"] == 3
    assert xs[1]["mana_value"] == 3

    # X=2: base {2}{G}{G} (4 total) -> reduction takes generic to 1 (3
    # total) -> 3 is NOT less than the floor of 3, no change. Two tokens
    # for the same 3 mana as X=0/X=1 -- the best choice.
    assert xs[2]["total_mana"] == 3
    assert xs[2]["mana_value"] == 4
    assert xs[2]["generic"] == 1

    # X=3: base {3}{G}{G} (5 total) -> reduction takes generic to 2 (4
    # total) -> floor not needed. Costs MORE (4) than X=2's 3 -- confirms
    # X=2 is strictly better than going higher.
    assert xs[3]["total_mana"] == 4
    assert xs[3]["mana_value"] == 5

    # The actual optimum (largest X at the floor price) is computable
    # directly off this table: cheapest-mana entries, take the largest X.
    cheapest = min(r["total_mana"] for r in result["results"])
    best_x = max(r["x"] for r in result["results"] if r["total_mana"] == cheapest)
    assert best_x == 2


# --- A c014-STYLE multi-modifier case with a different shape ----------------


def test_c014_style_multi_modifier_case_increase_reduction_and_floor():
    # A hypothetical stacking three distinct modifier kinds at once: a
    # generic {1}{U}{U} base, a +1 increase, a -2 reduction, and a floor of
    # 4 -- exercises all three kinds together in one call.
    r = _one(calculate_cost(
        base_cost={"generic": 1, "colored": {"U": 2}, "x_coefficient": 0},
        modifiers=[
            {"kind": "increase", "amount": 1, "cite": "increase effect"},
            {"kind": "reduction", "amount": 2, "cite": "reduction effect"},
            {"kind": "floor_total", "amount": 4, "cite": "floor effect"},
        ],
    ))
    # increase: 1 -> 2 generic (4 total). reduction: 2 -> 0 generic (2
    # total, applied only 2 of the 2 amount -- no floor-clamp note since it
    # lands exactly on 0). floor: 2 total < 4 -> bump generic by 2 -> 2
    # generic, 4 total.
    assert r["generic"] == 2
    assert r["total_mana"] == 4
    assert r["mana_value"] == 3  # base cost only: 1 generic + 2 colored


# --- Refusals: malformed input never produces a guessed number ---------------


def test_missing_base_cost_refused():
    result = calculate_cost(base_cost=None)
    assert result["ok"] is False
    assert "error" in result


def test_negative_generic_refused():
    result = calculate_cost(base_cost={"generic": -1, "colored": {}, "x_coefficient": 0})
    assert result["ok"] is False


def test_unknown_color_key_refused():
    result = calculate_cost(base_cost={"generic": 0, "colored": {"Z": 1}, "x_coefficient": 0})
    assert result["ok"] is False


def test_unknown_modifier_kind_refused():
    result = calculate_cost(
        base_cost={"generic": 1, "colored": {}, "x_coefficient": 0},
        modifiers=[{"kind": "discount", "amount": 1, "cite": "?"}],
    )
    assert result["ok"] is False
    assert "kind" in result["error"]


def test_negative_modifier_amount_refused():
    result = calculate_cost(
        base_cost={"generic": 1, "colored": {}, "x_coefficient": 0},
        modifiers=[{"kind": "reduction", "amount": -1, "cite": "?"}],
    )
    assert result["ok"] is False


def test_zero_modifier_amount_refused():
    # A modifier with amount=0 isn't a real modifier -- refuse rather than
    # silently no-op it (the caller misclassified something).
    result = calculate_cost(
        base_cost={"generic": 1, "colored": {}, "x_coefficient": 0},
        modifiers=[{"kind": "reduction", "amount": 0, "cite": "?"}],
    )
    assert result["ok"] is False


def test_negative_x_value_refused():
    result = calculate_cost(
        base_cost={"generic": 0, "colored": {}, "x_coefficient": 1},
        x_values=[-1],
    )
    assert result["ok"] is False


def test_non_dict_base_cost_refused():
    result = calculate_cost(base_cost="not a dict")
    assert result["ok"] is False


def test_non_int_generic_refused():
    result = calculate_cost(base_cost={"generic": "two", "colored": {}, "x_coefficient": 0})
    assert result["ok"] is False


def test_bool_is_not_accepted_as_int():
    # Python bools are ints (isinstance(True, int) is True) -- guard against
    # a stray `true`/`false` being silently treated as 1/0.
    result = calculate_cost(base_cost={"generic": True, "colored": {}, "x_coefficient": 0})
    assert result["ok"] is False

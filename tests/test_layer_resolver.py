# Tests for the deterministic layer-system resolver -- Slice 1
# (docs/plan-layer-system-tool.md Sec 3a/3b/3b.5/9,
# src/rulesagent/tools/layer_resolver.py).
#
# Slice 1 scope only: layers 4 (type), 5 (colour), 6 (abilities). CDAs first
# (CR 613.3), then timestamp order (CR 613.7). No layer 2, no 7a-7d, no CR
# 613.6 is_active gate, no applies_if, no depends_on ordering -- those are
# later slices (see the module docstring for the documented boundary).

from rulesagent.tools.layer_resolver import resolve_layers

WAYWARD_ANGEL_BASE = {
    "name": "Wayward Angel",
    "card_types": ["Creature"],
    "supertypes": [],
    "subtypes": ["Angel", "Horror"],
    "colors": ["W"],
    "abilities": ["Flying", "Vigilance"],
    "power": 4,
    "toughness": 4,
    "controller": "A",
}


# --- The founding test: rg811's layer-6 ordering ----------------------------
# (plan Sec 9, Slice 1: "the one that isolates ordering with nothing else
# moving"). remove_all_abilities at ts 1, then add_abilities at ts 2 ->
# Flying/Vigilance gone, only the granted abilities remain.


def test_rg811_layer6_ordering_remove_then_add():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            {
                "id": "e2a",
                "source_id": "e2",
                "layer": "6",
                "timestamp": 1,
                "is_cda": False,
                "depends_on": None,
                "dependency_reason": None,
                "operation": {"kind": "remove_all_abilities"},
                "cite": "test: Humility-style remove-all",
            },
            {
                "id": "e1b",
                "source_id": "e1",
                "layer": "6",
                "timestamp": 2,
                "is_cda": False,
                "depends_on": None,
                "dependency_reason": None,
                "operation": {
                    "kind": "add_abilities",
                    "value": ["Trample", "At the beginning of your upkeep, sacrifice a creature."],
                },
                "cite": "test: threshold-style grant",
            },
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["abilities"] == [
        "Trample",
        "At the beginning of your upkeep, sacrifice a creature.",
    ]


# --- The asymmetry test: reverse timestamp order gives a different answer --
# (task instructions: "That asymmetry is the whole point of the tool; if it
# does not hold, the engine is wrong.") Same two operations, add first (ts
# 1), remove-all second (ts 2) -> everything gone, including the grant.


def test_reverse_timestamp_order_gives_different_answer():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            {
                "id": "e1b",
                "source_id": "e1",
                "layer": "6",
                "timestamp": 1,
                "is_cda": False,
                "depends_on": None,
                "dependency_reason": None,
                "operation": {
                    "kind": "add_abilities",
                    "value": ["Trample", "At the beginning of your upkeep, sacrifice a creature."],
                },
                "cite": "test: threshold-style grant",
            },
            {
                "id": "e2a",
                "source_id": "e2",
                "layer": "6",
                "timestamp": 2,
                "is_cda": False,
                "depends_on": None,
                "dependency_reason": None,
                "operation": {"kind": "remove_all_abilities"},
                "cite": "test: Humility-style remove-all",
            },
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["abilities"] == []


# --- No effects: base passes through untouched ------------------------------


def test_no_effects_passes_base_through():
    result = resolve_layers(base=WAYWARD_ANGEL_BASE, effects=None)
    assert result["ok"] is True, result
    assert result["result"] == {
        "card_types": ["Creature"],
        "supertypes": [],
        "subtypes": ["Angel", "Horror"],
        "colors": ["W"],
        "abilities": ["Flying", "Vigilance"],
        "power": 4,
        "toughness": 4,
        "controller": "A",
    }
    assert result["trace"] == []
    assert result["dependencies_declared"] is False


def _part(**overrides):
    """A minimal well-formed effect part, with any fields overridden."""
    p = {
        "id": "e1",
        "source_id": "s1",
        "layer": "6",
        "timestamp": 1,
        "is_cda": False,
        "depends_on": None,
        "dependency_reason": None,
        "operation": {"kind": "remove_all_abilities"},
        "cite": "test",
    }
    p.update(overrides)
    return p


# --- Layer 4 -- type operations ----------------------------------------------


def test_layer4_set_types_replaces_the_named_category_only():
    base = {**WAYWARD_ANGEL_BASE, "supertypes": ["Legendary"]}
    result = resolve_layers(
        base=base,
        effects=[_part(id="e1", layer="4", timestamp=1, operation={
            "kind": "set_types", "subtypes": ["Frog"],
        })],
    )
    assert result["ok"] is True, result
    assert result["result"]["subtypes"] == ["Frog"]
    assert result["result"]["card_types"] == ["Creature"]  # untouched category
    assert result["result"]["supertypes"] == ["Legendary"]  # untouched category


def test_layer4_add_types_appends_without_duplicating():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="4", timestamp=1, operation={
            "kind": "add_types", "card_types": ["Artifact", "Creature"],
        })],
    )
    assert result["ok"] is True, result
    assert result["result"]["card_types"] == ["Creature", "Artifact"]


def test_layer4_remove_types_drops_named_entries():
    base = {**WAYWARD_ANGEL_BASE, "subtypes": ["Angel", "Horror"]}
    result = resolve_layers(
        base=base,
        effects=[_part(id="e1", layer="4", timestamp=1, operation={
            "kind": "remove_types", "subtypes": ["Horror"],
        })],
    )
    assert result["ok"] is True, result
    assert result["result"]["subtypes"] == ["Angel"]


# --- Layer 5 -- colour operations --------------------------------------------


def test_layer5_set_colors_replaces_wholesale():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="5", timestamp=1, operation={
            "kind": "set_colors", "value": ["B"],
        })],
    )
    assert result["ok"] is True, result
    assert result["result"]["colors"] == ["B"]


def test_layer5_add_colors_unions_without_duplicating():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="5", timestamp=1, operation={
            "kind": "add_colors", "value": ["W", "U"],
        })],
    )
    assert result["ok"] is True, result
    assert result["result"]["colors"] == ["W", "U"]


# --- Layer 6 -- cant_have_abilities (CR 113.11) ------------------------------


def test_cant_have_abilities_clears_and_blocks_later_adds():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            _part(id="e1", source_id="s1", layer="6", timestamp=1,
                  operation={"kind": "cant_have_abilities"}),
            _part(id="e2", source_id="s2", layer="6", timestamp=2,
                  operation={"kind": "add_abilities", "value": ["Trample"]}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["abilities"] == []


def test_cant_have_abilities_does_not_block_earlier_adds():
    # Order matters: an add_abilities BEFORE cant_have_abilities already
    # happened and gets wiped by cant_have_abilities's own clear, same as
    # remove_all -- it's only LATER adds that are suppressed.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            _part(id="e1", source_id="s1", layer="6", timestamp=1,
                  operation={"kind": "add_abilities", "value": ["Trample"]}),
            _part(id="e2", source_id="s2", layer="6", timestamp=2,
                  operation={"kind": "cant_have_abilities"}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["abilities"] == []


# --- CR 613.3 -- CDAs before timestamp order ---------------------------------


def test_cda_applies_before_non_cda_regardless_of_timestamp():
    # Non-CDA has the EARLIER timestamp but CDAs still go first per 613.3.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            _part(id="e_noncda", source_id="s1", layer="5", timestamp=1, is_cda=False,
                  operation={"kind": "set_colors", "value": ["U"]}),
            _part(id="e_cda", source_id="s2", layer="5", timestamp=2, is_cda=True,
                  operation={"kind": "set_colors", "value": ["B"]}),
        ],
    )
    assert result["ok"] is True, result
    # CDA (e_cda) applies first -> [B], then non-CDA (e_noncda) applies -> [U].
    assert result["result"]["colors"] == ["U"]
    applied_order = [t["applied"] for t in result["trace"] if t["layer"] == "5"]
    assert applied_order == ["e_cda", "e_noncda"]


# --- Cross-layer combination (rg807/rg811-shaped, layers 4-6 only) ----------


def test_cross_layer_combination_layer_order_is_4_then_5_then_6():
    # Turn-to-Frog-shaped effect: layer 4 sets subtype, layer 5 sets colour,
    # layer 6 removes all abilities -- applied in that fixed layer order
    # regardless of list order in the input.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            _part(id="e6", source_id="frog", layer="6", timestamp=1,
                  operation={"kind": "remove_all_abilities"}),
            _part(id="e4", source_id="frog", layer="4", timestamp=1,
                  operation={"kind": "set_types", "subtypes": ["Frog"]}),
            _part(id="e5", source_id="frog", layer="5", timestamp=1,
                  operation={"kind": "set_colors", "value": ["U"]}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["subtypes"] == ["Frog"]
    assert result["result"]["colors"] == ["U"]
    assert result["result"]["abilities"] == []
    assert [t["layer"] for t in result["trace"]] == ["4", "5", "6"]


# --- Trace shape --------------------------------------------------------------


def test_trace_entries_have_expected_shape():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", source_id="src1", layer="5", timestamp=3, is_cda=True,
                        operation={"kind": "set_colors", "value": ["B"]})],
    )
    assert result["ok"] is True, result
    assert len(result["trace"]) == 1
    entry = result["trace"][0]
    assert entry["layer"] == "5"
    assert entry["applied"] == "e1"
    assert entry["source_id"] == "src1"
    assert "CDA" in entry["why"]
    assert entry["state_after"] == {"colors": ["B"]}


# --- Refusals: base -----------------------------------------------------------


def test_refuses_missing_base():
    result = resolve_layers(base=None)
    assert result["ok"] is False
    assert "base" in result["error"]


def test_refuses_non_dict_base():
    result = resolve_layers(base="not a dict")
    assert result["ok"] is False
    assert "base" in result["error"]


def test_refuses_base_with_wrong_field_type():
    bad = {**WAYWARD_ANGEL_BASE, "card_types": "Creature"}  # should be a list
    result = resolve_layers(base=bad)
    assert result["ok"] is False
    assert "card_types" in result["error"]


def test_refuses_base_with_unknown_color_token():
    bad = {**WAYWARD_ANGEL_BASE, "colors": ["X"]}
    result = resolve_layers(base=bad)
    assert result["ok"] is False
    assert "color" in result["error"].lower()


# --- Refusals: effect part structure ------------------------------------------


def test_refuses_duplicate_part_id():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            _part(id="dup", layer="6", timestamp=1, operation={"kind": "remove_all_abilities"}),
            _part(id="dup", layer="5", timestamp=1, operation={"kind": "set_colors", "value": ["B"]}),
        ],
    )
    assert result["ok"] is False
    assert "dup" in result["error"]


def test_refuses_operation_kind_illegal_for_its_layer():
    # add_abilities is a layer-6 operation, declared on layer 4.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="4", timestamp=1,
                        operation={"kind": "add_abilities", "value": ["Trample"]})],
    )
    assert result["ok"] is False
    assert "not legal for layer" in result["error"]


def test_refuses_duplicate_timestamp_same_layer_never_tie_breaks():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            _part(id="e1", source_id="s1", layer="6", timestamp=1,
                  operation={"kind": "remove_all_abilities"}),
            _part(id="e2", source_id="s2", layer="6", timestamp=1,
                  operation={"kind": "add_abilities", "value": ["Trample"]}),
        ],
    )
    assert result["ok"] is False
    assert "timestamp" in result["error"]


def test_refuses_unknown_color_token_in_operation():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="5", timestamp=1,
                        operation={"kind": "set_colors", "value": ["X"]})],
    )
    assert result["ok"] is False
    assert "color" in result["error"].lower()


def test_refuses_unknown_layer_token():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="banana", timestamp=1,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "unknown layer token" in result["error"]


def test_refuses_out_of_slice_layer_distinctly_from_unknown():
    # Layer 7c is a REAL CR layer, just not implemented until Slice 2 --
    # must not be conflated with an unknown layer token.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7c", timestamp=1,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "not yet supported" in result["error"]
    assert "unknown layer token" not in result["error"]


def test_refuses_layer_2_as_not_yet_supported():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="2", timestamp=1,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "not yet supported" in result["error"]


def test_refuses_non_integer_timestamp():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1.5,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "timestamp" in result["error"]


def test_refuses_bool_timestamp_mirroring_cost_calculator_strictness():
    # bool is a subclass of int in Python -- must be explicitly rejected,
    # same discipline as cost_calculator._is_nonneg_int.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=True,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "timestamp" in result["error"]


def test_refuses_negative_timestamp():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=-1,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "timestamp" in result["error"]


def test_refuses_non_bool_is_cda():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1, is_cda="yes",
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "is_cda" in result["error"]


def test_refuses_applies_if_as_not_yet_supported():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        applies_if={"has_no_abilities": True})],
    )
    assert result["ok"] is False
    assert "applies_if" in result["error"]
    assert "not yet supported" in result["error"]


def test_refuses_nonempty_depends_on_as_not_yet_supported():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        depends_on=["some_other_part"],
                        dependency_reason="test dependency")],
    )
    assert result["ok"] is False
    assert "depends_on" in result["error"]
    assert "not yet supported" in result["error"]


def test_empty_depends_on_is_accepted():
    # depends_on: [] (or None) is the "nothing declared" case, not a
    # dependency assertion -- must not be refused.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        depends_on=[])],
    )
    assert result["ok"] is True, result
    assert result["dependencies_declared"] is False


def test_refuses_missing_operation():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1, operation=None)],
    )
    assert result["ok"] is False


def test_refuses_missing_part_id():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id=None, layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "id" in result["error"]


def test_never_raises_on_garbage_effects_type():
    result = resolve_layers(base=WAYWARD_ANGEL_BASE, effects="not a list")
    assert result["ok"] is False


def test_never_raises_on_garbage_part_type():
    result = resolve_layers(base=WAYWARD_ANGEL_BASE, effects=["not a dict"])
    assert result["ok"] is False

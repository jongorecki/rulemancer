# Tests for the deterministic layer-system resolver -- Slice 1
# (docs/plan-layer-system-tool.md Sec 3a/3b/3b.5/9,
# src/rulesagent/tools/layer_resolver.py).
#
# Slice 1 scope only: layers 4 (type), 5 (colour), 6 (abilities). CDAs first
# (CR 613.3), then timestamp order (CR 613.7). No layer 2, no 7a-7d, no CR
# 613.6 is_active gate, no applies_if, no depends_on ordering -- those are
# later slices (see the module docstring for the documented boundary).

from rulesagent.tools.layer_resolver import resolve_layers, _is_active

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


def test_layer_7c_is_now_supported_distinctly_from_unknown_layer():
    # Slice 2 adds 7c. remove_all_abilities is still illegal there (it's a
    # layer-6 operation kind) -- the refusal is now "not legal for layer",
    # same message shape as any other layer/operation mismatch, not the old
    # Slice-1 "not yet supported" placeholder.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7c", timestamp=1,
                        operation={"kind": "remove_all_abilities"})],
    )
    assert result["ok"] is False
    assert "not legal for layer" in result["error"]


def test_layer_2_is_now_supported_set_controller():
    # Slice 2 adds layer 2 (control-changing effects, CR 613.1b).
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", source_id="s1", layer="2", timestamp=1,
                        operation={"kind": "set_controller", "value": "B"})],
    )
    assert result["ok"] is True, result
    assert result["result"]["controller"] == "B"


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


def test_applies_if_is_now_supported_option_b():
    # Slice 2 ships applies_if (option B, Jon's ruling plan Sec 8.1). A
    # well-formed predicate is accepted and evaluated against live state
    # (not refused), and correctly gates the effect out when false: this
    # base already has abilities, so "only if no abilities" is FALSE and
    # remove_all_abilities is correctly skipped -- a no-op here, not a
    # refusal.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        applies_if={"has_no_abilities": True})],
    )
    assert result["ok"] is True, result
    assert result["result"]["abilities"] == ["Flying", "Vigilance"]
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["id"] == "e1"


def test_refuses_applies_if_with_unknown_predicate_key():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        applies_if={"has_flavor_text": True})],
    )
    assert result["ok"] is False
    assert "applies_if" in result["error"]
    assert "unknown predicate key" in result["error"]


def test_refuses_applies_if_with_more_than_one_predicate_key():
    # Option B is explicitly "no nesting" -- exactly one predicate per
    # applies_if, never a compound condition.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        applies_if={"has_no_abilities": True, "has_color": "W"})],
    )
    assert result["ok"] is False
    assert "applies_if" in result["error"]
    assert "exactly one predicate key" in result["error"]


def test_refuses_applies_if_with_wrong_value_type():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="6", timestamp=1,
                        operation={"kind": "remove_all_abilities"},
                        applies_if={"power_gte": "four"})],
    )
    assert result["ok"] is False
    assert "power_gte" in result["error"]


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


# =============================================================================
# Slice 2 -- layers 7a-7d, the CR 613.6 is_active gate, applies_if (option B)
# (docs/plan-layer-system-tool.md Sec 3a/3b/3b.5/9, Slice 2).
# =============================================================================


# --- rg3868, the richest seed (plan Sec 3b.5) --------------------------------
# Muraganda Petroglyphs + Wayward Angel (7+ cards in graveyard) + Humility.
# Gold: black 6/6, no abilities.


def test_rg3868_muraganda_wayward_angel_humility():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[
            {
                "id": "e1a", "source_id": "e1", "layer": "5", "timestamp": 1,
                "is_cda": False, "depends_on": None, "dependency_reason": None,
                "operation": {"kind": "set_colors", "value": ["B"]},
                "applies_if": None, "cite": "Wayward Angel threshold",
            },
            {
                "id": "e1b", "source_id": "e1", "layer": "6", "timestamp": 1,
                "is_cda": False, "depends_on": None, "dependency_reason": None,
                "operation": {
                    "kind": "add_abilities",
                    "value": ["Trample", "At the beginning of your upkeep, sacrifice a creature."],
                },
                "applies_if": None, "cite": "Wayward Angel threshold",
            },
            {
                "id": "e1c", "source_id": "e1", "layer": "7c", "timestamp": 1,
                "is_cda": False, "depends_on": None, "dependency_reason": None,
                "operation": {"kind": "modify_pt", "power": 3, "toughness": 3},
                "applies_if": None, "cite": "Wayward Angel threshold",
            },
            {
                "id": "e2a", "source_id": "e2", "layer": "6", "timestamp": 2,
                "is_cda": False, "depends_on": None, "dependency_reason": None,
                "operation": {"kind": "remove_all_abilities"},
                "applies_if": None, "cite": "Humility",
            },
            {
                "id": "e2b", "source_id": "e2", "layer": "7b", "timestamp": 2,
                "is_cda": False, "depends_on": None, "dependency_reason": None,
                "operation": {"kind": "set_pt", "power": 1, "toughness": 1},
                "applies_if": None, "cite": "Humility",
            },
            {
                "id": "e3a", "source_id": "e3", "layer": "7c", "timestamp": 3,
                "is_cda": False, "depends_on": None, "dependency_reason": None,
                "operation": {"kind": "modify_pt", "power": 2, "toughness": 2},
                "applies_if": {"has_no_abilities": True},
                "cite": "Muraganda Petroglyphs",
            },
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["colors"] == ["B"]
    assert result["result"]["abilities"] == []
    assert result["result"]["power"] == 6
    assert result["result"]["toughness"] == 6


# --- rg807 / rg811 -- same two cards, only the timestamps differ (plan Sec
# 3b.5). This pair is the tool's whole thesis: identical effects, one
# integer swapped, and the answers diverge on both colour and abilities.


def _wayward_angel_threshold_parts(ts):
    return [
        {
            "id": "e1a", "source_id": "e1", "layer": "5", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {"kind": "set_colors", "value": ["B"]},
            "applies_if": None, "cite": "Wayward Angel threshold",
        },
        {
            "id": "e1b", "source_id": "e1", "layer": "6", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {
                "kind": "add_abilities",
                "value": ["Trample", "At the beginning of your upkeep, sacrifice a creature."],
            },
            "applies_if": None, "cite": "Wayward Angel threshold",
        },
        {
            "id": "e1c", "source_id": "e1", "layer": "7c", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {"kind": "modify_pt", "power": 3, "toughness": 3},
            "applies_if": None, "cite": "Wayward Angel threshold",
        },
    ]


def _turn_to_frog_parts(ts):
    return [
        {
            "id": "e2_4", "source_id": "e2", "layer": "4", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {"kind": "set_types", "subtypes": ["Frog"]},
            "applies_if": None, "cite": "Turn to Frog",
        },
        {
            "id": "e2_5", "source_id": "e2", "layer": "5", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {"kind": "set_colors", "value": ["U"]},
            "applies_if": None, "cite": "Turn to Frog",
        },
        {
            "id": "e2_6", "source_id": "e2", "layer": "6", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {"kind": "remove_all_abilities"},
            "applies_if": None, "cite": "Turn to Frog",
        },
        {
            "id": "e2_7b", "source_id": "e2", "layer": "7b", "timestamp": ts,
            "is_cda": False, "depends_on": None, "dependency_reason": None,
            "operation": {"kind": "set_pt", "power": 1, "toughness": 1},
            "applies_if": None, "cite": "Turn to Frog",
        },
    ]


def test_rg807_wayward_angel_ts1_turn_to_frog_ts2():
    # Gold: 4/4 blue Frog, no abilities.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=_wayward_angel_threshold_parts(1) + _turn_to_frog_parts(2),
    )
    assert result["ok"] is True, result
    assert result["result"]["subtypes"] == ["Frog"]
    assert result["result"]["colors"] == ["U"]
    assert result["result"]["abilities"] == []
    assert result["result"]["power"] == 4
    assert result["result"]["toughness"] == 4


def test_rg811_turn_to_frog_ts1_wayward_angel_ts2():
    # Same two cards as rg807, timestamps SWAPPED (CR 613.7f: Wayward Angel
    # got a new timestamp on turning face up). Gold: 4/4 black Frog with
    # trample and the upkeep trigger, nothing else.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=_turn_to_frog_parts(1) + _wayward_angel_threshold_parts(2),
    )
    assert result["ok"] is True, result
    assert result["result"]["subtypes"] == ["Frog"]
    assert result["result"]["colors"] == ["B"]
    assert result["result"]["abilities"] == [
        "Trample",
        "At the beginning of your upkeep, sacrifice a creature.",
    ]
    assert result["result"]["power"] == 4
    assert result["result"]["toughness"] == 4


def test_rg807_and_rg811_differ_only_by_timestamp_and_diverge():
    # The explicit thesis assertion: identical payload, one integer swapped
    # per card, and colour + abilities diverge (power/toughness happen to
    # land the same by coincidence -- both are 4/4 -- but colour and
    # abilities are the real proof).
    rg807 = resolve_layers(base=WAYWARD_ANGEL_BASE,
                            effects=_wayward_angel_threshold_parts(1) + _turn_to_frog_parts(2))
    rg811 = resolve_layers(base=WAYWARD_ANGEL_BASE,
                            effects=_turn_to_frog_parts(1) + _wayward_angel_threshold_parts(2))
    assert rg807["ok"] is True and rg811["ok"] is True
    assert rg807["result"]["colors"] != rg811["result"]["colors"]
    assert rg807["result"]["abilities"] != rg811["result"]["abilities"]
    assert rg807["result"]["colors"] == ["U"]
    assert rg811["result"]["colors"] == ["B"]
    assert rg807["result"]["abilities"] == []
    assert rg811["result"]["abilities"] != []


# --- CR 613.4d -- the three switch_pt examples, verbatim from the rules ----
# ("data/raw/MagicCompRules 20260619.txt" line 2993-2995).


def test_cr613_4d_example_a_new_pump_after_switch_unswitches_correctly():
    # 1/3, +0/+1 (7c), switch (7d) -> 4/1. New +5/+0 (7c, ALWAYS resolves
    # before 7d regardless of when it was cast) -> "unswitched" 6/4, so
    # actual power/toughness is 4/6. This is the critical example: it
    # proves 7c always applies before 7d regardless of timestamp.
    base = {**WAYWARD_ANGEL_BASE, "power": 1, "toughness": 3}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="e1", source_id="s1", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 0, "toughness": 1}),
            _part(id="e2", source_id="s2", layer="7c", timestamp=2,
                  operation={"kind": "modify_pt", "power": 5, "toughness": 0}),
            _part(id="e3", source_id="s3", layer="7d", timestamp=1,
                  operation={"kind": "switch_pt"}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 4
    assert result["result"]["toughness"] == 6


def test_cr613_4d_example_b_expired_pump_omitted_before_switch():
    # Same base, but the +0/+1 effect has already ended by the queried
    # moment -- modelled as a second, separate resolve_layers call that
    # simply omits it (the caller decides what's still active at the point
    # in time being asked about). Expected: 3/1.
    base = {**WAYWARD_ANGEL_BASE, "power": 1, "toughness": 3}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="e3", source_id="s3", layer="7d", timestamp=1,
                  operation={"kind": "switch_pt"}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 3
    assert result["result"]["toughness"] == 1


def test_cr613_4d_example_c_two_switches_cancel():
    # 1/3, +0/+1 (7c) -> 1/4, then switched twice (7d, distinct timestamps)
    # -> the switches cancel and it becomes 1/4.
    base = {**WAYWARD_ANGEL_BASE, "power": 1, "toughness": 3}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="e1", source_id="s1", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 0, "toughness": 1}),
            _part(id="e2", source_id="s2", layer="7d", timestamp=1,
                  operation={"kind": "switch_pt"}),
            _part(id="e3", source_id="s3", layer="7d", timestamp=2,
                  operation={"kind": "switch_pt"}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 1
    assert result["result"]["toughness"] == 4


# --- CR 613.5 -- Gray Ogre (7b always before 7c) and Honor of the Pure
# (has_color predicate), both verbatim from the rules text.


def test_cr613_5_gray_ogre_7b_always_before_7c():
    # 2/2 -> +1/+1 counter (7c) -> "+4/+4 until EOT" (7c) -> "creatures get
    # +0/+2" (7c) -> "becomes 0/1 until EOT" (7b). Gold: 5/8. Proves 7b
    # applies before 7c even though the 0/1 effect was the LAST one to
    # start, chronologically.
    base = {**WAYWARD_ANGEL_BASE, "power": 2, "toughness": 2}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="counter", source_id="s1", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 1, "toughness": 1}),
            _part(id="spell", source_id="s2", layer="7c", timestamp=2,
                  operation={"kind": "modify_pt", "power": 4, "toughness": 4}),
            _part(id="enchantment", source_id="s3", layer="7c", timestamp=3,
                  operation={"kind": "modify_pt", "power": 0, "toughness": 2}),
            _part(id="becomes01", source_id="s4", layer="7b", timestamp=4,
                  operation={"kind": "set_pt", "power": 0, "toughness": 1}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 5
    assert result["result"]["toughness"] == 8


def test_cr613_5_honor_of_the_pure_has_color_predicate_true():
    # 2/2 black creature turned white (layer 5); Honor of the Pure ("White
    # creatures you control get +1/+1", applies_if has_color W) -> 3/3.
    base = {**WAYWARD_ANGEL_BASE, "colors": ["B"], "power": 2, "toughness": 2, "abilities": []}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="turn_white", source_id="s1", layer="5", timestamp=1,
                  operation={"kind": "set_colors", "value": ["W"]}),
            _part(id="honor", source_id="s2", layer="7c", timestamp=2,
                  operation={"kind": "modify_pt", "power": 1, "toughness": 1},
                  applies_if={"has_color": "W"}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["colors"] == ["W"]
    assert result["result"]["power"] == 3
    assert result["result"]["toughness"] == 3


def test_cr613_5_honor_of_the_pure_has_color_predicate_false_after_turning_red():
    # Same creature, later turned red instead of white -- Honor of the
    # Pure's predicate is now false and it does not apply. Back to 2/2.
    base = {**WAYWARD_ANGEL_BASE, "colors": ["B"], "power": 2, "toughness": 2, "abilities": []}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="turn_red", source_id="s1", layer="5", timestamp=1,
                  operation={"kind": "set_colors", "value": ["R"]}),
            _part(id="honor", source_id="s2", layer="7c", timestamp=2,
                  operation={"kind": "modify_pt", "power": 1, "toughness": 1},
                  applies_if={"has_color": "W"}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["colors"] == ["R"]
    assert result["result"]["power"] == 2
    assert result["result"]["toughness"] == 2
    assert result["skipped_count"] == 1


# --- CR 613.6 is_active gate -- the converse case ----------------------------
# "an ability whose ONLY part is in layer 7c, whose source is removed in
# layer 6, never started -- so it correctly does NOT apply."


def test_is_active_gate_direct_unit_never_removed():
    assert _is_active("src", layer_index=6, started={}, removed_at={}) is True


def test_is_active_gate_direct_unit_removed_later_than_now():
    assert _is_active("src", layer_index=2, started={}, removed_at={"src": 5}) is True


def test_is_active_gate_direct_unit_started_before_removal_continues():
    assert _is_active("src", layer_index=6, started={"src": 2}, removed_at={"src": 3}) is True


def test_is_active_gate_direct_unit_converse_never_started_does_not_apply():
    # The load-bearing converse: removed at or before this layer, but never
    # started (no earlier part ever applied for this source) -> inactive.
    assert _is_active("src", layer_index=6, started={}, removed_at={"src": 3}) is False
    assert _is_active("src", layer_index=6, started={}, removed_at={"src": 6}) is False


def test_is_active_gate_end_to_end_converse_via_base_ability_source_seed():
    # End-to-end version of the converse: the object has a printed ability
    # "Ancient Blessing" that ALSO (by the caller's convention of naming
    # source_id after the printed ability text it corresponds to) grants a
    # +2/+2 static bonus, with its ONLY registered part in layer 7c. A
    # different source (Humility-style) strips all abilities in layer 6,
    # before "Ancient Blessing"'s 7c part has ever run -- so removed_at is
    # set for it while started never was, and the CR 613.6 gate correctly
    # keeps its +2/+2 from ever applying.
    base = {
        **WAYWARD_ANGEL_BASE,
        "abilities": ["Ancient Blessing"],
        "power": 4, "toughness": 4,
    }
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="strip", source_id="humility", layer="6", timestamp=1,
                  operation={"kind": "remove_all_abilities"}),
            _part(id="bonus", source_id="Ancient Blessing", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 2, "toughness": 2}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["abilities"] == []
    # The +2/+2 never activates -- the generating ability was removed
    # before it ever started.
    assert result["result"]["power"] == 4
    assert result["result"]["toughness"] == 4
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["id"] == "bonus"
    assert "613.6" in result["skipped"][0]["why"]


# --- Mechanism 3 -- expect / warning on predicate disagreement --------------


def test_expect_mismatch_emits_warning_and_still_applies():
    # e3a's predicate genuinely evaluates TRUE (abilities are empty), but
    # the model wrongly expected it to evaluate FALSE. The engine is right
    # and applies the effect anyway; the mismatch is surfaced as a warning,
    # not a refusal, and ok stays True.
    base = {**WAYWARD_ANGEL_BASE, "abilities": [], "power": 4, "toughness": 4}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="e3a", source_id="e3", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 2, "toughness": 2},
                  applies_if={"has_no_abilities": True, "expect": False}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 6
    assert result["result"]["toughness"] == 6
    assert result["skipped_count"] == 0
    assert len(result["warnings"]) == 1
    assert "e3a" in result["warnings"][0]


def test_expect_mismatch_emits_warning_when_skipped_too():
    # Symmetric case: predicate evaluates FALSE (so the part is correctly
    # skipped) but the model expected TRUE -- also a warning, and
    # skipped_count reflects the real skip.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,  # has Flying, Vigilance -- not "no abilities"
        effects=[
            _part(id="e3a", source_id="e3", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 2, "toughness": 2},
                  applies_if={"has_no_abilities": True, "expect": True}),
        ],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 4
    assert result["result"]["toughness"] == 4
    assert result["skipped_count"] == 1
    assert len(result["warnings"]) == 1
    assert "e3a" in result["warnings"][0]


def test_expect_match_emits_no_warning():
    base = {**WAYWARD_ANGEL_BASE, "abilities": [], "power": 4, "toughness": 4}
    result = resolve_layers(
        base=base,
        effects=[
            _part(id="e3a", source_id="e3", layer="7c", timestamp=1,
                  operation={"kind": "modify_pt", "power": 2, "toughness": 2},
                  applies_if={"has_no_abilities": True, "expect": True}),
        ],
    )
    assert result["ok"] is True, result
    assert result["warnings"] == []
    assert result["skipped_count"] == 0


# --- New operation kinds -- basic coverage per layer -------------------------


def test_layer7a_cda_pt_sets_power_and_toughness():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7a", timestamp=1, is_cda=True,
                        operation={"kind": "cda_pt", "power": 0, "toughness": 0})],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 0
    assert result["result"]["toughness"] == 0


def test_layer7b_set_pt_overrides_base():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7b", timestamp=1,
                        operation={"kind": "set_pt", "power": 1, "toughness": 1})],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 1
    assert result["result"]["toughness"] == 1


def test_layer7c_modify_pt_is_additive_and_signed():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7c", timestamp=1,
                        operation={"kind": "modify_pt", "power": -1, "toughness": -1})],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 3
    assert result["result"]["toughness"] == 3


def test_layer7d_switch_pt_swaps_power_and_toughness():
    base = {**WAYWARD_ANGEL_BASE, "power": 1, "toughness": 4}
    result = resolve_layers(
        base=base,
        effects=[_part(id="e1", layer="7d", timestamp=1,
                        operation={"kind": "switch_pt"})],
    )
    assert result["ok"] is True, result
    assert result["result"]["power"] == 4
    assert result["result"]["toughness"] == 1


# --- Refusals: new operation-kind/layer mismatches ---------------------------


def test_refuses_set_pt_declared_in_layer_7c():
    # A model error that would otherwise produce a plausible wrong number --
    # set_pt is a layer-7b operation, not 7c.
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7c", timestamp=1,
                        operation={"kind": "set_pt", "power": 1, "toughness": 1})],
    )
    assert result["ok"] is False
    assert "not legal for layer" in result["error"]


def test_refuses_non_integer_pt_value():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="7c", timestamp=1,
                        operation={"kind": "modify_pt", "power": "three", "toughness": 1})],
    )
    assert result["ok"] is False
    assert "power" in result["error"]


def test_refuses_set_controller_with_empty_value():
    result = resolve_layers(
        base=WAYWARD_ANGEL_BASE,
        effects=[_part(id="e1", layer="2", timestamp=1,
                        operation={"kind": "set_controller", "value": ""})],
    )
    assert result["ok"] is False

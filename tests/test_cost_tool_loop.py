# Tests for the calculate_cost tool-dispatch loop wired into RulesAgent.answer()
# (docs/plan-cost-calculator-tool.md Sec 3b, docs/spike-tool-use-findings.md).
#
# No network: a scripted fake `.messages.parse()` client, same pattern as
# tests/test_degenerate.py / tests/test_uncited_success.py's _ScriptedClient,
# extended to also record every call's kwargs (so we can assert `tools=` is
# only ever attached when the trigger fires) and to return fake tool_use
# content blocks shaped like the real Anthropic SDK's (`.type`, `.id`,
# `.name`, `.input`).

import json

from rulesagent.contracts import Answer, Card
from rulesagent.generate import answer as ans


class _FakeToolUseBlock:
    def __init__(self, id_, name, input_):
        self.type = "tool_use"
        self.id = id_
        self.name = name
        self.input = input_


class _FakeResponse:
    def __init__(self, stop_reason, content, parsed_output=None):
        self.stop_reason = stop_reason
        self.content = content
        self.parsed_output = parsed_output


class _ScriptedToolClient:
    """Fake .messages.parse() client that returns a scripted sequence of
    _FakeResponse objects (or raises a scripted exception), one per call,
    and records every call's full kwargs for inspection."""

    def __init__(self, script):
        self.messages = self
        self._script = list(script)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class _EmptyStore:
    def search(self, query, k):
        return []


_REAL_ANSWER = Answer(
    text="Awaken the Woods with X=2 costs {1}{G}{G} (3 total) and makes 2 tokens.",
    tldr="Cast it for X=2.",
    citations=["601.2f"],
    answered=True,
    suggested_followups=[],
)

# A question shaped like c014: {X} present AND a "costs {1} less" phrase --
# the deterministic trigger's exact target shape.
TRIGGER_QUESTION = (
    "A spell that costs {X}{G}{G} gets its cost reduced -- it costs {1} "
    "less. If I cast it with X=2, what does it cost?"
)

# A plain rules question -- no {X}, no cost-changing phrase. Trigger must
# never fire on this.
PLAIN_QUESTION = "Does trample interact with deathtouch?"


# --- _needs_cost_tool: pure trigger unit tests -------------------------------


def test_trigger_fires_on_x_plus_cost_phrase():
    assert ans._needs_cost_tool(TRIGGER_QUESTION, []) is True


def test_trigger_does_not_fire_on_plain_question():
    assert ans._needs_cost_tool(PLAIN_QUESTION, []) is False


def test_trigger_requires_both_x_and_cost_phrase():
    assert ans._needs_cost_tool("What is {X} in a mana cost?", []) is False
    assert ans._needs_cost_tool("This spell costs {1} less now.", []) is False


# --- Change B: exclude mana-PRODUCTION questions (rg289 false positive,
# docs/report-costtool-validation.md Stage 2) -- calculate_cost computes a
# PAID cost via CR 601.2f, the wrong instrument for "how much mana does X
# add." Converge/color-count questions (rg6636/rg6916 shape) are genuine
# multi-modifier {X}-cost firings and must keep firing. ----------------------


def test_trigger_excludes_mana_production_question():
    # rg289 shape: Ice Cauldron's activation cost has {X}; Suppression Field
    # increases activation costs by {2} -- both trip the old trigger, but the
    # question asks how much mana an ability ADDS (produces), not what a
    # spell/ability costs to pay.
    cards = [
        Card(
            name="Ice Cauldron",
            oracle_text=(
                "{X}, {T}: You may exile a nonland card from your hand. You "
                "may cast that card for as long as it remains exiled. Put a "
                "charge counter on this artifact and note the type and "
                "amount of mana spent to pay this activation cost.\n"
                "{T}, Remove a charge counter from this artifact: Add this "
                "artifact's last noted type and amount of mana."
            ),
            type_line="Artifact",
            mana_cost="",
            oracle_id="ice-cauldron",
        ),
        Card(
            name="Suppression Field",
            oracle_text=(
                "Activated abilities cost {2} more to activate unless "
                "they're mana abilities."
            ),
            type_line="Enchantment",
            mana_cost="{2}",
            oracle_id="suppression-field",
        ),
    ]
    question = (
        "Angelina activates Ice Cauldron's first ability with X=1, paying "
        "{C}{C}{C}. On Angelina's next turn, they activate Ice Cauldron's "
        "second ability. How much mana do they add?"
    )
    assert ans._needs_cost_tool(question, cards) is False


def test_trigger_still_fires_on_genuine_converge_x_cost_question():
    # rg6636 shape: Thalia taxes noncreature spells by {1}; Prismatic
    # Ending's own cost is {X}{W} (Converge). A genuine multi-modifier
    # {X}-cost question -- must keep firing, not get excluded by Change B.
    cards = [
        Card(
            name="Thalia, Guardian of Thraben",
            oracle_text="First strike\nNoncreature spells cost {1} more to cast.",
            type_line="Legendary Creature -- Human Soldier",
            mana_cost="{W}",
            oracle_id="thalia",
        ),
        Card(
            name="Prismatic Ending",
            oracle_text=(
                "Converge -- Exile target nonland permanent if its mana "
                "value is less than or equal to the number of colors of "
                "mana spent to cast this spell."
            ),
            type_line="Sorcery",
            mana_cost="{X}{W}",
            oracle_id="prismatic-ending",
        ),
    ]
    question = (
        "Nylah controls Thalia, Guardian of Thraben. If Ali wants to exile "
        "it, how much mana do they need to pay for Prismatic Ending?"
    )
    assert ans._needs_cost_tool(question, cards) is True


# --- Non-tool path stays byte-behaviour-identical ----------------------------


def test_non_triggered_question_never_attaches_tools_kwarg():
    client = _ScriptedToolClient([_FakeResponse("end_turn", [], _REAL_ANSWER)])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(PLAIN_QUESTION)
    assert result.answered is True
    assert len(client.calls) == 1
    assert "tools" not in client.calls[0]
    assert client.calls[0]["system"] == ans.SYSTEM  # no trigger sentence appended
    assert agent.last_tool_calls is None


# --- Triggered path: converges through one tool call -------------------------


def test_triggered_question_converges_after_one_tool_call():
    tool_input = {
        "base_cost": {"generic": 0, "colored": {"G": 2}, "x_coefficient": 1},
        "modifiers": [{"kind": "reduction", "amount": 1, "cite": "test"}],
        "x_values": [2],
    }
    tool_block = _FakeToolUseBlock("toolu_1", "calculate_cost", tool_input)
    client = _ScriptedToolClient([
        _FakeResponse("tool_use", [tool_block], None),
        _FakeResponse("end_turn", [], _REAL_ANSWER),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(TRIGGER_QUESTION)

    assert result is _REAL_ANSWER
    assert len(client.calls) == 2
    # tools= attached on both rounds of the triggered attempt.
    assert client.calls[0]["tools"] == [ans.CALCULATE_COST_TOOL]
    assert client.calls[1]["tools"] == [ans.CALCULATE_COST_TOOL]
    # Trigger sentence appended to system, base SYSTEM left untouched.
    assert client.calls[0]["system"] == ans.SYSTEM + "\n" + ans.TOOL_TRIGGER_SENTENCE
    assert ans.SYSTEM in client.calls[0]["system"]
    # Round 2's message list grew: the assistant tool_use turn + the
    # tool_result turn were appended on top of the original one-message list.
    assert len(client.calls[1]["messages"]) == 3
    assert client.calls[1]["messages"][0]["role"] == "user"
    assert client.calls[1]["messages"][1]["role"] == "assistant"
    assert client.calls[1]["messages"][2]["role"] == "user"
    tool_result_msg = client.calls[1]["messages"][2]["content"][0]
    assert tool_result_msg["type"] == "tool_result"
    assert tool_result_msg["tool_use_id"] == "toolu_1"

    # Telemetry: last_tool_calls records the invocation and its real result.
    assert agent.last_tool_calls is not None
    assert len(agent.last_tool_calls) == 1
    logged = agent.last_tool_calls[0]
    assert logged["name"] == "calculate_cost"
    assert logged["input"] == tool_input
    assert logged["result"]["ok"] is True
    assert logged["result"]["results"][0]["total_mana"] == 3  # matches the hand-derived c014 number


def test_triggered_question_chains_two_tool_calls():
    block_a = _FakeToolUseBlock("toolu_a", "calculate_cost", {
        "base_cost": {"generic": 1, "colored": {}, "x_coefficient": 0}, "modifiers": [],
    })
    block_b = _FakeToolUseBlock("toolu_b", "calculate_cost", {
        "base_cost": {"generic": 2, "colored": {}, "x_coefficient": 0}, "modifiers": [],
    })
    client = _ScriptedToolClient([
        _FakeResponse("tool_use", [block_a], None),
        _FakeResponse("tool_use", [block_b], None),
        _FakeResponse("end_turn", [], _REAL_ANSWER),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(TRIGGER_QUESTION)
    assert result is _REAL_ANSWER
    assert len(client.calls) == 3  # within TOOL_ROUND_CAP (== 4)
    assert len(agent.last_tool_calls) == 2


# --- Name-routed dispatch (docs/plan-layer-system-tool.md Sec 3d must-fix 4)
#
# Before this fix the dispatch loop called _run_calculate_cost
# unconditionally on ANY tool_use block, regardless of block.name, because
# there had only ever been one registered tool. This is must-fix 4 and the
# whole reason the generalisation work exists: once a second tool is
# registered, a tool_use block for it must never be fed to the cost
# calculator's handler.


def test_unrecognized_tool_name_returns_unknown_tool_error_and_skips_calculate_cost(monkeypatch):
    # Swap in a spy for the exact handler registered under "calculate_cost"
    # in _TOOL_DISPATCH -- the real call site the dispatch loop uses. If a
    # mismatched block.name were ever routed to it, this spy would record
    # the call, so an empty `calls` list is positive proof it was never
    # reached (not just an inference from the returned error string).
    #
    # Uses a genuinely unregistered name ("totally_bogus_tool") rather than
    # "resolve_layers" -- resolve_layers is now itself a registered tool
    # (see test_resolve_layers_tool_use_does_not_reach_calculate_cost below
    # for that must-fix-4 case), so it is no longer an example of an
    # UNRECOGNIZED name.
    calls = []

    def _spy_calculate_cost(input_):
        calls.append(input_)
        return {"ok": True, "results": []}

    monkeypatch.setitem(ans._TOOL_DISPATCH, "calculate_cost", _spy_calculate_cost)

    bogus_block = _FakeToolUseBlock("toolu_bogus", "totally_bogus_tool", {"some": "input"})
    client = _ScriptedToolClient([
        _FakeResponse("tool_use", [bogus_block], None),
        _FakeResponse("end_turn", [], _REAL_ANSWER),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(TRIGGER_QUESTION)

    assert result is _REAL_ANSWER
    # The registered calculate_cost handler (now a spy) never fired for a
    # tool_use block named "totally_bogus_tool".
    assert calls == []

    # The tool_result sent back to the model carries the explicit
    # unknown-tool error, not a calculate_cost-shaped payload.
    tool_result_msg = client.calls[1]["messages"][2]["content"][0]
    assert tool_result_msg["tool_use_id"] == "toolu_bogus"
    result_payload = json.loads(tool_result_msg["content"])
    assert result_payload["ok"] is False
    assert "unknown tool" in result_payload["error"]
    assert "totally_bogus_tool" in result_payload["error"]

    # Telemetry still records the call, with the real (error) result.
    assert agent.last_tool_calls[0]["name"] == "totally_bogus_tool"
    assert agent.last_tool_calls[0]["result"]["ok"] is False


# --- Round cap fires on a pathological loop ----------------------------------


def test_round_cap_fires_on_never_ending_tool_use():
    # Every round returns tool_use, never end_turn -- across BOTH retry
    # attempts. The round cap must stop each attempt at TOOL_ROUND_CAP calls
    # rather than looping forever, and the whole answer() call must still
    # return (the honest non-answer), not hang.
    always_tool_use = _FakeResponse(
        "tool_use",
        [_FakeToolUseBlock("toolu_x", "calculate_cost", {
            "base_cost": {"generic": 1, "colored": {}, "x_coefficient": 0}, "modifiers": [],
        })],
        None,
    )
    script = [always_tool_use] * (ans.TOOL_ROUND_CAP * 2)  # 2 attempts worth
    client = _ScriptedToolClient(script)
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(TRIGGER_QUESTION)

    assert result.answered is False
    assert "no structured answer" in result.text
    # Exactly TOOL_ROUND_CAP calls per attempt, 2 attempts -- proves the cap
    # actually bounded the loop rather than exhausting the whole script.
    assert len(client.calls) == ans.TOOL_ROUND_CAP * 2


def test_round_cap_value_leaves_room_for_a_chained_call_plus_terminal_turn():
    # Guard the cap itself: docs/plan-layer-system-tool.md Sec 8.3 (Jon's
    # ruling) raised it from 3 to 4 -- rounds 0-2 tool-capable (room for a
    # chained pair of tool calls, spike Case B's shape, or a self-correcting
    # second call) plus round 3 as the terminal forced-answer turn.
    assert ans.TOOL_ROUND_CAP == 4


# --- Final round forces tool_choice="none" (Phase 4 cap-exhaustion fix) ------
#
# Root cause (Phase 1 instrumented repro, prod claude-sonnet-5, 24
# generations): 16 of 17 failing attempts were cap-exhaustion -- the model
# kept emitting tool_use every round, so the for/else round-cap guard fired
# and the generation degraded to the empty-output sentinel, never because of
# truncation or payload size. The fix forbids tools on the LAST permitted
# round only (tool_choice={"type": "none"}, tools left attached) so the
# model must emit the terminal structured Answer instead of another tool
# call.
#
# _ConditionalToolChoiceClient models a stubborn tool-calling model: it keeps
# returning tool_use forever UNLESS the incoming call's tool_choice is
# exactly {"type": "none"}, in which case it complies and answers. Fed
# through the real loop, this reproduces the cap-exhaustion bug when no
# round ever sends tool_choice="none" (today, pre-fix) and proves recovery
# once the final round does (post-fix).


class _ConditionalToolChoiceClient:
    """Fake .messages.parse() client that only stops calling the tool when
    THIS call's tool_choice is forced to "none" -- otherwise it always
    returns another tool_use, no matter how many rounds have passed. Records
    every call's full kwargs for inspection."""

    def __init__(self):
        self.messages = self
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tool_choice") == {"type": "none"}:
            return _FakeResponse("end_turn", [], _REAL_ANSWER)
        return _FakeResponse(
            "tool_use",
            [_FakeToolUseBlock("toolu_stubborn", "calculate_cost", {
                "base_cost": {"generic": 1, "colored": {}, "x_coefficient": 0},
                "modifiers": [],
            })],
            None,
        )


def test_final_round_forces_tool_choice_none_and_recovers_a_real_answer():
    client = _ConditionalToolChoiceClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(TRIGGER_QUESTION)

    # Exactly TOOL_ROUND_CAP calls: the fix must recover within the first
    # attempt's permitted rounds, not exhaust the cap and retry.
    assert len(client.calls) == ans.TOOL_ROUND_CAP

    # The final permitted round is forced to tool_choice="none" while tools
    # stays attached -- forbidding further tool calls without dropping the
    # tool definitions from the request.
    last_call = client.calls[-1]
    assert last_call["tool_choice"] == {"type": "none"}
    assert last_call["tools"] == [ans.CALCULATE_COST_TOOL]

    # Every earlier round is untouched: no tool_choice key at all (today's
    # call shape, byte-identical).
    for earlier_call in client.calls[:-1]:
        assert "tool_choice" not in earlier_call

    # Forced to answer, the stubborn model complies -- a real, non-empty
    # answer, not the cap-exhaustion degraded sentinel.
    assert result is _REAL_ANSWER
    assert result.answered is True


# --- Cap semantics pinned at the new value (docs/plan-layer-system-tool.md
# Sec 8.3, Jon's ruling): raised from 3 to 4. Rounds 0-2 are tool-capable
# (no tool_choice restriction) and round 3 is the forced-answer round
# (tool_choice={"type": "none"}). Pinned explicitly, on top of the generic
# ans.TOOL_ROUND_CAP-relative assertions above, so a future accidental cap
# change is caught even if someone "fixes" this test to match instead of
# noticing the regression.


def test_tool_round_cap_is_four_with_three_tool_capable_rounds_then_forced_answer():
    assert ans.TOOL_ROUND_CAP == 4

    client = _ConditionalToolChoiceClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(TRIGGER_QUESTION)

    assert len(client.calls) == 4
    tool_capable_rounds = client.calls[:3]
    forced_answer_round = client.calls[3]
    for call in tool_capable_rounds:
        assert "tool_choice" not in call
        assert call["tools"] == [ans.CALCULATE_COST_TOOL]
    assert forced_answer_round["tool_choice"] == {"type": "none"}
    assert forced_answer_round["tools"] == [ans.CALCULATE_COST_TOOL]

    assert result is _REAL_ANSWER
    assert result.answered is True




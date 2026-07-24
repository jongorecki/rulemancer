# Tests for the calculate_cost tool-dispatch loop wired into RulesAgent.answer()
# (docs/plan-cost-calculator-tool.md Sec 3b, docs/spike-tool-use-findings.md).
#
# No network: a scripted fake `.messages.parse()` client, same pattern as
# tests/test_degenerate.py / tests/test_uncited_success.py's _ScriptedClient,
# extended to also record every call's kwargs (so we can assert `tools=` is
# only ever attached when the trigger fires) and to return fake tool_use
# content blocks shaped like the real Anthropic SDK's (`.type`, `.id`,
# `.name`, `.input`).

from rulesagent.contracts import Answer
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
    assert len(client.calls) == 3  # within TOOL_ROUND_CAP == 3
    assert len(agent.last_tool_calls) == 2


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
    # Guard the cap itself: must be >= 3 so a single chained tool call (spike
    # Case B's shape) still has a terminal turn available within the cap.
    assert ans.TOOL_ROUND_CAP >= 3

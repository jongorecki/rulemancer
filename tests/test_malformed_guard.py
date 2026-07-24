# Tests for the malformed-answer guard (docs/report-costtool-validation.md /
# evals/_phase1_costtool_repro_AFTER.log): once the terminal tool_choice=none
# fix (tests/test_cost_tool_loop.py) eliminated empty-output, 7 of 24 phase-1
# generations shipped `answered=True` with GARBLED text instead -- chat-
# template/scratchpad leakage or a bare fragment -- which `_degenerate()`
# (tests/test_degenerate.py) never catches, since it only inspects blank
# text. These tests pin the new, narrower `_malformed()` detector and the
# agent-level routing that retries a malformed draw once, then falls through
# to the same honest non-answer `_degenerate()` already uses -- never
# shipping the garbage, and never reversing the separate last_uncited_success
# (q029) ruling for a coherent-but-uncited answer (tests/test_uncited_success.py).

from rulesagent.contracts import Answer
from rulesagent.generate import answer as ans
from rulesagent.generate.answer import _malformed

# --- Real garbled draws, verbatim from evals/_phase1_costtool_repro_AFTER.log
# (rg6636 rep0, rg6636 rep1, rg6916 rep2, rg897 rep2, rg6636 rep3) ----------

LEAKAGE_TEXT = (
    ".. Let's do actual answer.The above thinking is chatter; now write "
    "final.actual final answer below.completed inline in JSON.actual final "
    "now.assistantfinal 이 답변을 JSON으로 작성합니다.assistantfinal{"
)


def test_leakage_marker_text_is_malformed():
    assert _malformed(LEAKAGE_TEXT) is True


def test_bare_word_fragment_is_malformed():
    assert _malformed("content") is True


def test_short_phrase_fragment_is_malformed():
    assert _malformed("Not needed") is True


def test_single_punctuation_fragment_is_malformed():
    assert _malformed(",") is True


def test_punctuation_soup_fragment_is_malformed():
    assert _malformed(",-.text field..{|answ|>") is True


# --- Negative fixtures: coherent real answers must NEVER match (hard
# guardrail -- catching one of these is worse than missing all the word
# salad below). -------------------------------------------------------------

NEGATIVE_ANSWERS = [
    "Blue Sun's Zenith costs {1}{U}{U}{U} (4 mana total) to draw 2 cards, "
    "and it can't be countered. Here's why: Blue Sun's Zenith has a base "
    "cost of {X}{U}{U}{U}.",
    "Angelina adds {C}{C}{C} (three colorless mana), usable only to cast "
    "the card that was exiled with Ice Cauldron.",
    "Yes -- Chalice of the Void's ability triggers and counters Shivan "
    "Fire. Chalice of the Void has 1 charge counter.",
    "If you cast Awaken the Woods with X=0, it still costs {1}{G}{G} (3 "
    "total mana) once Trinisphere finishes its work.",
]


def test_negative_fixtures_are_never_malformed():
    for text in NEGATIVE_ANSWERS:
        assert _malformed(text) is False, text


# --- Agent-level tests (fake client, no network) ----------------------------
# Same _ScriptedClient/_FakeResponse/_EmptyStore pattern as
# tests/test_degenerate.py and tests/test_uncited_success.py.


class _FakeResponse:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class _ScriptedClient:
    def __init__(self, script):
        self.messages = self
        self._script = list(script)
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _FakeResponse(item)


class _EmptyStore:
    def search(self, query, k):
        return []


def _answer(**overrides) -> Answer:
    defaults = dict(
        text="", tldr="", citations=[], answered=True, suggested_followups=[],
    )
    defaults.update(overrides)
    return Answer(**defaults)


def test_first_attempt_malformed_second_attempt_real_returns_real_answer():
    real = Answer(
        text="A" * 300, tldr="tldr", citations=["100.1"],
        answered=True, suggested_followups=[],
    )
    client = _ScriptedClient([_answer(text="content"), real])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert result.text.startswith("A" * 300)
    assert result.answered is True
    assert client.calls == 2


def test_both_attempts_malformed_returns_honest_non_answer():
    client = _ScriptedClient([
        _answer(text=","),
        _answer(text="Not needed"),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert result.answered is False
    assert result.text != ""
    assert "no structured answer" in result.text
    # The garbled draws are never shipped, even as a "weak" fallback -- same
    # shape as the q029 blank-answered-true case (only an honest decline is
    # ever reused as `weak`).
    assert "content" not in result.text
    assert "Not needed" not in result.text


def test_leakage_text_alone_triggers_honest_non_answer_after_retry():
    client = _ScriptedClient([
        _answer(text=LEAKAGE_TEXT),
        _answer(text=LEAKAGE_TEXT),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert result.answered is False
    assert "no structured answer" in result.text


def test_coherent_uncited_answer_is_not_treated_as_malformed():
    # Hard guardrail: a COHERENT prose answer that merely lacks citations
    # must stay on the existing last_uncited_success path (flagged, not
    # retried) -- the malformed guard must never fire on it.
    real_but_uncited = Answer(
        text="A" * 300, tldr="tldr", citations=[],
        answered=True, suggested_followups=[],
    )
    client = _ScriptedClient([real_but_uncited])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert client.calls == 1  # not retried
    assert result.answered is True
    assert result.citations == []
    assert agent.last_uncited_success is True

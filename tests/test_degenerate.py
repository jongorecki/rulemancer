# Tests for q029 empty-answer guard (docs/plan-q029-empty-answer-guard.md,
# Plan A). L1's gate 4 caught `answered:true` with fully blank `text` slipping
# past `_degenerate()`, which today only inspects the `answered=False` branch.
# These tests pin the extended behavior: (1) direct unit tests of
# `_degenerate()` itself, and (2) agent-level tests, via the same
# fake-`.messages.parse`-client pattern tests/test_answer_prompt_v3.py uses,
# that the retry/weak-fallback machinery in `answer()` actually routes a
# q029-shaped draw correctly end to end.

import pytest
from pydantic import ValidationError

from rulesagent.contracts import Answer
from rulesagent.generate import answer as ans
from rulesagent.generate.answer import _degenerate


def _answer(**overrides) -> Answer:
    defaults = dict(
        text="", tldr="", citations=[], answered=True, suggested_followups=[],
    )
    defaults.update(overrides)
    return Answer(**defaults)


# --- 1-7: _degenerate() unit tests -----------------------------------------


def test_answered_true_blank_text_is_degenerate():
    # 1. exact q029 shape.
    assert _degenerate(_answer(answered=True, text="")) is True


def test_answered_true_whitespace_only_text_is_degenerate():
    # 2.
    assert _degenerate(_answer(answered=True, text="   \n\t")) is True


def test_answered_true_terse_legit_answer_is_not_degenerate():
    # 3. regression guard for terse legit answers -- NOT caught.
    assert _degenerate(_answer(answered=True, text="Yes.")) is False


def test_answered_true_blank_text_with_citations_is_still_degenerate():
    # 4. blank text is bad regardless of citations.
    assert _degenerate(_answer(answered=True, text="", citations=["100.1"])) is True


def test_answered_false_blank_no_citations_is_degenerate():
    # 5. existing case, regression guard.
    assert _degenerate(_answer(answered=False, text="", citations=[])) is True


def test_answered_false_honest_decline_is_not_degenerate():
    # 6. existing case, regression guard: 200+ char honest decline.
    long_decline = (
        "The provided rules don't cover this specific interaction in enough "
        "detail to answer confidently -- the context is missing the rule "
        "governing replacement effect ordering for this zone change, so I "
        "can't say for certain what happens here without guessing."
    )
    assert len(long_decline) >= 200
    assert _degenerate(_answer(answered=False, text=long_decline, citations=[])) is False


def test_answered_true_real_answer_with_citations_is_not_degenerate():
    # 7. regression guard.
    real = "A" * 300
    assert _degenerate(_answer(answered=True, text=real, citations=["100.1"])) is False


# --- 8-12: agent-level tests (fake client, no network) ----------------------


class _Recorded(Exception):
    pass


class _FakeResponse:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class _ScriptedClient:
    """Fake .messages.parse() client that returns a scripted sequence of
    results, one per call -- either an Answer (wrapped as a fake response) or
    an exception instance to raise."""

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


def _validation_error() -> ValidationError:
    try:
        Answer.model_validate({})
    except ValidationError as e:
        return e
    raise AssertionError("expected ValidationError")


def test_first_attempt_q029_shaped_second_attempt_real_returns_real_answer():
    # 8. Attempt 1 q029-shaped, attempt 2 real answer -> answer() returns the
    # real answer.
    real = Answer(
        text="A" * 300, tldr="tldr", citations=["100.1"],
        answered=True, suggested_followups=[],
    )
    client = _ScriptedClient([_answer(answered=True, text=""), real])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert result.text.startswith("A" * 300)
    assert result.answered is True
    assert client.calls == 2


def test_both_attempts_q029_shaped_returns_honest_non_answer():
    # 9. Both attempts q029-shaped -> answer() returns the honest non-answer
    # Answer (answered=False), not either blank draft -- the fallback-guard
    # test (weak-selection tie-break: a blank answered=true draw must never
    # be returned as-is even after both retries).
    client = _ScriptedClient([
        _answer(answered=True, text=""),
        _answer(answered=True, text="   "),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert result.answered is False
    assert result.text != ""
    assert "no structured answer" in result.text


def test_first_attempt_q029_shaped_second_raises_validation_error_falls_back():
    # 10. Attempt 1 q029-shaped, attempt 2 raises ValidationError -> same
    # honest fallback (the blank answered=true weak draw is never used).
    client = _ScriptedClient([
        _answer(answered=True, text=""),
        _validation_error(),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("does trample work with deathtouch")
    assert result.answered is False
    assert "no structured answer" in result.text


def test_existing_false_branch_degenerate_still_retries_no_regression():
    # 11. Existing False-branch degenerate case still retries as before.
    honest_decline = (
        "The provided rules don't cover this specific interaction in enough "
        "detail to answer confidently -- the context is missing the rule "
        "governing replacement effect ordering for this zone change, so I "
        "can't say for certain what happens here without guessing at all."
    )
    client = _ScriptedClient([
        _answer(answered=False, text="", citations=[]),
        _answer(answered=False, text=honest_decline, citations=[]),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer("some obscure rules question")
    assert result.answered is False
    assert result.text == honest_decline
    assert client.calls == 2


def test_no_cards_path_with_q029_shaped_draw():
    # 12. No-cards path with a q029-shaped draw (q029's real question had no
    # bracketed cards) -- confirms the guard fires on a plain, card-free
    # question, not just in a card-referencing scenario.
    client = _ScriptedClient([
        _answer(answered=True, text=""),
        _answer(answered=True, text=""),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    result = agent.answer(
        "If a permanent phases out during the cleanup step, does it phase "
        "back in before or after the next untap step begins?"
    )
    assert result.answered is False
    assert "no structured answer" in result.text

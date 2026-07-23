# Tests for c012 silent-drop observability (docs/plan-q029-empty-answer-guard.md,
# Plan B). RulesAgent.answer()'s card-ref resolution comprehension has zero
# observability: a confirmed 404 miss and a transient fetch error both
# vanish silently (the fetch error currently CRASHES the whole request
# instead). These tests pin the replacement loop: both outcomes are recorded
# on `agent.last_unresolved_refs`, logged as a warning, and a transient fetch
# error degrades gracefully instead of crashing `answer()`.
#
# Same monkeypatch-at-import-site seam as tests/test_answer_prompt_v3.py's
# `spies` fixture (`get_card` patched on the `answer` module's own
# namespace, since it does `from ...scryfall import get_card`).

import logging

import httpx
import pytest

from rulesagent.contracts import Answer, Card
from rulesagent.generate import answer as ans


class _Recorded(Exception):
    pass


class _RecordingClient:
    def __init__(self):
        self.messages = self
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        raise _Recorded


class _FakeResponse:
    def __init__(self, parsed_output):
        self.parsed_output = parsed_output


class _ScriptedClient:
    def __init__(self, script):
        self.messages = self
        self._script = list(script)

    def parse(self, **kwargs):
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _FakeResponse(item)


class _EmptyStore:
    def search(self, query, k):
        return []


def _stub_card(name: str) -> Card:
    return Card(
        name=name,
        oracle_text=f"{name} oracle text.",
        type_line="Instant",
        mana_cost="{1}{U}",
        oracle_id=f"oracle-{name.lower()}",
        rulings=[],
    )


def _real_answer() -> Answer:
    return Answer(
        text="A" * 200, tldr="tldr", citations=["100.1"],
        answered=True, suggested_followups=[],
    )


def _fake_get_card(outcomes: dict):
    """outcomes: {ref -> Card | None | Exception instance}."""

    def fake(ref, no_refresh=False):
        outcome = outcomes[ref]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return fake


def test_all_refs_resolve_gives_empty_unresolved_list(monkeypatch):
    # 1.
    monkeypatch.setattr(ans, "get_card", _fake_get_card({
        "Bolt": _stub_card("Bolt"), "Fork": _stub_card("Fork"),
    }))
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)
    with pytest.raises(_Recorded):
        agent.answer("[Bolt] and [Fork] question")
    assert agent.last_unresolved_refs == []


def test_one_not_found_among_two_refs_is_recorded_and_logged(monkeypatch, caplog):
    # 2.
    monkeypatch.setattr(ans, "get_card", _fake_get_card({
        "Bolt": _stub_card("Bolt"), "Missing": None,
    }))
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)
    with caplog.at_level(logging.WARNING, logger="rulesagent.generate.answer"):
        with pytest.raises(_Recorded):
            agent.answer("[Bolt] and [Missing] question")
    assert agent.last_unresolved_refs == [{"ref": "Missing", "reason": "not_found"}]
    assert len(agent.last_cards) == 1
    assert agent.last_cards[0].name == "Bolt"
    assert any("Missing" in r.message for r in caplog.records)


def test_transient_fetch_error_does_not_crash_answer(monkeypatch, caplog):
    # 3. The crash->graceful regression test: a raised exception from
    # get_card (simulated httpx error) must not propagate out of answer();
    # the other ref still resolves; reason:"error" is recorded; a warning
    # is logged.
    monkeypatch.setattr(ans, "get_card", _fake_get_card({
        "Bolt": _stub_card("Bolt"),
        "Missing": httpx.ConnectError("simulated transient failure"),
    }))
    client = _ScriptedClient([_real_answer()])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    with caplog.at_level(logging.WARNING, logger="rulesagent.generate.answer"):
        result = agent.answer("[Bolt] and [Missing] question")
    assert result.answered is True
    assert agent.last_unresolved_refs == [{"ref": "Missing", "reason": "error"}]
    assert len(agent.last_cards) == 1
    assert any("Missing" in r.message for r in caplog.records)


def test_failing_ref_referenced_only_in_history_is_still_recorded(monkeypatch):
    # 4.
    monkeypatch.setattr(ans, "get_card", _fake_get_card({"Missing": None}))
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)
    history = [{"role": "user", "content": "[Missing] card question"}]
    with pytest.raises(_Recorded):
        agent.answer("a follow-up question with no brackets", history=history)
    assert agent.last_unresolved_refs == [{"ref": "Missing", "reason": "not_found"}]


def test_no_brackets_gives_empty_unresolved_list_and_no_warnings(monkeypatch, caplog):
    # 5.
    calls = []

    def fake_get_card(ref, no_refresh=False):
        calls.append(ref)
        raise AssertionError("get_card should never be called with no refs")

    monkeypatch.setattr(ans, "get_card", fake_get_card)
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)
    with caplog.at_level(logging.WARNING, logger="rulesagent.generate.answer"):
        with pytest.raises(_Recorded):
            agent.answer("a plain rules question with no card refs")
    assert agent.last_unresolved_refs == []
    assert calls == []
    assert not any("card ref failed to resolve" in r.message for r in caplog.records)

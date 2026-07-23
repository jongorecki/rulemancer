# Tests for the Plan A amendment (docs/plan-q029-empty-answer-guard.md header
# ruling 1, binding): additionally FLAG (surface, do NOT retry) any
# `answered:true` answer with zero citations -- "then it's not grounding in
# the rules." Blank text still triggers the existing retry/degenerate
# machinery (tests/test_degenerate.py); this is the separate, non-retried
# surfacing for a non-blank `answered:true` draw that nonetheless cites
# nothing -- a real answer, single attempt, log warning + a Debug field, so
# the ungrounded "success" is auditable without being auto-retried (respects
# the false-positive concern for legitimately card-only-grounded answers).

import logging

from rulesagent.contracts import Answer
from rulesagent.generate import answer as ans
from rulesagent.api import main


class _FakeResponse:
    def __init__(self, parsed_output):
        self.parsed_output = parsed_output


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


def test_answered_true_no_citations_is_flagged_not_retried(caplog):
    real_but_uncited = Answer(
        text="A" * 300, tldr="tldr", citations=[],
        answered=True, suggested_followups=[],
    )
    client = _ScriptedClient([real_but_uncited])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    with caplog.at_level(logging.WARNING, logger="rulesagent.generate.answer"):
        result = agent.answer("does trample work with deathtouch")
    # Surfaced, not retried: only ONE client call, the draw is returned as-is.
    assert client.calls == 1
    assert result.answered is True
    assert result.citations == []
    assert agent.last_uncited_success is True
    assert any("no citations" in r.message.lower() for r in caplog.records)


def test_answered_true_with_citations_is_not_flagged():
    real = Answer(
        text="A" * 300, tldr="tldr", citations=["100.1"],
        answered=True, suggested_followups=[],
    )
    client = _ScriptedClient([real])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    agent.answer("does trample work with deathtouch")
    assert agent.last_uncited_success is False


def test_answered_false_no_citations_does_not_set_uncited_flag():
    # answered=false + no citations is the EXISTING _degenerate() concern
    # (retried); it's not what this new flag is about (which is scoped to
    # answered=true only).
    honest_decline = (
        "The provided rules don't cover this specific interaction in enough "
        "detail to answer confidently -- the context is missing the rule "
        "governing replacement effect ordering for this zone change entirely."
    )
    client = _ScriptedClient([
        Answer(text=honest_decline, tldr="t", citations=[], answered=False, suggested_followups=[]),
    ])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    agent.answer("some obscure rules question")
    assert agent.last_uncited_success is False


class _FakeAgent:
    model = "fake-model"

    def __init__(self, uncited_success):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []
        self.last_uncited_success = uncited_success

    def answer(self, question, history=None):
        return Answer(
            text="An ungrounded-looking success.", tldr="tldr", citations=[],
            answered=True, suggested_followups=[],
        )


def test_debug_uncited_success_mirrors_agent_attribute(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent(True))
    monkeypatch.setitem(main._state, "chunk_map", {})
    req = main.AnswerRequest(question="a plain question")
    resp = main.answer(req)
    assert resp.debug.uncited_success is True

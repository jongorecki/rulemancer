# API-level test for the fuzzy-fallback / ambiguity-guard debug surface
# (docs/plan-scryfall-local-bulk.md Sec 4): Debug.fuzzy_fallbacks must
# surface whatever RulesAgent.answer() recorded on
# agent.last_fuzzy_fallbacks for that request. Same pattern as
# tests/test_api_debug.py's unresolved_card_refs test.

from rulesagent.api import main
from rulesagent.contracts import Answer


class _FakeAgent:
    model = "fake-model"

    def __init__(self, fuzzy_fallbacks):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []
        self.last_fuzzy_fallbacks = fuzzy_fallbacks

    def answer(self, question, history=None):
        return Answer(
            text="An honest answer.", tldr="tldr", citations=[],
            answered=True, suggested_followups=[],
        )


class _FakeAgentNoAttr:
    """A store double that predates this slice -- no last_fuzzy_fallbacks
    attribute at all. main.py must degrade to an empty list, not crash
    (mirrors the existing getattr guard for last_uncited_success)."""

    model = "fake-model"

    def __init__(self):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []

    def answer(self, question, history=None):
        return Answer(
            text="An honest answer.", tldr="tldr", citations=[],
            answered=True, suggested_followups=[],
        )


def test_debug_fuzzy_fallbacks_matches_agent_attribute(monkeypatch):
    events = [{
        "ref": "Lightning Blot", "reason": "fuzzy_match",
        "matched_name": "Lightning Bolt", "oracle_id": "oracle-bolt",
        "score": 92.0, "candidates": [],
    }]
    monkeypatch.setitem(main._state, "agent", _FakeAgent(events))
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="[Lightning Blot] does this work?")
    resp = main.answer(req)

    assert resp.debug.fuzzy_fallbacks == events


def test_debug_fuzzy_fallbacks_empty_when_none_fired(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent([]))
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="a plain rules question")
    resp = main.answer(req)

    assert resp.debug.fuzzy_fallbacks == []


def test_debug_fuzzy_fallbacks_degrades_to_empty_list_when_agent_lacks_attr(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgentNoAttr())
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="a plain rules question")
    resp = main.answer(req)

    assert resp.debug.fuzzy_fallbacks == []

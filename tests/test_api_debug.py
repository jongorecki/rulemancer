# Minimal API-level test for c012 observability (docs/plan-q029-empty-answer-
# guard.md, Plan B, TDD item 6): Debug.unresolved_card_refs must surface
# whatever RulesAgent.answer() recorded on agent.last_unresolved_refs for
# that request.
#
# Deliberately does NOT go through FastAPI's lifespan (which loads the real
# vector store + a live anthropic client) -- main.answer() is a plain
# function that reads module-level `_state`, so a fake agent double is
# substituted directly and the route function is called in-process. No
# network, no TestClient, no ANTHROPIC_API_KEY needed.

from rulesagent.api import main
from rulesagent.contracts import Answer


class _FakeAgent:
    model = "fake-model"

    def __init__(self, unresolved):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = unresolved

    def answer(self, question, history=None):
        return Answer(
            text="An honest answer.", tldr="tldr", citations=[],
            answered=True, suggested_followups=[],
        )


def test_debug_unresolved_card_refs_matches_agent_attribute(monkeypatch):
    unresolved = [{"ref": "Missing", "reason": "not_found"}]
    monkeypatch.setitem(main._state, "agent", _FakeAgent(unresolved))
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="[Missing] does this work?")
    resp = main.answer(req)

    assert resp.debug.unresolved_card_refs == unresolved


def test_debug_unresolved_card_refs_empty_when_all_resolved(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent([]))
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="a plain rules question")
    resp = main.answer(req)

    assert resp.debug.unresolved_card_refs == []

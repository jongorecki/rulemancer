# Tests for the fuzzy-fallback / ambiguity-guard debug surface
# (docs/plan-scryfall-local-bulk.md Sec 4): "Always flagged, never silent --
# every fuzzy-fallback hit is logged and surfaced in the API's debug
# payload." get_card()'s own signature/return type stay unchanged, so this
# travels via scryfall.pop_fuzzy_fallbacks(), drained once per answer() call
# onto agent.last_fuzzy_fallbacks -- same lifecycle as last_unresolved_refs
# (tests/test_unresolved_refs.py), mirrored here.

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


class _EmptyStore:
    def search(self, query, k):
        return []


def _stub_card(name: str) -> Card:
    return Card(
        name=name, oracle_text=f"{name} text.", type_line="Instant",
        mana_cost="{1}{U}", oracle_id=f"oracle-{name.lower()}", rulings=[],
    )


def test_fuzzy_fallbacks_empty_when_none_fired(monkeypatch):
    monkeypatch.setattr(ans, "get_card", lambda ref, no_refresh=False: _stub_card(ref))
    monkeypatch.setattr(ans, "pop_fuzzy_fallbacks", lambda: [])
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)

    with pytest.raises(_Recorded):
        agent.answer("[Bolt] question")

    assert agent.last_fuzzy_fallbacks == []


def test_fuzzy_fallbacks_surfaced_from_scryfall_side_channel(monkeypatch):
    event = {
        "ref": "Lightning Blot", "reason": "fuzzy_match",
        "matched_name": "Lightning Bolt", "oracle_id": "oracle-bolt",
        "score": 92.0, "candidates": [],
    }
    monkeypatch.setattr(ans, "get_card", lambda ref, no_refresh=False: _stub_card("Bolt"))
    monkeypatch.setattr(ans, "pop_fuzzy_fallbacks", lambda: [event])
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)

    with pytest.raises(_Recorded):
        agent.answer("[Lightning Blot] question")

    assert agent.last_fuzzy_fallbacks == [event]


def test_fuzzy_fallbacks_default_empty_list_before_first_answer_call():
    agent = ans.RulesAgent(_EmptyStore(), client=_RecordingClient())

    assert agent.last_fuzzy_fallbacks == []

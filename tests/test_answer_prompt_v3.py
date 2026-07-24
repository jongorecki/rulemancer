# Tests for generator prompt v3 (docs/plan-prompt-tuning.md Sec 1, Task 1 in
# docs/plan-v3-execution-tasks.md) and the RulesAgent-level config for
# selectable rewriter version + the Part B ruling-query union toggle
# (Sec 2c is parked -- NOT this).
#
# TDD: the union-toggle dispatch test is written before RulesAgent gains a
# `ruling_query_mode` param -- watch it fail first (TypeError: unexpected
# keyword argument), then implement.
#
# No network/embeddings/vector store needed: get_card, select_rulings, and
# select_rulings_union are all monkeypatched at the point answer.py imports
# them, and the generation client is a recording fake that raises the
# instant .messages.parse() is called (same pattern as
# tests/test_prompt_identity.py's _RecordingClient / evals/
# run_openrouter_arm.py's copy of it) -- rewrite_query() is fed the SAME fake
# client, so its own internal try/except swallows the fake's raise and falls
# back to queries=[question], keeping the whole call offline and deterministic.

# Restored 2026-07-25 (docs/plan-v5-symbol-injection.md Slice 1). v3 is
# production again and now lives in ans.SYSTEM_VERSIONS[3], so these
# assertions target the registry entry rather than the module-level
# SYSTEM alias -- they keep guarding v3 no matter which version ships.

import pytest

from rulesagent.contracts import Card
from rulesagent.generate import answer as ans


def test_prompt_version_is_3():
    assert ans.PROMPT_VERSION == 3


def test_system_contains_all_six_new_bullets_verbatim_key_phrases():
    s = ans.SYSTEM_VERSIONS[3]
    # 1a
    assert "never by a role word" in s
    assert "substitute its full name instead" in s
    # 1b
    assert "Mana symbols are not interchangeable" in s
    assert "break it out by symbol rather than only giving a lump number" in s
    # 1c (replaces the old multiplayer bullet)
    assert "don't assume a two-player game" in s
    assert "do not invent multiplayer rules that weren't provided" in s
    assert "If the provided rules cover multiplayer or Commander cases, address" not in s
    # 1d
    assert "say plainly which timing you're assuming" in s
    # 1e
    assert "A card's own printed rules text always wins" in s
    # 1f
    assert "Open the text field with a direct, unmistakable answer" in s


def test_system_bullet_order_matches_plan_insert_points():
    """1a is the new first bullet (before the old [1] citations bullet); 1b
    sits between [3] define-key-term and [4] name-zones; 1d sits between [6]
    accurate-and-to-the-point and [7] card-data; 1e sits between [7] and [8]
    ruling-authoritative; 1f sits between [9] ruling-label and [10] tldr."""
    s = ans.SYSTEM_VERSIONS[3]
    i_1a = s.index("never by a role word")
    i_cite = s.index("Cite the exact rule numbers")
    i_define = s.index("Define any key term")
    i_1b = s.index("Mana symbols are not interchangeable")
    i_zones = s.index("Name the specific zones")
    i_1c = s.index("don't assume a two-player game")
    i_accurate = s.index("Keep the answer accurate and to the point")
    i_1d = s.index("say plainly which timing you're assuming")
    i_carddata = s.index('labeled "Card data"')
    i_1e = s.index("A card's own printed rules text always wins")
    i_ruling_auth = s.index("A provided ruling is itself authoritative")
    i_ruling_label = s.index('Card rulings in the context are labeled')
    i_1f = s.index("Open the text field with a direct")
    i_tldr = s.index("Fill the tldr field")

    assert i_1a < i_cite < i_define < i_1b < i_zones < i_1c < i_accurate
    assert i_accurate < i_1d < i_carddata < i_1e < i_ruling_auth < i_ruling_label
    assert i_ruling_label < i_1f < i_tldr


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
        name=name,
        oracle_text=f"{name} oracle text.",
        type_line="Instant",
        mana_cost="{1}{U}",
        oracle_id=f"oracle-{name.lower()}",
        rulings=[f"{name} ruling zero.", f"{name} ruling one."],
    )


@pytest.fixture
def spies(monkeypatch):
    """Monkeypatch get_card + select_rulings + select_rulings_union at the
    names answer.py actually calls (its own module namespace, since it does
    `from ... import get_card` etc.) and return the call-recording dicts."""
    calls = {"select_rulings": [], "select_rulings_union": []}

    def fake_get_card(ref, no_refresh=False):
        return _stub_card(ref)

    def fake_select_rulings(card, question):
        calls["select_rulings"].append((card.name, question))
        return [(0, 0.9)]

    def fake_select_rulings_union(card, queries):
        calls["select_rulings_union"].append((card.name, list(queries)))
        return [(0, 0.9)]

    monkeypatch.setattr(ans, "get_card", fake_get_card)
    monkeypatch.setattr(ans, "select_rulings", fake_select_rulings)
    monkeypatch.setattr(ans, "select_rulings_union", fake_select_rulings_union)
    return calls


def test_ruling_query_mode_defaults_to_raw(spies):
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client)
    assert agent.ruling_query_mode == "raw"
    with pytest.raises(_Recorded):
        agent.answer("[Bolt] question about it")
    assert spies["select_rulings"] == [("Bolt", "Bolt question about it")]
    assert spies["select_rulings_union"] == []


def test_ruling_query_mode_union_uses_question_plus_rewrites(spies):
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client, ruling_query_mode="union")
    with pytest.raises(_Recorded):
        agent.answer("[Bolt] question about it")
    assert spies["select_rulings"] == []
    assert len(spies["select_rulings_union"]) == 1
    name, queries = spies["select_rulings_union"][0]
    assert name == "Bolt"
    # rewrite_query's own fallback (fake client raises -> caught -> falls
    # back to queries=[question]) means the union query set is exactly
    # [question] here -- still proves the union path was taken and was fed
    # the question, without needing a real rewrite.
    assert queries == ["Bolt question about it"]


def test_ruling_query_mode_union_without_rewrite_falls_back_to_question_only(spies):
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client, ruling_query_mode="union", rewrite=False)
    with pytest.raises(_Recorded):
        agent.answer("[Bolt] question about it")
    name, queries = spies["select_rulings_union"][0]
    assert queries == ["Bolt question about it"]


def test_rulesagent_defaults_rewrite_version_to_v2():
    agent = ans.RulesAgent(_EmptyStore())
    assert agent.rewrite_version == "v2"


def test_rulesagent_threads_rewrite_version_into_rewrite_query(monkeypatch):
    captured = {}

    def fake_rewrite_query(question, model, n, client, context=None, version="v2"):
        captured["version"] = version
        from rulesagent.contracts import RewrittenQuery
        return RewrittenQuery(original=question, queries=[question], clarification=None)

    monkeypatch.setattr(ans, "rewrite_query", fake_rewrite_query)
    client = _RecordingClient()
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite_version="v1")
    with pytest.raises(_Recorded):
        agent.answer("does trample work with deathtouch")
    assert captured["version"] == "v1"

# Tests for generator prompt v4 (docs/plan-prompt-v4.md Sec 2 (4a-4e) + Sec 3
# row 3b, docs/plan-v4e-execution-tasks.md Task 1). Replaces
# tests/test_answer_prompt_v3.py's SYSTEM-content assertions (v3 is
# production again as of 2026-07-25 and lives in SYSTEM_VERSIONS[3]; it is
# no longer reachable only through the
# frozen eval capture, evals/answers/_prompts_C.json) while keeping that
# file's RulesAgent-config tests (ruling_query_mode dispatch, rewrite_version
# threading), which are orthogonal to SYSTEM content and unaffected by the
# v3 -> v4 bump.
#
# No network/embeddings/vector store needed: get_card, select_rulings, and
# select_rulings_union are all monkeypatched at the point answer.py imports
# them, and the generation client is a recording fake that raises the
# instant .messages.parse() is called (same pattern as
# tests/test_prompt_identity.py's _RecordingClient / evals/
# run_openrouter_arm.py's copy of it) -- rewrite_query() is fed the SAME fake
# client, so its own internal try/except swallows the fake's raise and falls
# back to queries=[question], keeping the whole call offline and deterministic.

import pytest

from rulesagent.contracts import Card
from rulesagent.generate import answer as ans


def test_v4_is_selectable_but_not_production():
    # v4 was REVERTED from production 2026-07-25 (it failed its own go
    # criterion) but is retained as a runnable prompt because the v5 grid
    # generates from it. Assert it is still selectable, and that it is NOT
    # what production ships -- test_answer_prompt_v3 owns that assertion.
    assert 4 in ans.SYSTEM_VERSIONS
    assert ans.PROMPT_VERSION != 4


def test_system_contains_3b_intro_clause():
    s = ans.SYSTEM_VERSIONS[4]
    assert "State assumptions when the context doesn't cover something" in s


def test_system_contains_1a_untouched_full_card_names_bullet():
    """1a is untouched by v4 -- carried over from the old test_answer_
    prompt_v3.py (removed in this bump), which asserted both phrases below;
    the fix-loop review flagged that "substitute its full name instead" lost
    coverage when that file was deleted, so it's restored here."""
    s = ans.SYSTEM_VERSIONS[4]
    assert "never by a role word" in s
    assert "substitute its full name instead" in s


def test_system_contains_4a_notation_legend_both_tiers():
    s = ans.SYSTEM_VERSIONS[4]
    # CORE tier: generic/colorless/colored/hybrid/Phyrexian/{X}/tap/untap.
    assert "Notation legend, CORE tier" in s
    assert "N generic mana, payable with any color or with colorless mana" in s
    assert "colorless mana specifically -- it is NOT generic" in s
    assert "cost can be paid with one mana of EITHER named color" in s  # hybrid
    # Fix-loop correction (CR 107.4e): monocolored hybrids like {2/B} are
    # NOT "one mana of a color" on both halves -- the numeral half is "two
    # mana of any type," not one generic mana.
    assert "a monocolored hybrid symbol such as {2/B} can be paid with " \
           "either one mana of that color or two mana of any type" in s
    assert "OR by paying 2 life instead" in s  # Phyrexian
    assert "{T} in a cost means \"tap this permanent\"" in s
    assert "{Q} means \"untap this permanent.\"" in s
    # Cost math + worked example (ruling #3: worked example retained).
    assert "cost-REDUCTION effect" in s
    assert "never goes below {0} generic" in s
    assert "{1}{G}{G}" in s
    # REFERENCE tier: energy/snow/loyalty, labeled untested-by-current-eval.
    assert "Notation legend, REFERENCE tier" in s
    assert "not exercised by the current eval question set" in s
    assert "{E} means one energy counter" in s
    assert "one mana of any type produced by a snow source" in s
    assert "loyalty symbol on a planeswalker ability" in s
    # v3's definitions-only mana bullet is gone, replaced in place.
    assert "Mana symbols are not interchangeable" not in s


def test_system_contains_scryfall_hybrid_families_and_mana_value_rule():
    """Second fix-loop pass (Scryfall's "Colors and Costs" API doc, supplied
    verbatim by the controller since the page 403s automated fetches): the
    colorless-hybrid/hybrid-Phyrexian/{C/P}/{H} families extend the existing
    hybrid sentences, plus the mana-value COUNTING rule (highest-value
    addition per Jon/the coordinator -- targets the c014 cluster's
    mana-arithmetic failures)."""
    s = ans.SYSTEM_VERSIONS[4]
    assert "a colorless hybrid symbol such as {C/W} is paid with one " \
           "colorless mana or one mana of the named color" in s
    assert "a hybrid Phyrexian symbol such as {W/U/P} is paid with one " \
           "mana of either named color or 2 life" in s
    assert "{C/P} is paid with one colorless mana or 2 life" in s
    # Second correction: {H} is "any colored mana," not a single fixed
    # color -- Scryfall's table says "One colored mana or two life," and
    # CR 107.4g confirms {H} with no colored background means any of the
    # fifteen Phyrexian symbols, not the card's own color.
    assert "{H} is paid with one colored mana of any color, or 2 life" in s
    assert "{H} is paid with one mana of the card's color" not in s
    # The mana-value counting rule.
    assert "For a mana value or total-cost COUNT" in s
    assert "counts as 1 no matter which half would be paid" in s
    assert "a monocolored hybrid such as {2/W} counts as 2" in s
    assert "{X}, {Y}, and {Z} count as 0 wherever the object isn't on " \
           "the stack" in s
    # Jon's ruling (second correction): half/infinite symbols are Un-set
    # only, never tournament-legal, and are dropped from the legend
    # entirely -- not in the mana-value rule, not in REFERENCE tier.
    assert "half symbol" not in s
    assert "{HW}" not in s
    assert "{HR}" not in s
    assert "½" not in s  # {½}
    assert "∞" not in s  # {∞}


def test_system_contains_reference_tier_rare_and_nonmana_symbols():
    s = ans.SYSTEM_VERSIONS[4]
    assert "{L} means one mana from a legendary source" in s
    assert "{Y} and {Z} work like {X} as extra variables" in s
    assert "{PW} marks a planeswalker" in s
    # Second correction: Scryfall's table just says "Chaos" -- the
    # Planechase attribution was an unsourced addition, trimmed.
    assert "{CHAOS} is the Chaos symbol" in s
    assert "{CHAOS} is the Chaos symbol on Planechase" not in s
    assert "{A} is an acorn counter" in s
    assert "{TK} is a ticket counter" in s
    assert "{D} means one potential land drop" in s
    # CRITICAL disambiguation: bare {P} is the modal budget pawprint, NOT
    # Phyrexian mana (which always carries a color component).
    assert "MODAL BUDGET PAWPRINT" in s
    assert "NOT Phyrexian mana" in s
    assert "Phyrexian mana always has a color component" in s


def test_system_contains_4b_revised_multiplayer_bullet():
    s = ans.SYSTEM_VERSIONS[4]
    assert "state each outcome separately and say which is which" in s
    assert "\"defending player(s)\" (plural-aware)" in s
    assert "do not invent multiplayer rules that weren't provided" in s


def test_system_contains_4c_generalized_assumption_bullet_alongside_1d():
    s = ans.SYSTEM_VERSIONS[4]
    # 1d (timing) stays, unchanged, its own bullet.
    assert "say plainly which timing you're assuming" in s
    assert "Never resolve an ambiguous timing question as if only one order were" in s
    # 4c: separate, general bullet -- not merged into 1d.
    assert "When the answer depends on a fact the question doesn't state" in s
    assert "don't ask the question back to the user" in s


def test_system_contains_4d_answer_intended_question_bullet():
    s = ans.SYSTEM_VERSIONS[4]
    assert "Answer the practical question a player is actually asking" in s


def test_system_contains_4e_no_false_starts_clause_on_1f():
    s = ans.SYSTEM_VERSIONS[4]
    assert "Open the text field with a direct, unmistakable answer" in s
    assert ("Never write a claim in the text field that you're about to "
            "contradict a sentence later") in s
    assert "discard it rather than \"correcting\" it in place" in s


def test_system_bullet_order_matches_v4_insert_points():
    """3b sits in the intro paragraph, before 1a. 4a (CORE+cost-math+
    REFERENCE) replaces 1b between [3] define-key-term and [4] name-zones.
    4b sits where 1c did. 1d stays put, unchanged; 4c sits immediately after
    it, still before the card-data bullet. 4d sits immediately before 1f
    (which now also carries 4e's appended clause) and before tldr."""
    s = ans.SYSTEM_VERSIONS[4]
    i_3b = s.index("State assumptions when the context doesn't cover something")
    i_1a = s.index("never by a role word")
    i_cite = s.index("Cite the exact rule numbers")
    i_define = s.index("Define any key term")
    i_4a_core = s.index("Notation legend, CORE tier")
    i_4a_costmath = s.index("Cost math: a cost-REDUCTION")
    i_4a_ref = s.index("Notation legend, REFERENCE tier")
    i_zones = s.index("Name the specific zones")
    i_4b = s.index("state each outcome separately")
    i_accurate = s.index("Keep the answer accurate and to the point")
    i_1d = s.index("say plainly which timing you're assuming")
    i_4c = s.index("When the answer depends on a fact the question doesn't state")
    i_carddata = s.index('labeled "Card data"')
    i_1e = s.index("A card's own printed rules text always wins")
    i_ruling_auth = s.index("A provided ruling is itself authoritative")
    i_ruling_label = s.index("Card rulings in the context are labeled")
    i_4d = s.index("Answer the practical question a player is actually asking")
    i_1f = s.index("Open the text field with a direct")
    i_4e = s.index("Never write a claim in the text field")
    i_tldr = s.index("Fill the tldr field")

    assert i_3b < i_1a < i_cite < i_define
    assert i_define < i_4a_core < i_4a_costmath < i_4a_ref < i_zones
    assert i_zones < i_4b < i_accurate
    assert i_accurate < i_1d < i_4c < i_carddata < i_1e < i_ruling_auth < i_ruling_label
    assert i_ruling_label < i_4d < i_1f < i_4e < i_tldr


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

# API-level test for plan-answer-ui-fixes Fix 3 (card info panel): the /answer
# response's CardOut must carry per-face data (power/toughness/loyalty/defense,
# each face's own name/mana_cost/type_line/oracle_text) so the frontend can
# render a full card info block without a second Scryfall fetch, and must
# handle a multi-faced card (e.g. a modal DFC) correctly -- both faces
# present, not just the front.
#
# Same pattern as test_api_debug.py: main.answer() is a plain function that
# reads module-level _state, so a fake agent double is substituted directly
# and the route is called in-process. No network, no TestClient needed.

from rulesagent.api import main
from rulesagent.contracts import Answer, Card, CardFace


class _FakeAgent:
    model = "fake-model"

    def __init__(self, cards):
        self.last_cards = cards
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []

    def answer(self, question, history=None):
        return Answer(
            text="An honest answer.", tldr="tldr", citations=[],
            answered=True, suggested_followups=[],
        )


def _single_faced_card():
    return Card(
        name="Grist, the Hunger Tide",
        oracle_text="Whenever a creature an opponent controls dies, "
                     "put a loyalty counter on Grist.",
        type_line="Legendary Creature -- Insect",
        mana_cost="{1}{B}{G}",
        oracle_id="oracle-grist",
        rulings=["[Grist, the Hunger Tide ruling #1] A test ruling."],
        layout="normal",
        faces=[CardFace(
            name="Grist, the Hunger Tide", mana_cost="{1}{B}{G}",
            type_line="Legendary Creature -- Insect",
            oracle_text="Whenever a creature an opponent controls dies, "
                         "put a loyalty counter on Grist.",
            power="1", toughness="1", loyalty="", defense="",
        )],
    )


def _double_faced_card():
    return Card(
        name="Valki, God of Lies // Tibalt, Cosmic Impostor",
        oracle_text="Front face text.\n\nBack face text.",
        type_line="Legendary Creature -- God // Legendary Planeswalker -- Tibalt",
        mana_cost="",
        oracle_id="oracle-valki-tibalt",
        rulings=["[Valki, God of Lies ruling #1] A front-face ruling."],
        layout="modal_dfc",
        faces=[
            CardFace(
                name="Valki, God of Lies", mana_cost="{1}{B}",
                type_line="Legendary Creature -- God",
                oracle_text="Front face text.",
                power="1", toughness="3", loyalty="", defense="",
            ),
            CardFace(
                name="Tibalt, Cosmic Impostor", mana_cost="{2}{B}{R}{R}",
                type_line="Legendary Planeswalker -- Tibalt",
                oracle_text="Back face text.",
                power="", toughness="", loyalty="9", defense="",
            ),
        ],
    )


def test_card_out_carries_single_face_stats(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent([_single_faced_card()]))
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="How does [Grist, the Hunger Tide] work?")
    resp = main.answer(req)

    assert len(resp.cards) == 1
    card = resp.cards[0]
    assert card.name == "Grist, the Hunger Tide"
    assert card.power == "1"
    assert card.toughness == "1"
    assert card.loyalty == ""
    assert card.layout == "normal"
    assert len(card.faces) == 1
    assert card.faces[0].oracle_text.startswith("Whenever a creature")


def test_card_out_carries_both_faces_of_a_double_faced_card(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent([_double_faced_card()]))
    monkeypatch.setitem(main._state, "chunk_map", {})

    req = main.AnswerRequest(question="How does [Valki, God of Lies] work?")
    resp = main.answer(req)

    assert len(resp.cards) == 1
    card = resp.cards[0]
    # Top-level power/toughness/loyalty is blank for a multi-faced card --
    # the two faces can disagree, so `faces` is the only correct source.
    assert card.power == ""
    assert card.loyalty == ""
    assert len(card.faces) == 2
    front, back = card.faces
    assert front.name == "Valki, God of Lies"
    assert front.power == "1" and front.toughness == "3"
    assert back.name == "Tibalt, Cosmic Impostor"
    assert back.loyalty == "9"
    assert back.oracle_text == "Back face text."

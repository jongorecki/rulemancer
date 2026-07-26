"""Citation labels on card rulings are applied at the prompt boundary.

WHY THESE TESTS EXIST. The system prompt tells the model that card rulings are
labeled `[Card Name ruling #4]` and that it must cite that exact label. For the
two derivability arms that promise was false: `evals/build_gold_prompts.py` calls
`build_prompt()` directly, and the labelling used to live in `RulesAgent.answer()`
-- so those prompts rendered a bare bullet list while still demanding labelled
citations. With nothing to copy, the model counted bullets **1-based**, and the
last ruling of an N-ruling card came out as `#N`: one past the end of the 0-based
scheme. 341 citations in arm B, not one of them `#0`, where `#0` is the
production arm's most common index. Details: docs/report-ruling-citation-offbyone.md

The fix moved labelling into `build_prompt()`, the boundary every builder shares.
These tests hold that boundary:

- a raw card rendered through `build_prompt()` comes out labelled (the bug);
- labels are 0-based and never exceed the card's real ruling count (the symptom);
- labelling is idempotent, so `answer()` labelling a subset first cannot produce
  a doubled label and cannot change production's bytes (the regression risk the
  fix itself introduced).
"""
import re

import pytest

from rulesagent.contracts import Card, Chunk, Retrieved
from rulesagent.generate import answer as ans

LABEL = re.compile(r"\[([^\]]+) ruling #(\d+)\]")


def _card(name="Rescuer Sphinx", n=3) -> Card:
    return Card(
        name=name,
        oracle_text="Flying",
        type_line="Creature — Sphinx",
        mana_cost="{2}{U}{U}",
        oracle_id=f"oracle-{name.lower().replace(' ', '-')}",
        rulings=[f"Ruling number {i} for {name}." for i in range(n)],
    )


def _labels(text: str) -> list[tuple[str, int]]:
    return [(m.group(1), int(m.group(2))) for m in LABEL.finditer(text)]


def test_raw_card_through_build_prompt_is_labelled():
    """The actual bug: build_gold_prompts.py passes raw cards and got none."""
    _, user = ans.build_prompt("q?", [], [_card()])
    assert _labels(user) == [("Rescuer Sphinx", 0), ("Rescuer Sphinx", 1), ("Rescuer Sphinx", 2)]


def test_labels_are_zero_based_and_in_range():
    """The symptom: a cited index must never exceed the card's ruling count."""
    card = _card(n=4)
    _, user = ans.build_prompt("q?", [], [card])
    idx = [i for _, i in _labels(user)]
    assert min(idx) == 0, "0-based: a 1-based scheme is what produced the bug"
    assert max(idx) == len(card.rulings) - 1
    assert len(idx) == len(card.rulings)


def test_subset_keeps_original_indices():
    """answer() shows a few rulings but must cite the index that maps back to
    ruling_id() and the gold oracle_id#index -- so a subset is NOT renumbered."""
    card = _card(n=8)
    picked = ans.label_rulings(card, [2, 5])
    assert [i for _, i in _labels("\n".join(picked.rulings))] == [2, 5]
    _, user = ans.build_prompt("q?", [], [picked])
    assert [i for _, i in _labels(user)] == [2, 5]


def test_labelling_is_idempotent():
    """answer() labels, then build_prompt() labels again. A doubled label would
    corrupt every citation in production."""
    card = _card()
    once = ans.label_rulings(card)
    twice = ans.label_rulings(once)
    assert twice.rulings == once.rulings
    for r in twice.rulings:
        assert len(LABEL.findall(r)) == 1, f"doubled label: {r!r}"


def test_idempotent_for_a_prelabelled_subset():
    """The exact production shape: subset labelled with original indices, then
    passed through build_prompt(), which labels positionally. Positional
    relabelling here would silently renumber 2 and 5 to 0 and 1."""
    card = _card(n=8)
    _, user = ans.build_prompt("q?", [], [ans.label_rulings(card, [2, 5])])
    assert [i for _, i in _labels(user)] == [2, 5]
    assert "[Rescuer Sphinx ruling #0]" not in user


def test_no_cards_means_no_labels_and_no_card_block():
    _, user = ans.build_prompt("q?", [], [])
    assert _labels(user) == []
    assert "Card data:" not in user


def test_card_with_no_rulings_is_unchanged():
    card = Card(name="Plains", oracle_text="", type_line="Basic Land — Plains",
                mana_cost="", oracle_id="oracle-plains", rulings=[])
    assert ans.label_rulings(card).rulings == []
    _, user = ans.build_prompt("q?", [], [card])
    assert _labels(user) == []


def test_every_label_in_a_multi_card_prompt_resolves_to_its_own_card():
    """A label naming card A with card B's index is the mis-citation class this
    whole investigation was about."""
    a, b = _card("Primal Vigor", n=4), _card("Rescuer Sphinx", n=3)
    _, user = ans.build_prompt("q?", [], [a, b])
    counts = {"Primal Vigor": len(a.rulings), "Rescuer Sphinx": len(b.rulings)}
    for name, i in _labels(user):
        assert name in counts, f"label names an unknown card: {name}"
        assert i < counts[name], f"{name} ruling #{i} is out of range ({counts[name]} rulings)"


def _retrieved(source_id: str, text: str) -> Retrieved:
    return Retrieved(
        chunk=Chunk(source_id=source_id, kind="rule", section="Test",
                    text=text, embed_text=text),
        score=1.0,
    )


@pytest.mark.parametrize("with_rules", [False, True])
def test_labelling_does_not_depend_on_retrieval(with_rules):
    retrieved = [_retrieved("614.12", "Some replacement effects...")] if with_rules else []
    _, user = ans.build_prompt("q?", retrieved, [_card()])
    assert len(_labels(user)) == 3

# Golden tests for the parser.
#
# Each test is one real, hand-picked entry from the actual CR file (not a
# made-up example), with the exact expected Rule or GlossaryEntry written
# out by hand. If the parser ever changes -- rewritten by a different
# model, refactored, whatever -- these are what tell you instantly whether
# it still produces the same output for the tricky cases, not just the
# easy ones.
#
# These will fail with an ImportError until parser.py actually implements
# `parse_comprehensive_rules`. That's expected -- the tests come first.

from pathlib import Path

import pytest

from rulesagent.ingest.parser import parse_comprehensive_rules

CR_PATH = (
    Path(__file__).parent.parent / "data" / "raw" / "MagicCompRules 20260619.txt"
)


@pytest.fixture(scope="session")
def parsed():
    """Parses the real CR file once and reuses it across every test below,
    so we're not re-reading a 9000+ line file for each individual check."""
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    return {
        "rules": {r.number: r for r in rules},
        "glossary": {g.term: g for g in glossary},
    }


# --- sanity checks -----------------------------------------------------
# Not edge cases -- just "did something go badly wrong," e.g. the parser
# stopped early, or swallowed the whole file into one bucket.

def test_parses_several_thousand_rules(parsed):
    assert len(parsed["rules"]) > 2000


def test_parses_a_substantial_glossary(parsed):
    assert len(parsed["glossary"]) > 500


# --- first rule in the file ---------------------------------------------

def test_first_rule_100_1(parsed):
    r = parsed["rules"]["100.1"]
    assert r.text == (
        "These Magic rules apply to any Magic game with two or more players, "
        "including two-player games and multiplayer games."
    )
    assert r.parent_chain == ["100"]
    assert r.section == "Game Concepts"
    assert r.kind == "rule"
    assert r.examples == []


# --- plain rule vs. lettered subrule, same rule family -------------------

def test_plain_rule_104_3(parsed):
    r = parsed["rules"]["104.3"]
    assert r.text == "There are several ways to lose the game."
    assert r.parent_chain == ["104"]
    assert r.kind == "rule"
    assert r.examples == []


def test_lettered_subrule_104_3a(parsed):
    r = parsed["rules"]["104.3a"]
    assert r.text == (
        "A player can concede the game at any time. A player who concedes "
        "leaves the game immediately. That player loses the game."
    )
    assert r.parent_chain == ["104", "104.3"]
    assert r.kind == "subrule"
    assert r.examples == []


# --- a rule with one example, kept separate from `text` -------------------

def test_rule_with_one_example_101_2(parsed):
    r = parsed["rules"]["101.2"]
    assert r.text == (
        "When a rule or effect allows or directs something to happen, and "
        "another effect states that it can’t happen, the “can’t” "
        "effect takes precedence."
    )
    assert "Example:" not in r.text  # confirms examples were split out, not left in
    assert r.examples == [
        "If one effect reads “You may play an additional land this turn” "
        "and another reads “You can’t play lands this turn,” the effect "
        "that precludes you from playing lands wins."
    ]


# --- a subrule with a cross-reference and no example ----------------------

def test_subrule_with_cross_reference_101_2a(parsed):
    r = parsed["rules"]["101.2a"]
    assert r.text == (
        "Adding abilities to objects and removing abilities from objects "
        "don’t fall under this rule. (See rule 113.10.)"
    )
    # DECISION check: the cross-reference stays embedded in plain text,
    # it is not pulled into its own field.
    assert "See rule 113.10" in r.text
    assert r.examples == []


# --- a rule with THREE examples in a row ----------------------------------
# This is the case that settles "can one rule have more than one Example:
# block" -- yes. If your parser only grabs the first one, this test catches it.

def test_rule_with_three_examples_107_1b(parsed):
    r = parsed["rules"]["107.1b"]
    assert len(r.examples) == 3
    assert r.examples[0].startswith("If a 3/4 creature gets -5/-0")
    assert r.examples[1].startswith("Viridian Joiner is a 1/2 creature")
    assert r.examples[2].startswith("Chameleon Colossus is a 4/4 creature")


# --- multiple cross-references in one subrule, with quoted rule names -----

def test_subrule_with_multiple_cross_references_100_2d(parsed):
    r = parsed["rules"]["100.2d"]
    assert r.text == (
        "Some formats and casual play variants allow players to use a "
        "supplementary deck of nontraditional Magic cards (see rule 108.2a). "
        "These supplementary decks have their own deck construction rules. "
        "See rule 717, “Attraction Cards;” rule 901, “Planechase;” "
        "and rule 904, “Archenemy.”"
    )


# --- unicode: curly quotes, apostrophes, and a trademark symbol -----------
# If the parser reads the file with the wrong encoding or does any naive
# ASCII cleanup, this is the test that will catch it.

def test_rule_with_unicode_characters_100_7(parsed):
    r = parsed["rules"]["100.7"]
    assert r.text == (
        "Certain cards are intended for casual play and may have features "
        "and text that aren’t covered by these rules. These include Mystery "
        "Booster playtest cards, promotional cards and cards in “Un-sets” "
        "that were printed with a silver border, and cards in the "
        "Unfinity™ expansion that have an acorn symbol at the bottom of "
        "the card."
    )


# --- glossary: single-sense term ------------------------------------------

def test_glossary_single_sense_abandon(parsed):
    g = parsed["glossary"]["Abandon"]
    assert g.definitions == [
        "To turn a face-up ongoing scheme card face down and put it on the "
        "bottom of its owner’s scheme deck. See rule 701.33, “Abandon.”"
    ]


# --- glossary: multi-sense term -------------------------------------------
# DECISION (see contracts.py / DECISIONS.md): the trailing "See rule..."
# line that follows both numbered senses gets appended onto the LAST
# definition, since that's where it sits in the source. Flag this test if
# that convention feels wrong on review -- it's the one part of the
# glossary shape that isn't a hard fact from the file, it's a judgment call.

def test_glossary_multi_sense_ability(parsed):
    g = parsed["glossary"]["Ability"]
    assert g.definitions == [
        "Text on an object that explains what that object does or can do.",
        "An activated or triggered ability on the stack. This kind of "
        "ability is an object. See rule 113, “Abilities,” and section 6, "
        "“Spells, Abilities, and Effects.”",
    ]


# --- Credits section produces nothing -------------------------------------

def test_credits_produces_no_rule_or_glossary_entry(parsed):
    assert "Credits" not in parsed["glossary"]
    assert not any(
        "Richard Garfield" in r.text for r in parsed["rules"].values()
    )
    assert not any(
        "Richard Garfield" in g.term or any("Richard Garfield" in d for d in g.definitions)
        for g in parsed["glossary"].values()
    )

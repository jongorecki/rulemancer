# Golden tests for the chunker.
#
# Each test is one real, hand-picked case from the actual CR file (not a
# made-up example). Mirrors the style of tests/test_golden_parser.py: parse
# the real file once per session, build chunks once per session, then
# assert exact expected shapes for the tricky cases documented in
# DECISIONS.md ("Chunking: label-like rules don't get their own chunk").

from pathlib import Path

import pytest

from rulesagent.ingest.chunker import chunk_rules
from rulesagent.ingest.parser import parse_comprehensive_rules

CR_PATH = (
    Path(__file__).parent.parent / "data" / "raw" / "MagicCompRules 20260619.txt"
)


@pytest.fixture(scope="session")
def parsed():
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    return rules, glossary


@pytest.fixture(scope="session")
def chunked(parsed):
    rules, glossary = parsed
    chunks = chunk_rules(rules, glossary)
    return {
        "chunks": chunks,
        "by_source_id_rule": {c.source_id: c for c in chunks if c.kind == "rule"},
        "by_source_id_glossary": {c.source_id: c for c in chunks if c.kind == "glossary"},
        "num_rules_in": len(rules),
        "num_glossary_in": len(glossary),
    }


# --- sanity checks -------------------------------------------------------

def test_fewer_chunks_than_rules_but_still_several_thousand(chunked):
    num_rule_chunks = len(chunked["by_source_id_rule"])
    assert num_rule_chunks < chunked["num_rules_in"]
    assert len(chunked["chunks"]) > 2000


def test_every_glossary_entry_becomes_exactly_one_chunk(chunked):
    assert len(chunked["by_source_id_glossary"]) == chunked["num_glossary_in"]


# --- label-like rules produce no chunk of their own -----------------------

def test_label_205_3_subtypes_produces_no_chunk(chunked):
    assert "205.3" not in chunked["by_source_id_rule"]


def test_label_701_49_venture_produces_no_chunk(chunked):
    assert "701.49" not in chunked["by_source_id_rule"]


# --- "!" edge case: flavor-named keywords are labels, not sentences -------

def test_for_mirrodin_702_163_is_treated_as_a_label(chunked):
    assert "702.163" not in chunked["by_source_id_rule"]


def test_start_your_engines_702_179_is_treated_as_a_label(chunked):
    assert "702.179" not in chunked["by_source_id_rule"]


# --- a label's text reaches the index only via its children's chunks -----

def test_child_of_label_205_3_has_parent_text_prepended(chunked):
    c = chunked["by_source_id_rule"]["205.3a"]
    assert c.text.startswith("Subtypes ")
    assert "A card can have one or more subtypes printed on its type line." in c.text


def test_child_of_label_701_49_has_parent_text_prepended(chunked):
    c = chunked["by_source_id_rule"]["701.49a"]
    assert c.text.startswith("Venture into the Dungeon ")


# --- a normal rule with one example ---------------------------------------

def test_rule_with_example_101_2_contains_rule_text_and_example(chunked):
    c = chunked["by_source_id_rule"]["101.2"]
    assert "can’t” effect takes precedence." in c.text
    assert "the effect that precludes you from playing lands wins." in c.text


# --- a rule with three examples: all three must be present ----------------

def test_rule_with_three_examples_107_1b_has_all_three(chunked):
    c = chunked["by_source_id_rule"]["107.1b"]
    assert "If a 3/4 creature gets -5/-0" in c.text
    assert "Viridian Joiner is a 1/2 creature" in c.text
    assert "Chameleon Colossus is a 4/4 creature" in c.text


# --- a rule whose section is a normal field, unaffected by chunking -------

def test_rule_chunk_carries_source_id_kind_and_section(chunked):
    c = chunked["by_source_id_rule"]["101.2"]
    assert c.source_id == "101.2"
    assert c.kind == "rule"
    assert c.section == "Game Concepts"


# --- glossary: one chunk, term + definitions joined -----------------------

def test_glossary_term_ability_is_one_chunk(chunked):
    c = chunked["by_source_id_glossary"]["Ability"]
    assert c.kind == "glossary"
    assert c.section == "Glossary"
    assert c.source_id == "Ability"
    assert c.text.startswith("Ability. Text on an object that explains what "
                              "that object does or can do.")
    assert "An activated or triggered ability on the stack." in c.text

# Golden tests for section-wide coverage.
#
# The parser/chunker golden tests in test_golden_parser.py and
# test_golden_chunker.py cluster in section 1 and the glossary. These
# tests prove the parser behaves across ALL nine numbered sections, and
# reinforce the section-7 label handling (261 of the 269 label-like rules
# live in section 7, so it's the highest-risk area).
#
# Design (see DECISIONS.md, "expand golden tests"): breadth cases assert
# STRUCTURE (section name, kind, parent_chain, example count) rather than
# full exact text -- the goal is "every section is handled," and structure
# is the robust, cheap way to prove it. Exact-text assertions are reserved
# for the section-7 label/child behavior, where subtle breakage bites.
# Every expected value here was transcribed from the real CR file, not
# guessed.

from pathlib import Path

import pytest

from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.ingest.chunker import chunk_rules

CR_PATH = (
    Path(__file__).parent.parent / "data" / "raw" / "MagicCompRules 20260619.txt"
)


@pytest.fixture(scope="session")
def parsed():
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    return {
        "rules": {r.number: r for r in rules},
        "chunk_ids": {c.source_id for c in chunks},
        "chunks": {c.source_id: c for c in chunks},
        "section_names": {r.section for r in rules},
    }


# --- every numbered section is present and named correctly ----------------

def test_all_nine_sections_present(parsed):
    expected = {
        "Game Concepts",
        "Parts of a Card",
        "Card Types",
        "Zones",
        "Turn Structure",
        "Spells, Abilities, and Effects",
        "Additional Rules",
        "Multiplayer Rules",
        "Casual Variants",
    }
    assert expected <= parsed["section_names"]


# --- breadth: one representative rule per section 2 through 9 --------------
# Structural assertions only: section, kind, parent_chain, example count.

def test_section2_parts_of_a_card_201_2b(parsed):
    r = parsed["rules"]["201.2b"]
    assert r.section == "Parts of a Card"
    assert r.kind == "subrule"
    assert r.parent_chain == ["201", "201.2"]
    assert len(r.examples) == 1


def test_section3_card_types_302_3(parsed):
    r = parsed["rules"]["302.3"]
    assert r.section == "Card Types"
    assert r.kind == "rule"
    assert r.parent_chain == ["302"]
    assert len(r.examples) == 1


def test_section4_zones_400_6(parsed):
    r = parsed["rules"]["400.6"]
    assert r.section == "Zones"
    assert r.kind == "rule"
    assert r.parent_chain == ["400"]
    assert len(r.examples) == 1


def test_section5_turn_structure_500_10(parsed):
    r = parsed["rules"]["500.10"]
    assert r.section == "Turn Structure"
    assert r.kind == "rule"
    assert r.parent_chain == ["500"]
    assert len(r.examples) == 1


def test_section6_spells_abilities_effects_601_2c(parsed):
    r = parsed["rules"]["601.2c"]
    assert r.section == "Spells, Abilities, and Effects"
    assert r.kind == "subrule"
    assert r.parent_chain == ["601", "601.2"]
    assert len(r.examples) == 1


def test_section7_additional_rules_700_1(parsed):
    r = parsed["rules"]["700.1"]
    assert r.section == "Additional Rules"
    assert r.kind == "rule"
    assert r.parent_chain == ["700"]
    assert len(r.examples) == 1


def test_section8_multiplayer_800_4a_has_four_examples(parsed):
    # Also a second multi-example case (the first is 107.1b): confirms the
    # parser collects all four Example: blocks, not just the first.
    r = parsed["rules"]["800.4a"]
    assert r.section == "Multiplayer Rules"
    assert r.kind == "subrule"
    assert r.parent_chain == ["800", "800.4"]
    assert len(r.examples) == 4


def test_section9_casual_variants_902_4(parsed):
    r = parsed["rules"]["902.4"]
    assert r.section == "Casual Variants"
    assert r.kind == "rule"
    assert r.parent_chain == ["902"]
    assert len(r.examples) == 1


# --- section-7 label handling: exact behavior -----------------------------
# 701.5 is the keyword "Cast" -- a bare label. It must NOT get its own
# chunk; its text must instead reach the index prepended onto its child
# 701.5a's chunk. This is the core label mechanic, tested on real data.

def test_keyword_label_701_5_cast_has_no_chunk(parsed):
    assert parsed["rules"]["701.5"].text == "Cast"
    assert "701.5" not in parsed["chunk_ids"]


def test_keyword_child_701_5a_prepends_cast_label(parsed):
    chunk = parsed["chunks"]["701.5a"]
    assert chunk.kind == "rule"
    # own text starts "To cast a spell..."; with the "Cast" label prepended
    # the chunk text leads with the label. (Stops before the first
    # apostrophe to keep the assertion free of unicode punctuation.)
    assert chunk.text.startswith("Cast To cast a spell is to take it from the zone it")

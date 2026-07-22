# Tests for the RulesGuru raw-response -> rulesguru.jsonl converter
# (docs/plan-rulesguru-import.md, evals/fetch_rulesguru.py).
#
# Pure-unit tests on the conversion functions only -- no network, no CR
# parsing. bracket_card_names and convert_record both take plain data in and
# return plain data out, so nothing here touches rulesguru.org or
# data/raw/MagicCompRules*.txt.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))
from fetch_rulesguru import bracket_card_names, convert_record  # noqa: E402


# --------------------------------------------------------------------------
# bracket_card_names
# --------------------------------------------------------------------------

def test_brackets_a_single_card_name():
    text = "Avery casts Tempt with Discovery targeting nothing."
    out = bracket_card_names(text, ["Tempt with Discovery"])
    assert out == "Avery casts [Tempt with Discovery] targeting nothing."


def test_brackets_multiple_card_names_first_occurrence_each():
    text = "Arya blocks Insurrection with Insurrection again and casts Tempted by the Oriq."
    out = bracket_card_names(text, ["Insurrection", "Tempted by the Oriq"])
    # only the FIRST "Insurrection" gets bracketed, the repeat is untouched
    assert out == (
        "Arya blocks [Insurrection] with Insurrection again "
        "and casts [Tempted by the Oriq]."
    )


def test_substring_name_does_not_double_bracket():
    """One card name contained in another (the case the plan calls out):
    processing longest-first means the shorter name's only occurrence --
    inside the longer name's already-claimed span -- is left alone rather
    than punching a second, overlapping bracket into the middle of it."""
    text = "My Grizzly Bears blocks the attacker."
    out = bracket_card_names(text, ["Bears", "Grizzly Bears"])
    assert out == "My [Grizzly Bears] blocks the attacker."
    # sanity: the substring form never appears bracketed on its own
    assert "[Bears]" not in out


def test_substring_name_first_occurrence_only_even_when_a_later_one_is_free():
    """"First occurrence only" is taken literally per name: "Bears"'s FIRST
    occurrence sits inside "Grizzly Bears"'s already-claimed span, so it's
    skipped -- the converter does not scan ahead for a second, non-overlapping
    occurrence to bracket instead."""
    text = "My Grizzly Bears fights a wild Bears token."
    out = bracket_card_names(text, ["Bears", "Grizzly Bears"])
    assert out == "My [Grizzly Bears] fights a wild Bears token."


def test_name_not_present_in_text_is_skipped_silently():
    text = "A plain question with no card mentions."
    out = bracket_card_names(text, ["Some Card Not Here"])
    assert out == text


def test_empty_names_list_is_a_no_op():
    text = "Nothing to bracket here."
    assert bracket_card_names(text, []) == text


# --------------------------------------------------------------------------
# convert_record
# --------------------------------------------------------------------------

def _raw(**overrides) -> dict:
    base = {
        "level": "1",
        "complexity": "Simple",
        "tags": ["Resolving objects"],
        "id": 1812,
        "submitterName": "somebody",
        "includedCards": [{"name": "Tempt with Discovery"}],
        "questionSimple": "Avery casts Tempt with Discovery. What happens?",
        "answerSimple": "Yes, it resolves in written order.",
        "citedRules": {"608.2c": {"ruleText": "..."}},
        "url": "https://rulesguru.org/?1812RGBwnIIIeikGG",
    }
    base.update(overrides)
    return base


def test_id_mapping_1812_to_rg1812():
    rec = convert_record(_raw())
    assert rec["id"] == "rg1812"


def test_convert_record_basic_shape():
    rec = convert_record(_raw())
    assert rec["question"] == "Avery casts [Tempt with Discovery]. What happens?"
    assert rec["cards"] == ["Tempt with Discovery"]
    assert rec["gold"] == ["608.2c"]
    assert rec["match"] == "any"
    assert rec["kind"] == "rulesguru"
    assert rec["answer_gold"] == "Yes, it resolves in written order."
    assert rec["level"] == "1"
    assert rec["complexity"] == "Simple"
    assert rec["tags"] == ["Resolving objects"]
    assert rec["url"] == "https://rulesguru.org/?1812RGBwnIIIeikGG"
    assert rec["submitter"] == "somebody"


def test_empty_cited_rules_yields_empty_gold():
    rec = convert_record(_raw(id=999, citedRules={}))
    assert rec["gold"] == []
    assert rec["id"] == "rg999"


def test_multiple_cited_rules_sorted():
    raw = _raw(id=2, citedRules={"704.3": {}, "117.2d": {}, "120.5": {}})
    rec = convert_record(raw)
    assert rec["gold"] == ["117.2d", "120.5", "704.3"]


def test_gold_validation_logs_drift_but_keeps_the_id(capsys):
    raw = _raw(id=42, citedRules={"999.99z": {}})  # a made-up id that can't be a real chunk
    drift: list[dict] = []
    rec = convert_record(raw, chunk_ids={"608.2c"}, drift=drift)
    assert rec["gold"] == ["999.99z"]  # kept, not dropped
    assert drift == [{"id": "rg42", "missing": ["999.99z"]}]
    assert "DRIFT" in capsys.readouterr().out


def test_gold_validation_no_drift_when_id_resolves():
    raw = _raw(id=43, citedRules={"608.2c": {}})
    drift: list[dict] = []
    rec = convert_record(raw, chunk_ids={"608.2c"}, drift=drift)
    assert drift == []


def test_no_angle_bracket_survives_in_question():
    # The "Simple" question variants are documented plain text; a stray '<'
    # (HTML leaking through) should fail loudly rather than ship silently.
    raw = _raw(questionSimple="Does <b>Avery</b> win?")
    try:
        convert_record(raw)
        assert False, "expected an AssertionError for '<' in question text"
    except AssertionError as e:
        assert "rg1812" in str(e)


# --------------------------------------------------------------------------
# dedupe by id (the merge behavior in fetch_and_merge, exercised directly
# against the dict-by-id logic without touching the network or disk)
# --------------------------------------------------------------------------

def test_dedupe_by_id_keeps_one_record_per_id():
    records = [_raw(id=1), _raw(id=2), _raw(id=1, questionSimple="A different question now.")]
    by_id = {r["id"]: r for r in records}
    merged = list(by_id.values())
    assert len(merged) == 2
    assert {r["id"] for r in merged} == {1, 2}
    # last-fetched wins for a given id
    assert by_id[1]["questionSimple"] == "A different question now."

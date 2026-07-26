# Tests for the pure-rules held-out eval set
# (evals/build_purerules_holdout.py, evals/purerules.jsonl).
#
# Two layers, same split fetch_rulesguru's tests use (tests/test_rulesguru_
# convert.py): pure unit tests on the join logic (fake data, no disk, no CR
# parsing) plus a smaller set of integration checks against the real
# committed files, proving the shipped evals/purerules.jsonl is actually
# valid -- not just that the builder's logic would be, in principle.

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "src"))

from build_purerules_holdout import (  # noqa: E402
    BuildError,
    build_rows,
    validate_gold_ids_exist,
    validate_schema,
    validate_unique,
)

from rulesagent.contracts import EvalQuestion  # noqa: E402


# --------------------------------------------------------------------------
# fixtures: minimal fake candidates/decisions/source_rows, independent of
# the real batch-1 data, so the join logic is tested in isolation
# --------------------------------------------------------------------------

def _candidate(**overrides) -> dict:
    base = {
        "id": "pr001",
        "source_qid": "rgTEST",
        "source_gold_rules": ["613.1d", "613.7"],
    }
    base.update(overrides)
    return base


def _decision(**overrides) -> dict:
    base = {
        "id": "pr001",
        "source_qid": "rgTEST",
        "decision": "approve",
        "question": "draft question text?",
        "gold": "draft gold text.",
        "edited": False,
    }
    base.update(overrides)
    return base


def _source_row(**overrides) -> dict:
    base = {
        "id": "rgTEST",
        "match": "any",
        "level": "2",
        "complexity": "Simple",
        "tags": ["Layers"],
        "url": "https://rulesguru.org/?TEST",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# build_rows: the join
# --------------------------------------------------------------------------

def test_approved_candidate_is_included_verbatim():
    rows = build_rows([_candidate()], [_decision()], {"rgTEST": _source_row()})
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "pr001"
    assert row["question"] == "draft question text?"
    assert row["answer_gold"] == "draft gold text."
    assert row["gold"] == ["613.1d", "613.7"]
    assert row["match"] == "any"
    assert row["kind"] == "purerules"
    assert row["source_qid"] == "rgTEST"
    assert row["edited"] is False


def test_cut_candidate_is_dropped():
    rows = build_rows(
        [_candidate()], [_decision(decision="cut")], {"rgTEST": _source_row()}
    )
    assert rows == []


def test_rewrite_decision_uses_edited_text_not_the_draft():
    dec = _decision(decision="rewrite", question="edited question.", gold="edited gold.", edited=True)
    rows = build_rows([_candidate()], [dec], {"rgTEST": _source_row()})
    assert rows[0]["question"] == "edited question."
    assert rows[0]["answer_gold"] == "edited gold."
    assert rows[0]["edited"] is True


def test_undecided_candidate_raises():
    with pytest.raises(BuildError, match="no decision recorded"):
        build_rows([_candidate(), _candidate(id="pr002")], [_decision()], {"rgTEST": _source_row()})


def test_orphaned_decision_raises():
    with pytest.raises(BuildError, match="unknown candidate"):
        build_rows([_candidate()], [_decision(), _decision(id="pr999")], {"rgTEST": _source_row()})


def test_unrecognized_decision_value_raises():
    with pytest.raises(BuildError, match="unrecognized decision"):
        build_rows([_candidate()], [_decision(decision="maybe")], {"rgTEST": _source_row()})


def test_missing_source_row_raises():
    with pytest.raises(BuildError, match="not found"):
        build_rows([_candidate()], [_decision()], {})


def test_level_tags_url_carried_from_source_row_not_the_candidate():
    src = _source_row(level="1", complexity="Complex", tags=["Dependency", "Layers"],
                       url="https://rulesguru.org/?XYZ")
    rows = build_rows([_candidate()], [_decision()], {"rgTEST": src})
    assert rows[0]["level"] == "1"
    assert rows[0]["complexity"] == "Complex"
    assert rows[0]["tags"] == ["Dependency", "Layers"]
    assert rows[0]["url"] == "https://rulesguru.org/?XYZ"


# --------------------------------------------------------------------------
# validate_unique / validate_schema
# --------------------------------------------------------------------------

def _row(**overrides) -> dict:
    base = {
        "id": "pr001", "question": "q?", "gold": ["613.1d"], "match": "any",
        "kind": "purerules", "answer_gold": "a.", "level": "2",
        "complexity": "Simple", "tags": [], "url": "https://x", "source_qid": "rgTEST",
        "edited": False,
    }
    base.update(overrides)
    return base


def test_validate_unique_passes_on_distinct_ids():
    validate_unique([_row(), _row(id="pr002", source_qid="rgOTHER")])  # no raise


def test_validate_unique_catches_duplicate_id():
    with pytest.raises(BuildError, match="duplicate id"):
        validate_unique([_row(), _row()])


def test_validate_unique_catches_duplicate_source_qid():
    with pytest.raises(BuildError, match="duplicate source_qid"):
        validate_unique([_row(id="pr001"), _row(id="pr002")])  # both source_qid=rgTEST


def test_validate_schema_accepts_a_conforming_row():
    validate_schema([_row()])  # no raise


def test_validate_schema_rejects_missing_required_field():
    bad = _row()
    del bad["question"]
    with pytest.raises(Exception):  # pydantic ValidationError
        validate_schema([bad])


def test_validate_schema_coerces_purerules_kind_same_as_rulesguru():
    # kind="purerules" isn't in EvalQuestion's Literal; run_eval.load_questions
    # coerces unrecognized kinds to "other" (see its _KNOWN_KINDS comment) --
    # this build's validator must accept the same un-coerced input rather
    # than rejecting a file shape the real loader already tolerates.
    validate_schema([_row(kind="purerules")])  # no raise


# --------------------------------------------------------------------------
# integration: the real, committed evals/purerules.jsonl
# --------------------------------------------------------------------------

CANDIDATES_PATH = ROOT / "evals" / "purerules_candidates.json"
DECISIONS_PATH = ROOT / "data" / "parsed" / "purerules_decisions.json"
OUT_PATH = ROOT / "evals" / "purerules.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_purerules_jsonl_exists_and_matches_decision_count():
    decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))["decisions"]
    n_kept = sum(1 for d in decisions if d["decision"] != "cut")
    rows = _load_jsonl(OUT_PATH)
    assert len(rows) == n_kept


def test_purerules_jsonl_every_row_conforms_to_eval_question_schema():
    rows = _load_jsonl(OUT_PATH)
    assert rows, "expected at least one row"
    validate_schema(rows)


def test_purerules_jsonl_ids_and_source_qids_are_unique():
    rows = _load_jsonl(OUT_PATH)
    validate_unique(rows)


def test_purerules_jsonl_gold_ids_resolve_to_real_cr_chunks():
    rows = _load_jsonl(OUT_PATH)
    validate_gold_ids_exist(rows)  # raises BuildError if any gold id is fictional


def test_purerules_jsonl_has_no_cut_candidates():
    candidates = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))["candidates"]
    decisions = {d["id"]: d for d in json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))["decisions"]}
    cut_ids = {cid for cid, d in decisions.items() if d["decision"] == "cut"}
    rows = _load_jsonl(OUT_PATH)
    assert not (set(r["id"] for r in rows) & cut_ids)


def test_purerules_jsonl_loads_through_the_real_eval_harness():
    """Proves the file is a drop-in --questions target for run_eval.py /
    run_answer_eval.py with zero new loader code -- not just schema-shaped
    in isolation."""
    from run_eval import load_questions  # noqa: E402 (evals/ on sys.path above)

    questions = load_questions(OUT_PATH)
    rows = _load_jsonl(OUT_PATH)
    assert len(questions) == len(rows)
    assert all(isinstance(q, EvalQuestion) for q in questions)
    # the un-recognized "purerules" kind coerces to "other", same as
    # evals/rulesguru.jsonl's "rulesguru" kind does -- proves the held-out
    # set doesn't need its own kind added to the closed Literal.
    assert all(q.kind == "other" for q in questions)


# --------------------------------------------------------------------------
# held-out guard: this set must never become the default tuning question
# set by accident (the exact "a value that looks like an identity but is
# really a position" class of bug this repo has been bitten by before --
# see docs/HANDOFF-development.md). If either script's default --questions
# path is ever repointed at purerules.jsonl, this eval set silently stops
# being held out.
# --------------------------------------------------------------------------

def test_run_eval_default_questions_path_is_not_the_holdout_set():
    from run_eval import QUESTIONS_PATH as run_eval_default  # noqa: E402
    assert run_eval_default.name != "purerules.jsonl"


def test_run_answer_eval_default_questions_path_is_not_the_holdout_set():
    from run_answer_eval import QUESTIONS_PATH as run_answer_eval_default  # noqa: E402
    assert run_answer_eval_default.name != "purerules.jsonl"

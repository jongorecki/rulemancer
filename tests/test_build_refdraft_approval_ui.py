"""Tests for evals/build_refdraft_approval_ui.py.

Asserts on the built HTML/payload because that is the artifact -- the tool's
whole output is one self-contained file, so "did the merge/flagging ship" is a
question about the file's contents.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "evals" / "build_refdraft_approval_ui.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_refdraft_approval_ui", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )


def _draft(**over) -> dict:
    row = {
        "id": "q001",
        "question": "Do creatures phasing back in trigger enter the battlefield abilities?",
        "answer_gold": "No, phasing in isn't a zone change.",
        "cited_rules": ["702.26d"],
        "cr_quotes": {"702.26d": "The phasing event doesn’t actually cause a zone change."},
        "gold_agrees": True,
        "gold_note": "",
        "confidence": "high",
        "uncertainty": "",
    }
    row.update(over)
    return row


def _question(**over) -> dict:
    row = {"id": "q001", "question": "placeholder", "gold": ["702.26d"], "kind": "interaction"}
    row.update(over)
    return row


def _extract_payload(html: str) -> dict:
    marker = "const DATA = "
    line = next(ln for ln in html.splitlines() if ln.startswith(marker))
    return json.loads(line[len(marker):].rstrip(";"))


def _build(tmp_path: Path, drafts: list[dict], questions: list[dict]) -> str:
    mod = _load_module()
    drafts_path = tmp_path / "_refdraft_merged.jsonl"
    questions_path = tmp_path / "questions.jsonl"
    out_path = tmp_path / "out.html"
    _write_jsonl(drafts_path, drafts)
    _write_jsonl(questions_path, questions)

    mod.DRAFTS = drafts_path
    mod.QUESTIONS = questions_path
    mod.OUT = out_path
    mod.main()
    return out_path.read_text(encoding="utf-8")


def test_builds_and_merges_mined_gold(tmp_path):
    html = _build(
        tmp_path,
        [_draft()],
        [_question(gold=["702.26d"])],
    )
    data = _extract_payload(html)
    row = data["rows"][0]
    assert row["id"] == "q001"
    assert row["mined_gold"] == ["702.26d"]
    assert row["cited_rules"] == ["702.26d"]


def test_disagreement_row_carries_gold_agrees_false(tmp_path):
    html = _build(
        tmp_path,
        [_draft(id="q008", gold_agrees=False, gold_note="misses 701.21a",
                cited_rules=["702.74a", "603.3"])],
        [_question(id="q008", gold=["702.74a", "603.3"])],
    )
    data = _extract_payload(html)
    row = data["rows"][0]
    assert row["gold_agrees"] is False
    assert row["gold_note"] == "misses 701.21a"


def test_missing_question_id_defaults_to_empty_mined_gold(tmp_path):
    """A draft id with no matching row in questions.jsonl must not crash the
    build -- it should just carry an empty mined_gold list."""
    html = _build(tmp_path, [_draft(id="q999")], [_question(id="q001")])
    data = _extract_payload(html)
    assert data["rows"][0]["mined_gold"] == []


def test_cr_quotes_embedded_verbatim(tmp_path):
    html = _build(
        tmp_path,
        [_draft(cr_quotes={"702.26d": "UNIQUE_QUOTE_MARKER_TEXT"})],
        [_question()],
    )
    assert "UNIQUE_QUOTE_MARKER_TEXT" in html


def test_medium_confidence_flagged_in_payload(tmp_path):
    html = _build(tmp_path, [_draft(confidence="medium")], [_question()])
    data = _extract_payload(html)
    assert data["rows"][0]["confidence"] == "medium"


def test_no_template_placeholder_survives(tmp_path):
    html = _build(tmp_path, [_draft()], [_question()])
    assert "__PAYLOAD__" not in html


def test_export_uses_expected_field_names(tmp_path):
    """The export button must build objects with the spec'd shape:
    {id, decision, edited_answer, notes}."""
    html = _build(tmp_path, [_draft()], [_question()])
    assert "edited_answer:" in html
    assert "decision:" in html
    assert "notes:" in html
    assert "refdraft_decisions.json" in html


def test_all_31_real_rows_round_trip():
    """Smoke test against the real repo data files, if present."""
    real_drafts = REPO / "evals" / "_refdraft_merged.jsonl"
    real_questions = REPO / "evals" / "questions.jsonl"
    if not real_drafts.exists() or not real_questions.exists():
        return
    mod = _load_module()
    out = REPO / "evals" / "_test_refdraft_scratch_out.html"
    mod.DRAFTS = real_drafts
    mod.QUESTIONS = real_questions
    mod.OUT = out
    try:
        mod.main()
        html = out.read_text(encoding="utf-8")
        data = _extract_payload(html)
        assert len(data["rows"]) == 31
        disagreeing = [r["id"] for r in data["rows"] if not r["gold_agrees"]]
        assert set(disagreeing) == {"q008", "q014", "q021", "q029"}
        medium = [r["id"] for r in data["rows"] if r["confidence"] != "high"]
        assert medium == ["q008"]
    finally:
        if out.exists():
            out.unlink()

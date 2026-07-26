"""Tests for the gold-audit additions to the grading UI.

docs/spec-gold-audit-ui.md. Scoped to the NEW behaviour -- the retrieved panel
and the verdict-vocabulary switch -- rather than retrofitting coverage onto all
562 lines of build_grading_ui.py.

These assert on the built HTML because that is the artifact: the tool's whole
output is one self-contained file, so "did the panel ship" is a question about
the file's contents and nothing else.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "evals" / "build_grading_ui.py"


def _row(**over) -> dict:
    row = {
        "id": "rgTEST", "kind": "other", "match": "any", "answered": True,
        "question": "Does [Grizzly Bears] die?",
        "answer": "Yes, per [104.3a].", "answer_gold": "Yes.",
        "citations": ["104.3a"], "cited_text": {"104.3a": "cited text here"},
        "gold": ["104.3a"], "gold_text": {"104.3a": "gold text here"},
    }
    row.update(over)
    return row


def _build(tmp_path: Path, rows: list[dict], *extra: str) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    inp = tmp_path / "in.json"
    out = tmp_path / "out.html"
    inp.write_text(json.dumps(rows), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--in", str(inp), "--out", str(out), *extra],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr
    return out.read_text(encoding="utf-8")


def _cfg(html: str) -> dict:
    line = next(ln for ln in html.splitlines() if ln.startswith("const CFG = "))
    return json.loads(line[len("const CFG = "):].rstrip(";"))


# --- verdict vocabulary ------------------------------------------------------

def test_default_vocabulary_is_unchanged(tmp_path):
    """answer-quality stays the default so every existing invocation is
    untouched by the gold-audit work."""
    cfg = _cfg(_build(tmp_path, [_row()]))
    assert [b["v"] for b in cfg["buttons"]] == ["correct", "partial", "wrong"]
    assert cfg["export"] == "answer_verdicts.json"


def test_gold_audit_vocabulary(tmp_path):
    cfg = _cfg(_build(tmp_path, [_row()], "--verdicts", "gold-audit"))
    assert [b["v"] for b in cfg["buttons"]] == [
        "rulesguru-wrong", "gold-incomplete", "ours-wrong", "ambiguous"]
    assert cfg["export"] == "gold_audit_verdicts.json"


def test_vocabularies_do_not_share_localstorage(tmp_path):
    """Separate storage keys are not cosmetic: both UIs are graded in the same
    browser, and a shared key would surface a correct/partial/wrong grade as a
    prior verdict in a gold audit whose buttons cannot express it."""
    a = _cfg(_build(tmp_path / "a", [_row()]))
    b = _cfg(_build(tmp_path / "b", [_row()], "--verdicts", "gold-audit"))
    assert a["storage"] != b["storage"]
    assert a["export"] != b["export"]


# --- retrieved panel ---------------------------------------------------------

def test_retrieved_text_is_embedded(tmp_path):
    html = _build(tmp_path, [_row(
        retrieved_rule_ids=["104.3a", "601.2b"],
        retrieved_text={"104.3a": "gold text here", "601.2b": "RETRIEVED ONLY TEXT"},
        retrieved_provenance="probe",
    )])
    # The distinguishing string belongs to a rule that is retrieved but neither
    # cited nor gold -- so finding it proves the retrieved panel carries its own
    # text rather than the assertion passing on the cited/gold copies.
    assert "RETRIEVED ONLY TEXT" in html


def test_missing_chunk_is_visible_not_dropped(tmp_path):
    """A retrieved id with no text must render the visible fallback. Silently
    omitting it would understate what retrieval returned."""
    html = _build(tmp_path, [_row(
        retrieved_rule_ids=["104.3a", "999.9z"],
        retrieved_text={"104.3a": "gold text here"},
        retrieved_provenance="run",
    )])
    data = json.loads(next(ln for ln in html.splitlines()
                           if ln.startswith("const DATA = "))[len("const DATA = "):].rstrip(";"))
    assert data[0]["retrieved_rule_ids"] == ["104.3a", "999.9z"]
    assert "999.9z" not in data[0]["retrieved_text"]
    assert "(text not found as a chunk)" in html


@pytest.mark.parametrize("prov", ["probe", "run"])
def test_provenance_round_trips_per_row(tmp_path, prov):
    """Per-row, not per-file: a mixed queue (batch 1 probes + batch 2 recorded)
    must label each row for what it actually is."""
    html = _build(tmp_path, [
        _row(id="rgA", retrieved_rule_ids=["104.3a"],
             retrieved_text={"104.3a": "t"}, retrieved_provenance=prov),
        _row(id="rgB", retrieved_rule_ids=["104.3a"],
             retrieved_text={"104.3a": "t"}, retrieved_provenance="run"),
    ])
    data = json.loads(next(ln for ln in html.splitlines()
                           if ln.startswith("const DATA = "))[len("const DATA = "):].rstrip(";"))
    assert [r["retrieved_provenance"] for r in data] == [prov, "run"]


def test_no_retrieved_ids_emits_no_panel_data(tmp_path):
    """Rows that never recorded retrieval must not sprout an empty panel."""
    html = _build(tmp_path, [_row()])
    data = json.loads(next(ln for ln in html.splitlines()
                           if ln.startswith("const DATA = "))[len("const DATA = "):].rstrip(";"))
    assert not data[0].get("retrieved_rule_ids")


def test_no_template_placeholders_survive(tmp_path):
    """A missed substitution ships a literal __TOKEN__ into the page."""
    html = _build(tmp_path, [_row()], "--verdicts", "gold-audit")
    for token in ("__DATA__", "__CFG__", "__TITLE__", "__HINT__", "__SRC__"):
        assert token not in html

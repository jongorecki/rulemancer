"""evals/qidfilter.py: `--qids` scattered-subset selection, plus its wiring
into both eval runners (run_answer_eval.py, run_openrouter_arm.py).

Two layers:
- Pure unit tests against `select_qids()` -- no runners involved.
- CLI wiring tests -- `--qids`/`--limit` mutual exclusion, and that a real
  (mocked-backend) run only answers the requested ids, in master-file order,
  with the heartbeat's n_total reflecting the FILTERED count (not the full
  question set) -- same no-live-HTTP mocking pattern as
  test_resume_prompts_cache_guard.py, so this never hits a real API.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

from qidfilter import QidFilterError, select_qids  # noqa: E402

from evals import run_answer_eval as rae  # noqa: E402
from evals import run_openrouter_arm as roa  # noqa: E402
from rulesagent.contracts import Answer  # noqa: E402
from rulesagent.generate import openrouter_backend as orb  # noqa: E402

import progress  # noqa: E402


def _q(id_):
    """Minimal EvalQuestion-shaped stand-in -- select_qids only needs `.id`,
    but use the real contract so this can't drift from what the runners
    actually pass in."""
    from rulesagent.contracts import EvalQuestion
    return EvalQuestion(id=id_, question=f"Question {id_}?", gold=[])


# ---------------------------------------------------------------------------
# select_qids() -- pure unit tests
# ---------------------------------------------------------------------------

def test_select_qids_returns_master_order_not_cli_order():
    questions = [_q("q001"), _q("q002"), _q("q003"), _q("q004")]
    result = select_qids(questions, "q004,q001,q003")
    assert [q.id for q in result] == ["q001", "q003", "q004"]


def test_select_qids_tolerates_whitespace_around_ids():
    questions = [_q("q001"), _q("q002")]
    result = select_qids(questions, " q002 , q001 ")
    assert [q.id for q in result] == ["q001", "q002"]


def test_select_qids_unknown_id_names_it():
    questions = [_q("q001"), _q("q002")]
    with pytest.raises(QidFilterError) as exc_info:
        select_qids(questions, "q001,q999")
    assert "q999" in str(exc_info.value)


def test_select_qids_duplicate_id_errors():
    questions = [_q("q001"), _q("q002")]
    with pytest.raises(QidFilterError) as exc_info:
        select_qids(questions, "q001,q002,q001")
    assert "q001" in str(exc_info.value)


def test_select_qids_empty_spec_errors():
    questions = [_q("q001")]
    with pytest.raises(QidFilterError):
        select_qids(questions, "")


def test_select_qids_whitespace_only_spec_errors():
    questions = [_q("q001")]
    with pytest.raises(QidFilterError):
        select_qids(questions, "   ")


def test_select_qids_trailing_comma_errors():
    questions = [_q("q001"), _q("q002")]
    with pytest.raises(QidFilterError):
        select_qids(questions, "q001,q002,")


def test_select_qids_single_id():
    questions = [_q("q001"), _q("q002"), _q("q003")]
    result = select_qids(questions, "q002")
    assert [q.id for q in result] == ["q002"]


# ---------------------------------------------------------------------------
# CLI wiring -- shared fixtures
# ---------------------------------------------------------------------------

def _fake_or_result(system, user, model, reasoning=None):
    import hashlib
    h = hashlib.sha256(user.encode()).hexdigest()[:8]
    return orb.ORResult(
        answer=Answer(text=f"answer-{h}", tldr="t", citations=[], answered=True,
                      suggested_followups=[]),
        requested_model=model, served_model=model, provider="Fake",
        temperature_sent=0.0, seed_sent=orb.SEED,
        usage={"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001},
    )


class _FakeResponse:
    def __init__(self, parsed_output):
        self.parsed_output = parsed_output
        self.stop_reason = "end_turn"


class _FakeMessages:
    def parse(self, model, max_tokens, system, messages, output_format):
        import hashlib
        user = messages[0]["content"]
        h = hashlib.sha256(user.encode()).hexdigest()[:8]
        return _FakeResponse(Answer(text=f"answer-{h}", tldr="t", citations=[],
                                    answered=True, suggested_followups=[]))


class _FakeAnthropicClient:
    def __init__(self, *a, **kw):
        self.messages = _FakeMessages()


def _write_questions(path: Path, ids: list[str]):
    path.write_text("\n".join(
        json.dumps({"id": i, "question": f"Q for {i}", "gold": []}) for i in ids
    ), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI wiring -- --qids and --limit together is an error, both runners
# ---------------------------------------------------------------------------

def test_run_answer_eval_qids_and_limit_together_exits_1(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001", "q002", "q003"])
    out = tmp_path / "out.json"
    argv = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions), "--out", str(out),
        "--qids", "q001", "--limit", "2",
    ]
    with patch("sys.argv", argv), patch("anthropic.Anthropic", _FakeAnthropicClient):
        with pytest.raises(SystemExit) as exc_info:
            rae.main()
    assert exc_info.value.code == 1
    assert not out.exists()


def test_run_openrouter_arm_qids_and_limit_together_exits_1(tmp_path):
    questions = tmp_path / "q.jsonl"
    empty_cards = tmp_path / "cards.jsonl"
    _write_questions(questions, ["q001", "q002", "q003"])
    empty_cards.write_text("", encoding="utf-8")
    out = tmp_path / "out.json"
    argv = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--out", str(out), "--qids", "q001", "--limit", "2",
    ]
    with patch("sys.argv", argv), patch.object(orb, "generate", side_effect=_fake_or_result):
        with pytest.raises(SystemExit) as exc_info:
            roa.main()
    assert exc_info.value.code == 1
    assert not out.exists()


# ---------------------------------------------------------------------------
# CLI wiring -- --qids actually selects the scattered subset, master order,
# and the heartbeat's n_total is the FILTERED count (requirement 3).
# ---------------------------------------------------------------------------

def test_run_answer_eval_qids_selects_subset_in_master_order(tmp_path, monkeypatch):
    progress_dir = tmp_path / "_progress"
    monkeypatch.setattr(progress, "PROGRESS_DIR", progress_dir)

    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001", "q002", "q003", "q004"])
    out = tmp_path / "out.json"
    argv = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions), "--out", str(out),
        "--qids", "q003,q001",
    ]
    with patch("sys.argv", argv), patch("anthropic.Anthropic", _FakeAnthropicClient):
        rae.main()

    rows = json.loads(out.read_bytes())
    assert [r["id"] for r in rows] == ["q001", "q003"]  # master order, not CLI order

    hb_file = progress_dir / f"{out.stem}.json"
    hb = json.loads(hb_file.read_text(encoding="utf-8"))
    assert hb["n_total"] == 2  # filtered count, not the full 4-question set


def test_run_openrouter_arm_qids_selects_subset_in_master_order(tmp_path, monkeypatch):
    progress_dir = tmp_path / "_progress"
    monkeypatch.setattr(progress, "PROGRESS_DIR", progress_dir)

    questions = tmp_path / "q.jsonl"
    empty_cards = tmp_path / "cards.jsonl"
    _write_questions(questions, ["q001", "q002", "q003", "q004"])
    empty_cards.write_text("", encoding="utf-8")
    out = tmp_path / "out.json"
    argv = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--out", str(out), "--qids", "q004,q002",
    ]
    with patch("sys.argv", argv), patch.object(orb, "generate", side_effect=_fake_or_result):
        roa.main()

    data = json.loads(out.read_bytes())
    assert [r["id"] for r in data["results"]] == ["q002", "q004"]  # master order

    hb_file = progress_dir / f"{out.stem}.json"
    hb = json.loads(hb_file.read_text(encoding="utf-8"))
    assert hb["n_total"] == 2  # filtered count, not the full 4-question set


def test_run_answer_eval_qids_unknown_id_exits_1_with_message(tmp_path, capsys):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001", "q002"])
    out = tmp_path / "out.json"
    argv = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions), "--out", str(out),
        "--qids", "q001,q999",
    ]
    with patch("sys.argv", argv), patch("anthropic.Anthropic", _FakeAnthropicClient):
        with pytest.raises(SystemExit) as exc_info:
            rae.main()
    assert exc_info.value.code == 1
    assert not out.exists()
    captured = capsys.readouterr()
    assert "q999" in captured.out
    assert "[ERROR]" in captured.out

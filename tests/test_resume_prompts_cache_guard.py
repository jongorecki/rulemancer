"""Resume-safety regression test (coordinator review, on top of docs/plan-
run-progress.md): the v5 2x2 symbol-injection grid runs four cells sharing
model/rewrite_version/ruling_query_mode/reasoning and differing ONLY in
which prompts file they read. Before this fix, aiming two such cells at the
same --out by accident would have resume silently keep rows generated from
a DIFFERENT prompt -- worse than the pre-resume behavior (a path collision
used to just waste money by regenerating everything).

This asserts the fix in both runners: model/rewrite_version/ruling_query_mode
all matching is NOT enough to resume when the prompts-cache identity
(path + content digest) differs -- that specific mismatch must hard-error
(non-zero exit) and leave the existing output file completely untouched,
never silently resumed from and never silently regenerated over.

No live HTTP/Anthropic calls -- openrouter_backend.generate() and
anthropic.Anthropic are both patched, same pattern as
test_openrouter_reasoning.py / the schema-identity gate used during manual
verification.
"""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from evals import run_answer_eval as rae
from evals import run_openrouter_arm as roa
from rulesagent.contracts import Answer
from rulesagent.generate import openrouter_backend as orb


def _fake_or_result(system, user, model, reasoning=None):
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
        user = messages[0]["content"]
        h = hashlib.sha256(user.encode()).hexdigest()[:8]
        return _FakeResponse(Answer(text=f"answer-{h}", tldr="t", citations=[],
                                    answered=True, suggested_followups=[]))


class _FakeAnthropicClient:
    def __init__(self, *a, **kw):
        self.messages = _FakeMessages()


def _write_cache(path: Path, ids: list[str], system_text: str):
    path.write_text(json.dumps({
        "rewrite_version": "v2", "ruling_query_mode": "raw", "n_questions": len(ids),
        "prompts": {i: {"system": system_text, "user": f"USER-{i}"} for i in ids},
    }), encoding="utf-8")


def _write_questions(path: Path, ids: list[str]):
    path.write_text("\n".join(
        json.dumps({"id": i, "question": f"Q for {i}", "gold": []}) for i in ids
    ), encoding="utf-8")


def test_openrouter_arm_hard_errors_on_prompts_cache_collision(tmp_path):
    questions = tmp_path / "q.jsonl"
    empty_cards = tmp_path / "cards.jsonl"
    _write_questions(questions, ["q001", "q002"])
    empty_cards.write_text("", encoding="utf-8")

    cache_a = tmp_path / "cache_a.json"
    cache_b = tmp_path / "cache_b.json"
    _write_cache(cache_a, ["q001", "q002"], "SYSTEM VARIANT A")
    _write_cache(cache_b, ["q001", "q002"], "SYSTEM VARIANT B -- totally different prompt")

    out = tmp_path / "out.json"

    argv_a = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--prompts-cache", str(cache_a), "--out", str(out),
    ]
    with patch("sys.argv", argv_a), patch.object(orb, "generate", side_effect=_fake_or_result):
        roa.main()

    written_after_a = out.read_bytes()
    assert json.loads(written_after_a)["summary"]["prompts_cache_sha256"] is not None

    # Same model/rewrite_version/ruling_query_mode/reasoning, DIFFERENT
    # prompts cache, SAME --out -- the exact v5-grid path-collision shape.
    argv_b = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--prompts-cache", str(cache_b), "--out", str(out),
    ]
    with patch("sys.argv", argv_b), patch.object(orb, "generate", side_effect=_fake_or_result):
        with pytest.raises(SystemExit) as exc_info:
            roa.main()

    assert exc_info.value.code != 0
    # The existing file must be completely untouched -- no silent resume,
    # no silent regenerate, no partial write from the aborted second run.
    assert out.read_bytes() == written_after_a


def test_openrouter_arm_still_resumes_when_cache_matches(tmp_path):
    """Sanity check the fix isn't overzealous: an actual restart of the SAME
    command (same cache) still resumes normally, no error."""
    questions = tmp_path / "q.jsonl"
    empty_cards = tmp_path / "cards.jsonl"
    _write_questions(questions, ["q001", "q002", "q003"])
    empty_cards.write_text("", encoding="utf-8")

    cache = tmp_path / "cache.json"
    _write_cache(cache, ["q001", "q002", "q003"], "SYSTEM")
    out = tmp_path / "out.json"

    argv = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--prompts-cache", str(cache), "--out", str(out),
    ]
    with patch("sys.argv", argv), patch.object(orb, "generate", side_effect=_fake_or_result):
        roa.main()
    first = json.loads(out.read_bytes())
    assert len(first["results"]) == 3

    # Same exact command again -- must resume cleanly (no error), and
    # produce a byte-identical file (all rows already present, all skipped).
    with patch("sys.argv", argv), patch.object(orb, "generate", side_effect=_fake_or_result):
        roa.main()
    second = out.read_bytes()
    assert json.loads(second) == first


def test_answer_eval_hard_errors_on_prompts_cache_collision(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001", "q002"])

    cache_a = tmp_path / "cache_a.json"
    cache_b = tmp_path / "cache_b.json"
    _write_cache(cache_a, ["q001", "q002"], "SYSTEM VARIANT A")
    _write_cache(cache_b, ["q001", "q002"], "SYSTEM VARIANT B -- totally different prompt")

    out = tmp_path / "out.json"

    argv_a = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions),
        "--prompts-cache", str(cache_a), "--out", str(out),
        "--rewrite-version", "v2", "--ruling-query-mode", "raw",
    ]
    with patch("sys.argv", argv_a), \
         patch("anthropic.Anthropic", _FakeAnthropicClient):
        rae.main()

    written_after_a = out.read_bytes()
    rows_after_a = json.loads(written_after_a)
    assert rows_after_a[0]["prompts_cache_sha256"] is not None

    argv_b = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions),
        "--prompts-cache", str(cache_b), "--out", str(out),
        "--rewrite-version", "v2", "--ruling-query-mode", "raw",
    ]
    with patch("sys.argv", argv_b), \
         patch("anthropic.Anthropic", _FakeAnthropicClient):
        with pytest.raises(SystemExit) as exc_info:
            rae.main()

    assert exc_info.value.code != 0
    assert out.read_bytes() == written_after_a


def test_answer_eval_still_resumes_when_cache_matches(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001", "q002", "q003"])
    cache = tmp_path / "cache.json"
    _write_cache(cache, ["q001", "q002", "q003"], "SYSTEM")
    out = tmp_path / "out.json"

    argv = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions),
        "--prompts-cache", str(cache), "--out", str(out),
        "--rewrite-version", "v2", "--ruling-query-mode", "raw",
    ]
    with patch("sys.argv", argv), patch("anthropic.Anthropic", _FakeAnthropicClient):
        rae.main()
    first = json.loads(out.read_bytes())
    assert len(first) == 3

    with patch("sys.argv", argv), patch("anthropic.Anthropic", _FakeAnthropicClient):
        rae.main()
    assert json.loads(out.read_bytes()) == first

"""Condition-E reasoning passthrough tests (docs/plan-v4e-execution-tasks.md
Task 2, docs/plan-condition-e-reasoning.md Sec 2).

Covers only the body-builder branch in openrouter_backend._attempt(): the
`reasoning` parameter must be a pure additive no-op when absent (byte-
identical request body to today, so every past eval number stays valid) and
must add exactly one key, unchanged otherwise, when supplied.

No live HTTP call here -- httpx.post is patched so the test asserts on the
constructed request body, never a network response.
"""
import argparse
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evals import run_openrouter_arm as roa
from rulesagent.contracts import Answer
from rulesagent.generate import openrouter_backend as orb


def _fake_response(content: str = '{"answered": true, "text": "ok", "tldr": "ok", '
                                   '"citations": [], "suggested_followups": []}'):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "model": "openai/gpt-5-mini",
        "provider": "OpenAI",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        "choices": [{"message": {"content": content}}],
    }
    return resp


def test_reasoning_absent_body_unchanged():
    """Default (no reasoning arg) -- body has no 'reasoning' key, and every
    other key/value matches today's fixed set exactly."""
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _fake_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post):
        result = orb._attempt("SYS", "USER", "openai/gpt-5-mini", "fake-key", 30.0)

    assert result.answer is not None
    body = captured["body"]
    assert "reasoning" not in body
    assert body == {
        "model": "openai/gpt-5-mini",
        "messages": [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "USER"},
        ],
        "provider": {"allow_fallbacks": False},
        "seed": orb.SEED,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "strict": True,
                "schema": orb._answer_schema(),
            },
        },
        "max_tokens": 16384,
        # no "temperature": gpt-5-mini is in NO_TEMPERATURE
    }


def test_reasoning_absent_matches_model_with_temperature():
    """Same no-op guarantee for a model that DOES get temperature sent, so
    the reasoning-absent default doesn't perturb that branch either."""
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _fake_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post):
        orb._attempt("SYS", "USER", "some/other-model", "fake-key", 30.0)

    body = captured["body"]
    assert "reasoning" not in body
    assert body["temperature"] == 0.0


def test_reasoning_set_adds_key_only():
    """reasoning={'effort': 'high'} -- body gains exactly that key with that
    value; nothing else moves."""
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _fake_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post):
        result = orb._attempt("SYS", "USER", "openai/gpt-5-mini", "fake-key", 30.0,
                              reasoning={"effort": "high"})

    assert result.answer is not None
    body = captured["body"]
    assert body["reasoning"] == {"effort": "high"}
    without_reasoning = {k: v for k, v in body.items() if k != "reasoning"}
    assert without_reasoning == {
        "model": "openai/gpt-5-mini",
        "messages": [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "USER"},
        ],
        "provider": {"allow_fallbacks": False},
        "seed": orb.SEED,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "strict": True,
                "schema": orb._answer_schema(),
            },
        },
        "max_tokens": 16384,
    }


def test_generate_threads_reasoning_through():
    """generate() passes its `reasoning` kwarg down to _attempt() so the
    top-level public entry point (used by run_openrouter_arm.py) actually
    reaches the body builder."""
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _fake_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        result = orb.generate("SYS", "USER", "openai/gpt-5-mini",
                              reasoning={"effort": "high"})

    assert result.answer is not None
    assert captured["body"]["reasoning"] == {"effort": "high"}


def test_generate_default_still_omits_reasoning():
    """generate() with no reasoning kwarg (every existing call site) keeps
    producing a body with no 'reasoning' key -- the default path callers
    depend on is untouched."""
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _fake_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        result = orb.generate("SYS", "USER", "openai/gpt-5-mini")

    assert result.answer is not None
    assert "reasoning" not in captured["body"]


# --- evals/run_openrouter_arm.py --reasoning CLI passthrough --------------

def test_parse_reasoning_none_when_absent():
    p = argparse.ArgumentParser()
    assert roa._parse_reasoning(p, None) is None


@pytest.mark.parametrize("shorthand", ["low", "medium", "high"])
def test_parse_reasoning_shorthand(shorthand):
    p = argparse.ArgumentParser()
    assert roa._parse_reasoning(p, shorthand) == {"effort": shorthand}


def test_parse_reasoning_raw_json_escape_hatch():
    p = argparse.ArgumentParser()
    raw = '{"effort": "xhigh", "exclude": true}'
    assert roa._parse_reasoning(p, raw) == {"effort": "xhigh", "exclude": True}


def test_parse_reasoning_invalid_string_errors():
    p = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        roa._parse_reasoning(p, "not-json-and-not-shorthand")


def test_parse_reasoning_rejects_non_object_json():
    p = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        roa._parse_reasoning(p, "[1, 2, 3]")


# --- --retry-errors x --reasoning interaction (fix-loop findings 1/2/3) ----
# Pattern follows tests/test_retry_errors_guard.py's model-mismatch guard.

def _make_retry_fixture(tmpdir: str, recorded_reasoning):
    """One errored row + its matching prompts_cache -- everything a real
    retry needs to reach the generate() call (not skip it as a cache miss)."""
    cache_path = Path(tmpdir) / "cache.json"
    cache_path.write_text(json.dumps({
        "rewrite_version": "v2", "ruling_query_mode": "raw", "n_questions": 1,
        "prompts": {"q001": {"system": "SYS", "user": "USER"}},
    }), encoding="utf-8")
    data = {
        "model": "openai/gpt-5-mini",
        "rewrite_version": "v2",
        "ruling_query_mode": "raw",
        "reasoning": recorded_reasoning,
        "prompts_cache": str(cache_path),
        "results": [
            {
                "id": "q001",
                "question": "What is a rule?",
                "answered": None,
                "text": None,
                "citations": None,
                "error": "timeout",
                "raw_text": None,
            }
        ],
        "summary": {"n_questions": 1, "answered": 0, "parse_failures": 0, "total_cost": 0},
    }
    answers_file = Path(tmpdir) / "answers.json"
    answers_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return answers_file, data


def _fake_answer_result():
    return orb.ORResult(
        answer=Answer(text="ok", tldr="ok", citations=[], answered=True, suggested_followups=[]),
        requested_model="openai/gpt-5-mini", served_model="openai/gpt-5-mini",
        provider="OpenAI", temperature_sent=None, seed_sent=orb.SEED,
        usage={"completion_tokens": 1},
    )


def test_retry_no_reasoning_flag_reuses_file_value():
    """(a) --retry-errors with --reasoning OMITTED silently reuses the
    file's recorded reasoning -- the normal, expected path -- and generate()
    is actually called with it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        answers_file, _ = _make_retry_fixture(tmpdir, {"effort": "high"})

        with patch("sys.argv", [
            "run_openrouter_arm.py",
            "--retry-errors", str(answers_file),
            "--model", "openai/gpt-5-mini",
        ]), patch.object(roa.openrouter_backend, "generate",
                         return_value=_fake_answer_result()) as mock_generate:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                roa.main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        assert "refusing to silently change the reasoning config" not in output
        mock_generate.assert_called_once()
        assert mock_generate.call_args.kwargs["reasoning"] == {"effort": "high"}
        written = json.loads(answers_file.read_text(encoding="utf-8"))
        assert written["results"][0]["error"] is None  # row actually got retried


def test_retry_matching_reasoning_flag_proceeds():
    """(b) --retry-errors with --reasoning explicitly matching the file's
    recorded value proceeds normally (no error, row gets retried)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        answers_file, _ = _make_retry_fixture(tmpdir, {"effort": "high"})

        with patch("sys.argv", [
            "run_openrouter_arm.py",
            "--retry-errors", str(answers_file),
            "--model", "openai/gpt-5-mini",
            "--reasoning", "high",
        ]), patch.object(roa.openrouter_backend, "generate",
                         return_value=_fake_answer_result()) as mock_generate:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                roa.main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        assert "refusing to silently change the reasoning config" not in output
        mock_generate.assert_called_once()
        assert mock_generate.call_args.kwargs["reasoning"] == {"effort": "high"}
        written = json.loads(answers_file.read_text(encoding="utf-8"))
        assert written["results"][0]["error"] is None


def test_retry_conflicting_reasoning_flag_hard_errors_and_does_not_write():
    """(c) --retry-errors with --reasoning explicitly DIFFERING from the
    file's recorded value hard-errors and never touches the output file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        answers_file, original_data = _make_retry_fixture(tmpdir, {"effort": "high"})
        original_bytes = answers_file.read_bytes()

        with patch("sys.argv", [
            "run_openrouter_arm.py",
            "--retry-errors", str(answers_file),
            "--model", "openai/gpt-5-mini",
            "--reasoning", "low",
        ]), patch.object(roa.openrouter_backend, "generate",
                         return_value=_fake_answer_result()) as mock_generate:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                roa.main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        assert "refusing to silently change the reasoning config" in output
        mock_generate.assert_not_called()
        # File on disk is byte-for-byte untouched -- the guard fires before
        # any row is retried or the file is rewritten.
        assert answers_file.read_bytes() == original_bytes


def test_retry_legacy_file_without_reasoning_key_treated_as_none():
    """A pre-condition-E answers file has no 'reasoning' key at all --
    data.get("reasoning") is None, so omitting --reasoning reuses that
    (matches), and explicitly passing --reasoning high is a mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache_path.write_text(json.dumps({
            "rewrite_version": "v2", "ruling_query_mode": "raw", "n_questions": 1,
            "prompts": {"q001": {"system": "SYS", "user": "USER"}},
        }), encoding="utf-8")
        data = {
            "model": "openai/gpt-5-mini",
            "rewrite_version": "v2",
            "ruling_query_mode": "raw",
            # no "reasoning" key -- legacy file
            "prompts_cache": str(cache_path),
            "results": [{
                "id": "q001", "question": "What is a rule?", "answered": None,
                "text": None, "citations": None, "error": "timeout", "raw_text": None,
            }],
            "summary": {"n_questions": 1, "answered": 0, "parse_failures": 0, "total_cost": 0},
        }
        answers_file = Path(tmpdir) / "answers.json"
        answers_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with patch("sys.argv", [
            "run_openrouter_arm.py",
            "--retry-errors", str(answers_file),
            "--model", "openai/gpt-5-mini",
            "--reasoning", "high",
        ]), patch.object(roa.openrouter_backend, "generate",
                         return_value=_fake_answer_result()) as mock_generate:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                roa.main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        assert "refusing to silently change the reasoning config" in output
        mock_generate.assert_not_called()

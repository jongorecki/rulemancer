"""Malformed-200-body handling in openrouter_backend._attempt() (docs/
plan-run-progress.md Sec 4/5.4): a malformed or truncated HTTP 200 body used
to escape `_attempt()`'s except clauses entirely (json.JSONDecodeError isn't
an httpx.HTTPError subclass), killing the whole run with zero rows saved --
the bug that crashed the first default r2 (Google aborting gemini-flash-lite
generations mid-stream still returns 200). This asserts the fix: a
truncated/malformed 200 body is retried through the SAME bounded-retry loop
as a transient HTTP failure, and a body that's permanently bad ends as a
recorded error row (result.answer is None, result.error set), never an
uncaught exception.

No live HTTP call -- httpx.post is patched, same pattern as
test_openrouter_reasoning.py. time.sleep is also patched so the retry
backoff doesn't actually slow the test down."""

import json
from unittest.mock import MagicMock, patch

from rulesagent.generate import openrouter_backend as orb


def _ok_response(content: str = '{"answered": true, "text": "ok", "tldr": "ok", '
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


def _malformed_response():
    """A 200 whose body doesn't even parse as JSON -- raise_for_status()
    never fires (it's a real 200), but .json() blows up, exactly the
    Google-mid-stream-abort shape the docstring in openrouter_backend.py
    describes."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    return resp


def test_malformed_200_retries_then_succeeds():
    """First two responses are malformed 200s, third is a clean one --
    _attempt() must retry past the malformed ones and return the real
    answer, never raise."""
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None):
        calls["n"] += 1
        return _malformed_response() if calls["n"] < 3 else _ok_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.object(orb.time, "sleep", return_value=None):
        result = orb._attempt("SYS", "USER", "openai/gpt-5-mini", "fake-key", 30.0)

    assert result.answer is not None
    assert result.error is None
    assert calls["n"] == 3  # two malformed attempts, then the real one


def test_malformed_200_permanently_bad_ends_as_error_row_not_a_raise():
    """Every response is malformed -- _attempt() exhausts its retry budget
    and returns an ORResult with error set (a recorded error row), rather
    than letting json.JSONDecodeError propagate out and kill the run."""
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None):
        calls["n"] += 1
        return _malformed_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.object(orb.time, "sleep", return_value=None):
        result = orb._attempt("SYS", "USER", "openai/gpt-5-mini", "fake-key", 30.0)

    assert result.answer is None
    assert result.error is not None
    assert result.error.startswith("json:")
    assert calls["n"] == 5  # the existing 5-attempt retry budget, unchanged


def test_malformed_200_generate_wrapper_also_survives():
    """The public generate() entry point (what the runners actually call)
    doesn't re-raise either -- a permanently malformed body surfaces as an
    ORResult with error set, same as a definitive HTTP failure."""
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None):
        calls["n"] += 1
        return _malformed_response()

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.object(orb.time, "sleep", return_value=None), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        result = orb.generate("SYS", "USER", "openai/gpt-5-mini")

    assert result.answer is None
    assert result.error is not None
    assert result.error.startswith("json:")

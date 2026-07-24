# Tests for rewriter prompt versioning (docs/plan-prompt-tuning.md Sec 2,
# Task 1 in docs/plan-v3-execution-tasks.md).
#
# TDD: written before rewrite.py supports a `version` param on rewrite_query()
# or a SYSTEM_VERSIONS mapping -- watch these fail first (AttributeError /
# ImportError / TypeError on the not-yet-existing pieces), then implement.
#
# Every test uses a fake anthropic client (no network) and a tmp_path-backed
# KVCache (never touches the real data/cache.db), following the
# _RecordingClient pattern already used by tests/test_prompt_identity.py and
# evals/run_openrouter_arm.py.

import inspect
import json
from unittest.mock import patch

import pytest

from rulesagent.cache import KVCache
from rulesagent.retrieve import rewrite as rw

# The exact byte content of today's SYSTEM string (rewrite.py lines 52-71,
# pre-v3), copied verbatim -- this is the frozen "v1 must stay byte-identical"
# guarantee the plan requires. If this test starts failing, v1's wording
# changed and that's a regression, not a fixture to update casually.
FROZEN_V1_SYSTEM = """You rewrite casual Magic: The Gathering rules questions into the \
vocabulary the official Comprehensive Rules actually use, so that a semantic \
search over the rules text finds the rules that answer them.

The rules use precise technical language that players rarely say out loud. \
Rewrite the question the way the rules themselves would phrase it, and name \
the underlying game concepts likely at issue (for example: priority, the \
stack, zones, steps and phases, timing, state-based actions, or the discrete \
parts of casting a spell or activating an ability).

Requirements:
- Produce exactly {n} distinct rewrite(s). With more than one, each must \
attack the question from a genuinely different angle rather than restating \
the same phrasing.
- Never include rule numbers. You do not know them, and a wrong number \
poisons the search.
- Each rewrite is a self-contained question or statement, not a keyword list.
- Set clarification ONLY if the correct answer would materially differ \
between readings (player count, which of two cards is meant, a named \
format). Most questions need none -- leave it null."""


class _FakeResponse:
    def __init__(self, queries, clarification=None):
        self.parsed_output = rw._Rewrites(queries=queries, clarification=clarification)


class _FakeMessages:
    def __init__(self, queries, clarification=None):
        self.calls: list[dict] = []
        self._queries = queries
        self._clarification = clarification

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._queries, self._clarification)


class _FakeClient:
    def __init__(self, queries=("a rewrite",), clarification=None):
        self.messages = _FakeMessages(list(queries), clarification)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Every test gets a fresh on-disk cache, never the real data/cache.db."""
    monkeypatch.setattr(rw, "_cache", KVCache("rewrite", db_path=tmp_path / "cache.db"))


def test_v1_system_is_byte_identical_to_frozen_text():
    assert rw.SYSTEM_VERSIONS["v1"] == FROZEN_V1_SYSTEM


def test_default_prompt_version_is_v2():
    assert rw.PROMPT_VERSION == "v2"


def test_v2_system_contains_v1_text_plus_two_new_bullets():
    v1, v2 = rw.SYSTEM_VERSIONS["v1"], rw.SYSTEM_VERSIONS["v2"]
    assert v1 != v2
    # v2 must still carry every v1 bullet verbatim -- nothing dropped, only added.
    assert "Never include rule numbers." in v2
    assert "Each rewrite is a self-contained question or statement" in v2
    assert "Set clarification ONLY if the correct answer" in v2
    # The two new bullets (Sec 2a / 2b), verbatim key phrases.
    assert "one generic mana" in v2
    assert "one green mana" in v2
    assert "the defending player" in v2
    assert "when there is more than one opponent" in v2


def test_rewrite_query_defaults_to_v2_system():
    client = _FakeClient()
    rw.rewrite_query("what does trample do", "test-model", 1, client)
    sent_system = client.messages.calls[0]["system"]
    assert sent_system == rw.SYSTEM_VERSIONS["v2"].format(n=1)


def test_rewrite_query_uses_v1_system_when_requested():
    client = _FakeClient()
    rw.rewrite_query("what does trample do", "test-model", 1, client, version="v1")
    sent_system = client.messages.calls[0]["system"]
    assert sent_system == rw.SYSTEM_VERSIONS["v1"].format(n=1)


def test_cache_key_includes_selected_version():
    """A v1 call and a v2 call for the IDENTICAL (model, n, question) must
    write to DIFFERENT cache keys -- otherwise switching versions would
    silently keep serving a rewrite made under the other version's prompt."""
    client_v1 = _FakeClient(queries=["v1 rewrite"])
    client_v2 = _FakeClient(queries=["v2 rewrite"])

    rw.rewrite_query("what does trample do", "test-model", 1, client_v1, version="v1")
    rw.rewrite_query("what does trample do", "test-model", 1, client_v2, version="v2")

    key_v1 = json.dumps(["test-model", "v1", 1, "what does trample do"])
    key_v2 = json.dumps(["test-model", "v2", 1, "what does trample do"])
    assert rw._cache.get(key_v1) is not None
    assert rw._cache.get(key_v2) is not None
    assert json.loads(rw._cache.get(key_v1))[0] == ["v1 rewrite"]
    assert json.loads(rw._cache.get(key_v2))[0] == ["v2 rewrite"]


def test_v1_cache_entry_is_not_served_for_a_v2_request():
    """A cold v2 call must NOT be satisfied by a warm v1 cache entry for the
    same question -- the version string must be part of the cache lookup,
    not just the write."""
    client_v1 = _FakeClient(queries=["v1 rewrite"])
    rw.rewrite_query("what does trample do", "test-model", 1, client_v1, version="v1")

    client_v2 = _FakeClient(queries=["v2 rewrite"])
    result = rw.rewrite_query("what does trample do", "test-model", 1, client_v2, version="v2")

    # The v2 call must have actually hit the (fake) API, not returned the
    # v1-cached rewrite -- proven two ways: a real API call was made, and
    # the result reflects the v2 client's response, not v1's.
    assert len(client_v2.messages.calls) == 1
    assert result.queries == ["v2 rewrite"]


def test_rewrite_query_still_works_with_no_version_kwarg_at_all():
    """Existing call sites (evals/run_eval.py, answer.py, etc.) call
    rewrite_query() positionally without a `version` kwarg -- must keep
    working and get the new v2 default, not raise a TypeError."""
    client = _FakeClient()
    result = rw.rewrite_query("what does trample do", "test-model", 1, client, context=None)
    assert result.queries == ["a rewrite"]
    assert client.messages.calls[0]["system"] == rw.SYSTEM_VERSIONS["v2"].format(n=1)


# --- backend seam: OpenRouter (gpt5mini) rewriter arm ------------------------
# TDD for the gpt5mini rewriter-arm spec: rewrite_query() gains a
# `backend: str = "anthropic"` kwarg. Default behavior (no `backend` passed,
# or `backend="anthropic"` explicitly) must stay byte-for-byte identical to
# today -- that's the control arm and any drift invalidates the comparison.
# The new "openrouter" branch reuses the SAME content-building logic as the
# Anthropic branch and routes through openrouter_backend.call_structured()
# instead of anthropic.Anthropic().messages.parse().


def test_backend_param_defaults_to_anthropic():
    sig = inspect.signature(rw.rewrite_query)
    assert sig.parameters["backend"].default == "anthropic"


def test_backend_anthropic_explicit_matches_omitted_default():
    """Passing backend='anthropic' explicitly must behave identically to
    omitting it -- both must call the Anthropic client the same way. Two
    distinct questions are used so the second call is never a cache hit for
    the first (which would mean the Anthropic client is never touched at
    all, telling us nothing) -- what's compared is the SHAPE of the call
    (everything but the question-derived content), which must match."""
    client_default = _FakeClient(queries=["r1"])
    rw.rewrite_query("what does trample do", "test-model", 1, client_default)

    client_explicit = _FakeClient(queries=["r1"])
    rw.rewrite_query(
        "what does deathtouch do", "test-model", 1, client_explicit, backend="anthropic"
    )

    call_default = client_default.messages.calls[0]
    call_explicit = client_explicit.messages.calls[0]
    assert call_default["model"] == call_explicit["model"]
    assert call_default["max_tokens"] == call_explicit["max_tokens"]
    assert call_default["system"] == call_explicit["system"]
    assert call_default["output_format"] == call_explicit["output_format"]


def test_openrouter_backend_never_constructs_anthropic_client():
    """backend='openrouter' must never touch anthropic.Anthropic, even with
    client=None (the default construction path for the Anthropic branch)."""
    with patch("rulesagent.retrieve.rewrite.anthropic.Anthropic") as mock_anthropic, \
         patch.object(rw.openrouter_backend, "call_structured",
                      return_value={"queries": ["x"], "clarification": None}):
        rw.rewrite_query("what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter")
    mock_anthropic.assert_not_called()


def test_openrouter_backend_builds_same_content_as_anthropic_for_same_inputs():
    """The content-building logic (question, or the context-resolution
    wrapper) must be REUSED identically by both branches -- same question +
    same context must produce the exact same system/user text regardless of
    backend."""
    client = _FakeClient(queries=["anthropic rewrite"])
    rw.rewrite_query(
        "what if it's phased out", "test-model", 1, client,
        context="Earlier turn about creatures.",
    )
    anthropic_system = client.messages.calls[0]["system"]
    anthropic_content = client.messages.calls[0]["messages"][0]["content"]

    captured = {}

    def fake_call_structured(system, user, model, schema, schema_name="output", timeout=300.0):
        captured["system"] = system
        captured["user"] = user
        return {"queries": ["openrouter rewrite"], "clarification": None}

    with patch.object(rw.openrouter_backend, "call_structured", side_effect=fake_call_structured):
        rw.rewrite_query(
            "what if it's phased out", "test-model", 1, None,
            context="Earlier turn about creatures.", backend="openrouter",
        )

    assert captured["system"] == anthropic_system
    assert captured["user"] == anthropic_content


def test_openrouter_backend_returns_rewritten_query_from_parsed_json():
    def fake_call_structured(system, user, model, schema, schema_name="output", timeout=300.0):
        return {"queries": ["a", "b"], "clarification": "which creature?"}

    with patch.object(rw.openrouter_backend, "call_structured", side_effect=fake_call_structured):
        result = rw.rewrite_query(
            "what does trample do", "openai/gpt-5-mini", 2, None, backend="openrouter"
        )

    assert result.queries == ["a", "b"]
    assert result.clarification == "which creature?"
    assert result.original == "what does trample do"


def test_openrouter_backend_falls_back_on_none_from_call_structured():
    with patch.object(rw.openrouter_backend, "call_structured", return_value=None):
        result = rw.rewrite_query(
            "what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter"
        )
    assert result.queries == ["what does trample do"]
    assert result.clarification is None


def test_openrouter_backend_falls_back_on_call_structured_raising():
    """Same broad-except discipline as the Anthropic branch: any exception
    from the OpenRouter call degrades to the fallback, never propagates."""
    with patch.object(rw.openrouter_backend, "call_structured", side_effect=RuntimeError("boom")):
        result = rw.rewrite_query(
            "what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter"
        )
    assert result.queries == ["what does trample do"]
    assert result.clarification is None


def test_openrouter_backend_passes_strict_schema_for_rewrites():
    captured = {}

    def fake_call_structured(system, user, model, schema, schema_name="output", timeout=300.0):
        captured["schema"] = schema
        return {"queries": ["x"], "clarification": None}

    with patch.object(rw.openrouter_backend, "call_structured", side_effect=fake_call_structured):
        rw.rewrite_query("what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter")

    schema = captured["schema"]
    assert schema["additionalProperties"] is False
    assert "title" not in schema
    assert set(schema["required"]) == set(schema["properties"].keys())


def test_openrouter_backend_result_is_cached_same_as_anthropic():
    """The cache key (model, version, n, question) is untouched -- a second
    call with identical inputs must be a cache hit, zero further calls to
    call_structured, same discipline as the Anthropic branch."""
    call_count = {"n": 0}

    def fake_call_structured(system, user, model, schema, schema_name="output", timeout=300.0):
        call_count["n"] += 1
        return {"queries": ["cached rewrite"], "clarification": None}

    with patch.object(rw.openrouter_backend, "call_structured", side_effect=fake_call_structured):
        first = rw.rewrite_query("what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter")
        second = rw.rewrite_query("what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter")

    assert call_count["n"] == 1
    assert first.queries == second.queries == ["cached rewrite"]


def test_openrouter_backend_temperature_key_absent_for_no_temperature_model_end_to_end():
    """End-to-end (no mocking of call_structured itself, only the HTTP layer)
    -- gpt-5-mini's request body must omit `temperature` entirely, and a
    model outside NO_TEMPERATURE must send temperature: 0."""
    from unittest.mock import MagicMock

    from rulesagent.generate import openrouter_backend as orb

    def _ok(content):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "model": "openai/gpt-5-mini", "provider": "OpenAI",
            "usage": {}, "choices": [{"message": {"content": content}}],
        }
        return resp

    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _ok('{"queries": ["x"], "clarification": null}')

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        rw.rewrite_query("what does trample do", "openai/gpt-5-mini", 1, None, backend="openrouter")

    assert "temperature" not in captured["body"]

    captured.clear()
    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        rw.rewrite_query("some/other-model question", "some/other-model", 1, None, backend="openrouter")

    assert captured["body"]["temperature"] == 0.0

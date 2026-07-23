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

import json

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

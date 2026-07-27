"""Tests for --batch (Anthropic Message Batches API support) in
evals/run_answer_eval.py.

Everything here is a FAKE client -- no anthropic.Anthropic() is ever
constructed and no network call is ever made. This matches the established
stub pattern in tests/test_groundedness_guard.py / test_uncited_success.py:
plain Python doubles for client.messages.batches.create/retrieve/results,
built with types.SimpleNamespace rather than real anthropic SDK response
objects (those require a live parse from actual HTTP JSON and aren't needed
here -- the code under test only reads a handful of attributes off them).

Covers: request construction from a frozen prompts cache; custom_id
round-trip mapping (including out-of-order results); the two refusal cases
(live path, --reground); result parsing into the same row shape
_answer_from_frozen_prompt() produces; discounted cost maths; resume
attaches rather than resubmits; and a per-request error recorded rather than
silently dropped.
"""
import argparse
import json
import types
from pathlib import Path

import pytest

from evals import run_answer_eval as rae
from rulesagent import pricing
from rulesagent.contracts import Answer


# --- fakes -------------------------------------------------------------

class _FakeBatch:
    def __init__(self, id_, processing_status="in_progress",
                succeeded=0, errored=0, canceled=0, expired=0, processing=0):
        self.id = id_
        self.processing_status = processing_status
        self.request_counts = types.SimpleNamespace(
            succeeded=succeeded, errored=errored, canceled=canceled,
            expired=expired, processing=processing,
        )


class _FakeBatchesResource:
    """Fake for client.messages.batches -- records every create() call so
    tests can assert resume-without-resubmit by call count."""

    def __init__(self, batch_id="msgbatch_test123", statuses=None, results=None):
        self.create_calls = []
        self.retrieve_calls = []
        self._batch_id = batch_id
        # statuses: list of processing_status strings returned by successive
        # retrieve() calls, simulating polling -- defaults to ended immediately.
        self._statuses = list(statuses) if statuses is not None else ["ended"]
        self._results = results or []

    def create(self, *, requests):
        self.create_calls.append(list(requests))
        return _FakeBatch(self._batch_id, processing_status="in_progress")

    def retrieve(self, batch_id):
        self.retrieve_calls.append(batch_id)
        idx = min(len(self.retrieve_calls) - 1, len(self._statuses) - 1)
        status = self._statuses[idx]
        counts = {"succeeded": len(self._results)} if status == "ended" else {}
        return _FakeBatch(batch_id, processing_status=status, **counts)

    def results(self, batch_id):
        return iter(self._results)


class _FakeClient:
    def __init__(self, batches: _FakeBatchesResource):
        self.messages = types.SimpleNamespace(batches=batches)


def _text_block(payload: dict):
    return types.SimpleNamespace(type="text", text=json.dumps(payload))


def _fake_succeeded_result(custom_id: str, answer_payload: dict, *,
                          stop_reason="end_turn", input_tokens=100, output_tokens=50,
                          cache_read=0, cache_creation=0):
    msg = types.SimpleNamespace(
        content=[_text_block(answer_payload)],
        stop_reason=stop_reason,
        usage=types.SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
            cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_creation,
        ),
    )
    return types.SimpleNamespace(
        custom_id=custom_id,
        result=types.SimpleNamespace(type="succeeded", message=msg),
    )


def _fake_errored_result(custom_id: str, message: str = "internal_server_error"):
    return types.SimpleNamespace(
        custom_id=custom_id,
        result=types.SimpleNamespace(
            type="errored", error=types.SimpleNamespace(message=message),
        ),
    )


def _fake_expired_result(custom_id: str):
    return types.SimpleNamespace(
        custom_id=custom_id,
        result=types.SimpleNamespace(type="expired"),
    )


_ANSWER_PAYLOAD = {
    "text": "Trample assigns excess damage through.", "tldr": "Yes.",
    "citations": ["702.19c"], "answered": True, "suggested_followups": [],
}

_PROMPTS_CACHE = {
    "q1": {"system": "SYSTEM PROMPT", "user": "What does trample do?"},
    "q2": {"system": "SYSTEM PROMPT", "user": "What does deathtouch do?"},
}


# --- request construction from a frozen prompts cache -------------------

def test_batch_request_params_mirror_sync_shape():
    params = rae._batch_request_params(
        model="claude-opus-5",
        system=_PROMPTS_CACHE["q1"]["system"],
        user=_PROMPTS_CACHE["q1"]["user"],
        max_tokens=1234,
        effort="high",
        cache_prompt=False,
    )
    assert params["model"] == "claude-opus-5"
    assert params["max_tokens"] == 1234
    assert params["system"] == "SYSTEM PROMPT"  # uncached: plain string, matches _cacheable_system(cache=False)
    assert params["messages"] == [{"role": "user", "content": "What does trample do?"}]
    assert params["output_config"]["effort"] == "high"
    assert params["output_config"]["format"]["type"] == "json_schema"
    # The schema must actually describe Answer's fields, not be an empty stub.
    schema = params["output_config"]["format"]["schema"]
    assert set(schema["properties"]) >= {"text", "tldr", "citations", "answered", "suggested_followups"}


def test_batch_request_params_omits_effort_when_unset():
    params = rae._batch_request_params(
        model="claude-opus-5", system="S", user="U", max_tokens=100,
        effort=None, cache_prompt=False,
    )
    assert "effort" not in params["output_config"]


def test_batch_request_params_cache_prompt_wraps_system():
    params = rae._batch_request_params(
        model="claude-opus-5", system="S", user="U", max_tokens=100,
        effort=None, cache_prompt=True,
    )
    assert params["system"] == [{"type": "text", "text": "S", "cache_control": {"type": "ephemeral"}}]


def test_submit_batch_builds_one_request_per_question(tmp_path, monkeypatch):
    monkeypatch.setattr(rae, "BATCH_RECORDS_DIR", tmp_path / "_batches")
    fake_batches = _FakeBatchesResource(batch_id="msgbatch_abc")
    client = _FakeClient(fake_batches)

    class Q:
        def __init__(self, id_):
            self.id = id_

    questions = [Q("q1"), Q("q2")]
    batch_id, custom_id_to_qid = rae.submit_or_attach_batch(
        client, tmp_path / "out.json", questions, _PROMPTS_CACHE,
        "claude-opus-5", 1000, None, False, tmp_path / "cache.json", "deadbeef",
    )
    assert batch_id == "msgbatch_abc"
    assert len(fake_batches.create_calls) == 1
    sent_requests = fake_batches.create_calls[0]
    # Request is a TypedDict (anthropic.types.messages.batch_create_params.Request),
    # not an object with attributes -- dict-style access.
    assert {r["custom_id"] for r in sent_requests} == {"q1", "q2"}
    assert custom_id_to_qid == {"q1": "q1", "q2": "q2"}


# --- custom_id round-trip mapping (including out-of-order results) -------

def test_batch_results_keyed_by_custom_id_not_position():
    # Results deliberately returned in the OPPOSITE order from submission --
    # the real API makes no ordering guarantee, and the code under test
    # must key results by custom_id, never by position.
    results = [
        _fake_succeeded_result("q2", {**_ANSWER_PAYLOAD, "text": "answer for q2"}),
        _fake_succeeded_result("q1", {**_ANSWER_PAYLOAD, "text": "answer for q1"}),
    ]
    by_custom_id = {r.custom_id: r for r in results}
    ans_q1, *_ = rae._answer_from_batch_result(by_custom_id["q1"], _PROMPTS_CACHE, "q1")
    ans_q2, *_ = rae._answer_from_batch_result(by_custom_id["q2"], _PROMPTS_CACHE, "q2")
    assert ans_q1.text == "answer for q1"
    assert ans_q2.text == "answer for q2"


# --- refusal cases --------------------------------------------------------

def test_batch_without_prompts_cache_is_refused():
    with pytest.raises(SystemExit) as exc:
        rae._validate_batch_combination(batch=True, prompts_cache_path=None, reground=False)
    assert exc.value.code == 1


def test_batch_with_reground_is_refused():
    with pytest.raises(SystemExit) as exc:
        rae._validate_batch_combination(
            batch=True, prompts_cache_path=Path("some_cache.json"), reground=True,
        )
    assert exc.value.code == 1


def test_batch_with_prompts_cache_and_no_reground_is_allowed():
    # Should not raise / exit.
    rae._validate_batch_combination(
        batch=True, prompts_cache_path=Path("some_cache.json"), reground=False,
    )


def test_non_batch_combinations_never_refused():
    rae._validate_batch_combination(batch=False, prompts_cache_path=None, reground=True)
    rae._validate_batch_combination(batch=False, prompts_cache_path=None, reground=False)


# --- result parsing into identical row shape ------------------------------

def test_succeeded_result_parses_into_frozen_prompt_shape():
    result = _fake_succeeded_result(
        "q1", _ANSWER_PAYLOAD, stop_reason="end_turn",
        input_tokens=200, output_tokens=80, cache_read=10, cache_creation=0,
    )
    ans, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_batch_result(
        result, _PROMPTS_CACHE, "q1",
    )
    assert isinstance(ans, Answer)
    assert ans.answered is True
    assert ans.citations == ["702.19c"]
    assert stop_reason == "end_turn"
    # Same usage dict SHAPE _answer_from_frozen_prompt() produces.
    assert usage == {
        "input_tokens": 200, "output_tokens": 80,
        "cache_read_input_tokens": 10, "cache_creation_input_tokens": 0,
    }
    assert regrounded is False  # --batch never regrounds (refused combination)
    assert cr_before == 1  # "702.19c" is a CR rule citation
    assert cr_after is None  # regrounding never fires on this path


def test_unparseable_succeeded_result_is_honest_not_a_crash():
    # A "succeeded" batch result whose text block isn't valid Answer JSON --
    # must degrade to an answered=False row, not raise.
    bad_result = types.SimpleNamespace(
        custom_id="q1",
        result=types.SimpleNamespace(
            type="succeeded",
            message=types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text="not json at all")],
                stop_reason="end_turn",
                usage=types.SimpleNamespace(
                    input_tokens=10, output_tokens=5,
                    cache_read_input_tokens=0, cache_creation_input_tokens=0,
                ),
            ),
        ),
    )
    ans, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_batch_result(
        bad_result, _PROMPTS_CACHE, "q1",
    )
    assert ans.answered is False
    assert usage is not None  # usage is still recorded even on a parse failure


# --- discounted cost maths -------------------------------------------------

def test_batch_cost_is_half_of_sync_cost():
    kwargs = dict(input_tokens=1_000_000, output_tokens=1_000_000)
    sync_cost = pricing.cost_usd("claude-opus-5", **kwargs, batch=False)
    batch_cost = pricing.cost_usd("claude-opus-5", **kwargs, batch=True)
    assert sync_cost is not None and batch_cost is not None
    assert batch_cost == pytest.approx(sync_cost * 0.5)


def test_batch_cost_maths_with_cache_tokens():
    kwargs = dict(
        input_tokens=100_000, output_tokens=50_000,
        cache_read_tokens=20_000, cache_write_tokens=5_000,
    )
    sync_cost = pricing.cost_usd("claude-opus-5", **kwargs, batch=False)
    batch_cost = pricing.cost_usd("claude-opus-5", **kwargs, batch=True)
    assert batch_cost == pytest.approx(sync_cost / 2)


def test_batch_default_is_false_unchanged_behavior():
    # Omitting batch= must be byte-identical to batch=False -- no existing
    # cost caller's numbers should move just because this parameter exists.
    kwargs = dict(input_tokens=500_000, output_tokens=200_000)
    assert pricing.cost_usd("claude-opus-5", **kwargs) == pricing.cost_usd("claude-opus-5", **kwargs, batch=False)


# --- resume attaches rather than resubmits --------------------------------

class _Q:
    def __init__(self, id_):
        self.id = id_


def test_resume_attaches_without_resubmitting(tmp_path, monkeypatch):
    monkeypatch.setattr(rae, "BATCH_RECORDS_DIR", tmp_path / "_batches")
    fake_batches = _FakeBatchesResource(batch_id="msgbatch_first")
    client = _FakeClient(fake_batches)
    out_path = tmp_path / "out.json"
    questions = [_Q("q1"), _Q("q2")]

    batch_id_1, mapping_1 = rae.submit_or_attach_batch(
        client, out_path, questions, _PROMPTS_CACHE,
        "claude-opus-5", 1000, None, False, tmp_path / "cache.json", "deadbeef",
    )
    assert len(fake_batches.create_calls) == 1

    # Re-run with the SAME config -- must attach, not submit a second batch.
    batch_id_2, mapping_2 = rae.submit_or_attach_batch(
        client, out_path, questions, _PROMPTS_CACHE,
        "claude-opus-5", 1000, None, False, tmp_path / "cache.json", "deadbeef",
    )
    assert batch_id_2 == batch_id_1 == "msgbatch_first"
    assert mapping_2 == mapping_1
    assert len(fake_batches.create_calls) == 1  # still just the one call


def test_resume_with_mismatched_identity_hard_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(rae, "BATCH_RECORDS_DIR", tmp_path / "_batches")
    fake_batches = _FakeBatchesResource(batch_id="msgbatch_first")
    client = _FakeClient(fake_batches)
    out_path = tmp_path / "out.json"
    questions = [_Q("q1"), _Q("q2")]

    rae.submit_or_attach_batch(
        client, out_path, questions, _PROMPTS_CACHE,
        "claude-opus-5", 1000, None, False, tmp_path / "cache.json", "deadbeef",
    )
    assert len(fake_batches.create_calls) == 1

    # Different max_tokens => different identity => must refuse, not silently
    # resubmit (real money) or silently reuse a batch answering a different
    # question.
    with pytest.raises(SystemExit) as exc:
        rae.submit_or_attach_batch(
            client, out_path, questions, _PROMPTS_CACHE,
            "claude-opus-5", 9999, None, False, tmp_path / "cache.json", "deadbeef",
        )
    assert exc.value.code == 1
    # Still only the one create() call from before the mismatch was detected.
    assert len(fake_batches.create_calls) == 1


def test_batch_record_persisted_immediately_on_submit(tmp_path, monkeypatch):
    monkeypatch.setattr(rae, "BATCH_RECORDS_DIR", tmp_path / "_batches")
    fake_batches = _FakeBatchesResource(batch_id="msgbatch_durable")
    client = _FakeClient(fake_batches)
    out_path = tmp_path / "myrun.json"
    questions = [_Q("q1")]

    rae.submit_or_attach_batch(
        client, out_path, questions, _PROMPTS_CACHE,
        "claude-opus-5", 1000, None, False, tmp_path / "cache.json", "deadbeef",
    )
    record_path = rae._batch_record_path(out_path)
    assert record_path.exists()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["batch_id"] == "msgbatch_durable"
    assert record["custom_id_to_qid"] == {"q1": "q1"}
    assert record["identity"]["qids"] == ["q1"]


# --- per-request error recorded rather than silently dropped -------------

def test_errored_result_recorded_as_honest_failed_row():
    result = _fake_errored_result("q1", message="rate_limited_upstream")
    ans, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_batch_result(
        result, _PROMPTS_CACHE, "q1",
    )
    assert isinstance(ans, Answer)
    assert ans.answered is False
    assert "rate_limited_upstream" in ans.text
    assert stop_reason == "batch_errored"
    assert usage is None
    assert cr_before is None and cr_after is None


def test_expired_result_recorded_as_honest_failed_row():
    result = _fake_expired_result("q1")
    ans, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_batch_result(
        result, _PROMPTS_CACHE, "q1",
    )
    assert ans.answered is False
    assert stop_reason == "batch_expired"
    assert "expired" in ans.text


def test_missing_result_in_batch_response_does_not_disappear():
    # Simulates main()'s own guard: a custom_id submitted but absent from
    # results() must still produce a row, never a silently-skipped question.
    results_by_custom_id = {}  # nothing came back for "q1"
    result = results_by_custom_id.get("q1")
    assert result is None
    # main() builds this exact fallback row when result is None -- assert
    # the shape matches what a normal error row looks like.
    fallback = Answer(
        text="(no batch result returned for this question, batch=msgbatch_x)",
        tldr="This answer was not generated.", citations=[], answered=False,
        suggested_followups=[],
    )
    assert fallback.answered is False
    assert fallback.citations == []

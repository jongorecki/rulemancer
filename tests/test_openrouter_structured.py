"""Tests for the generic structured-output primitive in openrouter_backend.py
(build_strict_schema / call_structured), added so the rewrite arm can route
openai/gpt-5-mini through OpenRouter with the same strict-schema shaping and
HTTP retry discipline generate()/_attempt() already use for Answer, without
duplicating either (docs/plan for the gpt5mini rewriter arm).

No live HTTP -- httpx.post is patched, same pattern as
test_openrouter_reasoning.py / test_openrouter_malformed_json.py.
"""

import json
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from rulesagent.generate import openrouter_backend as orb


class _Sample(BaseModel):
    queries: list[str]
    clarification: str | None = None


def _dumps(d: dict) -> str:
    """json.dumps via the module-level `json` import -- needed because the
    fake_post() helpers below shadow the name `json` with their own kwarg."""
    return json.dumps(d)


def _ok_response(content: str):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "model": "openai/gpt-5-mini",
        "provider": "OpenAI",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        "choices": [{"message": {"content": content}}],
    }
    return resp


# --- build_strict_schema -----------------------------------------------------

def test_build_strict_schema_strips_title_sets_additional_properties_false():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    assert "title" not in schema
    assert schema["additionalProperties"] is False


def test_build_strict_schema_required_matches_all_properties():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    assert set(schema["required"]) == set(schema["properties"].keys())


def test_build_strict_schema_strips_nested_property_titles():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    for prop in schema["properties"].values():
        assert "title" not in prop


def test_answer_schema_uses_build_strict_schema():
    """_answer_schema() (used by generate()/_attempt(), untouched behavior)
    must now be a thin wrapper over the same shared helper the rewrite arm
    uses, not a second copy of the strict-schema logic."""
    from rulesagent.contracts import Answer
    assert orb._answer_schema() == orb.build_strict_schema(Answer.model_json_schema())


# --- call_structured ----------------------------------------------------------

def test_call_structured_returns_parsed_json_on_success():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    payload = {"queries": ["a rewrite"], "clarification": None}

    def fake_post(url, json=None, timeout=None, headers=None):
        return _ok_response(_dumps(payload))

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        result = orb.call_structured("SYS", "USER", "openai/gpt-5-mini", schema)

    assert result == payload


def test_call_structured_no_api_key_returns_none():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    with patch.dict("os.environ", {}, clear=True):
        result = orb.call_structured("SYS", "USER", "openai/gpt-5-mini", schema)
    assert result is None


def test_call_structured_omits_temperature_for_no_temperature_model():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _ok_response('{"queries": ["x"], "clarification": null}')

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        orb.call_structured("SYS", "USER", "openai/gpt-5-mini", schema)

    assert "openai/gpt-5-mini" in orb.NO_TEMPERATURE
    assert "temperature" not in captured["body"]


def test_call_structured_sends_temperature_zero_for_other_models():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _ok_response('{"queries": ["x"], "clarification": null}')

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        orb.call_structured("SYS", "USER", "some/other-model", schema)

    assert captured["body"]["temperature"] == 0.0


def test_call_structured_uses_strict_json_schema_response_format():
    schema = orb.build_strict_schema(_Sample.model_json_schema())
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["body"] = json
        return _ok_response('{"queries": ["x"], "clarification": null}')

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        orb.call_structured("SYS", "USER", "openai/gpt-5-mini", schema, schema_name="rewrites")

    rf = captured["body"]["response_format"]
    assert rf == {
        "type": "json_schema",
        "json_schema": {"name": "rewrites", "strict": True, "schema": schema},
    }


def test_call_structured_returns_none_on_malformed_content():
    schema = orb.build_strict_schema(_Sample.model_json_schema())

    def fake_post(url, json=None, timeout=None, headers=None):
        return _ok_response("not valid json")

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        result = orb.call_structured("SYS", "USER", "openai/gpt-5-mini", schema)

    assert result is None


def test_call_structured_returns_none_on_openrouter_error_body():
    schema = orb.build_strict_schema(_Sample.model_json_schema())

    def fake_post(url, json=None, timeout=None, headers=None):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"error": {"message": "boom"}}
        return resp

    with patch.object(orb.httpx, "post", side_effect=fake_post), \
         patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-key"}):
        result = orb.call_structured("SYS", "USER", "openai/gpt-5-mini", schema)

    assert result is None

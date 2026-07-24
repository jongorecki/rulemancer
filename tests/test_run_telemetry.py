"""Per-row run telemetry (docs/spec-slice0-harness.md Task 3): stop_reason,
tool_calls, tool_rounds, usage, system_version, layers_tool on every row
evals/run_answer_eval.py writes.

End-to-end via a scripted fake Anthropic client, same pattern as
tests/test_retrieved_rule_ids.py (VectorStore/parse_comprehensive_rules/
chunk_rules faked -- no real data assets needed for the non-cache tests) and
tests/test_resume_prompts_cache_guard.py (the --prompts-cache tests rely on
the real repo CR text + vector store already present on master, same as
that file does).
"""
import json
from pathlib import Path
from unittest.mock import patch

from evals import run_answer_eval as rae
from rulesagent.contracts import Answer

import progress  # noqa: E402 -- see tests/test_retrieved_rule_ids.py's import comment


class _FrozenStore:
    chunks: list = []

    def search(self, query, k):
        return []


class _FakeVectorStore:
    @staticmethod
    def load(path):
        return _FrozenStore()


class _FakeUsage:
    def __init__(self, input_tokens=100, output_tokens=50,
                 cache_read_input_tokens=0, cache_creation_input_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read_input_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens


class _FakeToolUseBlock:
    def __init__(self, id_, name, input_):
        self.type = "tool_use"
        self.id = id_
        self.name = name
        self.input = input_


class _FakeResp:
    def __init__(self, parsed_output=None, stop_reason="end_turn", content=None, usage=None):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason
        self.content = content or []
        self.usage = usage if usage is not None else _FakeUsage()


_REAL_ANSWER = Answer(
    text="Trample interacts with deathtouch per 702.19e.",
    tldr="t", citations=["702.19e"], answered=True, suggested_followups=[],
)

_EXPECTED_USAGE = {
    "input_tokens": 100, "output_tokens": 50,
    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
}


class _ScriptedMessages:
    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._script.pop(0)


def _make_fake_client_class(script):
    class _Client:
        def __init__(self, *a, **kw):
            self.messages = _ScriptedMessages(script)

    return _Client


def _write_questions(path: Path, ids: list[str]) -> None:
    path.write_text("\n".join(
        json.dumps({"id": i, "question": f"Question text for {i}?", "gold": []})
        for i in ids
    ), encoding="utf-8")


def _write_cache(path: Path, ids: list[str], system_text: str) -> None:
    path.write_text(json.dumps({
        "rewrite_version": "v2", "ruling_query_mode": "raw", "n_questions": len(ids),
        "prompts": {i: {"system": system_text, "user": f"USER-{i}"} for i in ids},
    }), encoding="utf-8")


def _fake_parsed_dir(tmp_path: Path) -> Path:
    d = tmp_path / "parsed"
    d.mkdir()
    (d / f"vector_{rae.VECTOR_MODEL}.pkl").write_bytes(b"")
    return d


# --- Ordinary agent.answer() path: one uneventful round --------------------


def test_row_carries_stop_reason_tool_rounds_usage_and_provenance(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001"])
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    argv = [
        "run_answer_eval.py", "--model", "fake-model",
        "--questions", str(questions), "--out", str(out),
        "--no-rewrite", "--system-version", "v4nl", "--no-layers-tool",
    ]
    client_cls = _make_fake_client_class([_FakeResp(parsed_output=_REAL_ANSWER)])
    with patch("sys.argv", argv), \
         patch.object(rae, "PARSED_DIR", parsed_dir), \
         patch.object(rae, "VectorStore", _FakeVectorStore), \
         patch.object(rae, "parse_comprehensive_rules", return_value=([], [])), \
         patch.object(rae, "chunk_rules", return_value=[]), \
         patch("anthropic.Anthropic", client_cls), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"):
        rae.main()

    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert row["stop_reason"] == "end_turn"
    assert row["tool_calls"] is None  # no tool ever attached this call
    assert row["tool_rounds"] == 1  # one uneventful round through the loop
    assert row["usage"] == _EXPECTED_USAGE
    assert row["system_version"] == "v4nl"
    assert row["layers_tool"] is False


def test_layers_tool_defaults_true_and_system_version_defaults_to_production(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001"])
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    argv = [
        "run_answer_eval.py", "--model", "fake-model",
        "--questions", str(questions), "--out", str(out), "--no-rewrite",
    ]
    client_cls = _make_fake_client_class([_FakeResp(parsed_output=_REAL_ANSWER)])
    with patch("sys.argv", argv), \
         patch.object(rae, "PARSED_DIR", parsed_dir), \
         patch.object(rae, "VectorStore", _FakeVectorStore), \
         patch.object(rae, "parse_comprehensive_rules", return_value=([], [])), \
         patch.object(rae, "chunk_rules", return_value=[]), \
         patch("anthropic.Anthropic", client_cls), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"):
        rae.main()

    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert row["layers_tool"] is True
    from rulesagent.generate.answer import PROMPT_VERSION
    assert row["system_version"] == PROMPT_VERSION


# --- Tool round trip: multiple rounds + a real tool_calls entry ------------


def test_row_records_multiple_tool_rounds_and_tool_calls_on_cost_trigger(tmp_path):
    questions = tmp_path / "q.jsonl"
    trigger_q = ("A spell that costs {X}{G}{G} gets its cost reduced -- it costs "
                 "{1} less. If I cast it with X=2, what does it cost?")
    questions.write_text(
        json.dumps({"id": "c014", "question": trigger_q, "gold": []}), encoding="utf-8",
    )
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    tool_input = {
        "base_cost": {"generic": 0, "colored": {"G": 2}, "x_coefficient": 1},
        "modifiers": [{"kind": "reduction", "amount": 1, "cite": "test"}],
        "x_values": [2],
    }
    tool_block = _FakeToolUseBlock("toolu_1", "calculate_cost", tool_input)
    script = [
        _FakeResp(content=[tool_block], stop_reason="tool_use", parsed_output=None),
        _FakeResp(parsed_output=_REAL_ANSWER, stop_reason="end_turn"),
    ]
    argv = [
        "run_answer_eval.py", "--model", "fake-model",
        "--questions", str(questions), "--out", str(out), "--no-rewrite",
    ]
    client_cls = _make_fake_client_class(script)
    with patch("sys.argv", argv), \
         patch.object(rae, "PARSED_DIR", parsed_dir), \
         patch.object(rae, "VectorStore", _FakeVectorStore), \
         patch.object(rae, "parse_comprehensive_rules", return_value=([], [])), \
         patch.object(rae, "chunk_rules", return_value=[]), \
         patch("anthropic.Anthropic", client_cls), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"):
        rae.main()

    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert row["tool_rounds"] == 2
    assert row["stop_reason"] == "end_turn"
    assert row["tool_calls"] is not None
    assert len(row["tool_calls"]) == 1
    assert row["tool_calls"][0]["name"] == "calculate_cost"
    assert row["tool_calls"][0]["input"] == tool_input
    assert row["tool_calls"][0]["result"]["ok"] is True


# --- Frozen-prompt path (--prompts-cache): no tool loop at all -------------


def test_frozen_prompt_row_has_tool_rounds_none_but_real_stop_reason_and_usage(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001"])
    cache = tmp_path / "cache.json"
    _write_cache(cache, ["q001"], "SYSTEM")
    out = tmp_path / "out.json"

    argv = [
        "run_answer_eval.py", "--model", "fake/model",
        "--questions", str(questions),
        "--prompts-cache", str(cache), "--out", str(out),
        "--rewrite-version", "v2", "--ruling-query-mode", "raw",
    ]
    client_cls = _make_fake_client_class([_FakeResp(parsed_output=_REAL_ANSWER)])
    with patch("sys.argv", argv), patch("anthropic.Anthropic", client_cls):
        rae.main()

    row = json.loads(out.read_text(encoding="utf-8"))[0]
    # The absence is real and load-bearing (spec Task 3): _answer_from_frozen_
    # prompt() has no tool loop at all, so this must never be a fabricated 0
    # or 1 -- it must be None, distinguishable from "one real round".
    assert row["tool_rounds"] is None
    assert row["tool_calls"] is None
    assert row["stop_reason"] == "end_turn"
    assert row["usage"] == _EXPECTED_USAGE

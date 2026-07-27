"""retrieved_rule_ids schema-addition guard (miss-partition diagnostic gap).

Both eval runners now stamp each output row with `retrieved_rule_ids`: the
ordered list of `source_id`s the retriever actually returned for that
question, in rank order. Without this, a graded run can't be diagnosed after
the fact ("was the gold rule even in the context?") unless a --prompts-cache
capture happens to survive.

No live HTTP/Anthropic/OpenRouter calls anywhere in this file -- the
Anthropic client and openrouter_backend.generate() are both faked, same
pattern as tests/test_resume_prompts_cache_guard.py. Retrieval itself is
faked with a `_FrozenStore` (tests/test_prompt_identity.py's pattern): a
store double whose .search() always returns a fixed, hand-built ranked list
regardless of the query, so the "rank order" assertion is against a KNOWN
order, not whatever a real embedding happens to produce.

Both runners' Heartbeat side file (evals/answers/_progress/<run>.json) is
redirected into tmp_path -- evals/answers/ is gitignored/absent in a clean
worktree per the task header, and even where present this avoids leaving
stray files behind from a test run.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evals import run_answer_eval as rae
from evals import run_openrouter_arm as roa
from rulesagent.contracts import Answer, Chunk, Retrieved
from rulesagent.generate import openrouter_backend as orb

# Same trick run_answer_eval.py/run_openrouter_arm.py use to resolve
# `progress`/`qidfilter`/`run_eval` as top-level modules regardless of cwd:
# importing `evals.run_answer_eval` above already ran their
# `sys.path.insert(0, str(Path(__file__).parent))`, so `progress` now
# resolves to the SAME module object those runners hold a `Heartbeat`
# reference into (as opposed to `evals.progress`, a different sys.modules
# entry that would leave their internal PROGRESS_DIR unpatched).
import progress  # noqa: E402


# Fixed, hand-built ranked retrieval -- deliberately NOT sorted by score, so
# "rank order" in the assertions below means "the order the store returned
# them in", not "sorted by score" (they happen to agree here, but the row
# must preserve LIST order, not re-derive it from `score`).
_RETRIEVED = [
    Retrieved(
        chunk=Chunk(source_id="100.1", kind="rule", section="Game Concepts",
                    text="Test rule one text.", embed_text="Test rule one text."),
        score=0.91,
    ),
    Retrieved(
        chunk=Chunk(source_id="205.3a", kind="rule", section="Card Types",
                    text="Test rule two text.", embed_text="Test rule two text."),
        score=0.77,
    ),
    Retrieved(
        chunk=Chunk(source_id="Flying", kind="glossary", section="Glossary",
                    text="Test glossary entry text.", embed_text="Test glossary entry text."),
        score=0.55,
    ),
]
_EXPECTED_IDS = ["100.1", "205.3a", "Flying"]


class _FrozenStore:
    """tests/test_prompt_identity.py's pattern: .search() ignores the query
    and always returns the same fixed, pre-ranked list -- so retrieval order
    is a known quantity the test can assert against, not something a live
    embedding call would make flaky."""

    chunks: list = []  # no real chunks -> RulesAgent.chunk_map is {} (cross-ref
    # expansion degrades to a no-op per its own getattr-guard docstring)

    def search(self, query, k):
        return _RETRIEVED[:k]


class _FakeVectorStore:
    """Stands in for rulesagent.index.store.VectorStore in each runner's own
    module namespace -- .load() ignores the path (no real pkl needed) and
    hands back the frozen store above."""

    @staticmethod
    def load(path):
        return _FrozenStore()


def _fake_anthropic_answer(user_content: str) -> Answer:
    return Answer(text=f"answer for: {user_content[:20]}", tldr="t",
                  citations=[], answered=True, suggested_followups=[])


class _FakeMessages:
    def parse(self, model, max_tokens, system, messages, output_format):
        class _Resp:
            def __init__(self, parsed):
                self.parsed_output = parsed
                self.stop_reason = "end_turn"

        return _Resp(_fake_anthropic_answer(messages[0]["content"]))


class _FakeAnthropicClient:
    def __init__(self, *a, **kw):
        self.messages = _FakeMessages()


def _fake_or_result(system, user, model, reasoning=None):
    return orb.ORResult(
        answer=Answer(text=f"or-answer: {user[:20]}", tldr="t", citations=[],
                      answered=True, suggested_followups=[]),
        requested_model=model, served_model=model, provider="Fake",
        temperature_sent=0.0, seed_sent=orb.SEED,
        usage={"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001},
    )


def _write_questions(path: Path, ids: list[str]) -> None:
    path.write_text("\n".join(
        json.dumps({"id": i, "question": f"Question text for {i}?", "gold": []})
        for i in ids
    ), encoding="utf-8")


def _fake_parsed_dir(tmp_path: Path) -> Path:
    """A directory holding an (empty, never actually read since VectorStore
    is faked) vector_<VECTOR_MODEL>.pkl -- only its EXISTENCE is checked by
    main() before VectorStore.load() is called."""
    d = tmp_path / "parsed"
    d.mkdir()
    (d / f"vector_{rae.VECTOR_MODEL}.pkl").write_bytes(b"")
    return d


# ---------------------------------------------------------------------------
# run_answer_eval.py (the sonnet/Anthropic arm)
# ---------------------------------------------------------------------------

def test_run_answer_eval_row_carries_retrieved_rule_ids_in_rank_order(tmp_path):
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001", "q002"])
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    argv = [
        "run_answer_eval.py", "--model", "fake-model",
        "--questions", str(questions), "--out", str(out),
        "--no-rewrite",  # skip rewrite_query entirely -- no live call needed
    ]
    with patch("sys.argv", argv), \
         patch.object(rae, "PARSED_DIR", parsed_dir), \
         patch.object(rae, "VectorStore", _FakeVectorStore), \
         patch.object(rae, "parse_comprehensive_rules", return_value=([], [])), \
         patch.object(rae, "chunk_rules", return_value=[]), \
         patch("anthropic.Anthropic", _FakeAnthropicClient), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"):
        rae.main()

    rows = json.loads(out.read_text(encoding="utf-8"))
    assert len(rows) == 2
    for row in rows:
        assert row["retrieved_rule_ids"] == _EXPECTED_IDS
        assert all(isinstance(x, str) for x in row["retrieved_rule_ids"])


def test_run_answer_eval_schema_additive(tmp_path):
    """Every field this schema had before retrieved_rule_ids existed is still
    present, unchanged. Hardcoded against the pre-existing row shape (docs/
    HANDOFF-development.md: run output files feed build_arm_review.py /
    judge_*.py / opus_grader_calibration.py by known key -- removing or
    renaming one breaks them; adding one does not)."""
    questions = tmp_path / "q.jsonl"
    _write_questions(questions, ["q001"])
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    argv = [
        "run_answer_eval.py", "--model", "fake-model",
        "--questions", str(questions), "--out", str(out),
        "--no-rewrite",
    ]
    with patch("sys.argv", argv), \
         patch.object(rae, "PARSED_DIR", parsed_dir), \
         patch.object(rae, "VectorStore", _FakeVectorStore), \
         patch.object(rae, "parse_comprehensive_rules", return_value=([], [])), \
         patch.object(rae, "chunk_rules", return_value=[]), \
         patch("anthropic.Anthropic", _FakeAnthropicClient), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"):
        rae.main()

    row = json.loads(out.read_text(encoding="utf-8"))[0]

    pre_existing_keys = {
        "id", "question", "match", "kind", "show_rewrite", "rewrite_version",
        "ruling_query_mode", "condition", "run", "model", "prompts_cache",
        "prompts_cache_sha256", "answered", "answer", "citations", "gold",
        "gold_text", "cited_text", "rewrite_queries", "clarification",
    }
    # retrieved_rule_ids (miss-partition diagnostic) plus the Slice 0 harness
    # telemetry fields (docs/spec-slice0-harness.md Task 3): stop_reason,
    # tool_calls, tool_rounds, usage, system_version, layers_tool.
    new_keys = {
        "retrieved_rule_ids", "stop_reason", "tool_calls", "tool_rounds",
        "usage", "system_version", "layers_tool", "max_tokens",
        # effort (docs/spec-effort-and-norewrite.md Task 1): additive, and null
        # on every run that doesn't pass --effort. Recorded because the resume
        # guard compares it -- an effort arm and a default-effort arm are
        # different experiments, exactly like max_tokens.
        "effort",
        # prompt_supplied_rule_ids (coverage-metric measurement-bug fix):
        # ids that reached the model outside retrieval this run, via the
        # system prompt/tool schemas -- see
        # rulesagent.generate.answer.prompt_supplied_rule_ids(). Additive,
        # derived from system_version/layers_tool, always a list (possibly
        # empty), never absent.
        "prompt_supplied_rule_ids",
        # Groundedness-guard fields (docs/results-groundedness-guard.md,
        # tests/test_groundedness_guard.py): "reground" is this run's
        # --reground flag (constant per file); "regrounded" is whether the
        # re-ask actually fired for this row; cr_citations_before/after are
        # cr_rule_citations() counts pre-/post-reground. Additive, always
        # present (never absent), null-able only on cr_citations_after.
        "reground", "regrounded", "cr_citations_before", "cr_citations_after",
        # Citation-source classifier (docs/results-groundedness-guard.md,
        # tests/test_grounding_sources.py): "cites_cr_rule" is the per-row
        # bool; "citation_sources" is the full breakdown (per-citation
        # labels, the four counts, and the mutually-exclusive category).
        # Additive, always present.
        "cites_cr_rule", "citation_sources",
        # Batch API support (Anthropic Message Batches, --batch flag): whether
        # this row was generated via the batch endpoint (50% of sync price) --
        # added concurrently with the citation-source fields above. Additive,
        # always present.
        "batch",
    }
    assert pre_existing_keys <= row.keys()
    assert row.keys() - pre_existing_keys == new_keys
    # Spot-check a few pre-existing values are exactly what this config
    # produces -- not just that the keys survived.
    assert row["id"] == "q001"
    assert row["model"] == "fake-model"
    assert row["rewrite_queries"] == []  # --no-rewrite -> last_rewritten is None
    assert row["citations"] == []
    assert row["answered"] is True


# ---------------------------------------------------------------------------
# run_openrouter_arm.py (the OpenRouter arm)
# ---------------------------------------------------------------------------

def test_run_openrouter_arm_row_carries_retrieved_rule_ids_in_rank_order(tmp_path):
    questions = tmp_path / "q.jsonl"
    empty_cards = tmp_path / "cards.jsonl"
    _write_questions(questions, ["q001", "q002"])
    empty_cards.write_text("", encoding="utf-8")
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    argv = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--out", str(out),
    ]
    with patch("sys.argv", argv), \
         patch.object(roa, "PARSED_DIR", parsed_dir), \
         patch.object(roa, "VectorStore", _FakeVectorStore), \
         patch.object(orb, "generate", side_effect=_fake_or_result), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"), \
         patch("rulesagent.generate.answer.rewrite_query",
               side_effect=lambda question, *a, **kw: _FakeRewritten(question)):
        roa.main()

    data = json.loads(out.read_text(encoding="utf-8"))
    rows = data["results"]
    assert len(rows) == 2
    for row in rows:
        assert row["retrieved_rule_ids"] == _EXPECTED_IDS
        assert all(isinstance(x, str) for x in row["retrieved_rule_ids"])


def test_run_openrouter_arm_schema_additive(tmp_path):
    questions = tmp_path / "q.jsonl"
    empty_cards = tmp_path / "cards.jsonl"
    _write_questions(questions, ["q001"])
    empty_cards.write_text("", encoding="utf-8")
    out = tmp_path / "out.json"
    parsed_dir = _fake_parsed_dir(tmp_path)

    argv = [
        "run_openrouter_arm.py", "--model", "fake/model",
        "--questions", str(questions), "--cards", str(empty_cards),
        "--out", str(out),
    ]
    with patch("sys.argv", argv), \
         patch.object(roa, "PARSED_DIR", parsed_dir), \
         patch.object(roa, "VectorStore", _FakeVectorStore), \
         patch.object(orb, "generate", side_effect=_fake_or_result), \
         patch.object(progress, "PROGRESS_DIR", tmp_path / "progress"), \
         patch("rulesagent.generate.answer.rewrite_query",
               side_effect=lambda question, *a, **kw: _FakeRewritten(question)):
        roa.main()

    data = json.loads(out.read_text(encoding="utf-8"))
    row = data["results"][0]

    pre_existing_keys = {
        "id", "question", "served_model", "provider", "temperature_sent",
        "seed_sent", "usage", "answered", "text", "citations", "error",
        "raw_text",
    }
    assert pre_existing_keys <= row.keys()
    assert row.keys() - pre_existing_keys == {"retrieved_rule_ids"}
    assert row["id"] == "q001"
    assert row["served_model"] == "fake/model"
    assert row["error"] is None
    assert row["answered"] is True

    # The top-level payload shape (model/rewrite_version/.../summary) is
    # untouched too -- this feature only adds a per-row field.
    assert set(data.keys()) == {
        "model", "rewrite_version", "ruling_query_mode", "condition", "run",
        "reasoning", "prompts_cache", "results", "summary", "variance",
    }


class _FakeRewritten:
    """rulesagent.contracts.RewrittenQuery stand-in: queries=[question] so
    RulesAgent's single-query path (`if len(rewritten.queries) == 1`) calls
    store.search() directly, once, with no rrf_fuse involved -- keeping the
    retrieval order asserted above exactly _FrozenStore's own list order."""

    def __init__(self, question):
        self.original = question
        self.queries = [question]
        self.clarification = None

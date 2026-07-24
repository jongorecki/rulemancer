"""Regression test for the empty-rewrite-query crash: gpt5mini emitted an empty
query on rg5193, and Voyage's embed rejects empty strings, aborting the whole
retrieval eval. `_clean_queries` drops empties with an original-question
fallback. See run_eval.py's helper docstring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from run_eval import _clean_queries  # noqa: E402


def test_drops_empty_and_whitespace_queries():
    assert _clean_queries(["priority", "", "  ", "the stack"], "orig") == ["priority", "the stack"]


def test_falls_back_to_original_when_all_empty():
    # the exact shape that crashed the pass: a rewrite whose only surviving
    # content is empty -> must not yield an empty list (embed would reject it)
    assert _clean_queries(["", "   "], "who has priority?") == ["who has priority?"]


def test_leaves_clean_queries_untouched():
    assert _clean_queries(["a", "b"], "orig") == ["a", "b"]


def test_single_empty_falls_back():
    assert _clean_queries([""], "orig") == ["orig"]


def test_order_preserved():
    assert _clean_queries(["z", "", "a", "m"], "orig") == ["z", "a", "m"]

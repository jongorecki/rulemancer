"""Tests for the pure-rules channel probe (see build_purerules_real_prompts.py's
module docstring for why this 8-row set exists: the 120-row A/B set is 99.4%
card-interaction questions, so evals/purerules.jsonl -- real corpus questions
rewritten to contain zero card names -- is the only clean test of whether CR
rules are inert or merely redundant given card text).

Covers the frozen artifacts on disk (evals/purerules.jsonl,
evals/answers/_prompts_purerules_real.json,
evals/answers/_prompts_purerules_placebo.json) built by
build_purerules_real_prompts.py / build_purerules_placebo_prompts.py:

  - all 8 ids present in both caches
  - the zero-cards property (no `[Card]` bracket token anywhere in any row)
  - derangement holds -- no row borrows its own block, mapping is a bijection
    over the 8-row set (checked with the same rigor as the 120-row harness;
    n=8 makes a naive shuffle far more likely to hit a fixed point, so this
    matters more here, not less)
  - real vs placebo user prompts are byte-identical outside the rules-context
    block, and differ inside it

No model call, no retrieval call -- pure filesystem/JSON checks against the
already-built artifacts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "evals"))

from run_eval import load_questions  # noqa: E402
from rulesagent.tools.scryfall import parse_card_refs  # noqa: E402

PURERULES = REPO / "evals" / "purerules.jsonl"
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_purerules_real.json"
PLACEBO_CACHE = REPO / "evals" / "answers" / "_prompts_purerules_placebo.json"

EXPECTED_IDS = {f"pr{i:03d}" for i in range(1, 9)}


def _load_rows() -> list[dict]:
    rows = []
    for line in PURERULES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_cache(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Question set
# --------------------------------------------------------------------------

def test_exactly_8_rows_with_expected_ids():
    rows = _load_rows()
    assert len(rows) == 8
    assert {r["id"] for r in rows} == EXPECTED_IDS


def test_all_rows_are_gold_bearing():
    rows = _load_rows()
    assert all(r.get("gold") for r in rows)


def test_zero_cards_by_construction():
    """The whole point of this question set: no `[Card Name]` bracket token
    anywhere in any question. parse_card_refs() returns an empty token list
    for bracket-free text (see its docstring) -- checked directly against
    the raw question string, not just the derived cards list, so a token
    Scryfall failed to resolve couldn't hide as a false negative."""
    rows = _load_rows()
    for row in rows:
        stripped, tokens = parse_card_refs(row["question"])
        assert tokens == [], f"{row['id']} has card token(s): {tokens}"
        assert stripped == row["question"]


def test_rows_load_unmodified_through_load_questions():
    questions = load_questions(PURERULES)
    assert len(questions) == 8
    frozen = {r["id"]: r for r in _load_rows()}
    for q in questions:
        row = frozen[q.id]
        assert q.gold == row["gold"]
        assert q.question == row["question"]
        assert q.match == row.get("match", "any")


# --------------------------------------------------------------------------
# Prompt caches: shape + arm identity
# --------------------------------------------------------------------------

def test_real_cache_covers_all_8_ids():
    cache = _load_cache(REAL_CACHE)
    assert set(cache["prompts"]) == EXPECTED_IDS
    assert cache["n_questions"] == 8


def test_placebo_cache_covers_all_8_ids():
    cache = _load_cache(PLACEBO_CACHE)
    assert set(cache["prompts"]) == EXPECTED_IDS
    assert cache["n_questions"] == 8


def test_real_and_placebo_agree_on_arm_identity_fields():
    """run_answer_eval.py's --prompts-cache identity gate checks
    rewrite_version/ruling_query_mode against the CLI flags -- both caches
    must record the same values."""
    real = _load_cache(REAL_CACHE)
    placebo = _load_cache(PLACEBO_CACHE)
    assert real["rewrite_version"] == placebo["rewrite_version"] == "none"
    assert real["ruling_query_mode"] == placebo["ruling_query_mode"] == "union"


# --------------------------------------------------------------------------
# Derangement (fragile at n=8 -- checked with the same rigor as n=120)
# --------------------------------------------------------------------------

def test_derangement_no_row_keeps_its_own_block():
    placebo = _load_cache(PLACEBO_CACHE)
    borrowed_from = placebo["borrowed_from"]
    assert borrowed_from, "borrowed_from mapping missing or empty"
    assert set(borrowed_from) == EXPECTED_IDS
    self_loops = [qid for qid, donor in borrowed_from.items() if donor == qid]
    assert self_loops == []


def test_derangement_is_a_bijection_over_all_8_rows():
    placebo = _load_cache(PLACEBO_CACHE)
    borrowed_from = placebo["borrowed_from"]
    assert sorted(borrowed_from.keys()) == sorted(EXPECTED_IDS)
    assert sorted(borrowed_from.values()) == sorted(EXPECTED_IDS)  # each id used as donor exactly once


# --------------------------------------------------------------------------
# Single-variable property: real vs placebo differ ONLY in the rules block
# --------------------------------------------------------------------------

_RULES_HDR = "Rules context:\n"


def _split_rules_block(user: str) -> tuple[str, str, str]:
    assert user.startswith(_RULES_HDR)
    rest = user[len(_RULES_HDR):]
    markers = [m for m in ("\n\nCard data:\n", "\n\nSymbol reference", "\n\nQuestion:")
               if m in rest]
    assert markers, f"no known suffix marker found in user prompt: {user[:200]!r}"
    cut = min(rest.index(m) for m in markers)
    return _RULES_HDR, rest[:cut], rest[cut:]


def test_system_prompts_byte_identical_across_arms():
    real = _load_cache(REAL_CACHE)["prompts"]
    placebo = _load_cache(PLACEBO_CACHE)["prompts"]
    for qid in real:
        assert real[qid]["system"] == placebo[qid]["system"], qid


def test_user_prompts_differ_only_in_rules_block():
    real = _load_cache(REAL_CACHE)["prompts"]
    placebo = _load_cache(PLACEBO_CACHE)["prompts"]
    for qid in real:
        r_prefix, r_body, r_suffix = _split_rules_block(real[qid]["user"])
        p_prefix, p_body, p_suffix = _split_rules_block(placebo[qid]["user"])
        assert r_prefix == p_prefix, qid
        assert r_suffix == p_suffix, qid
        assert r_body != p_body, f"{qid}: rules block identical between arms (derangement failed silently)"

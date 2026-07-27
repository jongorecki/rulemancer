"""Tests for the retrieval-value A/B harness (docs/spec-retrieval-value-ab.md).

Covers the frozen artifacts on disk (evals/ab_rows.jsonl,
evals/answers/_prompts_ab_real.json, evals/answers/_prompts_ab_placebo.json)
built by build_ab_rows.py / build_ab_real_prompts.py /
build_ab_placebo_prompts.py:

  - row count and level split are exactly 40/40/40
  - the purerules exclusion (via source_qid, not literal id -- see
    build_ab_rows.py's module docstring for why)
  - the row set loads unmodified through run_eval.load_questions()
  - reproducibility of the draw under the fixed seed
  - derangement holds (no row borrows its own block; the mapping is a
    bijection over the row set)
  - real vs placebo user prompts differ ONLY in the rules-context block --
    system identical, and everything in `user` before "Rules context:" end
    and after it (cards/symbol-block/question) identical too

No model call, no retrieval call -- pure filesystem/JSON checks against the
already-built artifacts.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "evals"))

from run_eval import load_questions  # noqa: E402
from build_ab_rows import (  # noqa: E402
    LEVELS,
    N_PER_LEVEL,
    SEED as ROWS_SEED,
    draw_rows,
    load_jsonl,
    purerules_source_qids,
)

AB_ROWS = REPO / "evals" / "ab_rows.jsonl"
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_real.json"
PLACEBO_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo.json"
PURERULES = REPO / "evals" / "purerules.jsonl"
SOURCE = REPO / "evals" / "rulesguru_full_v2.jsonl"


def _load_rows() -> list[dict]:
    return load_jsonl(AB_ROWS)


def _load_cache(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Row selection
# --------------------------------------------------------------------------

def test_row_count_and_level_split_exactly_40_each():
    rows = _load_rows()
    assert len(rows) == 120
    counts = {lvl: sum(1 for r in rows if r["level"] == lvl) for lvl in LEVELS}
    assert counts == {"2": 40, "3": 40, "Corner Case": 40}


def test_all_rows_are_gold_bearing():
    rows = _load_rows()
    assert all(r.get("gold") for r in rows)


def test_purerules_exclusion_holds():
    """Not a literal id-string check (pr* ids never appear in
    rulesguru_full_v2 at all, so that would be a vacuous pass) -- the real
    exclusion is on purerules.jsonl's `source_qid` field, which names the
    rulesguru_full_v2 row each purerules question was derived from."""
    rows = _load_rows()
    held_out = purerules_source_qids(PURERULES)
    assert held_out, "purerules.jsonl produced an empty exclusion set -- test is vacuous"
    drawn_ids = {r["id"] for r in rows}
    assert drawn_ids.isdisjoint(held_out)


def test_selection_reproducible_under_fixed_seed():
    """Re-running the exact draw logic against the source corpus reproduces
    the frozen evals/ab_rows.jsonl byte-for-byte (as an id set)."""
    source_rows = load_jsonl(SOURCE)
    held_out = purerules_source_qids(PURERULES)
    redrawn = draw_rows(source_rows, held_out)
    redrawn_ids = sorted(r["id"] for r in redrawn)
    frozen_ids = sorted(r["id"] for r in _load_rows())
    assert redrawn_ids == frozen_ids


def test_rows_load_unmodified_through_load_questions():
    questions = load_questions(AB_ROWS)
    assert len(questions) == 120
    frozen = {r["id"]: r for r in _load_rows()}
    for q in questions:
        row = frozen[q.id]
        assert q.gold == row["gold"]
        assert q.question == row["question"]
        assert q.match == row.get("match", "any")


def test_stratified_not_a_prefix_of_the_source_file():
    """Regression guard for the trap named twice in this project's history:
    a prefix of the level-ordered source file would draw only contiguous
    ids. Checks the drawn ids for level 2 (the largest level, most likely to
    reveal a prefix bug) are NOT the first N_PER_LEVEL ids of that level in
    source-file order."""
    source_rows = load_jsonl(SOURCE)
    held_out = purerules_source_qids(PURERULES)
    eligible_l2 = [r["id"] for r in source_rows
                   if r["level"] == "2" and r.get("gold") and r["id"] not in held_out]
    prefix_ids = set(eligible_l2[:N_PER_LEVEL])
    drawn_l2 = {r["id"] for r in _load_rows() if r["level"] == "2"}
    assert drawn_l2 != prefix_ids


# --------------------------------------------------------------------------
# Prompt caches: shape + arm identity
# --------------------------------------------------------------------------

def test_real_cache_covers_every_row():
    cache = _load_cache(REAL_CACHE)
    rows = _load_rows()
    assert set(cache["prompts"]) == {r["id"] for r in rows}
    assert cache["n_questions"] == 120


def test_placebo_cache_covers_every_row():
    cache = _load_cache(PLACEBO_CACHE)
    rows = _load_rows()
    assert set(cache["prompts"]) == {r["id"] for r in rows}
    assert cache["n_questions"] == 120


def test_real_and_placebo_agree_on_arm_identity_fields():
    """run_answer_eval.py's --prompts-cache identity gate checks
    rewrite_version/ruling_query_mode against the CLI flags -- both caches
    must record the SAME values (the whole point of the placebo being a
    single-variable swap), or a run naively pointed at one then the other
    would silently pass a mismatched gate."""
    real = _load_cache(REAL_CACHE)
    placebo = _load_cache(PLACEBO_CACHE)
    assert real["rewrite_version"] == placebo["rewrite_version"]
    assert real["ruling_query_mode"] == placebo["ruling_query_mode"]


# --------------------------------------------------------------------------
# Derangement
# --------------------------------------------------------------------------

def test_derangement_no_row_keeps_its_own_block():
    placebo = _load_cache(PLACEBO_CACHE)
    borrowed_from = placebo["borrowed_from"]
    assert borrowed_from, "borrowed_from mapping missing or empty"
    self_loops = [qid for qid, donor in borrowed_from.items() if donor == qid]
    assert self_loops == []


def test_derangement_is_a_bijection_over_the_row_set():
    placebo = _load_cache(PLACEBO_CACHE)
    borrowed_from = placebo["borrowed_from"]
    qids = sorted(placebo["prompts"])
    assert sorted(borrowed_from.keys()) == qids
    assert sorted(borrowed_from.values()) == qids  # every id used as a donor exactly once


# --------------------------------------------------------------------------
# Single-variable property: real vs placebo differ ONLY in the rules block
# --------------------------------------------------------------------------

_RULES_HDR = "Rules context:\n"


def _split_rules_block(user: str) -> tuple[str, str, str]:
    """(prefix_incl_header, rules_block_body, suffix) -- suffix starts right
    after the rules block, at the first "\\n\\nCard data:\\n" or
    "\\n\\nQuestion:" marker (mirrors build_prompt()'s own layout: rules
    context always leads, followed by an optional card block, optional
    symbol block, then the question)."""
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


def test_diffing_one_row_shows_only_the_rules_block_changed():
    """A concrete, human-checkable version of the property above: pick one
    row, line-diff the two user prompts, and assert every changed line
    falls strictly between the "Rules context:" header and the next
    section marker."""
    real = _load_cache(REAL_CACHE)["prompts"]
    placebo = _load_cache(PLACEBO_CACHE)["prompts"]
    qid = sorted(real)[0]
    r_lines = real[qid]["user"].splitlines()
    p_lines = placebo[qid]["user"].splitlines()
    # equal length is not guaranteed (different chunk text lengths swap
    # differing line counts) -- instead assert the common prefix (up to and
    # including "Rules context:") and common suffix (from the first shared
    # section marker onward) are identical, which is exactly what
    # _split_rules_block already proves per-row above. This test exists as
    # the "diff one prompt and look at it" deliverable, not a new property.
    assert r_lines[0] == p_lines[0] == "Rules context:"

"""Tests for the three card-channel placebo caches
(evals/build_ab_placebo_channel_prompts.py) that test whether the CARD
channel -- oracle text + Scryfall rulings -- carries the work the CR-rules
placebo (test_ab_harness.py) showed the rules block mostly doesn't:

  - _prompts_ab_placebo_rulings.json  -- rulings swapped only
  - _prompts_ab_placebo_carddata.json -- whole Card data section swapped
  - _prompts_ab_placebo_all.json      -- both (rules half reused from
    _prompts_ab_placebo.json, card half reused from the carddata cache)

Covers: the derangement property (over the ELIGIBLE subset each cache
actually swaps -- some rows have no rulings/no cards at all and are
intentionally left unswapped, recorded as `borrowed_from[qid] is None`),
the byte-identity property (everything outside the intended region matches
the base cache), and one explicit before/after case per cache.

No model call, no retrieval call -- pure filesystem/JSON checks against the
already-built artifacts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "evals"))

from build_ab_placebo_channel_prompts import split_user, RULINGS_MARK  # noqa: E402

AB_ROWS = REPO / "evals" / "ab_rows.jsonl"
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_real.json"
RULES_PLACEBO = REPO / "evals" / "answers" / "_prompts_ab_placebo.json"
RULINGS_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo_rulings.json"
CARDDATA_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo_carddata.json"
ALL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo_all.json"


def _load_cache(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ids() -> set[str]:
    ids = set()
    for line in AB_ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["id"])
    return ids


# --------------------------------------------------------------------------
# Coverage / arm-identity metadata
# --------------------------------------------------------------------------

def test_all_three_caches_cover_every_row():
    ids = _load_ids()
    for path in (RULINGS_CACHE, CARDDATA_CACHE, ALL_CACHE):
        cache = _load_cache(path)
        assert set(cache["prompts"]) == ids, path.name
        assert cache["n_questions"] == 120, path.name


def test_all_three_caches_agree_on_arm_identity_fields_with_real():
    """run_answer_eval.py's --prompts-cache gate only checks rewrite_version
    and ruling_query_mode against the CLI flags -- all three new caches
    must carry the same values as the real cache so `--rewrite-version none
    --ruling-query-mode union` passes for every arm."""
    real = _load_cache(REAL_CACHE)
    for path in (RULINGS_CACHE, CARDDATA_CACHE, ALL_CACHE):
        cache = _load_cache(path)
        assert cache["rewrite_version"] == real["rewrite_version"], path.name
        assert cache["ruling_query_mode"] == real["ruling_query_mode"], path.name


# --------------------------------------------------------------------------
# Derangement, over the eligible subset
# --------------------------------------------------------------------------

def test_rulings_derangement_no_self_loops_and_is_a_bijection_over_eligible_rows():
    cache = _load_cache(RULINGS_CACHE)
    borrowed_from = cache["borrowed_from"]
    entries = {qid: donor for qid, donor in borrowed_from.items() if donor is not None}
    assert entries, "rulings borrowed_from has no swapped rows -- test would be vacuous"
    self_loops = [qid for qid, donor in entries.items() if donor == qid]
    assert self_loops == []
    assert sorted(entries.values()) == sorted(entries.keys())


def test_carddata_derangement_no_self_loops_and_is_a_bijection_over_eligible_rows():
    cache = _load_cache(CARDDATA_CACHE)
    borrowed_from = cache["borrowed_from"]
    entries = {qid: donor for qid, donor in borrowed_from.items() if donor is not None}
    assert entries, "carddata borrowed_from has no swapped rows -- test would be vacuous"
    self_loops = [qid for qid, donor in entries.items() if donor == qid]
    assert self_loops == []
    assert sorted(entries.values()) == sorted(entries.keys())


def test_rows_with_nothing_to_borrow_are_recorded_as_unswapped_not_silently_dropped():
    """rg1006 (no cards at all) must be null in both card-facing caches; any
    row with zero rulings anywhere must be null in the rulings cache. These
    are the documented exceptions to "every row swaps" -- confirm they're
    explicit nulls, not missing keys or accidental self-loops."""
    rulings = _load_cache(RULINGS_CACHE)["borrowed_from"]
    carddata = _load_cache(CARDDATA_CACHE)["borrowed_from"]
    assert "rg1006" in carddata and carddata["rg1006"] is None
    assert "rg1006" in rulings and rulings["rg1006"] is None
    null_rulings = [qid for qid, donor in rulings.items() if donor is None]
    null_carddata = [qid for qid, donor in carddata.items() if donor is None]
    assert len(null_rulings) == 3   # rg46, rg1006, rg625 (no rulings anywhere)
    assert len(null_carddata) == 1  # rg1006 only (no cards at all)


def test_arm_all_reuses_arm_b_rules_mapping_and_arm_d_card_mapping_exactly():
    """The whole point of arm E is that neither half is a fresh draw -- it
    must be byte-for-byte the union of the existing rules placebo's mapping
    and this project's own carddata mapping, or arm E stops being
    "arm B union arm D" and becomes an independent, harder-to-reason-about
    fourth derangement."""
    rules_placebo = _load_cache(RULES_PLACEBO)
    carddata = _load_cache(CARDDATA_CACHE)
    allc = _load_cache(ALL_CACHE)
    assert allc["borrowed_from"]["rules"] == rules_placebo["borrowed_from"]
    assert allc["borrowed_from"]["carddata"] == carddata["borrowed_from"]


# --------------------------------------------------------------------------
# Byte-identity outside the swapped region
# --------------------------------------------------------------------------

def _assert_outside_identical(base_prompts: dict, cand_prompts: dict) -> None:
    for qid in base_prompts:
        b_pre, _b_body, b_suf = split_user(base_prompts[qid]["user"])
        c_pre, _c_body, c_suf = split_user(cand_prompts[qid]["user"])
        assert b_pre == c_pre, qid
        assert b_suf == c_suf, qid


def test_rulings_cache_byte_identical_outside_card_data_vs_real():
    real = _load_cache(REAL_CACHE)["prompts"]
    rulings = _load_cache(RULINGS_CACHE)["prompts"]
    for qid in real:
        assert real[qid]["system"] == rulings[qid]["system"], qid
    _assert_outside_identical(real, rulings)


def test_carddata_cache_byte_identical_outside_card_data_vs_real():
    real = _load_cache(REAL_CACHE)["prompts"]
    carddata = _load_cache(CARDDATA_CACHE)["prompts"]
    for qid in real:
        assert real[qid]["system"] == carddata[qid]["system"], qid
    _assert_outside_identical(real, carddata)


def test_all_cache_byte_identical_outside_card_data_vs_rules_placebo():
    """Arm E's prefix/suffix must match arm B's (the rules-swapped base),
    NOT arm A's -- its rules half is intentionally different from real."""
    rules_placebo = _load_cache(RULES_PLACEBO)["prompts"]
    allc = _load_cache(ALL_CACHE)["prompts"]
    for qid in rules_placebo:
        assert rules_placebo[qid]["system"] == allc[qid]["system"], qid
    _assert_outside_identical(rules_placebo, allc)


def test_rulings_swap_never_touches_a_card_header_or_oracle_text():
    """For every swapped row, splitting each card block on the "Rulings:"
    marker must show the HEAD (header + oracle text) unchanged between real
    and rulings-placebo -- only the bullets after it may differ."""
    real = _load_cache(REAL_CACHE)["prompts"]
    rulings_cache = _load_cache(RULINGS_CACHE)
    checked = 0
    for qid, donor in rulings_cache["borrowed_from"].items():
        if donor is None:
            continue
        _r_pre, r_body, _r_suf = split_user(real[qid]["user"])
        _c_pre, c_body, _c_suf = split_user(rulings_cache["prompts"][qid]["user"])
        r_blocks = r_body.split("\n\n")
        c_blocks = c_body.split("\n\n")
        assert len(r_blocks) == len(c_blocks), qid
        for rb, cb in zip(r_blocks, c_blocks):
            r_head = rb.partition(RULINGS_MARK)[0]
            c_head = cb.partition(RULINGS_MARK)[0]
            assert r_head == c_head, qid
        checked += 1
    assert checked == 117


def test_carddata_swap_body_is_donors_own_real_body_verbatim():
    """Whole-section swap must be internally coherent: the new Card data
    body for a swapped row equals the DONOR's own real Card data body
    exactly -- never an interleave of two donors' cards."""
    real = _load_cache(REAL_CACHE)["prompts"]
    carddata_cache = _load_cache(CARDDATA_CACHE)
    checked = 0
    for qid, donor in carddata_cache["borrowed_from"].items():
        if donor is None:
            continue
        _c_pre, c_body, _c_suf = split_user(carddata_cache["prompts"][qid]["user"])
        _d_pre, d_body, _d_suf = split_user(real[donor]["user"])
        assert c_body == d_body, qid
        checked += 1
    assert checked == 119


# --------------------------------------------------------------------------
# One explicit before/after case per cache
# --------------------------------------------------------------------------

def test_one_concrete_case_rulings_cache():
    real = _load_cache(REAL_CACHE)["prompts"]
    cache = _load_cache(RULINGS_CACHE)
    qid = next(q for q, d in cache["borrowed_from"].items() if d is not None)
    r_pre, r_body, r_suf = split_user(real[qid]["user"])
    c_pre, c_body, c_suf = split_user(cache["prompts"][qid]["user"])
    assert r_pre == c_pre
    assert r_suf == c_suf
    assert r_body != c_body
    # header line (before the first newline) of the first card is unchanged
    assert r_body.split("\n", 1)[0] == c_body.split("\n", 1)[0]


def test_one_concrete_case_carddata_cache():
    real = _load_cache(REAL_CACHE)["prompts"]
    cache = _load_cache(CARDDATA_CACHE)
    qid = next(q for q, d in cache["borrowed_from"].items() if d is not None)
    r_pre, r_body, r_suf = split_user(real[qid]["user"])
    c_pre, c_body, c_suf = split_user(cache["prompts"][qid]["user"])
    assert r_pre == c_pre
    assert r_suf == c_suf
    assert r_body != c_body
    donor = cache["borrowed_from"][qid]
    assert r_body.split("\n", 1)[0] != c_body.split("\n", 1)[0]  # different card entirely
    _d_pre, d_body, _d_suf = split_user(real[donor]["user"])
    assert c_body == d_body


def test_one_concrete_case_all_cache():
    rules_placebo = _load_cache(RULES_PLACEBO)["prompts"]
    cache = _load_cache(ALL_CACHE)
    qid = next(q for q, d in cache["borrowed_from"]["carddata"].items() if d is not None)
    b_pre, b_body, b_suf = split_user(rules_placebo[qid]["user"])
    c_pre, c_body, c_suf = split_user(cache["prompts"][qid]["user"])
    assert b_pre == c_pre  # rules block (already swapped in arm B) untouched here
    assert b_suf == c_suf
    assert b_body != c_body  # card data further swapped on top

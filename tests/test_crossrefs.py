"""Unit tests for retrieve/crossrefs.py (docs/plan-l1-crossref-expansion.md,
Part A gate 1): ref extraction (both patterns, dedupe, cap), resolution
fallbacks (family ref, label skip), determinism, pool-dedupe.

Pure-function tests -- no agent, no store, no data assets.
"""

from rulesagent.contracts import Chunk, Retrieved
from rulesagent.retrieve.crossrefs import expand_crossrefs


def _chunk(source_id: str, text: str, kind: str = "rule") -> Chunk:
    return Chunk(source_id=source_id, kind=kind, section="Test", text=text, embed_text=text)


def _r(source_id: str, text: str, score: float = 0.5) -> Retrieved:
    return Retrieved(chunk=_chunk(source_id, text), score=score)


def _ids(retrieved: list[Retrieved]) -> list[str]:
    return [r.chunk.source_id for r in retrieved]


# --- ref extraction -------------------------------------------------------

def test_word_pattern_extracts_referenced_rule():
    retrieved = [_r("100.1", "For details, see rule 704.5, which covers this.")]
    chunk_map = {"100.1": retrieved[0].chunk, "704.5": _chunk("704.5", "State-based actions.")}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "704.5"]


def test_word_pattern_handles_plural_rules_and_letter_suffix():
    retrieved = [_r("100.1", "This follows rules 601.2a in every case.")]
    chunk_map = {"100.1": retrieved[0].chunk, "601.2a": _chunk("601.2a", "Propose the spell.")}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "601.2a"]


def test_bare_pattern_extracts_inline_parenthetical_mention():
    retrieved = [_r("100.1", "Costs are paid in full (601.2h) before it resolves.")]
    chunk_map = {"100.1": retrieved[0].chunk, "601.2h": _chunk("601.2h", "Pay the total cost.")}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "601.2h"]


def test_dedupes_same_ref_mentioned_twice_in_one_chunk():
    retrieved = [_r("100.1", "See rule 704.5. Also see rule 704.5 again.")]
    chunk_map = {"100.1": retrieved[0].chunk, "704.5": _chunk("704.5", "SBAs.")}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "704.5"]  # appears once, not twice


def test_dedupes_same_ref_mentioned_across_multiple_chunks():
    retrieved = [
        _r("100.1", "See rule 704.5 for details."),
        _r("100.2", "Also see rule 704.5 here."),
    ]
    chunk_map = {
        "100.1": retrieved[0].chunk,
        "100.2": retrieved[1].chunk,
        "704.5": _chunk("704.5", "SBAs."),
    }
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "100.2", "704.5"]


def test_first_mention_order_across_ranked_chunks():
    """Refs are appended in first-mention order, scanned rank-by-rank."""
    retrieved = [
        _r("100.1", "See rule 800.1 first."),
        _r("100.2", "See rule 704.5 second."),
    ]
    chunk_map = {
        "100.1": retrieved[0].chunk,
        "100.2": retrieved[1].chunk,
        "800.1": _chunk("800.1", "A."),
        "704.5": _chunk("704.5", "B."),
    }
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "100.2", "800.1", "704.5"]


# --- cap -------------------------------------------------------------------

def test_cap_limits_appended_count_to_max_extra():
    retrieved = [_r(
        "100.1",
        "See rule 201.1, rule 202.2, rule 203.3, rule 204.4, rule 205.5, rule 206.6.",
    )]
    chunk_map = {
        "100.1": retrieved[0].chunk,
        **{f"20{i}.{i}": _chunk(f"20{i}.{i}", f"chunk {i}") for i in range(1, 7)},
    }
    out = expand_crossrefs(retrieved, chunk_map, max_extra=3)
    assert _ids(out) == ["100.1", "201.1", "202.2", "203.3"]


# --- resolution fallbacks ----------------------------------------------------

def test_bare_family_ref_falls_back_to_entry_rule():
    """'see rule 704' (no decimal) with no '704' chunk falls back to '704.1',
    the family's entry rule -- ONE chunk, not a family dump."""
    retrieved = [_r("100.1", "This is governed by rule 704 as a whole.")]
    chunk_map = {
        "100.1": retrieved[0].chunk,
        "704.1": _chunk("704.1", "General copy rules."),
        "704.2": _chunk("704.2", "Also copy rules."),
    }
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "704.1"]  # not 704.2 too


def test_label_like_ref_with_no_chunk_is_skipped_not_crashed():
    """A ref that resolves to nothing at all (e.g. 701.5 'Cast', a label-like
    rule folded into its children -- never gets its own chunk) is silently
    skipped, not appended, and does not raise."""
    retrieved = [_r("100.1", "See rule 701.5 for the definition of casting.")]
    chunk_map = {"100.1": retrieved[0].chunk}  # 701.5 deliberately absent
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1"]


def test_bare_family_ref_with_no_chunk_at_all_is_skipped():
    """'see rule 704' when NEITHER '704' nor '704.1' exists in chunk_map."""
    retrieved = [_r("100.1", "This is governed by rule 704 as a whole.")]
    chunk_map = {"100.1": retrieved[0].chunk}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1"]


# --- pool dedupe -------------------------------------------------------------

def test_ref_already_in_organic_pool_is_not_reappended():
    retrieved = [
        _r("100.1", "See rule 704.5 for details."),
        _r("704.5", "State-based actions are checked."),
    ]
    chunk_map = {"100.1": retrieved[0].chunk, "704.5": retrieved[1].chunk}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "704.5"]  # unchanged -- no duplicate append
    assert out[1] is retrieved[1]  # organic entry untouched (same object, same score)


def test_family_fallback_dedupes_against_pool_too():
    """'see rule 704' folds to '704.1', but 704.1 is ALREADY organically in
    the pool -- must not be appended a second time."""
    retrieved = [
        _r("100.1", "This is governed by rule 704 as a whole."),
        _r("704.1", "General copy rules.", score=0.9),
    ]
    chunk_map = {"100.1": retrieved[0].chunk, "704.1": retrieved[1].chunk}
    out = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out) == ["100.1", "704.1"]
    assert out[1].score == 0.9  # the organic score, untouched


# --- organic pool / ranks untouched, appended entries scored 0.0 -----------

def test_organic_entries_and_ranks_untouched_appended_after():
    retrieved = [
        _r("704.5", "SBAs checked. See rule 800.1 too.", score=0.95),
        _r("100.1", "Something unrelated.", score=0.80),
    ]
    chunk_map = {
        "704.5": retrieved[0].chunk,
        "100.1": retrieved[1].chunk,
        "800.1": _chunk("800.1", "Extra."),
    }
    out = expand_crossrefs(retrieved, chunk_map)
    assert out[0] is retrieved[0]
    assert out[1] is retrieved[1]
    assert out[2].chunk.source_id == "800.1"
    assert out[2].score == 0.0  # sentinel -- never scored by the retriever


# --- determinism -------------------------------------------------------------

def test_determinism_same_input_same_output():
    retrieved = [
        _r("100.1", "See rule 704.5 and rule 800.1."),
        _r("100.2", "See rule 900.9 also."),
    ]
    chunk_map = {
        "100.1": retrieved[0].chunk,
        "100.2": retrieved[1].chunk,
        "704.5": _chunk("704.5", "A"),
        "800.1": _chunk("800.1", "B"),
        "900.9": _chunk("900.9", "C"),
    }
    out1 = expand_crossrefs(retrieved, chunk_map)
    out2 = expand_crossrefs(retrieved, chunk_map)
    assert _ids(out1) == _ids(out2)
    assert [r.score for r in out1] == [r.score for r in out2]


def test_empty_retrieved_returns_empty():
    assert expand_crossrefs([], {}) == []


def test_no_refs_in_text_returns_pool_unchanged():
    retrieved = [_r("100.1", "Nothing to see here, no cross references at all.")]
    chunk_map = {"100.1": retrieved[0].chunk}
    out = expand_crossrefs(retrieved, chunk_map)
    assert out == retrieved


# --- debug field -------------------------------------------------------------

def test_debug_dict_populated_with_refs_found_appended_skipped():
    retrieved = [_r("100.1", "See rule 704.5 and rule 701.5 (label, no chunk).")]
    chunk_map = {"100.1": retrieved[0].chunk, "704.5": _chunk("704.5", "SBAs.")}
    debug: dict = {}
    expand_crossrefs(retrieved, chunk_map, debug=debug)
    assert debug["refs_found"] == ["704.5", "701.5"]
    assert debug["appended"] == ["704.5"]
    assert debug["skipped"] == ["701.5"]


def test_debug_none_by_default_no_error():
    retrieved = [_r("100.1", "See rule 704.5.")]
    chunk_map = {"100.1": retrieved[0].chunk, "704.5": _chunk("704.5", "SBAs.")}
    # Should not raise when debug is omitted.
    out = expand_crossrefs(retrieved, chunk_map)
    assert len(out) == 2

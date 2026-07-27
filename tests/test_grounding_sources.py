"""Tests for the citation-source classifier (docs/results-groundedness-
guard.md, the "which source" monitor) and its retroactive scorer
(evals/grounding_sources.py).

No live Anthropic/API calls anywhere in this file -- everything here is
pure string/data classification, same $0-local-compute nature as the
finding itself.
"""
import json
from pathlib import Path

from rulesagent.contracts import Card, CardFace, Chunk, Retrieved
from rulesagent.generate import answer as ans
from evals import grounding_sources as gs


# --- classify_citation: the five classes ------------------------------------


def _sources(rules_context=(), rulings=(), cards=()):
    return ans.AvailableSources(
        rules_context_ids=frozenset(rules_context), ruling_labels=frozenset(rulings),
        card_names=frozenset(cards),
    )


def test_classify_cr_rule():
    sources = _sources(rules_context=["601.2b"])
    assert ans.classify_citation("601.2b", sources) == "cr_rule"


def test_classify_ruling():
    sources = _sources(rulings=["[Archive Trap ruling #2]"])
    assert ans.classify_citation("[Archive Trap ruling #2]", sources) == "ruling"


def test_classify_card():
    sources = _sources(cards=["Lightning Bolt"])
    assert ans.classify_citation("Lightning Bolt", sources) == "card"


def test_classify_unresolved():
    # Not present in ANY of the three source sets -- the fabrication canary.
    sources = _sources(rules_context=["601.2b"], rulings=["[Archive Trap ruling #2]"], cards=["Lightning Bolt"])
    assert ans.classify_citation("999.9z", sources) == "unresolved"


def test_classify_cr_shaped_but_not_present_is_unresolved():
    # A CR-rule-SHAPED citation not actually in the provided rules must not
    # be credited -- shape alone (cr_rule_citations()'s test) is not
    # presence. This is the exact defect the guard doc describes.
    sources = _sources(rules_context=["601.2b"])
    assert ans.classify_citation("104.3a", sources) == "unresolved"


# --- the two real traps: "//" split cards and apostrophes ------------------


def test_available_card_names_split_card_top_level_name():
    # _format_cards() top line for a multi-face card: "<name>  (<meta>)".
    card_text = "Pain // Suffering  (split, MV 2)\nFace 1: Pain {R}\nFace 2: Suffering {1}{B}"
    names = ans.available_card_names(card_text)
    assert "Pain // Suffering" in names
    assert "Pain" in names
    assert "Suffering" in names


def test_available_card_names_dfc_with_comma_in_face_name():
    card_text = (
        "Westvale Abbey // Ormendahl, Profane Prince  (transform, MV 0)\n"
        "Face 1: Westvale Abbey\nFace 2: Ormendahl, Profane Prince -- Legendary Creature -- Demon  (7/7)"
    )
    names = ans.available_card_names(card_text)
    assert "Westvale Abbey // Ormendahl, Profane Prince" in names
    assert "Westvale Abbey" in names
    assert "Ormendahl, Profane Prince" in names


def test_available_card_names_apostrophe_card():
    # Single-face header: "<name> <cost> -- <attrs>  (<meta>)".
    card_text = "Urza's Saga {1}  (MV 1)\nLegendary Land"
    names = ans.available_card_names(card_text)
    assert "Urza's Saga" in names


def test_available_card_names_apostrophe_after_s():
    card_text = "Inventors' Fair  (MV 3)\nLand"
    names = ans.available_card_names(card_text)
    assert "Inventors' Fair" in names


def test_citation_resolves_against_split_card_name():
    sources = _sources(cards=["Pain // Suffering", "Pain", "Suffering"])
    assert ans.classify_citation("Pain // Suffering", sources) == "card"
    assert ans.classify_citation("Suffering", sources) == "card"


def test_citation_resolves_against_apostrophe_card_name():
    sources = _sources(cards=["Urza's Saga"])
    assert ans.classify_citation("Urza's Saga", sources) == "card"


# --- ruling-only row must be grounded, not unresolved -----------------------


def test_ruling_only_row_is_grounded_not_unresolved():
    sources = _sources(rulings=["[Archive Trap ruling #2]"])
    breakdown = ans.citation_source_breakdown(["[Archive Trap ruling #2]"], sources)
    assert breakdown["unresolved"] == 0
    assert breakdown["ruling"] == 1
    assert breakdown["category"] == "rulings_or_cards_only"
    assert breakdown["cites_cr_rule"] is False


# --- row with no citations ---------------------------------------------------


def test_no_citations_row_is_nothing_resolvable():
    sources = _sources(rules_context=["601.2b"])
    breakdown = ans.citation_source_breakdown([], sources)
    assert breakdown == {
        "labels": [], "cr_rule": 0, "ruling": 0, "card": 0, "glossary": 0,
        "unresolved": 0, "category": "nothing_resolvable", "cites_cr_rule": False,
    }


# --- mixed-citation row: category follows CR-reliance first ----------------


def test_mixed_row_with_cr_rule_and_unresolved_is_cr_reliant_but_flags_unresolved():
    sources = _sources(rules_context=["601.2b"])
    breakdown = ans.citation_source_breakdown(["601.2b", "999.9z"], sources)
    assert breakdown["category"] == "cr_reliant"
    assert breakdown["cites_cr_rule"] is True
    assert breakdown["unresolved"] == 1  # the canary is independent of category


# --- available_sources_from_context: the live, structured path -------------


def test_available_sources_from_context_reads_retrieved_and_cards():
    retrieved = [Retrieved(
        chunk=Chunk(source_id="601.2b", kind="rule", section="x", text="t", embed_text="t"),
        score=0.9,
    )]
    card = Card(
        name="Pain // Suffering", oracle_text="", type_line="Sorcery // Sorcery",
        mana_cost="", oracle_id="oid1",
        rulings=["[Pain // Suffering ruling #0] Some ruling text."],
        faces=[CardFace(name="Pain"), CardFace(name="Suffering")],
    )
    sources = ans.available_sources_from_context(retrieved, [card])
    assert "601.2b" in sources.rules_context_ids
    assert "Pain // Suffering" in sources.card_names
    assert "Pain" in sources.card_names
    assert "Suffering" in sources.card_names
    assert "[Pain // Suffering ruling #0]" in sources.ruling_labels


# --- available_sources_from_prompt_text: the frozen-prompt-cache path ------


def test_available_sources_from_prompt_text_full_prompt():
    user = (
        "Rules context:\n[601.2b] Casting a spell text.\n\n[100.1] Preamble text.\n\n"
        "Card data:\nUrza's Saga {1}  (MV 1)\nLegendary Land\nRulings:\n"
        "- [Urza's Saga ruling #0] A ruling.\n\n"
        "Question: does this work"
    )
    sources = ans.available_sources_from_prompt_text(user)
    assert sources.rules_context_ids == frozenset({"601.2b", "100.1"})
    assert "Urza's Saga" in sources.card_names
    assert "[Urza's Saga ruling #0]" in sources.ruling_labels


def test_available_sources_from_prompt_text_no_card_data_block():
    user = "Rules context:\n[601.2b] Casting a spell text.\n\nQuestion: does this work"
    sources = ans.available_sources_from_prompt_text(user)
    assert sources.rules_context_ids == frozenset({"601.2b"})
    assert sources.card_names == frozenset()
    assert sources.ruling_labels == frozenset()


# --- glossary: the coordinator's spec-gap fix -------------------------------
# A citation is "unresolved" only if it matches NOTHING the prompt provided.
# A non-numeric id genuinely present in the rules context (a glossary chunk,
# not a CR rule number) is grounded -- bucket "glossary", precedence after
# cr_rule/ruling/card. Includes the two exact hard cases from
# normalize_source_id()'s own docstring: an apostrophe term and a
# multi-word term with spaces.


def test_classify_glossary_term():
    sources = _sources(rules_context=["Saga"])
    assert ans.classify_citation("Saga", sources) == "glossary"


def test_classify_glossary_term_apostrophe():
    sources = _sources(rules_context=["City's Blessing"])
    assert ans.classify_citation("City's Blessing", sources) == "glossary"


def test_classify_glossary_term_with_spaces():
    sources = _sources(rules_context=["Attacks and Isn't Blocked"])
    assert ans.classify_citation("Attacks and Isn't Blocked", sources) == "glossary"


def test_classify_precedence_cr_rule_before_glossary():
    # A citation that's BOTH numeric-shaped and present in the rules context
    # must classify as cr_rule, never glossary -- shape decides which check
    # runs first, but presence in rules_context_ids is what both checks share.
    sources = _sources(rules_context=["601.2b"])
    assert ans.classify_citation("601.2b", sources) == "cr_rule"


def test_classify_precedence_card_before_glossary():
    # A citation present in BOTH card_names and rules_context_ids (unusual,
    # but the precedence must still hold) classifies as card, not glossary.
    sources = _sources(rules_context=["Saga"], cards=["Saga"])
    assert ans.classify_citation("Saga", sources) == "card"


def test_available_sources_from_prompt_text_includes_glossary_ids():
    # _format_context() renders a glossary chunk exactly like a rule chunk:
    # "[source_id] text" -- the id just isn't numeric-shaped.
    user = (
        "Rules context:\n[714.3a] Sagas use lore counters...\n\n"
        "[Saga] Saga. An enchantment subtype.\n\n"
        "[City's Blessing] A player has the city's blessing if...\n\n"
        "Question: does this work"
    )
    sources = ans.available_sources_from_prompt_text(user)
    assert sources.rules_context_ids == frozenset({"714.3a", "Saga", "City's Blessing"})
    assert ans.classify_citation("Saga", sources) == "glossary"
    assert ans.classify_citation("City's Blessing", sources) == "glossary"
    assert ans.classify_citation("714.3a", sources) == "cr_rule"


def test_glossary_citation_grounds_the_row_not_unresolved():
    # THE exact defect from the coordinator's message: "Saga" was falling
    # through to unresolved despite being genuinely provided.
    sources = _sources(rules_context=["Saga"])
    breakdown = ans.citation_source_breakdown(["Saga"], sources)
    assert breakdown["unresolved"] == 0
    assert breakdown["glossary"] == 1
    assert breakdown["category"] == "rulings_or_cards_only"


# --- evals/grounding_sources.py: score_row / score_arm ----------------------


def test_score_row_uses_precomputed_citation_sources():
    row = {
        "answered": True, "citations": ["601.2b"],
        "citation_sources": {
            "labels": ["cr_rule"], "cr_rule": 1, "ruling": 0, "card": 0,
            "unresolved": 0, "category": "cr_reliant",
        },
        "cites_cr_rule": True,
    }
    scored = gs.score_row(row)
    assert scored["source"] == "row"
    assert scored["category"] == "cr_reliant"


def test_score_row_reconstructs_from_prompts_cache(tmp_path):
    # Real on-disk shape (evals/run_openrouter_arm.py --assemble-only, the
    # writer): metadata keys plus a "prompts" key holding {qid: {...}} --
    # NOT a bare {qid: {...}} dict. A prior version of this reconstruction
    # unwrapped nothing and silently scored every row "unknown" even though
    # a perfectly good cache file was sitting right there.
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({
        "derived_from": "questions.jsonl", "arm": "test",
        "prompts": {
            "q001": {"system": "sys", "user": (
                "Rules context:\n[601.2b] text.\n\nQuestion: q"
            )},
        },
    }), encoding="utf-8")
    row = {
        "id": "q001", "answered": True, "citations": ["601.2b"],
        "prompts_cache": str(cache_path),
    }
    scored = gs.score_row(row)
    assert scored["source"] == "prompts_cache"
    assert scored["category"] == "cr_reliant"


def test_score_row_reconstructs_from_bare_qid_keyed_cache(tmp_path):
    # Back-compat: a cache file that's already qid-keyed at the top level
    # (no "prompts" wrapper) is still usable.
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({
        "q001": {"system": "sys", "user": (
            "Rules context:\n[601.2b] text.\n\nQuestion: q"
        )},
    }), encoding="utf-8")
    row = {
        "id": "q001", "answered": True, "citations": ["601.2b"],
        "prompts_cache": str(cache_path),
    }
    scored = gs.score_row(row)
    assert scored["source"] == "prompts_cache"
    assert scored["category"] == "cr_reliant"


def test_score_row_reports_unknown_honestly_when_no_cache_available():
    row = {"id": "q001", "answered": True, "citations": ["601.2b"], "prompts_cache": None}
    scored = gs.score_row(row)
    assert scored["source"] == "unknown"
    assert scored["category"] == "unknown"


def test_score_row_reports_unknown_when_cache_file_is_missing(tmp_path):
    row = {
        "id": "q001", "answered": True, "citations": ["601.2b"],
        "prompts_cache": str(tmp_path / "does-not-exist.json"),
    }
    scored = gs.score_row(row)
    assert scored["source"] == "unknown"


# --- score_arm: the per-arm rate maths --------------------------------------


def _row(category, unresolved=0, answered=True, glossary=None):
    cs = {
        "labels": [], "cr_rule": 1 if category == "cr_reliant" else 0,
        "ruling": 0, "card": 0, "unresolved": unresolved, "category": category,
    }
    # glossary=None (the default) deliberately OMITS the key entirely --
    # simulates a row recorded before the glossary amendment, exercising
    # score_arm()'s `.get("glossary")` safe-access path rather than a real 0.
    if glossary is not None:
        cs["glossary"] = glossary
    return {
        "answered": answered, "citations": [],
        "citation_sources": cs,
        "cites_cr_rule": category == "cr_reliant",
    }


def test_score_arm_rate_maths():
    rows = [
        _row("cr_reliant"), _row("cr_reliant"), _row("cr_reliant"),
        _row("rulings_or_cards_only"),
        _row("nothing_resolvable", unresolved=1),
    ]
    metrics = gs.score_arm(rows)
    assert metrics["n_answered"] == 5
    assert metrics["n_scored"] == 5
    assert metrics["n_unknown"] == 0
    assert metrics["cr_reliance_rate"] == 3 / 5
    assert metrics["rulings_only_rate"] == 1 / 5
    assert metrics["nothing_resolvable_rate"] == 1 / 5
    assert metrics["unresolved_citation_rate"] == 1 / 5


def test_score_arm_glossary_rate():
    rows = [
        _row("rulings_or_cards_only", glossary=1),
        _row("rulings_or_cards_only", glossary=0),
        _row("cr_reliant"),  # no "glossary" key at all -- pre-amendment row shape
    ]
    metrics = gs.score_arm(rows)
    assert metrics["glossary_rate"] == 1 / 3


def test_score_arm_excludes_declined_rows_from_denominator():
    rows = [_row("cr_reliant"), _row("nothing_resolvable", answered=False)]
    metrics = gs.score_arm(rows)
    assert metrics["n_answered"] == 1
    assert metrics["cr_reliance_rate"] == 1.0


def test_score_arm_excludes_unknown_rows_from_denominator_but_counts_them():
    rows = [
        _row("cr_reliant"),
        {"answered": True, "citations": ["601.2b"], "prompts_cache": None},
    ]
    metrics = gs.score_arm(rows)
    assert metrics["n_answered"] == 2
    assert metrics["n_scored"] == 1
    assert metrics["n_unknown"] == 1
    assert metrics["cr_reliance_rate"] == 1.0


def test_score_arm_all_unknown_reports_none_rates():
    rows = [{"answered": True, "citations": ["601.2b"], "prompts_cache": None}]
    metrics = gs.score_arm(rows)
    assert metrics["n_scored"] == 0
    assert metrics["cr_reliance_rate"] is None

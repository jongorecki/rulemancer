# Tests for Slice 2, selective symbol injection
# (docs/plan-v5-symbol-injection.md Sec 5a, 3, 4). No network/embeddings/
# vector store needed -- SYMBOL_DEFS, _symbols_present, _collapse_families,
# _symbol_reference_block, and build_prompt's wiring are all pure functions
# over in-memory Card/Chunk/Retrieved objects.

import hashlib

from rulesagent.contracts import Card, CardFace, Chunk, Retrieved
from rulesagent.generate import answer as ans


def _card(name: str, mana_cost: str = "", oracle_text: str = "",
          faces: list[CardFace] | None = None) -> Card:
    return Card(
        name=name,
        oracle_text=oracle_text,
        type_line="Instant",
        mana_cost=mana_cost,
        oracle_id=f"oracle-{name.lower()}",
        faces=faces or [],
    )


def _retrieved(source_id: str, text: str) -> Retrieved:
    return Retrieved(
        chunk=Chunk(source_id=source_id, kind="rule", section="Test",
                    text=text, embed_text=text),
        score=1.0,
    )


# -- v3/v4 unchanged (SYSTEM_VERSIONS[3] and [4] guard) ----------------------

def test_system_versions_3_and_4_unchanged():
    v3 = ans.SYSTEM_VERSIONS[3]
    v4 = ans.SYSTEM_VERSIONS[4]
    assert len(v3) == 5189
    assert hashlib.sha256(v3.encode()).hexdigest() == (
        "25aa69e19208da80b033c15a19d11a3cafa90e23ee807552f17f758bedde06cc"
    )
    assert len(v4) == 10045


def test_v4nl_registered_and_drops_the_legend():
    assert "v4nl" in ans.SYSTEM_VERSIONS
    s = ans.SYSTEM_VERSIONS["v4nl"]
    # per-symbol definitions gone
    assert "Notation legend, CORE tier" not in s
    assert "Notation legend, REFERENCE tier" not in s
    assert "{E} means one energy counter" not in s
    assert "colorless mana specifically" not in s
    # what must survive: 3b intro clause, cost-math guidance, the
    # mana-value counting rule, and 4b/4c/4d/4e.
    assert "State assumptions when the context doesn't cover something" in s
    assert "Cost math: a cost-REDUCTION effect" in s
    assert "For a mana value or total-cost COUNT" in s
    assert "counts as 1 no matter which half would be paid" in s
    assert "state each outcome separately and say which is which" in s  # 4b
    assert "When the answer depends on a fact the question doesn't state" in s  # 4c
    assert "Answer the practical question a player is actually asking" in s  # 4d
    assert "discard it rather than \"correcting\" it in place" in s  # 4e


# -- Jon's Un-set ruling survives decomposition ------------------------------

def test_half_and_infinite_symbols_absent_from_symbol_defs():
    blob = " ".join(ans.SYMBOL_DEFS.values())
    assert "half symbol" not in blob
    assert "{HW}" not in blob
    assert "{HR}" not in blob
    assert "½" not in blob  # {1/2}
    assert "∞" not in blob  # {infinity}


def test_half_and_infinite_symbols_never_emitted_in_block():
    # Even if such a token somehow appeared in card/question text,
    # _classify_symbol has no case for it -- it's dropped, not guessed at.
    symbols = ans._symbols_present("{HW} {HR} {1/2} {infinity}")
    assert ans._symbol_reference_block(symbols) == ""


# -- Zero symbols: block empty, assembled prompt byte-identical -------------

def test_zero_symbols_gives_empty_block_and_byte_identical_prompt():
    retrieved = [_retrieved("100.1", "Rules-only text, no symbols here.")]
    card = _card("Ornithopter", mana_cost="", oracle_text="Flying.")
    # cards param intentionally omits mana_cost/oracle_text symbols
    _, user_with_cards = ans.build_prompt("Does this creature fly?", retrieved, [card])
    _, user_no_cards = ans.build_prompt("Does this creature fly?", retrieved, [])

    assert ans._symbols_present(ans._card_symbol_text([card]) + " Does this creature fly?") == set()
    assert "Symbol reference" not in user_with_cards
    # The only delta between the two should be the Card data section itself
    # -- no symbol block sneaks in either way.
    assert "Symbol reference" not in user_no_cards


def test_zero_symbols_block_is_empty_string():
    assert ans._symbol_reference_block(set()) == ""
    assert ans._symbol_reference_block({"{HW}"}) == ""  # unknown/unmapped symbol


# -- Family collapsing -------------------------------------------------------

def test_hybrid_family_collapses_to_one_definition():
    card = _card(
        "Manamorphose",
        mana_cost="{W/U}{U/B}{B/R}",
        oracle_text="Draw a card. {R/G}{G/W} also appear here for good measure.",
    )
    symbols = ans._symbols_present(ans._card_symbol_text([card]))
    assert symbols == {"{W/U}", "{U/B}", "{B/R}", "{R/G}", "{G/W}"}
    keys = ans._collapse_families(symbols)
    assert keys == ["hybrid"]
    block = ans._symbol_reference_block(symbols)
    assert block.count("A hybrid symbol such as {W/U}") == 1


def test_generic_numerals_collapse_to_one_entry():
    card = _card("Generic Beater", mana_cost="{0}{1}{2}{3}{20}")
    symbols = ans._symbols_present(ans._card_symbol_text([card]))
    keys = ans._collapse_families(symbols)
    assert keys == ["generic"]
    block = ans._symbol_reference_block(symbols)
    assert block.count("N generic mana") == 1


def test_colored_mana_symbols_dedupe_to_one_shared_sentence():
    # {B} and {G} are two DISTINCT SYMBOL_DEFS keys, but v4's source text
    # gives them the identical sentence -- the block must not pay for that
    # sentence twice.
    card = _card("Grist, the Hunger Tide", mana_cost="{1}{B}{G}")
    symbols = ans._symbols_present(ans._card_symbol_text([card]))
    block = ans._symbol_reference_block(symbols)
    assert block.count("each mean one mana of that single color") == 1


# -- Over-trigger guard: context symbols must never leak in ----------------

def test_context_only_symbols_do_not_appear_in_injected_block():
    # Card carries only {R}/{X}; the RETRIEVED rules context (CR 107.4-style
    # text) mentions {W}, {U}, {B}, {G}, {C}, {S}, {E} -- none of which are
    # on the card or in the question. None of those must leak into the block.
    card = _card("Fireblast", mana_cost="{4}{R}{R}",
                  oracle_text="You may sacrifice two Mountains rather than "
                              "pay this spell's mana cost.")
    context_text = (
        "107.4. Some objects' mana costs include the symbols {W}, {U}, "
        "{B}, {G}, {C}, {S}, and {E}, among others."
    )
    retrieved = [_retrieved("107.4", context_text)]
    question = "How much damage does [Fireblast] with {X}=5 deal?"

    system, user = ans.build_prompt(question, retrieved, [card])

    assert "{W}" in context_text and "Rules context" in user
    marker = "Symbol reference"
    assert marker in user
    block = user[user.index(marker):user.index("\n\nQuestion:")]
    # Present on the card/question: R (color) and X (question), generic {4}.
    assert "one mana of that single color" in block
    assert "resolve X to its actual value" in block
    assert "N generic mana" in block
    # Absent-from-card-and-question symbols the rules context introduced
    # must NOT appear as their own definition lines.
    for leaked in ("colorless mana specifically", "one energy counter",
                   "produced by a snow source"):
        assert leaked not in block


def test_symbols_present_never_scans_retrieved_context_directly():
    # _symbols_present itself is a dumb regex scan -- the guarantee comes
    # from build_prompt only ever calling it on card text + question, never
    # on the assembled `context` string. Assert that discipline directly:
    # a context string full of symbols, fed to _symbols_present alone,
    # WOULD match (proving the regex isn't context-aware) -- so the
    # over-trigger guard above is a build_prompt wiring guarantee, not a
    # property of the regex.
    context_text = "{W} {U} {B} {R} {G} {C} {S} {E}"
    assert len(ans._symbols_present(context_text)) == 8


# -- Card-less question with a symbol in the question text (Jon ruling #7,
# and the coordinator's spec-gap correction: this must NOT be nested inside
# `if cards:`) ----------------------------------------------------------

def test_cardless_question_with_symbol_still_injects():
    retrieved = [_retrieved("702.19b", "Trample rules text, no braces.")]
    question = "What does {T} mean on this card?"
    system, user = ans.build_prompt(question, retrieved, [])

    assert "Card data:" not in user  # no cards attached
    assert "Symbol reference" in user
    assert "\"tap this permanent\"" in user
    # Block still lands immediately before the Question: line.
    marker = "\n\nQuestion:"
    assert marker in user
    before_question = user[:user.index(marker)]
    assert before_question.rstrip().endswith(
        '{T} in a cost means "tap this permanent".'
    )


def test_cardless_question_without_symbol_emits_nothing():
    retrieved = [_retrieved("100.1", "no braces here")]
    _, user = ans.build_prompt("What is priority?", retrieved, [])
    assert "Symbol reference" not in user
    assert "Card data:" not in user


# -- Placement: block sits after Card data:, before Question: --------------

def test_block_placement_between_card_data_and_question():
    card = _card("Lightning Bolt", mana_cost="{R}", oracle_text="Deal 3 damage.")
    retrieved = [_retrieved("100.1", "no braces here")]
    _, user = ans.build_prompt("What does [Lightning Bolt] do?", retrieved, [card])

    i_card_data = user.index("Card data:")
    i_symbol = user.index("Symbol reference")
    i_question = user.index("\n\nQuestion:")
    assert i_card_data < i_symbol < i_question


# -- All faces of a multi-face card are scanned -----------------------------

def test_all_card_faces_are_scanned_for_symbols():
    faces = [
        CardFace(name="Front", mana_cost="{2}{W}", oracle_text="Front face text."),
        CardFace(name="Back", mana_cost="", oracle_text="Deals {X} damage, back face."),
    ]
    card = _card("Front // Back", mana_cost="", oracle_text="", faces=faces)
    retrieved: list[Retrieved] = []
    _, user = ans.build_prompt("What happens with [Front // Back]?", retrieved, [card])
    assert "Symbol reference" in user
    assert "resolve X to its actual value" in user
    assert "N generic mana" in user

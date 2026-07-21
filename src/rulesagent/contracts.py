# contracts.py
#
# This is the seam every parser/chunker/retriever call works against.
# Every field below reflects a real decision made on 2026-07-21 -- the
# short version of "why" is in the comment next to it, the longer version
# is in DECISIONS.md.

from pydantic import BaseModel
from typing import Literal


class GlossaryEntry(BaseModel):
    """A term from the Glossary section of the rules.

    DECISION: glossary terms get their own class instead of being folded
    into Rule. They aren't numbered like rules are -- they're a term plus
    one or more definitions -- and we want to be able to show a glossary
    hit as a clearly different kind of result from a rule hit, even though
    a definition often ends with a line like "See rule 113" that ties it
    back to a rule. That tie-back stays as plain text inside `definitions`
    -- we don't need a separate field to "remember" it, because it's
    already sitting right there in the text if something downstream ever
    wants to read it out.
    """

    term: str                  # e.g. "Ability"
    definitions: list[str]     # one entry per numbered sense -- "Ability"
                                # itself has two (senses 1 and 2 in the
                                # real glossary text)


class Rule(BaseModel):
    """One numbered rule or lettered subrule from the Comprehensive Rules.

    Glossary terms are never represented here -- see GlossaryEntry above.
    """

    number: str
    # The rule's own number, e.g. "104.3" or "104.3a". This is always a
    # real rule number now -- splitting out GlossaryEntry means we never
    # have to shove a term name in here instead.

    text: str
    # The rule's own sentence(s), number stripped off the front.
    # DECISION: does NOT include any "Example:" text that follows it --
    # that goes in `examples` below instead. Keeping them apart means a
    # later step (chunking) gets to decide whether to pull examples into
    # a chunk or leave them out, instead of that choice being locked in
    # here during parsing.

    examples: list[str] = []
    # Zero or more example blocks that trailed this rule in the source
    # file. Defaults to an empty list ("= []") so you don't have to type
    # `examples=[]` by hand every time you build a Rule that has none --
    # which is most of them.

    parent_chain: list[str]
    # DECISION: a full audit trail, every level, for every rule -- not
    # just for lettered subrules. Examples:
    #   rule "104.3a"  (a subrule)      -> ["104", "104.3"]
    #   rule "104.3"   (a plain rule)   -> ["104"]
    # A plain rule still gets its real parent recorded here, the same way
    # a subrule does -- nothing gets an empty list just because it's only
    # one level deep.
    # NOTE: this does NOT include the section name (e.g. "Game Concepts")
    # -- that's tracked once, separately, in `section` below, so it isn't
    # duplicated in two places.

    section: str
    # The section name this rule falls under, e.g. "Game Concepts".
    # DECISION: just the name, one field, no separate section-number field
    # and no lookup table. That kind of structure only earns its keep once
    # something actually needs to query "everything in section 7" -- add
    # it then, not now.

    kind: Literal["rule", "subrule"]
    # DECISION: only two values. "glossary" was cut from this list because
    # glossary terms are GlossaryEntry objects now, never Rule objects --
    # so this field is never asked to describe one. No fourth value for
    # section headers either: headers aren't stored as their own rows at
    # all, they just tell the parser what string to put in `section` for
    # the rules that follow.


# DECISION (already made by the plan, not re-opened here): cross-references
# like "see rule 201.3" stay as plain text wherever they show up -- inside
# Rule.text or inside a GlossaryEntry definition. They are not turned into
# links and not pulled into their own field. If a future feature wants to
# jump straight to a referenced rule, that's a field to add at that point,
# with its own line in DECISIONS.md -- not something to build now on spec.


class Chunk(BaseModel):
    """One retrievable unit -- the thing the search index actually holds and
    the thing a citation points back to. Rules and glossary entries both
    become Chunks so there's a single flat index to search; `kind` is what
    lets the display/citation step tell them apart.

    The chunking rules that turn Rule/GlossaryEntry objects into Chunks live
    in DECISIONS.md ("Chunking: label-like rules don't get their own chunk")
    and are implemented in ingest/chunker.py -- this model is just the shape
    they produce.
    """

    source_id: str
    # Citation anchor. A rule number ("104.3a") when kind == "rule", or the
    # glossary term ("Ability") when kind == "glossary". This is what an
    # answer cites so a human can go verify it in the actual rules.

    kind: Literal["rule", "glossary"]
    # "rule" covers both plain rules and subrules -- the rule/subrule split
    # matters at parse time, not at retrieval time, so it's collapsed here.

    section: str
    # "Game Concepts" etc. for rules; "Glossary" for glossary entries.

    text: str
    # The text that actually gets embedded and BM25-indexed. For a rule:
    # immediate-parent context prepended + the rule's own text + any
    # examples appended. For a glossary entry: the term plus its
    # definition(s). Label-like rules never produce a Chunk of their own --
    # their text reaches the index only as the prepended parent-context of
    # their children.

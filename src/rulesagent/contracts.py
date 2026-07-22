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
    # What the GENERATOR reads and what a citation displays -- the complete,
    # human-facing form. For a rule: immediate-parent context prepended + the
    # rule's own text + any examples appended. For a glossary entry: the term
    # plus its definition(s). Label-like rules never produce a Chunk of their
    # own -- their text reaches the index only via their children.

    embed_text: str
    # What the RETRIEVAL indexes (vector + BM25) actually embed/tokenize --
    # the maximally-DISTINCTIVE form. DECISION (see DECISIONS.md "split
    # embedded text from context text"): `text` was doing two jobs with
    # opposite needs -- the generator wants completeness, retrieval wants
    # distinctiveness -- and prepending a long shared parent preamble onto
    # every sibling made a whole rule-family embed to nearly the same vector
    # (the 601.2 family sat at 0.83-0.99 cosine). So embed_text is own text +
    # examples, and prepends the immediate parent's text ONLY when that parent
    # is folded (label-like, has no chunk of its own) -- because then the
    # parent's words exist nowhere else in the index and the child must carry
    # them. When the parent has its own chunk, its text is already retrievable
    # and duplicating it is pure noise. For glossary entries embed_text == text.


class Retrieved(BaseModel):
    """One search hit: a Chunk plus the score the retriever gave it. Kept as
    its own type (rather than a bare tuple) so every retriever -- BM25,
    vector, hybrid -- returns the same shape and the eval harness doesn't
    care which one produced it."""

    chunk: Chunk
    score: float


class EvalQuestion(BaseModel):
    """One labeled eval question. `gold` is the list of chunk source_ids that
    a correct retrieval must surface -- this is the human-authored judgment
    the whole eval rests on (see DESIGN.md "Do not delegate": the question
    set and what counts as correct are Jon's, not a model's).

    Loaded from evals/questions.jsonl, one JSON object per line.
    """

    id: str
    question: str
    gold: list[str]
    # Chunk source_ids (rule numbers like "104.3a", or glossary terms) that
    # count as a correct hit. NOTE: a gold id must be a source_id that
    # actually EXISTS as a chunk -- citing a folded label (e.g. "701.5"
    # "Cast", which has no chunk of its own) can never be retrieved. The
    # harness validates this and warns.

    match: Literal["any", "all", "groups"] = "any"
    # How the gold ids are scored:
    #   "any" (default): the gold ids are ALTERNATIVES -- finding any one in
    #     the top k is a correct hit. Right when the same answer is restated
    #     in two places (e.g. an SBA and its cross-reference), or when either
    #     rule independently answers the question.
    #   "all": the gold ids are ALL REQUIRED -- a true interaction where the
    #     answer isn't complete without every piece (e.g. trample + deathtouch
    #     needs both keyword definitions). Counts as a hit at k only if EVERY
    #     gold id lands within the top k.
    #   "groups": the general form -- an AND of ORs. Uses `gold_groups` below
    #     instead of `gold`: a hit iff EVERY group has at least one member in
    #     the top k. Added because ablation (docs/plan-card-gold-ablation.md)
    #     found real MIXED gold that any/all can't express -- e.g. c004 needs
    #     ALL of [704.3],[120.5],[117.2d] AND ANY ONE of the interchangeable
    #     lethal-damage rules [704.5g,704.4,120.6,302.7]. "any" and "all" are
    #     just the two degenerate cases of this (one big OR-group, or N
    #     one-member groups); the harness derives groups from match, so
    #     existing any/all questions score identically -- see run_eval.hit_at.

    gold_groups: list[list[str]] = []
    # Only used when match=="groups". Each inner list is an OR-group (satisfied
    # by any one member in the top k); the question is a hit iff ALL groups are
    # satisfied. `gold` should still hold the flat union of every id here, for
    # display and the "gold ids exist as chunks" validation.

    kind: Literal["rule", "glossary", "interaction", "other", "card-interaction"] = "rule"
    # Coarse question type, for breaking down recall by category later.
    # "interaction" = two rules combine; "card-interaction" = a card+rules
    # question in the separate card eval set (evals/cards.jsonl).


class RewrittenQuery(BaseModel):
    """The rewriter's output: one or more search-friendly rephrasings of the
    user's question, in the Comprehensive Rules' own vocabulary, plus an
    optional side-channel question for the user. See plan #3a
    (docs/plan-3a-query-rewriting.md, "Clarification: ask, but never wait")
    for the full rationale -- the short version: retrieval must never block
    on a human who isn't there, so `clarification` is an extra field, not a
    gate.
    """

    original: str
    # The user's question, verbatim, before any rewriting. Kept alongside
    # the rewrites so a caller always has what was actually asked -- e.g. to
    # log it, or to fuse it back into retrieval explicitly (the eval's
    # `+orig` variant) -- without threading the original question through
    # separately.

    queries: list[str]
    # One or more rewrites, in Comprehensive-Rules vocabulary. ALWAYS
    # non-empty -- retrieval never blocks on the rewriter. On a failed or
    # unparseable model response this falls back to [original] rather than
    # raising, so a rewriter outage degrades to "search for what the user
    # typed" instead of crashing the agent.

    clarification: str | None = None
    # An optional question worth asking the user back -- e.g. "did you mean
    # two-player or Commander?" -- set only when the correct answer would
    # materially differ between readings. Never gates retrieval: `queries`
    # is already populated regardless of whether this is set. In the eval
    # this is recorded and ignored; in the interactive demo (#4) it's shown
    # alongside the answer so the user can refine without blocking on it.


class Card(BaseModel):
    """A single card's Scryfall data, as fetched by tools/scryfall.py.

    DECISION: mirrors Chunk's role for cards -- this is the shape the
    generator prompt gets enriched with when the question `[bracket]`-
    references a card, alongside (not instead of) the retrieved rules.
    """

    name: str
    # The card's resolved name (Scryfall's, not necessarily the user's exact
    # spelling -- fuzzy name lookup and oracle_id lookup both resolve to
    # this). What answers should display when citing the card.

    oracle_text: str
    # The card's actual rules text. DECISION: for double-faced/split cards
    # where Scryfall puts text in `card_faces[]` instead of a top-level
    # `oracle_text`, both faces are joined here (see scryfall.py) so a card
    # never loses half its text just because of how it's printed.

    type_line: str
    # e.g. "Instant" or "Legendary Creature -- Human Wizard".

    mana_cost: str
    # e.g. "{2}{U}". Empty string for cards with no mana cost (lands, and
    # the back face of some double-faced cards).

    oracle_id: str
    # Scryfall's stable cross-printing UUID -- the same card printed in ten
    # sets shares one oracle_id. This is what `[uuid]` tokens in a question
    # resolve against, so answers can reference a card independent of which
    # printing/art a user has in mind.

    rulings: list[str] = []
    # Every ruling `comment` Scryfall has for this card, oldest schema
    # first (see scryfall.py `get_card`). DECISION: "add all of them for
    # now" (Jon) -- no relevance filtering against the question. Defaults
    # to [] so a card with no rulings doesn't force callers to pass one.


class Answer(BaseModel):
    """The generator's output: a cited answer, or an honest 'not found.'
    Structured so the answer-accuracy eval can check citations and the
    low-confidence path separately from the prose."""

    text: str
    # The answer in plain language. When answered is False, this explains
    # what the provided rules were missing rather than guessing.

    citations: list[str]
    # The rule numbers / glossary terms the answer actually relied on --
    # must come from the chunks provided in context, not outside knowledge.

    answered: bool
    # True if the provided rules were sufficient to answer. False triggers
    # the low-confidence path: the bot says it can't answer from the rules
    # it was given rather than hallucinating. This is the groundedness guard.

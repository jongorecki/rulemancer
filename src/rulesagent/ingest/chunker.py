"""Turns parsed Rule/GlossaryEntry records into the flat list of Chunks the
index actually holds. See DECISIONS.md ("Chunking: label-like rules don't
get their own chunk") for the reasoning behind the label heuristic below,
and tests/test_golden_chunker.py for the cases it's verified against.
"""

from rulesagent.contracts import Chunk, GlossaryEntry, Rule

# Trailing characters stripped before checking how a label-candidate's text
# ends. U+201D is the closing curly double-quote MTG rules text uses.
_TRAILING_CLOSERS = "”)"
_SENTENCE_ENDERS = (".", ":", "?")
# NOTE: "!" is deliberately excluded -- flavor-named keywords like
# "For Mirrodin!" end in "!" but are still labels, not sentences.

_LABEL_MAX_WORDS = 6


def _rules_with_children(rules: list[Rule]) -> set[str]:
    """Numbers of every rule that has at least one child rule underneath it.

    A rule's `parent_chain` already records its exact ancestor numbers (see
    contracts.py), so membership there is the precise "is this a child of
    that rule" check -- more precise than a raw string-prefix test, which
    would wrongly treat e.g. "100.10" as a child of "100.1"."""
    parents: set[str] = set()
    for rule in rules:
        parents.update(rule.parent_chain)
    return parents


def _is_label_like(rule: Rule, numbers_with_children: set[str]) -> bool:
    if rule.number not in numbers_with_children:
        return False
    if len(rule.text.split()) > _LABEL_MAX_WORDS:
        return False
    stripped = rule.text.rstrip(_TRAILING_CLOSERS)
    if stripped.endswith(_SENTENCE_ENDERS):
        return False
    return True


def _immediate_parent_text(rule: Rule, rules_by_number: dict[str, Rule]) -> str | None:
    """The text of the nearest ancestor in `rule.parent_chain` that exists
    as an actual Rule. `parent_chain` is ordered outermost-first, so the
    nearest ancestor is the last entry; group headers like "205" never show
    up as a Rule, so we keep walking outward until we find one that does
    (or run out, meaning no prepend)."""
    for ancestor_number in reversed(rule.parent_chain):
        ancestor = rules_by_number.get(ancestor_number)
        if ancestor is not None:
            return ancestor.text
    return None


def _chunk_for_rule(rule: Rule, rules_by_number: dict[str, Rule]) -> Chunk:
    parent_text = _immediate_parent_text(rule, rules_by_number)
    parts = [parent_text] if parent_text is not None else []
    parts.append(rule.text)
    parts.extend(rule.examples)
    return Chunk(
        source_id=rule.number,
        kind="rule",
        section=rule.section,
        text=" ".join(parts),
    )


def _chunk_for_glossary(entry: GlossaryEntry) -> Chunk:
    text = entry.term + ". " + " ".join(entry.definitions)
    return Chunk(
        source_id=entry.term,
        kind="glossary",
        section="Glossary",
        text=text,
    )


def chunk_rules(rules: list[Rule], glossary: list[GlossaryEntry]) -> list[Chunk]:
    rules_by_number = {rule.number: rule for rule in rules}
    numbers_with_children = _rules_with_children(rules)

    chunks: list[Chunk] = []
    for rule in rules:
        if _is_label_like(rule, numbers_with_children):
            continue
        chunks.append(_chunk_for_rule(rule, rules_by_number))

    for entry in glossary:
        chunks.append(_chunk_for_glossary(entry))

    return chunks

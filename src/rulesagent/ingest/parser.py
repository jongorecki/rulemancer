"""Parses the Magic: The Gathering Comprehensive Rules TXT into Rule and
GlossaryEntry records. See DESIGN.md (Day 1 section) and DECISIONS.md for
the edge cases and choices this implements, and tests/test_golden_parser.py
for the cases it's verified against.
"""

import re
from pathlib import Path

from rulesagent.contracts import GlossaryEntry, Rule

SECTION_HEADER_RE = re.compile(r"^[1-9]\.\s+(.+)$")
# The trailing period is OPTIONAL because the source is not consistent about
# it. `data/raw/MagicCompRules 20260619.txt` line 2719 reads "606.5 If the
# total cost..." with no period, so the strict form silently skipped it: rule
# 606.5 and its example were dropped from the corpus entirely -- not folded
# into a child, simply absent, leaving a hole between 606.4 and 606.6. Nothing
# raised. No retriever could surface it and no answer could cite it, which is
# why rg4420 (whose judge answer quotes 606.5 verbatim) was unanswerable.
#
# Measured blast radius of relaxing it: 3617 chunks -> 3618, added ['606.5'],
# removed []. A full sweep of the CR found exactly one line with this typo,
# against 1,169 well-formed rule lines, so the tolerance costs nothing and
# guards against the next one.
RULE_RE = re.compile(r"^(\d+\.\d+)\.?\s+(.+)$")
# Same tolerance as RULE_RE, for the mirror-image typo. Subrules normally carry
# NO period after the letter, but line 1059 reads "119.1d. In a two-player Brawl
# game..." with one, so the strict form skipped it and 119.1d vanished -- a hole
# between 119.1c and 119.1e that nothing reported. Found by
# tests/test_cr_parse_coverage.py the first time it ran, which is the argument
# for that test existing: the 606.5 sweep only looked at top-level rules and
# could never have seen this one.
SUBRULE_RE = re.compile(r"^(\d+\.\d+[a-z]+)\.?\s+(.+)$")
EXAMPLE_RE = re.compile(r"^Example:\s*(.+)$")
SENSE_RE = re.compile(r"^\d+\.\s+(.+)$")


def _parent_chain(number: str) -> list[str]:
    numeric_part = number.rstrip("abcdefghijklmnopqrstuvwxyz")
    has_letter = numeric_part != number
    parts = numeric_part.split(".")
    limit = len(parts) if has_letter else len(parts) - 1
    return [".".join(parts[:i]) for i in range(1, limit + 1)]


def _find_rules_region_start(lines: list[str]) -> int:
    """The Contents page near the top of the file repeats the same
    heading text ("1. Game Concepts", "Glossary", "Credits") that the real
    sections use later, so we can't find the real body by searching for
    that text from the top of the file. But the Contents page never
    contains a full rule line like "100.1." -- only section/group
    headings. So: find the first real rule, then walk backward to the
    nearest section heading right before it. That heading is guaranteed
    to be the real "1. Game Concepts," not the Contents-page one, because
    it's the one immediately preceding actual rule text.
    """
    first_rule_idx = next(i for i, line in enumerate(lines) if RULE_RE.match(line.strip()))
    for i in range(first_rule_idx - 1, -1, -1):
        if SECTION_HEADER_RE.match(lines[i].strip()):
            return i
    raise ValueError("Found a first rule but no section heading before it.")


def _find_heading(lines: list[str], heading: str, start: int) -> int:
    """First line equal to `heading`, searching from `start` onward.
    Searching only from `start` (past the Contents page) is what avoids
    matching the Contents page's own "Glossary"/"Credits" lines.
    """
    for i in range(start, len(lines)):
        if lines[i].strip() == heading:
            return i
    raise ValueError(f"Could not find a '{heading}' heading after line {start}.")


def _parse_rules(lines: list[str]) -> list[Rule]:
    rules: list[Rule] = []
    current_section = ""
    pending: dict | None = None
    in_example = False

    def finalize():
        nonlocal pending
        if pending is not None:
            rules.append(Rule(**pending))
            pending = None

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            finalize()
            in_example = False
            continue

        section_match = SECTION_HEADER_RE.match(line)
        if section_match:
            finalize()
            in_example = False
            current_section = section_match.group(1).strip()
            continue

        rule_match = RULE_RE.match(line)
        if rule_match:
            finalize()
            number, text = rule_match.group(1), rule_match.group(2)
            pending = {
                "number": number,
                "text": text,
                "examples": [],
                "parent_chain": _parent_chain(number),
                "section": current_section,
                "kind": "rule",
            }
            in_example = False
            continue

        subrule_match = SUBRULE_RE.match(line)
        if subrule_match:
            finalize()
            number, text = subrule_match.group(1), subrule_match.group(2)
            pending = {
                "number": number,
                "text": text,
                "examples": [],
                "parent_chain": _parent_chain(number),
                "section": current_section,
                "kind": "subrule",
            }
            in_example = False
            continue

        example_match = EXAMPLE_RE.match(line)
        if example_match and pending is not None:
            pending["examples"].append(example_match.group(1))
            in_example = True
            continue

        # A plain continuation line: either the current rule/example text
        # wrapped onto a second physical line. Anything that shows up with
        # no pending entry open (e.g. a group header like "104. Ending the
        # Game") is skipped -- group headers are never modeled as Rule
        # rows, they only matter for the section headers above.
        if pending is not None:
            if in_example:
                pending["examples"][-1] = f'{pending["examples"][-1]} {line}'
            else:
                pending["text"] = f'{pending["text"]} {line}'

    finalize()
    return rules


def _build_definitions(body_lines: list[str]) -> list[str]:
    if not body_lines:
        return []
    if not SENSE_RE.match(body_lines[0]):
        # Single-sense entry: everything under the term is one definition.
        return [" ".join(body_lines)]

    # Multi-sense entry: each numbered line starts a new sense. A line that
    # doesn't start a new sense (the trailing "See rule..." line shared
    # across all senses, e.g. under "Ability") gets appended onto the last
    # sense instead -- see DECISIONS.md for why.
    definitions: list[str] = []
    for line in body_lines:
        sense_match = SENSE_RE.match(line)
        if sense_match:
            definitions.append(sense_match.group(1))
        else:
            definitions[-1] = f"{definitions[-1]} {line}"
    return definitions


def _parse_glossary(lines: list[str]) -> list[GlossaryEntry]:
    entries: list[GlossaryEntry] = []
    term: str | None = None
    body: list[str] = []
    start_of_block = True

    def finalize():
        nonlocal term, body
        if term is not None:
            entries.append(GlossaryEntry(term=term, definitions=_build_definitions(body)))
        term = None
        body = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            finalize()
            start_of_block = True
            continue
        if start_of_block:
            term = line
            start_of_block = False
        else:
            body.append(line)

    finalize()
    return entries


def parse_comprehensive_rules(path: str | Path) -> tuple[list[Rule], list[GlossaryEntry]]:
    # utf-8-sig strips the BOM the file starts with -- plain utf-8 would
    # leave it stuck to the front of the first line.
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [line.rstrip("\r") for line in text.split("\n")]

    region_start = _find_rules_region_start(lines)
    glossary_start = _find_heading(lines, "Glossary", region_start)
    credits_start = _find_heading(lines, "Credits", glossary_start)

    rules = _parse_rules(lines[region_start:glossary_start])
    glossary = _parse_glossary(lines[glossary_start + 1 : credits_start])

    return rules, glossary

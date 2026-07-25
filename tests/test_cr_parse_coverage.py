"""Guard against rules being SILENTLY dropped from the corpus.

Rule 606.5 was missing from the index entirely for the life of this project.
The source line reads "606.5 If the total cost..." with no period after the
number, `RULE_RE` required one, and the line was skipped. Nothing raised. No
retriever could surface it, no answer could cite it, and rg4420 -- whose judge
answer quotes 606.5 verbatim -- was unanswerable by construction. It surfaced
only because a gold-mining pass needed a chunk inventory and someone read the
source line.

The parser now tolerates the missing period, but that fixes ONE typo. These
tests fix the CLASS: they assert that everything in the source which looks
like a rule actually became a rule. A different malformation in a future CR
release (missing space, an en-dash, a stray character) reddens the suite
instead of silently shrinking the corpus.

This matters most on a CR UPDATE. The Comprehensive Rules are re-released with
every set, and the failure mode is not a crash -- it is a slightly smaller
corpus that still answers most questions, so nothing looks wrong.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

CR_PATH = ROOT / "data" / "raw" / "MagicCompRules 20260619.txt"

# Deliberately LOOSER than the parser's own regexes: a rule number at the start
# of a line, with or without the trailing period, followed by text. Anything
# matching this is something a human would read as a rule, so the parser had
# better have produced it.
LOOKS_LIKE_RULE = re.compile(r"^(\d+\.\d+)\.?\s+\S")
LOOKS_LIKE_SUBRULE = re.compile(r"^(\d+\.\d+[a-z]+)\.?\s+\S")


@pytest.fixture(scope="module")
def parsed():
    if not CR_PATH.exists():
        pytest.skip(f"CR not present at {CR_PATH.name}")
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    return rules, glossary


def _source_rule_numbers() -> set[str]:
    found = set()
    for line in CR_PATH.read_text(encoding="utf-8").splitlines():
        m = LOOKS_LIKE_SUBRULE.match(line) or LOOKS_LIKE_RULE.match(line)
        if m:
            found.add(m.group(1))
    return found


def test_every_rule_shaped_line_was_parsed(parsed):
    """The load-bearing one. Every rule-shaped line in the source must appear
    as a parsed rule number -- otherwise something was skipped in silence."""
    rules, _ = parsed
    parsed_numbers = {r.number for r in rules}
    missing = sorted(_source_rule_numbers() - parsed_numbers)
    assert not missing, (
        f"{len(missing)} rule-shaped source line(s) did not parse into a rule: "
        f"{missing[:20]}. A malformation in the CR source is silently shrinking "
        f"the corpus -- these rules can never be retrieved or cited."
    )


def test_no_gaps_in_rule_numbering(parsed):
    """A cheap independent check on the same failure. Within a section, rule
    numbers run consecutively; a hole (606.4, 606.6 with no 606.5) is the
    signature of a dropped line even if the source malformation is one this
    module's regexes do not anticipate."""
    rules, _ = parsed
    by_section: dict[str, set[int]] = {}
    for r in rules:
        section, _, minor = r.number.partition(".")
        if minor.isdigit():
            by_section.setdefault(section, set()).add(int(minor))
    holes = []
    for section, minors in sorted(by_section.items()):
        for n in range(min(minors), max(minors)):
            if n not in minors and n != 0:
                holes.append(f"{section}.{n}")
    assert not holes, (
        f"gap(s) in rule numbering: {holes[:20]}. Each is a rule that exists in "
        f"the CR but not in the parsed corpus."
    )


def test_606_5_specifically_survives(parsed):
    """Regression pin for the rule that was actually lost. Its source line has
    no period after the number; if RULE_RE is ever tightened back, this fails
    before anything ships."""
    rules, glossary = parsed
    numbers = {r.number for r in rules}
    assert "606.5" in numbers, "606.5 dropped again -- RULE_RE's period is optional for a reason"
    ids = {c.source_id for c in chunk_rules(rules, glossary)}
    assert "606.5" in ids, "606.5 parsed but did not survive chunking"

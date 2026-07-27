"""The README is a public claim, so it gets a test like any other claim.

WHY: on 2026-07-27 the README still led with "31/31 correct" on 31 questions
while 1,409 questions had been measured, and still carried the rules-are-inert
conclusion that had already been overturned. A stale public claim is worse than
no claim, so the staleness is now a test failure rather than a memory.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
FIGURES = REPO / "docs" / "superpowers" / "plans" / "_verified-figures.md"

# Strings that were true once and are not true now. Each maps to why it died.
SUPERSEDED_CLAIMS: list[tuple[str, str]] = [
    ("31/31", "superseded by the 1,409-question headline run"),
    ("single worker with a lock", "caches moved to per-key SQLite writes"),
    ("dead weight", "the rules-are-inert conclusion was overturned"),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _percentages(text: str) -> set[str]:
    """Every percentage figure in a document, normalised to its digits."""
    return {m.group(1) for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%", text)}


def test_readme_has_no_superseded_claims():
    body = _read(README)
    found = [(claim, why) for claim, why in SUPERSEDED_CLAIMS if claim in body]
    assert not found, f"README still carries superseded claims: {found}"


def test_readme_does_not_quote_headline_to_three_digits():
    """85.88% implies a precision the instrument does not have."""
    body = _read(README)
    assert "85.88" not in body, (
        "the headline must read 'roughly 86%' with its error bars, "
        "not three significant figures"
    )


def test_readme_states_the_error_bars():
    body = _read(README).lower()
    assert "roughly 86%" in body, "the headline number is missing"
    assert "instrument variance" in body, (
        "the headline must carry the ~4pp judge instability alongside sampling error"
    )


def test_every_readme_percentage_is_traceable():
    """A percentage on the public page must appear in the verified figures file."""
    if not FIGURES.exists():
        pytest.skip("verified figures file not generated yet")
    readme_pcts = _percentages(_read(README))
    verified_pcts = _percentages(_read(FIGURES))
    untraceable = sorted(readme_pcts - verified_pcts)
    assert not untraceable, (
        f"README states percentages absent from the verified figures: {untraceable}"
    )

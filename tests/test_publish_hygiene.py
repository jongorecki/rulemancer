"""Nothing reaches a public repo that shouldn't. This runs over TRACKED files.

WHY tracked and not the working tree: the working tree contains .env and a pile
of scratch files that are correctly ignored. What matters is what `git push`
actually sends.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Require the key-shaped suffix, not just the prefix. A bare prefix (e.g.
# "sk-or-v1-") also matches this test's own source when a doc quotes these
# patterns in prose or in a code block -- that happened for real on
# 2026-07-27: docs/superpowers/plans/2026-07-27-evidence-surface.md embeds
# this file's own code and tripped test_no_key_shaped_strings_in_tracked_files
# on the regex literal alone, a false positive. Requiring real key-length
# characters after the prefix makes each pattern self-safe (the character
# right after the prefix in its own source is "[", which the character class
# does not match) without weakening detection of an actual leaked key.
KEY_PATTERNS = [
    re.compile(r"sk-ant-api[0-9]{2}-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    re.compile(r"\bpa-[A-Za-z0-9_-]{30,}"),
]

DROPPED = ["docs/archive/", "docs/HANDOFF-", "docs/OVERNIGHT-STATUS.md"]


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


def test_env_is_not_tracked():
    assert ".env" not in tracked_files()


def test_no_key_shaped_strings_in_tracked_files():
    offenders = []
    for rel in tracked_files():
        path = REPO / rel
        if not path.is_file() or path.suffix in {".png", ".pkl", ".db", ".woff2"}:
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in KEY_PATTERNS:
            if pattern.search(body):
                offenders.append((rel, pattern.pattern))
    assert not offenders, f"credential-shaped strings in tracked files: {offenders}"


def test_internal_docs_are_dropped_from_head():
    tracked = tracked_files()
    still_here = [f for f in tracked if any(f.startswith(d) for d in DROPPED)]
    assert not still_here, f"internal docs still tracked: {still_here}"


def test_cr_text_and_vector_store_are_not_tracked():
    tracked = tracked_files()
    leaked = [f for f in tracked if f.startswith(("data/raw/", "data/parsed/"))]
    assert not leaked, f"corpus data must not ship: {leaked}"

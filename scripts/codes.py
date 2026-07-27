"""Mint / list / revoke gated-demo access codes (docs/superpowers/plans/
2026-07-27-gated-demo.md Task 3).

    python scripts/codes.py new --label "Cribl -- Jane R." [--max-queries 25] [--notes "..."]
    python scripts/codes.py list
    python scripts/codes.py revoke <code>

Codes are "word-word-word-NN" -- three short words plus a two-digit number,
e.g. "beech-falcon-quill-85" (the design spec's prose: "three readable words
+ digits"). With 60 words this is 60 x 60 x 60 x 100 = 21,600,000 possible
codes, vs. 360,000 for the two-word shape -- 60x harder to guess, which
matters because every guessed code costs Jon real API credits, and still
short enough to read aloud or type off a phone.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rulesagent.demo_db import (  # noqa: E402
    DEFAULT_DEMO_DB,
    create_code,
    get_code_by_value,
    list_codes,
    revoke_code,
)

WORDLIST = [
    "raptor", "quill", "cedar", "otter", "birch", "heron", "maple", "finch",
    "elm", "osprey", "fir", "lark", "pine", "swift", "yew", "plover", "ash",
    "crane", "willow", "vole", "spruce", "wren", "alder", "kite", "hazel",
    "falcon", "poplar", "grouse", "beech", "sparrow", "aspen", "raven",
    "hemlock", "condor", "juniper", "harrier", "cypress", "kestrel", "linden",
    "merlin", "walnut", "peregrine", "hickory", "gannet", "sycamore", "ibis",
    "dogwood", "puffin", "chestnut", "curlew", "magnolia", "tern", "rowan",
    "grebe", "sequoia", "shrike", "larch", "warbler",
]


def generate_code(existing: set[str] | None = None) -> str:
    existing = existing or set()
    for _ in range(50):
        word1 = secrets.choice(WORDLIST)
        word2 = secrets.choice(WORDLIST)
        word3 = secrets.choice(WORDLIST)
        digits = f"{secrets.randbelow(100):02d}"
        code = f"{word1}-{word2}-{word3}-{digits}"
        if code not in existing:
            return code
    raise RuntimeError("could not generate a unique code after 50 attempts")


def _cmd_new(args: argparse.Namespace) -> int:
    if not args.label.strip():
        print("error: --label cannot be empty (Jon needs to know who holds this code)",
              file=sys.stderr)
        return 1
    existing = {row["code"] for row in list_codes(args.db)}
    code = generate_code(existing=existing)
    create_code(args.db, code, args.label, max_queries=args.max_queries, notes=args.notes)
    print(f"minted code: {code}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = list_codes(args.db)
    if not rows:
        print("(no codes minted yet)")
        return 0
    for row in rows:
        status = "REVOKED" if row["revoked_at"] else "active"
        print(f"{row['code']:20s} {status:8s} max_queries={row['max_queries']!s:5s} "
              f"label={row['label']!r} created={row['created_at']}")
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    row = get_code_by_value(args.db, args.code)
    if row is None:
        print(f"no such code: {args.code}", file=sys.stderr)
        return 1
    revoke_code(args.db, row["id"])
    print(f"revoked: {args.code}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mint/list/revoke gated-demo access codes")
    parser.add_argument("--db", type=Path, default=DEFAULT_DEMO_DB)
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="mint a new code")
    p_new.add_argument("--label", required=True)
    p_new.add_argument("--max-queries", type=int, default=25, dest="max_queries")
    p_new.add_argument("--notes", default="")
    p_new.set_defaults(func=_cmd_new)

    p_list = sub.add_parser("list", help="list all codes")
    p_list.set_defaults(func=_cmd_list)

    p_revoke = sub.add_parser("revoke", help="revoke a code")
    p_revoke.add_argument("code")
    p_revoke.set_defaults(func=_cmd_revoke)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

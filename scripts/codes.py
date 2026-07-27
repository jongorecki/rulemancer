"""Mint / list / revoke gated-demo access codes (docs/superpowers/plans/
2026-07-27-gated-demo.md Task 3).

    python scripts/codes.py new --label "Cribl -- Jane R." [--max-queries 25] [--notes "..."]
    python scripts/codes.py list
    python scripts/codes.py revoke <code>

Codes are "word-word-word-NN" -- three short words plus a two-digit number,
e.g. "beech-falcon-quill-85". generate_code()/WORDLIST live in
rulesagent.demo_db now (task-admin-mint-report.md), so this CLI and the
/admin mint form share the exact same generator and collision handling --
never two generators that could drift.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rulesagent.demo_db import (  # noqa: E402
    DEFAULT_DEMO_DB,
    WORDLIST,
    create_code,
    generate_code,
    get_code_by_value,
    list_codes,
    revoke_code,
)


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

# Slice 4 Task 3. Calls scripts/codes.py's main() directly (same in-process
# convention as tests/test_check_cr_update.py) -- no subprocess.

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codes as codes_cli  # noqa: E402

from rulesagent.demo_db import get_code_by_value, list_codes  # noqa: E402


def test_generate_code_shape():
    code = codes_cli.generate_code()
    word1, word2, digits = code.split("-")
    assert word1 in codes_cli.WORDLIST
    assert word2 in codes_cli.WORDLIST
    assert digits.isdigit() and len(digits) == 2


def test_generate_code_avoids_collisions():
    first = codes_cli.generate_code()
    second = codes_cli.generate_code(existing={first})
    assert second != first


def test_new_command_mints_and_prints_code(tmp_path, capsys):
    db = tmp_path / "demo.db"
    rc = codes_cli.main(["--db", str(db), "new", "--label", "Cribl -- Jane R."])
    out = capsys.readouterr().out

    assert rc == 0
    rows = list_codes(db)
    assert len(rows) == 1
    assert rows[0]["label"] == "Cribl -- Jane R."
    assert rows[0]["code"] in out  # the minted code is printed for Jon to copy


def test_new_command_respects_max_queries_flag(tmp_path):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "Test", "--max-queries", "10"])
    row = list_codes(db)[0]
    assert row["max_queries"] == 10


def test_new_command_defaults_max_queries_to_25(tmp_path):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "Test"])
    row = list_codes(db)[0]
    assert row["max_queries"] == 25


def test_list_command_prints_every_code(tmp_path, capsys):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "First"])
    codes_cli.main(["--db", str(db), "new", "--label", "Second"])
    capsys.readouterr()  # discard "new" output

    rc = codes_cli.main(["--db", str(db), "list"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "First" in out
    assert "Second" in out


def test_revoke_command_marks_code_revoked(tmp_path, capsys):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "Test"])
    minted = capsys.readouterr().out.strip().splitlines()[-1].split()[-1]

    rc = codes_cli.main(["--db", str(db), "revoke", minted])

    assert rc == 0
    assert get_code_by_value(db, minted)["revoked_at"] is not None


def test_revoke_unknown_code_returns_nonzero(tmp_path):
    db = tmp_path / "demo.db"
    rc = codes_cli.main(["--db", str(db), "revoke", "no-such-code-99"])
    assert rc != 0

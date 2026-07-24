"""evals/build_prompts_variant.py: parameterising --src/--out-prefix/
--variants and the overwrite guard added so a c020-only capture can never
collide with the frozen four-file evidence base
(_prompts_variant_{A,B,C,D}.json) from the completed v3/v4nl x inject
experiment.

No real capture is used -- a small synthetic {qid: {system, user}} fixture
built with the REAL build_prompt()/SYSTEM_VERSIONS[3] (both pure, no
network/API calls) stands in for `_prompts_C.json`. No Anthropic/
OpenRouter/Voyage calls happen anywhere in this file; cards.jsonl (real,
on disk) is never actually consulted because the synthetic qids never
appear in it, so card_qids naturally comes out empty without needing to
mock get_card()/Scryfall.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

import build_prompts_variant as bpv  # noqa: E402

from rulesagent.generate.answer import SYSTEM_VERSIONS, build_prompt  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _synthetic_capture(tmp_path: Path, qids: list[str]) -> Path:
    """A well-formed, rules-only (no card section) synthetic capture at
    PROMPT_VERSION 3 -- built via the real build_prompt() so gate 5
    (production parity) and gate 1 (v3 digest) both pass for real reasons,
    not because the fixture was hand-shaped to satisfy them."""
    prompts = {}
    for qid in qids:
        question = f"What happens when {qid} resolves with no targets?"
        system, user = build_prompt(question, [], [])
        assert system == SYSTEM_VERSIONS[3]  # sanity: matches gate 1's digest
        prompts[qid] = {"system": system, "user": user}
    capture = {
        "rewrite_version": "test-v1",
        "ruling_query_mode": "test-mode",
        "n_questions": len(qids),
        "prompts": prompts,
    }
    path = tmp_path / "synthetic_capture.json"
    path.write_text(json.dumps(capture), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. default invocation still targets the original source and output names
#    (config resolution only -- never touches real evals/answers/, which
#    doesn't exist in this worktree)
# ---------------------------------------------------------------------------

def test_default_args_resolve_to_original_source():
    args = bpv.build_arg_parser().parse_args([])
    assert args.src == bpv.SRC
    assert args.src.name == "_prompts_C.json"
    assert args.out_prefix == "_prompts_variant_"
    assert args.variants == "A,B,C,D"
    assert args.force is False
    assert args.check is False


def test_default_out_path_names_unchanged():
    for letter in "ABCD":
        assert bpv.out_path(letter, "_prompts_variant_") == (
            bpv.OUT_DIR / f"_prompts_variant_{letter}.json"
        )


# ---------------------------------------------------------------------------
# 2. --src + --out-prefix writes only the expected new filenames
# ---------------------------------------------------------------------------

def test_src_and_out_prefix_write_only_expected_filenames(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z020"])

    rc = bpv.main(["--src", str(src), "--out-prefix", "_prompts_c020_variant_"])

    assert rc == 0
    written = {p.name for p in out_dir.iterdir()}
    assert written == {
        "_prompts_c020_variant_A.json",
        "_prompts_c020_variant_B.json",
        "_prompts_c020_variant_C.json",
        "_prompts_c020_variant_D.json",
    }
    # the old default naming must NOT have been touched
    assert not any(n.startswith("_prompts_variant_") for n in written)


# ---------------------------------------------------------------------------
# 3. --variants A,D writes exactly two files
# ---------------------------------------------------------------------------

def test_variants_subset_writes_exactly_two_files(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z020"])

    rc = bpv.main([
        "--src", str(src),
        "--out-prefix", "_prompts_c020_variant_",
        "--variants", "A,D",
    ])

    assert rc == 0
    written = {p.name for p in out_dir.iterdir()}
    assert written == {
        "_prompts_c020_variant_A.json",
        "_prompts_c020_variant_D.json",
    }


def test_unknown_variant_letter_rejected(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z020"])

    rc = bpv.main(["--src", str(src), "--variants", "A,Q"])

    assert rc != 0
    assert list(out_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# 4. refusing to clobber an existing output, and --force overriding it
# ---------------------------------------------------------------------------

def test_refuses_to_overwrite_existing_output(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z020"])

    sentinel_path = out_dir / "_prompts_c020_variant_A.json"
    sentinel_path.write_text("SENTINEL -- must not be touched", encoding="utf-8")

    rc = bpv.main([
        "--src", str(src),
        "--out-prefix", "_prompts_c020_variant_",
        "--variants", "A",
    ])

    assert rc != 0
    assert sentinel_path.read_text(encoding="utf-8") == "SENTINEL -- must not be touched"


def test_force_overrides_existing_output(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z020"])

    sentinel_path = out_dir / "_prompts_c020_variant_A.json"
    sentinel_path.write_text("SENTINEL -- must not be touched", encoding="utf-8")

    rc = bpv.main([
        "--src", str(src),
        "--out-prefix", "_prompts_c020_variant_",
        "--variants", "A",
        "--force",
    ])

    assert rc == 0
    written = json.loads(sentinel_path.read_text(encoding="utf-8"))
    assert written["variant"] == "A"
    assert "z020" in written["prompts"]


def test_the_existing_four_evidence_files_are_unclobberable_by_accident(tmp_path, monkeypatch):
    """The motivating scenario: running the script against a NEW capture
    but with the OLD default output naming must never touch the frozen
    four-file evidence base."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    # stand-ins for the frozen evidence base, at the DEFAULT naming
    frozen = {}
    for letter in "ABCD":
        p = out_dir / f"_prompts_variant_{letter}.json"
        p.write_text(f"FROZEN EVIDENCE {letter}", encoding="utf-8")
        frozen[letter] = p
    src = _synthetic_capture(tmp_path, ["z020"])

    # accidental invocation: new --src, but no --out-prefix override
    rc = bpv.main(["--src", str(src)])

    assert rc != 0
    for letter, p in frozen.items():
        assert p.read_text(encoding="utf-8") == f"FROZEN EVIDENCE {letter}"


# ---------------------------------------------------------------------------
# 5. gates still report PASS on a well-formed synthetic source
# ---------------------------------------------------------------------------

def test_gates_pass_on_well_formed_single_question_source(tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z020"])

    rc = bpv.main(["--src", str(src), "--out-prefix", "_prompts_c020_variant_"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "DONE -- all gates PASS." in out
    assert "FAIL" not in out


def test_gates_pass_on_well_formed_multi_question_source(tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    src = _synthetic_capture(tmp_path, ["z001", "z002", "z003"])

    rc = bpv.main([
        "--src", str(src),
        "--out-prefix", "_prompts_synth_variant_",
        "--variants", "A,D",
    ])

    out = capsys.readouterr().out
    assert rc == 0
    assert "DONE -- all gates PASS." in out
    assert "FAIL" not in out
    # derived-from-source expectation, not the hardcoded 50-question count
    assert "question ids: 3 (expect 3)" in out


def test_default_src_still_checks_against_lib_v3ab_all_qids(tmp_path, monkeypatch, capsys):
    """A --src capture that's short of the real 50 questions must still be
    caught as incomplete WHEN it claims to be the default source (gate 1's
    id-completeness check must not have been silently defanged)."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(bpv, "OUT_DIR", out_dir)
    # deliberately build a capture at the (monkeypatched) "default" path
    # that is missing questions relative to lib_v3ab.ALL_QIDS
    src = _synthetic_capture(tmp_path, ["z020"])
    monkeypatch.setattr(bpv, "SRC", src)

    rc = bpv.main([])  # no --src -> args.src default == bpv.SRC == our short capture

    out = capsys.readouterr().out
    assert rc != 0
    assert "id set does not match ALL_QIDS" in out or "ABORT" in out

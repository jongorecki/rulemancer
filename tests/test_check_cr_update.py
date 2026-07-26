# Tests for scripts/check_cr_update.py -- see docs/spec-cr-update-check.md
# for the design this implements.
#
# Style note: unit-level classifier tests use small HAND-BUILT Rule objects
# (never invented MTG facts -- the text strings are placeholders, not rules
# claims) so they run instantly and don't depend on parsing the real CR.
# The end-to-end tests exercise the full pipeline (real parser, real
# chunker) against the real CR file plus small synthetic mutations of it,
# matching the verification list in the spec's section 6.
#
# One synthetic-renumber wrinkle worth recording: the spec's own example
# ("rename 704.5n to 704.5zz") trips test_no_gaps_in_subrule_letters,
# because 704.5n is NOT the last lettered subrule under 704.5 (p..z still
# follow it) -- an isolated rename with nothing cascading is exactly the
# gap-in-lettering signature that check exists to catch, and a REAL CR
# renumber always cascades the rest of the family rather than leaving a
# hole. test_synthetic_renumber_end_to_end below uses a text SWAP between
# two plain top-level rules (104.3 <-> 104.4) instead: same property being
# tested (byte-identical text moves to a different number, checker proposes
# exactly that remap), but without an artificial gap that has nothing to do
# with what's being verified. test_classify_rules_renumbered_unit below
# tests the classifier directly against the literal 704.5n/704.5zz shape
# from the spec, bypassing step 1 entirely, so that exact scenario is still
# covered.

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rulesagent.contracts import GlossaryEntry, Rule  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

import check_cr_update as ccu  # noqa: E402

CR_PATH = ROOT / "data" / "raw" / "MagicCompRules 20260619.txt"


def _rule(number: str, text: str, *, kind: str = "rule", section: str = "Test", parent_chain=None) -> Rule:
    return Rule(
        number=number, text=text, examples=[], kind=kind, section=section,
        parent_chain=parent_chain if parent_chain is not None else [number.split(".")[0]],
    )


# --- normalize() / rule_fingerprint() -------------------------------------

def test_normalize_collapses_whitespace():
    assert ccu.normalize("A   rule   with\nextra   space.") == "A rule with extra space."


def test_normalize_folds_curly_quotes_and_apostrophes():
    text = "A player’s hand is “empty.”"
    assert ccu.normalize(text) == 'A player\'s hand is "empty."'


def test_normalize_strips_leading_repeated_rule_number():
    assert ccu.normalize("704.5n This ability is a loyalty ability.") == "This ability is a loyalty ability."


def test_rule_fingerprint_stable_across_whitespace_and_quote_style():
    a = ccu.rule_fingerprint("A player’s hand  is empty.")
    b = ccu.rule_fingerprint("A player's hand is  empty.")
    assert a == b


def test_rule_fingerprint_differs_for_different_text():
    a = ccu.rule_fingerprint("Text one.")
    b = ccu.rule_fingerprint("Text two.")
    assert a != b


def test_rule_fingerprint_is_16_hex_chars():
    fp = ccu.rule_fingerprint("Some rule text.")
    assert len(fp) == 16
    int(fp, 16)  # raises if not hex


# --- classify_rules() -----------------------------------------------------

def test_classify_unchanged():
    old = [_rule("100.1", "Same text.")]
    new = [_rule("100.1", "Same text.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    assert classes["100.1"].cls == "unchanged"
    assert added == []


def test_classify_rules_renumbered_unit():
    """The spec's own literal example (704.5n -> 704.5zz), tested directly
    against the classifier so step 1's gap-detection (a real but separate
    concern, see module docstring above) never enters the picture."""
    old = [_rule("704.5n", "This is a loyalty ability.")]
    new = [_rule("704.5zz", "This is a loyalty ability.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    rc = classes["704.5n"]
    assert rc.cls == "renumbered"
    assert rc.target == "704.5zz"
    assert added == []  # the destination isn't "added" -- its text came from somewhere


def test_classify_edited_same_number_different_text():
    old = [_rule("100.1", "Original wording.")]
    new = [_rule("100.1", "Different wording entirely.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    assert classes["100.1"].cls == "edited"
    assert added == []  # same slot existed before -- edited, not added


def test_classify_deleted_when_text_and_number_both_gone():
    old = [_rule("100.1", "This rule vanishes.")]
    new = [_rule("100.2", "Unrelated rule.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    assert classes["100.1"].cls == "deleted"


def test_classify_added_brand_new_number_new_content():
    old = [_rule("100.1", "Existing rule.")]
    new = [_rule("100.1", "Existing rule."), _rule("100.2", "Brand new rule nobody had before.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    assert classes["100.1"].cls == "unchanged"
    assert added == ["100.2"]


def test_classify_ambiguous_duplicate_text_in_new():
    """Same text shows up at two different new numbers -- can't tell which
    is the "real" destination, so both stay flagged rather than guessed."""
    old = [_rule("100.1", "Duplicate text.")]
    new = [_rule("100.1", "Something else."), _rule("100.2", "Duplicate text."), _rule("100.3", "Duplicate text.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    rc = classes["100.1"]
    assert rc.cls == "ambiguous"
    assert rc.candidates == ["100.2", "100.3"]


def test_classify_swap_two_rules_both_renumbered():
    old = [_rule("104.3", "Text A."), _rule("104.4", "Text B.")]
    new = [_rule("104.3", "Text B."), _rule("104.4", "Text A.")]
    classes, added, _, _ = ccu.classify_rules(old, new)
    assert classes["104.3"].cls == "renumbered" and classes["104.3"].target == "104.4"
    assert classes["104.4"].cls == "renumbered" and classes["104.4"].target == "104.3"
    assert added == []


# --- chunk_id_diff() --------------------------------------------------------

def test_chunk_id_diff_added_removed_modified():
    old_rules = [_rule("100.1", "Old text."), _rule("100.2", "Stays the same.")]
    new_rules = [_rule("100.1", "New text, edited in place."), _rule("100.3", "Brand new rule.")]
    added, removed, modified, old_ids, new_ids = ccu.chunk_id_diff(old_rules, [], new_rules, [])
    assert added == {"100.3"}
    assert removed == {"100.2"}
    assert modified == {"100.1"}
    assert old_ids == {"100.1", "100.2"}
    assert new_ids == {"100.1", "100.3"}


def test_chunk_id_diff_identity_is_empty():
    rules = [_rule("100.1", "Text."), _rule("100.2", "More text.")]
    added, removed, modified, old_ids, new_ids = ccu.chunk_id_diff(rules, [], rules, [])
    assert added == set() and removed == set() and modified == set()


# --- parse-coverage checks (step 1) ----------------------------------------

def test_parse_coverage_checks_clean_on_real_cr():
    """Mirrors tests/test_cr_parse_coverage.py's own invariants -- these
    must be silent on the file that test suite already keeps clean."""
    if not CR_PATH.exists():
        pytest.skip(f"CR not present at {CR_PATH.name}")
    rules, _ = parse_comprehensive_rules(CR_PATH)
    violations = ccu.run_parse_coverage_checks(CR_PATH, rules)
    assert all(v == [] for v in violations.values()), violations


def test_parse_coverage_catches_a_dropped_rule_shaped_line(tmp_path):
    """A line that looks like a rule to a human but that the strict parser
    would skip (no space after the number) must show up as a gap."""
    text = (
        "1. Test Section\n\n"
        "100. Group\n"
        "100.1 First rule in the family.\n"
        "100.2If the total cost were reintroduced this way it would vanish.\n"
        "100.3 Third rule in the family.\n\n"
        "Glossary\n\nCredits\n"
    )
    cr_path = tmp_path / "broken.txt"
    cr_path.write_text(text, encoding="utf-8")
    rules, _ = parse_comprehensive_rules(cr_path)
    violations = ccu.run_parse_coverage_checks(cr_path, rules)
    assert violations["no_gaps_in_rule_numbering"] == ["100.2"]


# --- policy resolution ------------------------------------------------------

def test_whitespace_punct_predicate_matches_punctuation_only_change():
    assert ccu._pred_whitespace_or_punct_only(
        "A creature dies.", "A creature dies!"
    )


def test_whitespace_punct_predicate_rejects_real_wording_change():
    assert not ccu._pred_whitespace_or_punct_only(
        "A creature dies.", "A permanent dies."
    )


def test_policy_decision_resolves_matching_answered_entry():
    entries = [{
        "class": "edited",
        "when": "text change is whitespace/punctuation only",
        "decision": "auto-remap, do not flag",
        "ruled_by": "Jon", "ruled_at": "2026-07-25",
    }]
    decision = ccu.policy_decision(entries, "edited", "A creature dies.", "A creature dies!")
    assert decision == "auto-remap, do not flag"


def test_policy_decision_none_when_no_matching_entry():
    assert ccu.policy_decision([], "edited", "A creature dies.", "A different rule.") is None


def test_policy_decision_ignores_unrecognized_when_string():
    """A policy entry whose `when` isn't a predicate this script can verify
    must never silently resolve a flag -- see the module's policy-file
    docstring: an unverifiable rule is informational only."""
    entries = [{
        "class": "edited",
        "when": "some future situation this script has no predicate for",
        "decision": "auto-remap, do not flag",
        "ruled_by": "Jon", "ruled_at": "2026-07-25",
    }]
    assert ccu.policy_decision(entries, "edited", "A.", "B.") is None


def test_ensure_open_question_appends_once_per_class():
    entries: list[dict] = []
    assert ccu.ensure_open_question(entries, "deleted", ["100.1"]) is True
    assert len(entries) == 1
    assert entries[0]["decision"] is None
    # A second flag of the SAME class must not add a duplicate open question.
    assert ccu.ensure_open_question(entries, "deleted", ["200.2"]) is False
    assert len(entries) == 1


def test_ensure_open_question_does_not_touch_already_answered_entries():
    entries = [{
        "class": "deleted", "when": "whatever", "decision": "flag anyway",
        "ruled_by": "Jon", "ruled_at": "2026-07-25",
    }]
    # The existing entry is answered, so a NEW open question for "deleted"
    # should still be appended (the answered one resolves a different
    # situation than "no policy coverage at all").
    assert ccu.ensure_open_question(entries, "deleted", ["100.1"]) is True
    assert len(entries) == 2


def test_load_policy_missing_file_returns_empty_list(tmp_path):
    assert ccu.load_policy(tmp_path / "nope.json") == []


def test_save_and_load_policy_roundtrip(tmp_path):
    path = tmp_path / "policy.json"
    entries = [{"class": "edited", "when": "x", "decision": "y", "ruled_by": "Jon", "ruled_at": "2026-07-25"}]
    ccu.save_policy(path, entries)
    assert ccu.load_policy(path) == entries


# --- _collect_ref_slots() ----------------------------------------------------

def test_collect_ref_slots_finds_ids_in_gold_and_gold_groups_but_not_prose():
    record = {
        "id": "rg1",
        "question": "does 100.1 apply here?",
        "gold": ["100.1", "702.16"],
        "gold_groups": [["100.1"], ["702.16"]],
        "rationale": "100.1 is the rule that governs this, full stop.",
        "level": "0",
    }
    slots = ccu._collect_ref_slots(record)
    values = sorted({container[key] for container, key in slots})
    assert values == ["100.1", "702.16", "702.16"] or values == ["100.1", "702.16"]
    # every found slot must be an EXACT bare rule number, never a substring of prose
    for container, key in slots:
        assert ccu.RULE_ID_RE.match(container[key])


def test_collect_ref_slots_finds_ids_in_nested_decisions_headers_shape():
    record = {
        "id": "rg1",
        "decisions": [
            {"parent": "118.9", "action": "keep_parent", "chosen": []},
            {"parent": "105.2", "action": "narrow", "chosen": ["105.2c"]},
        ],
        "final_gold": ["118.9", "105.2c"],
    }
    slots = ccu._collect_ref_slots(record)
    values = sorted(container[key] for container, key in slots)
    assert values == ["105.2", "105.2c", "105.2c", "118.9", "118.9"]


# --- process_eval_file() ----------------------------------------------------

def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_process_eval_file_dry_run_leaves_file_untouched(tmp_path):
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, [{"id": "q1", "gold": ["100.1"]}])
    classes = {"100.1": ccu.RuleClass("100.1", "renumbered", target="100.2")}
    before = path.read_text(encoding="utf-8")

    result = ccu.process_eval_file(
        path, old_numbers={"100.1"}, classes=classes, new_rule_numbers={"100.2"},
        old_chunk_ids={"100.1"}, new_chunk_ids={"100.2"},
        old_text_by_number={"100.1": "text"}, new_text_by_number={"100.2": "text"},
        policy_entries=[], apply=False,
    )

    assert path.read_text(encoding="utf-8") == before  # dry run: untouched on disk
    assert result.remaps[("100.1", "100.2")] == {"q1"}
    assert result.changed is False  # dry run never mutates the in-memory record either
    assert result.records[0]["gold"] == ["100.1"]  # still the old number -- --apply is what moves it


def test_process_eval_file_apply_rewrites_the_file(tmp_path):
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, [{"id": "q1", "gold": ["100.1"]}])
    classes = {"100.1": ccu.RuleClass("100.1", "renumbered", target="100.2")}

    result = ccu.process_eval_file(
        path, old_numbers={"100.1"}, classes=classes, new_rule_numbers={"100.2"},
        old_chunk_ids={"100.1"}, new_chunk_ids={"100.2"},
        old_text_by_number={"100.1": "text"}, new_text_by_number={"100.2": "text"},
        policy_entries=[], apply=True,
    )
    assert result.changed is True
    assert result.records[0]["gold"] == ["100.2"]  # in-memory already updated

    # main() only calls _write_jsonl when fr.changed -- exercise that path directly.
    ccu._write_jsonl(path, result.records)
    on_disk = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert on_disk["gold"] == ["100.2"]


def test_process_eval_file_edited_is_flagged_without_policy(tmp_path):
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, [{"id": "q1", "gold": ["100.1"]}])
    classes = {"100.1": ccu.RuleClass("100.1", "edited")}

    result = ccu.process_eval_file(
        path, old_numbers={"100.1"}, classes=classes, new_rule_numbers={"100.1"},
        old_chunk_ids={"100.1"}, new_chunk_ids={"100.1"},
        old_text_by_number={"100.1": "Old wording."}, new_text_by_number={"100.1": "Completely new wording."},
        policy_entries=[], apply=False,
    )
    assert len(result.flags) == 1
    assert result.flags[0].cls == "edited"
    assert result.resolved_by_policy == []


def test_process_eval_file_edited_resolved_by_matching_policy(tmp_path):
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, [{"id": "q1", "gold": ["100.1"]}])
    classes = {"100.1": ccu.RuleClass("100.1", "edited")}
    policy = [{
        "class": "edited", "when": "text change is whitespace/punctuation only",
        "decision": "auto-remap, do not flag", "ruled_by": "Jon", "ruled_at": "2026-07-25",
    }]

    result = ccu.process_eval_file(
        path, old_numbers={"100.1"}, classes=classes, new_rule_numbers={"100.1"},
        old_chunk_ids={"100.1"}, new_chunk_ids={"100.1"},
        old_text_by_number={"100.1": "A creature dies."}, new_text_by_number={"100.1": "A creature dies!"},
        policy_entries=policy, apply=False,
    )
    assert result.flags == []
    assert result.resolved_by_policy == [("100.1", "q1")]


def test_process_eval_file_deleted_and_ambiguous_are_flagged(tmp_path):
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, [{"id": "q1", "gold": ["100.1"]}, {"id": "q2", "gold": ["100.2"]}])
    classes = {
        "100.1": ccu.RuleClass("100.1", "deleted"),
        "100.2": ccu.RuleClass("100.2", "ambiguous", candidates=["100.3", "100.4"]),
    }
    result = ccu.process_eval_file(
        path, old_numbers={"100.1", "100.2"}, classes=classes, new_rule_numbers=set(),
        old_chunk_ids=set(), new_chunk_ids=set(),
        old_text_by_number={"100.1": "x", "100.2": "y"}, new_text_by_number={},
        policy_entries=[], apply=False,
    )
    classes_seen = {f.cls for f in result.flags}
    assert classes_seen == {"deleted", "ambiguous"}


def test_process_eval_file_folded_parent_is_differential(tmp_path):
    """The regression this test pins: a gold id that was ALREADY not its
    own chunk in the OLD release (some pre-existing label-fold) must NOT be
    flagged just because it's still not a chunk in the new release -- only
    a chunk that the update itself took away should fire."""
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, [
        {"id": "q1", "gold": ["100.1"]},  # was a chunk in old, isn't in new -> flag
        {"id": "q2", "gold": ["100.2"]},  # was NEVER a chunk -> no flag
    ])
    classes = {
        "100.1": ccu.RuleClass("100.1", "unchanged"),
        "100.2": ccu.RuleClass("100.2", "unchanged"),
    }
    result = ccu.process_eval_file(
        path, old_numbers={"100.1", "100.2"}, classes=classes,
        new_rule_numbers={"100.1", "100.2"},
        old_chunk_ids={"100.1"},       # 100.2 was never a chunk
        new_chunk_ids=set(),           # neither is a chunk now
        old_text_by_number={"100.1": "x", "100.2": "y"},
        new_text_by_number={"100.1": "x", "100.2": "y"},
        policy_entries=[], apply=False,
    )
    flagged_numbers = {f.number for f in result.flags}
    assert flagged_numbers == {"100.1"}
    assert all(f.cls == "folded-parent" for f in result.flags)


# --- end-to-end CLI (main()) ------------------------------------------------

def _require_real_cr():
    if not CR_PATH.exists():
        pytest.skip(f"CR not present at {CR_PATH.name}")


def test_self_test_same_release_is_100pct_unchanged_0_remaps_0_flags(tmp_path):
    """The spec's own required self-test: --old and --new both pointing at
    the current release must classify 100% unchanged, 0 remaps, 0 flags.
    Runs against the REAL evals/ directory in dry-run mode (apply is never
    passed), which never writes to those files -- only --report/--policy
    land in tmp_path."""
    _require_real_cr()
    report_path = tmp_path / "report.md"
    policy_path = tmp_path / "policy.json"
    exit_code = ccu.main([
        "--old", str(CR_PATH), "--new", str(CR_PATH),
        "--eval-dir", str(ROOT / "evals"),
        "--report", str(report_path), "--policy", str(policy_path),
        "--skip-pytest-regression",
    ])
    assert exit_code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "| unchanged | 3153 |" in text or "| unchanged |" in text
    assert "| renumbered | 0 |" in text
    assert "| edited | 0 |" in text
    assert "| deleted | 0 |" in text
    assert "| ambiguous | 0 |" in text
    assert "## Flags -- need Jon or a re-mine\n\nNone." in text
    assert "## Step 3 -- gold id remaps (auto-safe: byte-identical text)\n\nNone." in text
    assert not policy_path.exists()  # no flags -> nothing written


def test_synthetic_renumber_end_to_end(tmp_path):
    """Swap two real top-level rules' text (104.3 <-> 104.4) -- see module
    docstring for why this replaces the spec's literal 704.5n/704.5zz
    example at the CLI level. A tmp eval file with a gold id pointing at
    one of the swapped numbers proves the remap gets reported (and, with
    --apply, actually rewritten)."""
    _require_real_cr()
    rules, _ = parse_comprehensive_rules(CR_PATH)
    by_num = {r.number: r for r in rules}
    a_text, b_text = by_num["104.3"].text, by_num["104.4"].text

    raw = CR_PATH.read_text(encoding="utf-8-sig")
    placeholder = "\x00SWAP\x00"
    swapped = raw.replace(a_text, placeholder, 1).replace(b_text, a_text, 1).replace(placeholder, b_text, 1)
    assert swapped != raw
    new_cr = tmp_path / "new_cr.txt"
    new_cr.write_text(swapped, encoding="utf-8")

    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    _write_jsonl(eval_dir / "questions.jsonl", [{"id": "q1", "gold": ["104.3"], "kind": "rule"}])

    report_path = tmp_path / "report.md"
    exit_code = ccu.main([
        "--old", str(CR_PATH), "--new", str(new_cr),
        "--eval-dir", str(eval_dir),
        "--report", str(report_path), "--policy", str(tmp_path / "policy.json"),
        "--skip-pytest-regression",
    ])
    assert exit_code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "| renumbered | 2 |" in text
    assert "`104.3` -> `104.4`" in text
    assert "q1" in text

    # Now with --apply: the eval file on disk should actually change.
    exit_code = ccu.main([
        "--old", str(CR_PATH), "--new", str(new_cr),
        "--eval-dir", str(eval_dir),
        "--report", str(report_path), "--policy", str(tmp_path / "policy2.json"),
        "--skip-pytest-regression", "--apply",
    ])
    assert exit_code == 0
    rewritten = json.loads((eval_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rewritten["gold"] == ["104.4"]


def test_synthetic_edit_end_to_end(tmp_path):
    """Change one word in a real rule's text; confirm it's classified
    `edited` and, when a gold id references it, flagged rather than
    remapped (edits never move an id -- the number didn't change)."""
    _require_real_cr()
    rules, _ = parse_comprehensive_rules(CR_PATH)
    by_num = {r.number: r for r in rules}
    old_text = by_num["100.1"].text
    assert "two or more players" in old_text
    new_text = old_text.replace("two or more players", "two or more duelists")

    raw = CR_PATH.read_text(encoding="utf-8-sig")
    edited_raw = raw.replace(old_text, new_text, 1)
    assert edited_raw != raw
    new_cr = tmp_path / "new_cr.txt"
    new_cr.write_text(edited_raw, encoding="utf-8")

    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    _write_jsonl(eval_dir / "questions.jsonl", [{"id": "q1", "gold": ["100.1"], "kind": "rule"}])

    report_path = tmp_path / "report.md"
    exit_code = ccu.main([
        "--old", str(CR_PATH), "--new", str(new_cr),
        "--eval-dir", str(eval_dir),
        "--report", str(report_path), "--policy", str(tmp_path / "policy.json"),
        "--skip-pytest-regression",
    ])
    assert exit_code == 2  # unresolved flag present
    text = report_path.read_text(encoding="utf-8")
    assert "| edited | 1 |" in text
    assert "### edited (1)" in text
    assert "`100.1`" in text
    # gold id must NOT have been touched -- edits are never auto-applied
    on_disk = json.loads((eval_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert on_disk["gold"] == ["100.1"]
    # an open policy question for "edited" should now exist
    policy = ccu.load_policy(tmp_path / "policy.json")
    assert any(e["class"] == "edited" and e["decision"] is None for e in policy)


def test_synthetic_edit_resolved_by_preexisting_policy(tmp_path):
    """Same edit as above, but this time evals/cr_update_policy.json already
    has a ruling covering whitespace/punctuation-only changes. Since the
    edit here is a real wording change (not punctuation-only), the policy
    must NOT resolve it -- proving the predicate is actually checked against
    the specific text, not just matched by class name."""
    _require_real_cr()
    rules, _ = parse_comprehensive_rules(CR_PATH)
    by_num = {r.number: r for r in rules}
    old_text = by_num["100.1"].text
    new_text = old_text.replace("two or more players", "two or more duelists")
    raw = CR_PATH.read_text(encoding="utf-8-sig")
    new_cr = tmp_path / "new_cr.txt"
    new_cr.write_text(raw.replace(old_text, new_text, 1), encoding="utf-8")

    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    _write_jsonl(eval_dir / "questions.jsonl", [{"id": "q1", "gold": ["100.1"], "kind": "rule"}])

    policy_path = tmp_path / "policy.json"
    ccu.save_policy(policy_path, [{
        "class": "edited", "when": "text change is whitespace/punctuation only",
        "decision": "auto-remap, do not flag", "ruled_by": "Jon", "ruled_at": "2026-07-25",
    }])

    exit_code = ccu.main([
        "--old", str(CR_PATH), "--new", str(new_cr),
        "--eval-dir", str(eval_dir),
        "--report", str(tmp_path / "report.md"), "--policy", str(policy_path),
        "--skip-pytest-regression",
    ])
    assert exit_code == 2  # still flagged: the predicate correctly does not match


def test_synthetic_drop_halts_at_step_1(tmp_path):
    """Reintroduce the exact class of typo that dropped 606.5 for the life
    of the project (see tests/test_cr_parse_coverage.py): remove the space
    after the rule number so the line no longer looks like a rule at all.
    Step 1 must halt before steps 2-5 run."""
    _require_real_cr()
    raw = CR_PATH.read_text(encoding="utf-8-sig")
    target = "606.5 If the total cost"
    assert target in raw
    dropped = raw.replace(target, "606.5If the total cost", 1)
    assert dropped != raw
    new_cr = tmp_path / "new_cr.txt"
    new_cr.write_text(dropped, encoding="utf-8")

    report_path = tmp_path / "report.md"
    exit_code = ccu.main([
        "--old", str(CR_PATH), "--new", str(new_cr),
        "--eval-dir", str(ROOT / "evals"),
        "--report", str(report_path), "--policy", str(tmp_path / "policy.json"),
        "--skip-pytest-regression",
    ])
    assert exit_code == 1
    text = report_path.read_text(encoding="utf-8")
    assert "HALTED" in text
    assert "606.5" in text
    assert not (tmp_path / "policy.json").exists()  # halted before step 3/4 policy writes


def test_answer_gold_field_is_never_touched(tmp_path):
    """Safety-boundary regression: answer_gold is judge-authored prose and
    must never be rewritten, even under --apply. Since the scan only
    matches whole-string bare rule numbers, a prose answer_gold can't
    collide with it -- this test pins that guarantee with a real rulesguru
    -shaped record whose answer happens to quote a rule number in prose."""
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    record = {
        "id": "rg1",
        "gold": ["100.1"],
        "answer_gold": "Yes, because rule 100.1 says exactly that.",
    }
    _write_jsonl(eval_dir / "questions.jsonl", [record])
    classes = {"100.1": ccu.RuleClass("100.1", "renumbered", target="100.2")}
    result = ccu.process_eval_file(
        eval_dir / "questions.jsonl", old_numbers={"100.1"}, classes=classes,
        new_rule_numbers={"100.2"}, old_chunk_ids={"100.1"}, new_chunk_ids={"100.2"},
        old_text_by_number={"100.1": "text"}, new_text_by_number={"100.2": "text"},
        policy_entries=[], apply=True,
    )
    assert result.records[0]["answer_gold"] == "Yes, because rule 100.1 says exactly that."
    assert result.records[0]["gold"] == ["100.2"]

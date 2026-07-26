"""Detects when a new Comprehensive Rules release silently drops or
renumbers a rule, and fixes gold automatically only where the fix is
provably safe. See docs/spec-cr-update-check.md for the full design --
this docstring only covers the shape of the code, not the reasoning.

Pure local compute. No AI calls, no network calls, nothing that can spend
API credits -- everything here is string handling, hashing, and JSON.

    uv run python scripts/check_cr_update.py --old <old CR.txt> --new <new CR.txt>

Exit codes:
    0 -- ran clean: nothing needs Jon's attention.
    1 -- HALTED at step 1: the new release fails parse coverage (a rule-shaped
         line didn't parse, or a numbering/lettering gap exists). Nothing
         downstream ran, because it would be measuring a corpus with a hole.
    2 -- ran to completion but left one or more flags for Jon (edited,
         deleted, ambiguous, or folded-parent gold ids). See the report.

Identity is by content, not position (rule_fingerprint below), the same
move ruling_id() made for card rulings (commit 7a316bd). A fingerprint
survives renumbering; a rule number does not.

Safety boundary (spec section 5, "what it must never do"):
    - `renumbered` (byte-identical text, id moved) is the ONLY class this
      script ever auto-remaps, and only when --apply is passed. Everything
      else -- edited, deleted, ambiguous, folded-parent -- is a flag, never
      a silent edit, unless a policy entry in evals/cr_update_policy.json
      explicitly answers that exact situation (see policy_decision()).
    - `answer_gold` is never touched. It isn't even inspected: the gold-id
      scan only ever matches strings shaped like a bare rule number
      ("704.5g"), and a judge-authored answer is prose, so it can never
      collide with that pattern.
    - The vector index is never rebuilt or appended to by this script --
      step 5 only *reports* what a human/other process should do.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rulesagent.contracts import Rule  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

# --- files step 3 touches -------------------------------------------------
# Exactly the list in docs/spec-cr-update-check.md section 3. Deliberately
# NOT a glob over every *.jsonl in evals/ -- the spec names these four
# specifically, and guessing beyond that risks silently "fixing" a file
# nobody asked to have touched.
EVAL_FILES = [
    "questions.jsonl",
    "rulesguru.jsonl",
    "rulesguru_full.jsonl",
    "questions_rulesguru150_v2.jsonl",
]
GOLD_PROPOSALS_GLOB = "gold_proposals_*.jsonl"


# ===========================================================================
# Content fingerprinting (spec section 2)
# ===========================================================================

_CURLY_TO_ASCII = {
    "‘": "'", "’": "'",   # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
}
# A rule's own text never starts with its number (parser.py already strips
# it -- see RULE_RE/SUBRULE_RE), but normalize() strips it anyway in case a
# future CR text or a hand-built Rule repeats it, exactly as the spec says.
_LEADING_NUMBER_RE = re.compile(r"^\d+\.\d+[a-z]*\.?\s+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """collapse whitespace, fold curly quotes/apostrophes to ASCII, strip
    the leading rule number if the text repeats it -- verbatim recipe from
    docs/spec-cr-update-check.md section 2."""
    for curly, straight in _CURLY_TO_ASCII.items():
        text = text.replace(curly, straight)
    text = _LEADING_NUMBER_RE.sub("", text.strip())
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def rule_fingerprint(text: str) -> str:
    """sha256(normalize(rule.text))[:16] -- the spec's formula exactly."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# Step 1 -- parse coverage on the NEW release
# ===========================================================================
# Duplicates the four invariants in tests/test_cr_parse_coverage.py, but as
# plain functions parameterized by an arbitrary path/rule list instead of
# pytest fixtures pinned to one hardcoded CR_PATH -- that file can't be
# reused directly against a caller-supplied --new file. main() ALSO shells
# out to run that test file for a real regression check, so one command
# covers both "does the new release parse cleanly" and "did the parser
# itself regress."

LOOKS_LIKE_RULE = re.compile(r"^(\d+\.\d+)\.?\s+\S")
LOOKS_LIKE_SUBRULE = re.compile(r"^(\d+\.\d+[a-z]+)\.?\s+\S")
SUBRULE_ALPHABET = [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in "lo"]


def _source_rule_numbers(cr_path: Path) -> set[str]:
    found = set()
    for line in cr_path.read_text(encoding="utf-8-sig").splitlines():
        m = LOOKS_LIKE_SUBRULE.match(line) or LOOKS_LIKE_RULE.match(line)
        if m:
            found.add(m.group(1))
    return found


def check_every_rule_shaped_line_parsed(cr_path: Path, rules: list[Rule]) -> list[str]:
    parsed_numbers = {r.number for r in rules}
    return sorted(_source_rule_numbers(cr_path) - parsed_numbers)


def check_no_gaps_in_rule_numbering(rules: list[Rule]) -> list[str]:
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
    return holes


def check_no_gaps_in_subrule_letters(rules: list[Rule]) -> list[str]:
    numbers = {r.number for r in rules}
    children: dict[str, list[str]] = {}
    for n in numbers:
        m = re.fullmatch(r"(\d+\.\d+)([a-z]+)", n)
        if m:
            children.setdefault(m.group(1), []).append(m.group(2))
    gaps = []
    for parent, letters in sorted(children.items()):
        got = sorted(letters, key=lambda s: (len(s), s))
        want = SUBRULE_ALPHABET[: len(got)]
        if got != want:
            missing = [f"{parent}{c}" for c in want if c not in got]
            gaps.append(f"{parent}: missing {missing or want}")
    return gaps


def check_every_subrule_has_parent(rules: list[Rule]) -> list[str]:
    numbers = {r.number for r in rules}
    return sorted(
        n for n in numbers
        if (m := re.fullmatch(r"(\d+\.\d+)[a-z]+", n)) and m.group(1) not in numbers
    )


def run_parse_coverage_checks(cr_path: Path, rules: list[Rule]) -> dict[str, list[str]]:
    return {
        "every_rule_shaped_line_parsed": check_every_rule_shaped_line_parsed(cr_path, rules),
        "no_gaps_in_rule_numbering": check_no_gaps_in_rule_numbering(rules),
        "no_gaps_in_subrule_letters": check_no_gaps_in_subrule_letters(rules),
        "every_subrule_has_parent": check_every_subrule_has_parent(rules),
    }


# ===========================================================================
# Step 2 -- classify every rule
# ===========================================================================

@dataclass
class RuleClass:
    number: str
    cls: str  # unchanged | renumbered | edited | deleted | ambiguous
    target: str | None = None          # renumbered -> the new number
    candidates: list[str] | None = None  # ambiguous -> every candidate


def classify_rules(
    old_rules: list[Rule], new_rules: list[Rule]
) -> tuple[dict[str, RuleClass], list[str], dict[str, str], dict[str, str]]:
    """Returns (per-old-number classification, added new numbers,
    old number->text, new number->text).

    Classification is keyed on the OLD rule number because that's what a
    gold id in an eval file actually is: a claim about the OLD release.
    `added` numbers (new content, no old counterpart) never need a gold
    remap -- nothing old could have pointed at them -- but step 5 needs
    them for the index diff.
    """
    old_text = {r.number: r.text for r in old_rules}
    new_text = {r.number: r.text for r in new_rules}
    old_fp = {n: rule_fingerprint(t) for n, t in old_text.items()}
    new_fp = {n: rule_fingerprint(t) for n, t in new_text.items()}

    old_fp_to_numbers: dict[str, list[str]] = defaultdict(list)
    for n, fp in old_fp.items():
        old_fp_to_numbers[fp].append(n)
    new_fp_to_numbers: dict[str, list[str]] = defaultdict(list)
    for n, fp in new_fp.items():
        new_fp_to_numbers[fp].append(n)

    results: dict[str, RuleClass] = {}
    for number, fp in old_fp.items():
        if number in new_fp and new_fp[number] == fp:
            results[number] = RuleClass(number, "unchanged")
            continue
        candidates = sorted(set(new_fp_to_numbers.get(fp, [])))
        siblings = old_fp_to_numbers.get(fp, [])
        if len(candidates) == 1 and len(siblings) == 1:
            results[number] = RuleClass(number, "renumbered", target=candidates[0])
        elif candidates:
            # Either side has duplicate text for this fingerprint --
            # can't tell which old rule maps to which new one.
            results[number] = RuleClass(number, "ambiguous", candidates=candidates)
        elif number in new_fp:
            results[number] = RuleClass(number, "edited")
        else:
            results[number] = RuleClass(number, "deleted")

    added = []
    for number, fp in new_fp.items():
        if number in old_fp:
            # This slot existed before, whatever happened to its content is
            # already captured by the old-side loop above (unchanged/edited)
            # -- an in-place edit is "edited", never also "added".
            continue
        if fp in old_fp_to_numbers:
            continue  # this is the destination of a renumber/ambiguous above
        added.append(number)

    return results, sorted(added), old_text, new_text


def chunk_id_diff(
    old_rules: list[Rule], old_glossary, new_rules: list[Rule], new_glossary
) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    """(added ids, removed ids, MODIFIED ids, full old id set, full new id set).

    "Modified" is the case step 5 would otherwise miss entirely: a chunk
    whose id (source_id) survives untouched but whose embed_text changed --
    an in-place `edited` rule, or a rule whose immediate parent changed and
    therefore altered what gets prepended (see chunker.py's label-folding).
    A pure id-set diff (added/removed) is blind to this, so an edited rule's
    STALE embedding would sit in the index forever with nothing ever
    flagging it for re-embedding."""
    old_chunks = {c.source_id: c for c in chunk_rules(old_rules, old_glossary)}
    new_chunks = {c.source_id: c for c in chunk_rules(new_rules, new_glossary)}
    old_ids, new_ids = set(old_chunks), set(new_chunks)
    modified = {
        cid for cid in (old_ids & new_ids)
        if old_chunks[cid].embed_text != new_chunks[cid].embed_text
    }
    return new_ids - old_ids, old_ids - new_ids, modified, old_ids, new_ids


# ===========================================================================
# Section 4 -- the policy file
# ===========================================================================
# "Nothing is auto-applied outside `renumbered` until a policy entry says
# so." A policy entry only ever resolves a flag if BOTH its class matches
# AND its `when` string names a predicate this script can actually check
# against the specific old/new text -- an unrecognised `when` is treated as
# informational only and the flag still fires. That is the conservative
# reading of an otherwise free-text field: a policy we can't verify must
# never silently suppress a flag.

def _pred_whitespace_or_punct_only(old_text: str, new_text: str) -> bool:
    """The one predicate the spec's own example names ("text change is
    whitespace/punctuation only"). Strips whitespace and common punctuation
    from both sides and compares what's left -- case is NOT folded, because
    a case change is a real wording change, not punctuation/whitespace."""
    strip_re = re.compile(r"[\s.,;:!?\"'()‘’“”-]+")
    return strip_re.sub("", old_text) == strip_re.sub("", new_text)


WHEN_PREDICATES: dict[str, Callable[[str, str], bool]] = {
    "text change is whitespace/punctuation only": _pred_whitespace_or_punct_only,
}


def load_policy(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_policy(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def policy_decision(entries: list[dict], cls: str, old_text: str, new_text: str) -> str | None:
    """Returns the ruled decision string if some answered entry resolves
    this exact (class, text-pair), else None (still a flag)."""
    for entry in entries:
        if entry.get("class") != cls or not entry.get("decision"):
            continue
        pred = WHEN_PREDICATES.get(entry.get("when", ""))
        if pred is not None and pred(old_text, new_text):
            return entry["decision"]
    return None


def ensure_open_question(entries: list[dict], cls: str, evidence: list[str]) -> bool:
    """Appends one open (unanswered) policy question for this class if none
    exists yet. Returns True if it appended something (caller should save).
    Deliberately one entry per class, not one per occurrence -- Jon answers
    a *pattern*, and the set of things he must answer is meant to shrink
    with each release, not grow with every affected question id."""
    for entry in entries:
        if entry.get("class") == cls and not entry.get("decision"):
            return False
    entries.append({
        "class": cls,
        "when": "(auto-generated -- describe the pattern and set `decision` "
                 "to resolve it automatically next time)",
        "evidence": evidence,
        "decision": None,
        "ruled_by": None,
        "ruled_at": None,
    })
    return True


# ===========================================================================
# Step 3 -- apply to every gold id in every eval file
# ===========================================================================

# A bare rule number, whole-string match only -- "704.5g", "109.2", "613.1".
# Whole-string equality (not a substring search) is what makes it safe to
# walk EVERY string in these files without knowing field names: a rationale
# sentence that happens to mention "109.2 itself says..." is the whole
# sentence, not "109.2" alone, so it never matches this pattern.
RULE_ID_RE = re.compile(r"^\d+\.\d+[a-z]*$")


def _collect_ref_slots(obj) -> list[tuple[dict | list, str | int]]:
    """Recursively finds every string leaf in a decoded JSON object that
    looks like a bare rule number, and returns (container, key) so the
    caller can read or overwrite it in place. Works across the differing
    schemas in questions.jsonl / rulesguru*.jsonl / gold_proposals_*.jsonl
    (gold, gold_groups, final_gold, final_gold_groups, decisions[].parent,
    decisions[].chosen, ...) without hardcoding any of those key names."""
    slots: list[tuple[dict | list, str | int]] = []

    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str):
                    if RULE_ID_RE.match(v):
                        slots.append((o, k))
                else:
                    _walk(v)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, str):
                    if RULE_ID_RE.match(v):
                        slots.append((o, i))
                else:
                    _walk(v)

    _walk(obj)
    return slots


@dataclass
class FlagRecord:
    file: str
    qid: str
    number: str
    cls: str
    note: str


@dataclass
class FileResult:
    records: list[dict | None]
    remaps: dict[tuple[str, str], set[str]] = field(default_factory=lambda: defaultdict(set))
    flags: list[FlagRecord] = field(default_factory=list)
    resolved_by_policy: list[tuple[str, str]] = field(default_factory=list)
    changed: bool = False


def process_eval_file(
    path: Path,
    old_numbers: set[str],
    classes: dict[str, RuleClass],
    new_rule_numbers: set[str],
    old_chunk_ids: set[str],
    new_chunk_ids: set[str],
    old_text_by_number: dict[str, str],
    new_text_by_number: dict[str, str],
    policy_entries: list[dict],
    apply: bool,
) -> FileResult:
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict | None] = [
        json.loads(line) if line.strip() else None for line in raw_lines
    ]

    result = FileResult(records=records)

    for record in records:
        if record is None:
            continue
        qid = record.get("id", "?")

        for container, key in _collect_ref_slots(record):
            value = container[key]
            if value not in old_numbers:
                continue  # not a number this checker has an opinion about
            rc = classes[value]

            final_number: str | None = value
            if rc.cls == "unchanged":
                pass
            elif rc.cls == "renumbered":
                result.remaps[(value, rc.target)].add(qid)
                final_number = rc.target
                if apply:
                    container[key] = rc.target
                    result.changed = True
            elif rc.cls == "edited":
                decision = policy_decision(
                    policy_entries, "edited",
                    old_text_by_number[value], new_text_by_number.get(value, ""),
                )
                if decision:
                    result.resolved_by_policy.append((value, qid))
                else:
                    result.flags.append(FlagRecord(
                        path.name, qid, value, "edited",
                        "text changed, same slot -- may no longer state the answer",
                    ))
            elif rc.cls == "deleted":
                result.flags.append(FlagRecord(
                    path.name, qid, value, "deleted",
                    "no rule in the new release has this text",
                ))
                final_number = None
            elif rc.cls == "ambiguous":
                result.flags.append(FlagRecord(
                    path.name, qid, value, "ambiguous",
                    f"duplicate text, candidates: {rc.candidates}",
                ))
                final_number = None

            # Folded-parent is a DIFFERENTIAL check: it only fires when the
            # update is what took the chunk away. A gold id that already
            # pointed at a label-like/no-chunk number in the OLD release
            # (e.g. because the mining pass hand-picked a parent number on
            # purpose) is a pre-existing condition this checker didn't
            # cause and has no business flagging -- that's the difference
            # between "702.16 was always like this" and "702.16 used to
            # have its own chunk and the new release folded it." Without
            # the `value in old_chunk_ids` guard, the self-test (old==new)
            # would flag every pre-existing case, which the spec's
            # verification list explicitly forbids (0 flags when nothing
            # changed).
            if (
                final_number is not None
                and final_number in new_rule_numbers
                and final_number not in new_chunk_ids
                and value in old_chunk_ids
            ):
                result.flags.append(FlagRecord(
                    path.name, qid, final_number, "folded-parent",
                    "rule text still exists in the new release but was folded "
                    "into its parent's chunk during re-chunking (the 702.16-class "
                    "problem) -- repairable by the existing mining pass",
                ))

    return result


def _write_jsonl(path: Path, records: list[dict | None]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) if r is not None else "" for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ===========================================================================
# Step 4 -- the report
# ===========================================================================

def _default_report_path(new_path: Path) -> Path:
    m = re.search(r"(\d{4})(\d{2})(\d{2})", new_path.stem)
    date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else date.today().isoformat()
    return ROOT / "docs" / f"cr-update-{date_str}.md"


def build_report(
    *,
    old_path: Path,
    new_path: Path,
    coverage_violations: dict[str, list[str]],
    classes: dict[str, RuleClass],
    added: list[str],
    remaps: dict[tuple[str, str], set[str]],
    flags: list[FlagRecord],
    resolved_by_policy: list[tuple[str, str]],
    chunk_added: set[str],
    chunk_removed: set[str],
    chunk_modified: set[str] = frozenset(),
) -> str:
    lines: list[str] = []
    lines.append(f"# CR update check: `{old_path.name}` -> `{new_path.name}`")
    lines.append("")
    lines.append(
        "Generated by `scripts/check_cr_update.py` (pure local compute, no AI calls)."
    )
    lines.append("")
    lines.append("## Step 1 -- parse coverage on the new release")
    if any(coverage_violations.values()):
        lines.append("")
        lines.append(
            "**HALTED.** The new release has malformed/dropped rule line(s); "
            "everything downstream would measure a corpus with a hole, so nothing "
            "past this point ran."
        )
        for name, violations in coverage_violations.items():
            if violations:
                lines.append(f"- `{name}`: {violations}")
        return "\n".join(lines) + "\n"
    lines.append("")
    lines.append("All four parse-coverage invariants passed.")
    lines.append("")

    lines.append("## Step 2 -- classification")
    lines.append("")
    counts = Counter(rc.cls for rc in classes.values())
    lines.append("| class | count |")
    lines.append("|---|---|")
    for cls in ("unchanged", "renumbered", "edited", "deleted", "ambiguous"):
        lines.append(f"| {cls} | {counts.get(cls, 0)} |")
    lines.append(f"| added | {len(added)} |")
    lines.append("")

    lines.append("## Step 3 -- gold id remaps (auto-safe: byte-identical text)")
    lines.append("")
    if remaps:
        for (old_n, new_n), qids in sorted(remaps.items()):
            lines.append(f"- `{old_n}` -> `{new_n}` ({len(qids)} question id(s): {', '.join(sorted(qids))})")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Flags -- need Jon or a re-mine")
    lines.append("")
    if flags:
        by_class: dict[str, list[FlagRecord]] = defaultdict(list)
        for f in flags:
            by_class[f.cls].append(f)
        for cls, items in sorted(by_class.items()):
            lines.append(f"### {cls} ({len(items)})")
            for it in items:
                lines.append(f"- `{it.number}` in `{it.file}` (question `{it.qid}`): {it.note}")
            lines.append("")
    else:
        lines.append("None.")
        lines.append("")

    if resolved_by_policy:
        lines.append("## Resolved silently by `evals/cr_update_policy.json`")
        lines.append("")
        for number, qid in resolved_by_policy:
            lines.append(f"- `{number}` (question `{qid}`)")
        lines.append("")

    lines.append("## Step 5 -- index")
    lines.append("")
    lines.append(f"Chunks added: {len(chunk_added)}")
    lines.append(f"Chunks removed: {len(chunk_removed)}")
    lines.append(f"Chunks modified (same id, changed embed text): {len(chunk_modified)}")
    lines.append("")
    if chunk_removed:
        lines.append(
            "**REBUILD REQUIRED.** Removed chunk(s) must be purged from the vector "
            "store, and `VectorStore` (src/rulesagent/index/store.py) has no "
            "partial-delete path -- only `.build()` over the whole corpus. Re-run "
            "`VectorStore.build(chunk_rules(new_rules, new_glossary), model=...)` "
            "and `.save(...)`."
        )
        lines.append(f"Removed: {sorted(chunk_removed)}")
    elif chunk_added or chunk_modified:
        lines.append(
            "**APPEND/RE-EMBED THE DELTA, do not rebuild.** No chunks were removed, "
            "so do not call `VectorStore.build()` over the whole corpus again -- "
            "Voyage returns slightly different vectors per call, and a full re-embed "
            "would perturb every retrieval number ever measured. Note: this repo has "
            "no incremental-append helper today (`VectorStore.build()` always embeds "
            "every chunk it's given), so updating just the delta below in the saved "
            "store is a script that still needs to be written -- this report is what "
            "tells you it only needs to cover the delta, not the whole corpus."
        )
        if chunk_added:
            lines.append(f"Added: {sorted(chunk_added)}")
        if chunk_modified:
            lines.append(
                f"Modified (stale embedding, same id -- from `edited` rules or a "
                f"changed label-folding parent): {sorted(chunk_modified)}"
            )
    else:
        lines.append("No index changes needed.")
    lines.append("")

    return "\n".join(lines)


# ===========================================================================
# CLI
# ===========================================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True, type=Path, help="path to the OLD CR .txt")
    ap.add_argument("--new", required=True, type=Path, help="path to the NEW CR .txt")
    ap.add_argument("--eval-dir", type=Path, default=ROOT / "evals",
                     help="directory holding the eval/gold jsonl files (default: evals/)")
    ap.add_argument("--policy", type=Path, default=ROOT / "evals" / "cr_update_policy.json",
                     help="path to the ask-once policy file")
    ap.add_argument("--report", type=Path, default=None,
                     help="report output path (default: docs/cr-update-<new date>.md)")
    ap.add_argument("--apply", action="store_true",
                     help="actually rewrite renumbered gold ids in the eval files "
                          "(default: dry run -- report only, per spec section 5)")
    ap.add_argument("--skip-pytest-regression", action="store_true",
                     help="skip re-running tests/test_cr_parse_coverage.py as a subprocess "
                          "(useful when this script is itself being tested under pytest)")
    args = ap.parse_args(argv)

    old_rules, old_glossary = parse_comprehensive_rules(args.old)
    new_rules, new_glossary = parse_comprehensive_rules(args.new)

    # --- Step 1 ------------------------------------------------------------
    coverage = run_parse_coverage_checks(args.new, new_rules)
    report_path = args.report or _default_report_path(args.new)
    if any(coverage.values()):
        text = build_report(
            old_path=args.old, new_path=args.new, coverage_violations=coverage,
            classes={}, added=[], remaps={}, flags=[], resolved_by_policy=[],
            chunk_added=set(), chunk_removed=set(),
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
        print(f"HALTED: {args.new.name} fails parse coverage. Report: {report_path}")
        for name, v in coverage.items():
            if v:
                print(f"  {name}: {v[:10]}{' ...' if len(v) > 10 else ''}")
        return 1

    if not args.skip_pytest_regression:
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             str(ROOT / "tests" / "test_cr_parse_coverage.py"), "-q"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print("HALTED: tests/test_cr_parse_coverage.py failed -- parser regression.")
            print(result.stdout[-4000:])
            return 1

    # --- Step 2 --------------------------------------------------------
    classes, added, old_text, new_text = classify_rules(old_rules, new_rules)
    old_numbers = set(old_text.keys())
    new_rule_numbers = set(new_text.keys())
    chunk_added, chunk_removed, chunk_modified, old_chunk_ids, new_chunk_ids = chunk_id_diff(
        old_rules, old_glossary, new_rules, new_glossary
    )

    # --- Step 3 ----------------------------------------------------------
    policy_entries = load_policy(args.policy)

    eval_paths = [args.eval_dir / name for name in EVAL_FILES]
    eval_paths = [p for p in eval_paths if p.exists()]
    eval_paths += sorted(args.eval_dir.glob(GOLD_PROPOSALS_GLOB))

    all_remaps: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_flags: list[FlagRecord] = []
    all_resolved: list[tuple[str, str]] = []
    file_results: dict[Path, FileResult] = {}

    for path in eval_paths:
        fr = process_eval_file(
            path, old_numbers, classes, new_rule_numbers, old_chunk_ids, new_chunk_ids,
            old_text, new_text, policy_entries, args.apply,
        )
        file_results[path] = fr
        for key, qids in fr.remaps.items():
            all_remaps[key] |= qids
        all_flags.extend(fr.flags)
        all_resolved.extend(fr.resolved_by_policy)

    policy_dirty = False
    for cls_name in sorted({f.cls for f in all_flags}):
        evidence = sorted({f.number for f in all_flags if f.cls == cls_name})[:5]
        if ensure_open_question(policy_entries, cls_name, evidence):
            policy_dirty = True
    if policy_dirty:
        save_policy(args.policy, policy_entries)

    if args.apply:
        for path, fr in file_results.items():
            if fr.changed:
                _write_jsonl(path, fr.records)

    # --- Step 4 --------------------------------------------------------
    text = build_report(
        old_path=args.old, new_path=args.new, coverage_violations=coverage,
        classes=classes, added=added, remaps=all_remaps, flags=all_flags,
        resolved_by_policy=all_resolved, chunk_added=chunk_added, chunk_removed=chunk_removed,
        chunk_modified=chunk_modified,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")

    counts = Counter(rc.cls for rc in classes.values())
    print(f"Report written: {report_path}")
    print(
        f"unchanged={counts.get('unchanged', 0)} renumbered={counts.get('renumbered', 0)} "
        f"edited={counts.get('edited', 0)} deleted={counts.get('deleted', 0)} "
        f"ambiguous={counts.get('ambiguous', 0)} added={len(added)}"
    )
    print(f"gold remaps: {len(all_remaps)}  flags: {len(all_flags)}  "
          f"resolved-by-policy: {len(all_resolved)}")
    if not args.apply and all_remaps:
        print("(dry run -- pass --apply to actually rewrite the eval files)")

    return 0 if not all_flags else 2


if __name__ == "__main__":
    raise SystemExit(main())

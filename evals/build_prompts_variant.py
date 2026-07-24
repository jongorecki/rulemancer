"""Derive evals/answers/_prompts_variant_{A,B,C,D}.json from the frozen
condition-C capture -- the v5 "bullets x injection" 2x2 grid
(docs/plan-v5-symbol-injection.md Sec 3/5b/5c). Generalises build_prompts_v4.py
(Sec 4's last paragraph): takes an explicit SYSTEM version per variant
instead of importing whatever answer.py's `SYSTEM` currently happens to be
bound to, so this instrument stays decoupled from whatever PROMPT_VERSION
production ships today.

  A = (system_version=3,      inject=False)   # production baseline
  B = (system_version=3,      inject=True)
  C = (system_version="v4nl", inject=False)
  D = (system_version="v4nl", inject=True)    # v5, the candidate

`_prompts_C.json` stores only {system, user} STRINGS, not the structured
retrieved/cards/question inputs that produced them -- so the injected
variants (B, D) cannot simply re-run build_prompt(). Instead they slice the
card section out of the frozen `user` string by its literal markers
(`Card data:` / `\\n\\nQuestion:`), scan ONLY that slice plus the question
text, and splice the reference block in at the position build_prompt would
place it (Sec 5b). All 50 questions are built for all 4 variants -- prompt
assembly is free (no API calls); the run script subsets later.

Five gates (Sec 5c), all hard failures, all reported PASS/FAIL with counts:
  1. v3 digest      -- captured system hashes to the recorded v3 digest.
  2. user-block eq   -- non-injected byte-identical to source; injected
                        byte-identical to source after removing the splice.
  3. card-block       -- the sliced card block equals _format_cards(cards)
     extraction         for that question's real cards (see the note below
                         on why this needs one adaptation for rulings).
  4. over-trigger     -- injected symbols subset of cards+question symbols,
                          none found only in the rules-context portion.
  5. production parity -- the real build_prompt(), called on the structured
                           inputs, produces an IDENTICAL reference block.

NOTE on gate 3 and live ruling selection (read before "fixing" this):
production's card list going into _format_cards() has each card's `rulings`
field REPLACED by a per-card mini-RAG selection (ruling_retrieval.select_
rulings against the question, RulesAgent.answer() around line 1097) --
relevance-filtered and re-labeled "[Name ruling #N]". That selection scores
Voyage embeddings and calls embed_query() live for every question -- there is
no cache for it (only the per-ruling embeddings are cached; the per-question
embed_query() call is not). Reproducing it here would mean one live Voyage
API call per card question, which this script must never make (no API
calls, no spending -- see the task brief). So gate 3 does NOT re-derive the
selection: it takes the ALREADY-SELECTED "[Name ruling #N] text" lines
verbatim out of the frozen block, rebuilds each Card with exactly those as
`.rulings`, and asserts _format_cards() of that reconstruction reproduces
the block byte-for-byte (this is what proves the slice boundary + every
non-ruling field -- name, cost, type, oracle text, faces, meta -- is
correct, i.e. the SAME thing get_card() returns today). It then separately
verifies each extracted ruling is AUTHENTIC: index N is in range and
card.rulings[N] (raw, from get_card(), unlabeled) equals the extracted text
verbatim -- so a hallucinated or drifted ruling label would still be caught,
without needing to re-score relevance. This does not affect gates 4/5 at
all: production's symbol scan (_card_symbol_text) only ever reads
mana_cost/oracle_text, never rulings, and those fields are identical whether
a card is pre- or post-ruling-selection (only `.rulings` differs) --
confirmed by diffing raw-get_card() symbol sets against the frozen card
block's full-text symbol sets (see the implementation report for the 8
questions where they differ, all via rulings/type-line text only).

Usage:  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/build_prompts_variant.py
        (add --check to verify existing files without rewriting them)

Parameterised source/output (added for c020's own capture, so a second
question's derivation can never collide with the frozen four-file evidence
base from the first paid experiment):
  --src PATH          capture to derive from (default: _prompts_C.json,
                       unchanged).
  --out-prefix PREFIX output filenames are PREFIX + {A,B,C,D}.json (default:
                       "_prompts_variant_", unchanged).
  --variants A,B,C,D  comma-separated subset of variant letters to derive
                       (default: all four, unchanged).
  --force             allow overwriting an output file that already exists.
                       Without it, ANY existing output file at a target path
                       aborts the whole run before anything is written --
                       this is what makes the existing four
                       _prompts_variant_*.json files unclobberable by
                       accident.

All four flags are additive: with none of them passed, behaviour is
byte-for-byte identical to before they existed. The five gates below no
longer assume a fixed 50-question / 19-card-question source -- their
expectations are derived from what's actually in the loaded capture (see
QIDS / card_qids below), except gate 1 (the v3 digest), which is a content
check, not a count, and is untouched.

Example, deriving only variants A and D for a c020-only capture:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/build_prompts_variant.py \\
      --src evals/answers/_prompts_c020_capture.json \\
      --out-prefix _prompts_c020_variant_ --variants A,D
"""
import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "evals"))

import lib_v3ab as L  # noqa: E402
from rulesagent.generate.answer import (  # noqa: E402
    SYSTEM_VERSIONS,
    _card_symbol_text,
    _format_cards,
    _symbol_reference_block,
    _symbols_present,
    build_prompt,
)
from rulesagent.tools.scryfall import get_card, parse_card_refs  # noqa: E402

SRC = REPO / "evals" / "answers" / "_prompts_C.json"
CARDS_JSONL = REPO / "evals" / "cards.jsonl"
OUT_DIR = REPO / "evals" / "answers"

# Recorded before the v4 edit (build_prompts_v4.py's own constant, unchanged
# here -- Sec 5c gate 1 is explicitly "unchanged" from the v4 script).
V3_SYSTEM_SHA256 = "25aa69e19208da80b033c15a19d11a3cafa90e23ee807552f17f758bedde06cc"

# variant letter -> (SYSTEM_VERSIONS key, inject symbols?)
VARIANTS: dict[str, tuple[int | str, bool]] = {
    "A": (3, False),
    "B": (3, True),
    "C": ("v4nl", False),
    "D": ("v4nl", True),
}

CARD_MARKER = "Card data:\n"
QUESTION_MARKER = "\n\nQuestion:"
RULINGS_HDR = "\nRulings:\n"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load(path: Path) -> dict:
    return json.loads(io.open(path, encoding="utf-8").read())


def out_path(letter: str, out_prefix: str = "_prompts_variant_") -> Path:
    return OUT_DIR / f"{out_prefix}{letter}.json"


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify existing output files instead of rewriting them")
    ap.add_argument("--src", type=Path, default=SRC,
                    help=f"capture to derive from (default: {SRC})")
    ap.add_argument("--out-prefix", default="_prompts_variant_",
                    help="output filenames are PREFIX + {A,B,C,D}.json "
                         "(default: %(default)r)")
    ap.add_argument("--variants", default="A,B,C,D",
                    help="comma-separated subset of variant letters to "
                         "derive, e.g. A,D (default: %(default)s)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing output file instead of "
                         "refusing to run")
    return ap


def resolve_variant_letters(raw: str) -> list[str] | None:
    """Parse --variants into an ordered, deduped list of letters, all valid
    keys of VARIANTS. Returns None (not a ValueError) for anything invalid
    or empty so callers can print a clean CLI error instead of a
    traceback."""
    letters = [v.strip() for v in raw.split(",") if v.strip()]
    if not letters:
        return None
    seen: set[str] = set()
    ordered = [v for v in letters if not (v in seen or seen.add(v))]
    if any(v not in VARIANTS for v in ordered):
        return None
    return ordered


def check_no_clobber(paths: list[Path], force: bool) -> list[Path]:
    """Paths that already exist on disk and would be silently overwritten.
    Empty when `force` is set, or when nothing collides. Callers are
    expected to call this BEFORE writing anything and abort if it's
    non-empty and not forced -- that's what makes an existing output file
    unclobberable by an ordinary invocation (one without --force),
    regardless of whether it was produced by a prior run of this script or
    by anything else."""
    if force:
        return []
    return [p for p in paths if p.exists()]


# ---------------------------------------------------------------------
# Splitting the frozen user block (shared by gates 2-5 and the builder)
# ---------------------------------------------------------------------

def split_question(user: str) -> tuple[str, str]:
    """(before, question): split at the literal '\\n\\nQuestion:' marker.
    `before` is everything up to (not including) the marker; `question` is
    the text after 'Question: ' (the space matches build_prompt's own
    `f"\\n\\nQuestion: {question}"`)."""
    idx = user.index(QUESTION_MARKER)
    before = user[:idx]
    after = user[idx + len(QUESTION_MARKER):]
    if not after.startswith(" "):
        raise ValueError("no space after the 'Question:' marker")
    return before, after[1:]


def split_before(before: str) -> tuple[str, str | None]:
    """(rules_context_text, card_block_text_or_None). card_block_text is the
    literal slice between 'Card data:\\n' and the end of `before` (== the
    end of the user block, since injection/question always come after) --
    None if this question has no card section."""
    idx = before.find(CARD_MARKER)
    if idx == -1:
        return before, None
    return before[:idx], before[idx + len(CARD_MARKER):]


def splice(before: str, block: str, question: str) -> str:
    """Rebuild a user string the way build_prompt() would: `before`,
    optionally the symbol reference block, then the Question marker."""
    user = before
    if block:
        user += f"\n\n{block}"
    user += f"{QUESTION_MARKER} {question}"
    return user


# ---------------------------------------------------------------------
# Gate 3 helper: recover the already-selected rulings verbatim from the
# frozen block (see the module docstring for why this doesn't re-run the
# live mini-RAG selection).
# ---------------------------------------------------------------------

_RULING_LINE_RE = re.compile(r"^\[(.+) ruling #(\d+)\] (.*)$", re.S)


def reconstruct_cards_for_gate3(qid: str, cards_raw: list, card_block_text: str):
    """Returns (rebuilt_cards, integrity_rows). `rebuilt_cards` carries each
    card's ALREADY-SELECTED "[Name ruling #N] text" lines (extracted
    verbatim from the block) as `.rulings`, so _format_cards(rebuilt_cards)
    should reproduce card_block_text byte-for-byte if our slice/markers are
    right. `integrity_rows` is [(name, index, text), ...] for the separate
    authenticity check against each card's raw (unlabeled) rulings."""
    segments = card_block_text.split("\n\n")
    if len(segments) != len(cards_raw):
        raise AssertionError(
            f"{qid}: card segment count {len(segments)} != {len(cards_raw)} cards "
            "(a card's own text likely contains a literal blank line)")
    rebuilt = []
    integrity_rows: list[tuple[str, int, str]] = []
    for card, seg in zip(cards_raw, segments):
        idx = seg.find(RULINGS_HDR)
        if idx == -1:
            rebuilt.append(card.model_copy(update={"rulings": []}))
            continue
        rulings_text = seg[idx + len(RULINGS_HDR):]
        raw_lines = re.split(r"\n(?=- \[)", rulings_text)
        labeled = []
        for line in raw_lines:
            if not line.startswith("- ["):
                raise AssertionError(f"{qid}: unexpected ruling line {line[:60]!r}")
            content = line[2:]
            labeled.append(content)
            m = _RULING_LINE_RE.match(content)
            if not m:
                raise AssertionError(f"{qid}: ruling line doesn't parse: {content[:80]!r}")
            name, i, text = m.group(1), int(m.group(2)), m.group(3)
            integrity_rows.append((name, i, text))
        rebuilt.append(card.model_copy(update={"rulings": labeled}))
    return rebuilt, integrity_rows


def main(argv: list[str] | None = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    failures: list[str] = []

    variant_letters = resolve_variant_letters(args.variants)
    if variant_letters is None:
        print(f"ERROR: --variants {args.variants!r} must be a comma-separated "
              f"subset of {sorted(VARIANTS)}")
        return 1
    selected_variants = {letter: VARIANTS[letter] for letter in variant_letters}

    src_path: Path = args.src
    out_prefix: str = args.out_prefix

    # Refuse to overwrite -- checked BEFORE any file is read or written, so
    # a bad invocation (e.g. running against a new capture with the old
    # default naming) aborts immediately instead of clobbering evidence.
    # `--check` never writes, so the guard doesn't apply to it.
    if not args.check:
        target_paths = [out_path(letter, out_prefix) for letter in selected_variants]
        clobber = check_no_clobber(target_paths, args.force)
        if clobber:
            print("\nERROR: refusing to overwrite existing output file(s) "
                  "(pass --force to overwrite):")
            for p in clobber:
                print(f"  - {p}")
            return 1

    src = load(src_path)
    prompts = src["prompts"]
    cards_jsonl = {json.loads(line)["id"]: json.loads(line)
                   for line in io.open(CARDS_JSONL, encoding="utf-8")}

    print(f"source          : {src_path.name}")
    print(f"rewrite_version : {src.get('rewrite_version')!r}")
    print(f"ruling_query_mode: {src.get('ruling_query_mode')!r}")

    # ---------------- gate 1: v3 digest -----------------------------
    systems = {e["system"] for e in prompts.values()}
    print(f"\n[gate 1] distinct system strings in capture: {len(systems)} (expect 1)")
    if len(systems) != 1:
        failures.append(f"capture holds {len(systems)} distinct system strings")
    captured_system = next(iter(systems))
    captured_sha = sha(captured_system)
    ok_v3 = captured_sha == V3_SYSTEM_SHA256
    print(f"[gate 1] captured system sha256: {captured_sha}")
    print(f"[gate 1] matches recorded v3 digest: {'PASS' if ok_v3 else 'FAIL'}")
    if not ok_v3:
        failures.append("captured system is not the recorded v3 SYSTEM")

    # id set completeness. QIDS is what the REST of the script iterates
    # over -- derived from the loaded capture itself, not a hardcoded
    # count, so a single-question source (e.g. a c020-only capture) works
    # the same way a 50-question one does. Against the untouched default
    # source, this is still checked against lib_v3ab.ALL_QIDS (the known
    # "should have all 50" oracle) -- byte-identical to the old gate. For
    # any other --src, there is no external oracle for what the id set
    # "should" be, so the expectation is just the source's own id set (a
    # self-consistency check: missing/extra can never fire, which is the
    # honest answer when there's nothing to compare against).
    ids = set(prompts)
    QIDS = sorted(ids)
    using_default_src = (src_path == SRC)
    expected_qids = L.ALL_QIDS if using_default_src else QIDS
    missing, extra = set(expected_qids) - ids, ids - set(expected_qids)
    print(f"\nquestion ids: {len(ids)} (expect {len(expected_qids)}); "
          f"missing={sorted(missing) or 'none'} extra={sorted(extra) or 'none'}")
    if missing or extra:
        failures.append("id set does not match ALL_QIDS" if using_default_src
                         else "id set does not match itself (should be impossible)")

    if failures:
        print("\nABORT (pre-derivation gates failed):")
        for f in failures:
            print(f"  - {f}")
        return 1

    # ---------------- marker-structure sanity (spec's "already
    # validated" claim, asserted here rather than trusted blind) --------
    # "card question" == present in cards.jsonl AND present in this
    # capture -- derived from QIDS, not a hardcoded "<= c019" cutoff, so a
    # c020-only source correctly gets card_qids == ["c020"] instead of [].
    card_qids = sorted(qid for qid in QIDS if qid in cards_jsonl)
    rules_qids = sorted(qid for qid in QIDS if qid not in card_qids)
    marker_bad = []
    for qid in QIDS:
        user = prompts[qid]["user"]
        n_card = user.count(CARD_MARKER)
        n_q = user.count(QUESTION_MARKER)
        expect_card = 1 if qid in card_qids else 0
        if n_card != expect_card or n_q != 1:
            marker_bad.append(qid)
    print(f"\nmarker structure: {len(QIDS) - len(marker_bad)}/{len(QIDS)} "
          f"as expected ({len(card_qids)} card qids w/ 1x 'Card data:', "
          f"{len(rules_qids)} rules qids w/ 0x, all w/ exactly 1x 'Question:')")
    if marker_bad:
        failures.append(f"marker structure violated for {marker_bad}")
        print("ABORT:", marker_bad)
        return 1

    # ---------------- resolve real cards for the card_qids -------------
    # Order matters (it's the order _format_cards renders them in, gate 3
    # checks byte equality): production resolves cards in FIRST-APPEARANCE
    # order of the `[Bracket]` tokens in the question (RulesAgent.answer(),
    # parse_card_refs + case-insensitive dedup), which is not always the
    # same order as cards.jsonl's "cards" list (e.g. c007 asks about
    # [Lightning Bolt] before [Mimic Vat] even though "cards" lists Mimic
    # Vat first) -- so tokens are parsed from the ORIGINAL bracketed
    # question text, not read off the "cards" field's order.
    cards_raw: dict[str, list] = {}
    for qid in card_qids:
        _stripped, tokens = parse_card_refs(cards_jsonl[qid]["question"])
        seen: set[str] = set()
        ordered_tokens = [t for t in tokens if not (t.lower() in seen or seen.add(t.lower()))]
        resolved = [get_card(t, no_refresh=True) for t in ordered_tokens]
        none_at = [t for t, c in zip(ordered_tokens, resolved) if c is None]
        if none_at:
            failures.append(f"{qid}: get_card() returned None for {none_at}")
            continue
        # Sanity cross-check against cards.jsonl's "cards" list -- loose
        # (substring, not equality): a modal DFC's resolved Card.name is
        # Scryfall's full "Front // Back" (e.g. "Valki, God of Lies //
        # Tibalt, Cosmic Impostor"), while cards.jsonl records only the
        # front face name ("Valki, God of Lies") that was actually
        # bracketed in the question.
        expected_names = cards_jsonl[qid]["cards"]
        got_names = [c.name for c in resolved]
        unmatched = [e for e in expected_names
                     if not any(e in g for g in got_names)]
        if len(got_names) != len(expected_names) or unmatched:
            failures.append(
                f"{qid}: resolved card names {got_names} don't line up with "
                f"cards.jsonl's {expected_names} (unmatched: {unmatched})")
            continue
        cards_raw[qid] = resolved
    if failures:
        print("\nABORT (card resolution failed):")
        for f in failures:
            print(f"  - {f}")
        return 1

    # ---------------- per-question derivation (source of truth for the
    # injected variants, and for gates 2-5) -----------------------------
    derived: dict[str, dict] = {}
    for qid in QIDS:
        user = prompts[qid]["user"]
        before, question = split_question(user)
        rules_context_text, card_block_text = split_before(before)
        if card_block_text is not None:
            card_text = _card_symbol_text(cards_raw[qid])
        else:
            card_text = ""
        # Exactly build_prompt()'s own scan call (Sec 5a): cards' mana_cost +
        # oracle_text (all faces) plus the question text, never the rules
        # context. Jon's ruling #7 (inject on a symbol named in a card-less
        # question) falls out for free -- card_text is "" and the scan is
        # just the question.
        symbols = _symbols_present(f"{card_text} {question}")
        block = _symbol_reference_block(symbols)
        derived[qid] = {
            "user": user, "before": before, "question": question,
            "rules_context_text": rules_context_text,
            "card_block_text": card_block_text,
            "symbols": symbols, "block": block,
        }

    # ---------------- build (or load, under --check) the selected variants
    outs: dict[str, dict] = {}
    for letter, (sysver, inject) in selected_variants.items():
        path = out_path(letter, out_prefix)
        if args.check:
            if not path.exists():
                print(f"\n--check: {path.name} does not exist")
                return 1
            outs[letter] = load(path)
            continue
        system_text = SYSTEM_VERSIONS[sysver]
        out_prompts = {}
        for qid in QIDS:
            d = derived[qid]
            user = splice(d["before"], d["block"], d["question"]) if inject else d["user"]
            out_prompts[qid] = {"system": system_text, "user": user}
        outs[letter] = {
            "derived_from": src_path.name,
            "variant": letter,
            "system_version": sysver,
            "inject": inject,
            "system_sha256": sha(system_text),
            "rewrite_version": src["rewrite_version"],
            "ruling_query_mode": src["ruling_query_mode"],
            "n_questions": src["n_questions"],
            "prompts": out_prompts,
        }

    if args.check:
        print(f"\n--check mode: verifying existing files without rewriting")

    # ---------------- gate 2: user-block equality -----------------------
    print(f"\n[gate 2] user-block equality (non-injected byte-identical to "
          f"source; injected byte-identical to source after removing the splice):")
    for letter, (sysver, inject) in selected_variants.items():
        equal = 0
        for qid in QIDS:
            out_user = outs[letter]["prompts"][qid]["user"]
            d = derived[qid]
            if inject:
                same = out_user == splice(d["before"], d["block"], d["question"])
            else:
                same = out_user == d["user"]
            equal += same
            if not same:
                print(f"    {letter}/{qid}: FAIL")
                failures.append(f"{letter}/{qid} user block mismatch")
        status = "PASS" if equal == len(QIDS) else "FAIL"
        print(f"    variant {letter} (sys={sysver}, inject={inject}): "
              f"{equal}/{len(QIDS)} -> {status}")

    # also verify the written system string is single and correct per variant
    for letter, (sysver, inject) in selected_variants.items():
        out_systems = {e["system"] for e in outs[letter]["prompts"].values()}
        expect = SYSTEM_VERSIONS[sysver]
        ok = len(out_systems) == 1 and next(iter(out_systems)) == expect
        if not ok:
            failures.append(f"{letter}: system strings not uniformly the {sysver} SYSTEM")
            print(f"    variant {letter} system check: FAIL")

    # ---------------- gate 3: card-block extraction ----------------------
    print(f"\n[gate 3] card-block extraction (sliced block == _format_cards(cards)):")
    extraction_ok = 0
    integrity_ok = 0
    integrity_total = 0
    for qid in card_qids:
        d = derived[qid]
        try:
            rebuilt, integrity_rows = reconstruct_cards_for_gate3(
                qid, cards_raw[qid], d["card_block_text"])
        except AssertionError as e:
            print(f"    {qid}: FAIL  ({e})")
            failures.append(f"{qid} gate3 parse: {e}")
            continue
        formatted = _format_cards(rebuilt)
        same = formatted == d["card_block_text"]
        extraction_ok += same
        if not same:
            print(f"    {qid}: FAIL  (reconstruction != sliced block)")
            failures.append(f"{qid} gate3 extraction mismatch")

        # authenticity: every extracted "[Name ruling #N] text" really is
        # card.rulings[N] on the real (raw, unlabeled) card -- no live
        # relevance-selection re-derivation needed for this check.
        by_name = {c.name: c for c in cards_raw[qid]}
        for name, i, text in integrity_rows:
            integrity_total += 1
            card = by_name.get(name)
            ok = card is not None and 0 <= i < len(card.rulings) and card.rulings[i] == text
            if ok:
                integrity_ok += 1
            else:
                print(f"    {qid}: ruling authenticity FAIL for [{name} ruling #{i}]")
                failures.append(f"{qid} ruling authenticity: {name}#{i}")
    print(f"    {extraction_ok}/{len(card_qids)} card blocks byte-identical to "
          f"reconstruction -> {'PASS' if extraction_ok == len(card_qids) else 'FAIL'}")
    print(f"    {integrity_ok}/{integrity_total} extracted ruling labels verified "
          f"authentic (index + text match the real card) -> "
          f"{'PASS' if integrity_ok == integrity_total else 'FAIL'}")

    # ---------------- gate 4: over-trigger --------------------------------
    print(f"\n[gate 4] over-trigger (injected symbols subset of cards+question; "
          f"none found only in the rules-context portion):")
    violations = 0
    exclusion_active = 0
    c014_report = None
    for qid in QIDS:
        d = derived[qid]
        cards_and_q = d["symbols"]
        whole_text = d["before"] + " " + d["question"]
        whole_symbols = _symbols_present(whole_text)
        rules_only = whole_symbols - cards_and_q
        if rules_only:
            exclusion_active += 1
        # (a) subset check -- tautological by construction (we only ever
        # scanned cards+question), asserted anyway as a real regression
        # guard on the derivation code itself.
        if not cards_and_q.issubset(whole_symbols):
            violations += 1
            print(f"    {qid}: FAIL (cards+question symbols not subset of whole block)")
            failures.append(f"{qid} gate4 subset violation")
        # (b) the load-bearing direction: no cards+question symbol leaks
        # from the rules-context-only set.
        if cards_and_q & rules_only:
            violations += 1
            print(f"    {qid}: FAIL (injected symbol found only in rules context: "
                  f"{cards_and_q & rules_only})")
            failures.append(f"{qid} gate4 over-trigger")
        if qid == "c014":
            c014_report = (len(whole_symbols), len(cards_and_q))
    print(f"    {len(QIDS) - violations}/{len(QIDS)} clean "
          f"-> {'PASS' if violations == 0 else 'FAIL'}")
    print(f"    {exclusion_active}/{len(QIDS)} questions have >=1 symbol found "
          f"ONLY in rules context (the exclusion is doing real work on these)")
    if c014_report:
        print(f"    c014 cross-check vs plan Sec 5a: whole-block distinct symbols="
              f"{c014_report[0]} (plan says 8), card+question distinct symbols="
              f"{c014_report[1]} (plan says 6)")

    # ---------------- gate 5: production parity ---------------------------
    print(f"\n[gate 5] production parity (real build_prompt() on structured "
          f"inputs reproduces the derivation's reference block):")
    parity_ok = 0
    for qid in QIDS:
        d = derived[qid]
        cards = cards_raw.get(qid, [])
        _sys2, user2 = build_prompt(d["question"], [], cards)
        before2, question2 = split_question(user2)
        if question2 != d["question"]:
            failures.append(f"{qid} gate5: question text drifted through build_prompt")
            print(f"    {qid}: FAIL (question text mismatch)")
            continue
        if cards:
            expected_cards_text = _format_cards(cards)
            idx = before2.find(CARD_MARKER)
            card_seg = before2[idx + len(CARD_MARKER):] if idx != -1 else None
            if card_seg is None or not card_seg.startswith(expected_cards_text):
                failures.append(f"{qid} gate5: could not locate card section in build_prompt output")
                print(f"    {qid}: FAIL (card section extraction)")
                continue
            remainder = card_seg[len(expected_cards_text):]
        else:
            prefix = "Rules context:\n"
            if not before2.startswith(prefix):
                failures.append(f"{qid} gate5: unexpected build_prompt prefix")
                print(f"    {qid}: FAIL (prefix)")
                continue
            remainder = before2[len(prefix):]
        if remainder == "":
            block2 = ""
        elif remainder.startswith("\n\n"):
            block2 = remainder[2:]
        else:
            failures.append(f"{qid} gate5: unexpected remainder {remainder[:40]!r}")
            print(f"    {qid}: FAIL (remainder shape)")
            continue
        same = block2 == d["block"]
        parity_ok += same
        if not same:
            print(f"    {qid}: FAIL (reference block differs from build_prompt's own)")
            failures.append(f"{qid} gate5 parity mismatch")
    print(f"    {parity_ok}/{len(QIDS)} identical -> "
          f"{'PASS' if parity_ok == len(QIDS) else 'FAIL'}")

    # ---------------- final verdict / write -------------------------------
    if failures:
        print("\nFAIL -- not written:" if not args.check else "\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1

    if not args.check:
        for letter in selected_variants:
            path = out_path(letter, out_prefix)
            io.open(path, "w", encoding="utf-8").write(
                json.dumps(outs[letter], ensure_ascii=False, indent=1))
            print(f"\nwrote {path} ({path.stat().st_size} bytes)")

    # ---------------- cost table -------------------------------------------
    print(f"\ncost table (measured total input chars = SYSTEM + user, all "
          f"{len(QIDS)} questions):")
    print(f"    {'variant':8} {'sys_chars':>10} {'sum_user_chars':>15} "
          f"{'total_chars':>12} {'avg/query':>10} {'injected_qs':>12}")
    for letter, (sysver, inject) in selected_variants.items():
        sys_chars = len(SYSTEM_VERSIONS[sysver])
        user_chars = sum(len(e["user"]) for e in outs[letter]["prompts"].values())
        total = sys_chars * len(QIDS) + user_chars
        n_injected = sum(1 for qid in QIDS if inject and derived[qid]["block"])
        print(f"    {letter:8} {sys_chars:>10} {user_chars:>15} {total:>12} "
              f"{total / len(QIDS):>10.1f} {n_injected:>12}")

    print(f"\nDONE -- all gates PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

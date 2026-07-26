"""Build the pure-rules held-out eval set from batch 1's approved decisions.

Joins evals/purerules_candidates.json (the drafted questions, one row per
candidate) with data/parsed/purerules_decisions.json (Jon's per-candidate
approve/rewrite/cut calls from the approval UI) into
evals/purerules.jsonl -- a file in the exact schema run_eval.load_questions()
and run_answer_eval.py already read (same shape as evals/rulesguru.jsonl:
EvalQuestion fields + answer_gold), so it drops straight in as
`--questions evals/purerules.jsonl` on either script with no new loader code.

This is deliberately dumb and mechanical: no drafting, no LLM calls, no
judgment about what a question should say. It only:
  - joins decisions to candidates by id (errors loudly on any mismatch --
    an undecided candidate or an orphaned decision is a review gap, not
    something to ship silently),
  - drops "cut" rows,
  - takes the approved/rewritten text verbatim from the decision,
  - carries `match`/`level`/`complexity`/`tags`/`url` forward from the
    ORIGINAL RulesGuru source row (evals/_layers_union_slice.jsonl), since
    those describe the underlying interaction and a paraphrase doesn't
    change them,
  - validates schema conformance, id/source_qid uniqueness, and that every
    gold CR id actually resolves to a real chunk (parsed from the local CR
    text file -- deterministic, no network, no API).

Run: .venv/Scripts/python.exe evals/build_purerules_holdout.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rulesagent.contracts import EvalQuestion  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

CANDIDATES = ROOT / "evals" / "purerules_candidates.json"
DECISIONS = ROOT / "data" / "parsed" / "purerules_decisions.json"
SLICE = ROOT / "evals" / "_layers_union_slice.jsonl"
CR_PATH = ROOT / "data" / "raw" / "MagicCompRules 20260619.txt"
OUT = ROOT / "evals" / "purerules.jsonl"

# EvalQuestion.kind is a closed Literal that predates external question
# sources (run_eval.load_questions coerces "rulesguru" -> "other" the same
# way for evals/rulesguru.jsonl). "purerules" is kept in the file for
# provenance and coerced only for the schema-validation check here.
_KNOWN_KINDS = {"rule", "glossary", "interaction", "other", "card-interaction"}


class BuildError(Exception):
    pass


def load_json(path: Path) -> dict:
    if not path.exists():
        raise BuildError(f"missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise BuildError(f"missing input: {path}")
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["id"]] = row
    return rows


def build_rows(candidates: list[dict], decisions: list[dict], source_rows: dict[str, dict]) -> list[dict]:
    """Pure join: candidates + decisions + source rows -> final eval rows.

    No file I/O, no CR parsing -- takes plain data in, returns plain data
    out, so this is unit-testable without touching disk (same shape as
    fetch_rulesguru.convert_record's split, per tests/test_rulesguru_convert.py).
    """
    cand_by_id = {c["id"]: c for c in candidates}
    dec_by_id = {d["id"]: d for d in decisions}

    cand_ids = set(cand_by_id)
    dec_ids = set(dec_by_id)
    undecided = sorted(cand_ids - dec_ids)
    orphaned = sorted(dec_ids - cand_ids)
    if undecided:
        raise BuildError(f"candidate(s) with no decision recorded: {undecided}")
    if orphaned:
        raise BuildError(f"decision(s) reference unknown candidate id(s): {orphaned}")

    rows = []
    for cid in sorted(cand_by_id):
        cand = cand_by_id[cid]
        dec = dec_by_id[cid]
        if dec["decision"] == "cut":
            continue
        if dec["decision"] not in ("approve", "rewrite"):
            raise BuildError(f"{cid}: unrecognized decision {dec['decision']!r}")

        source_qid = cand["source_qid"]
        src = source_rows.get(source_qid)
        if src is None:
            raise BuildError(f"{cid}: source row {source_qid!r} not found in {SLICE.name}")

        rows.append({
            "id": cid,
            "question": dec["question"],
            "gold": list(cand["source_gold_rules"]),
            "match": src.get("match", "any"),
            "kind": "purerules",
            "answer_gold": dec["gold"],
            "level": src.get("level"),
            "complexity": src.get("complexity"),
            "tags": src.get("tags", []),
            "url": src.get("url"),
            "source_qid": source_qid,
            "edited": bool(dec.get("edited", False)),
        })
    return rows


def validate_schema(rows: list[dict]) -> None:
    for row in rows:
        payload = dict(row)
        if payload.get("kind") not in _KNOWN_KINDS:
            payload["kind"] = "other"
        EvalQuestion.model_validate(payload)  # raises on any conformance failure


def validate_unique(rows: list[dict]) -> None:
    ids = [r["id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise BuildError(f"duplicate id(s) in output: {dupes}")
    qids = [r["source_qid"] for r in rows]
    dupe_qids = sorted({q for q in qids if qids.count(q) > 1})
    if dupe_qids:
        raise BuildError(f"duplicate source_qid(s) in output (near-duplicate questions "
                          f"should be dropped at draft time, not shipped twice): {dupe_qids}")


def validate_gold_ids_exist(rows: list[dict]) -> None:
    """Every gold CR id must resolve to a real chunk, or the question can
    never be hit at any k by construction (the exact bug class
    test_cr_parse_coverage.py exists to catch on the corpus side; this is
    the same check applied to a question set instead of the corpus)."""
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_ids = {c.source_id for c in chunks}
    missing_by_row = {}
    for row in rows:
        missing = [g for g in row["gold"] if g not in chunk_ids]
        if missing:
            missing_by_row[row["id"]] = missing
    if missing_by_row:
        raise BuildError(f"gold ids not found as real CR chunks: {missing_by_row}")


def main() -> None:
    candidates_doc = load_json(CANDIDATES)
    decisions_doc = load_json(DECISIONS)
    source_rows = load_source_rows(SLICE)

    rows = build_rows(candidates_doc["candidates"], decisions_doc["decisions"], source_rows)
    validate_unique(rows)
    validate_schema(rows)
    validate_gold_ids_exist(rows)

    n_cand = len(candidates_doc["candidates"])
    n_dec = len(decisions_doc["decisions"])
    n_cut = n_dec - len(rows)
    n_edited = sum(1 for r in rows if r["edited"])

    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(rows)} questions)")
    print(f"  candidates drafted: {n_cand} | decisions recorded: {n_dec} | "
          f"cut: {n_cut} | rewritten: {n_edited} | approved as-is: {len(rows) - n_edited}")
    print("  schema: OK | unique ids: OK | gold ids resolve to real CR chunks: OK")


if __name__ == "__main__":
    main()

"""Assemble the batch-1 gold-audit input: the derivability 15, plus a LABELLED
retrieval probe.

docs/spec-gold-audit-ui.md. The rows are the 11 unreachable + 4 incomplete-gold
questions from docs/results-derivability.md, which live already assembled in
evals/answers/derivability_C_failures.json.

WHY A PROBE AT ALL. Those rows carry no `retrieved_rule_ids`, and that is by
design rather than by defect: derivability arm B was gold-only, with retrieval
switched off, which is exactly what let it separate retrieval failure from
reasoning failure. So there is no "what the run pulled" to show. This script
retrieves NOW, against the CURRENT index, and marks every row it touches
`retrieved_provenance: "probe"` so the UI can say so on the row itself.

That label is the whole point. The index has changed since those runs (10
questions repointed onto child rules, 606.5 added), so the probe answers "would
retrieval find this today?" and NOT "what did that run pull?". This repo's
recurring defect is a number arriving with an unchecked claim about how it was
produced; an unlabelled retrieval panel would be exactly that.

FIDELITY, STATED PLAINLY. The probe is the pure-vector path -- store.search()
at TOP_K, no query rewriting. Production rewrites first (answer.py's
REWRITE_MODEL/REWRITE_N), so this is a FLOOR on what production would surface,
not a reproduction of it. It is deterministic apart from Voyage's own query-
embedding wobble, costs no Anthropic tokens at all, and is the right material
for the human judgment this batch exists to support: "which CR rules are near
this question", not "which arm won". `probe_config` records the parameters on
every row so the claim stays checkable.

Batch 2 rows (h2h/costbase) already carry a real `retrieved_rule_ids` and must
be built with `--provenance run`, which keeps their recorded ids and only
resolves the text.

Usage:
    python evals/build_gold_audit_input.py
    python evals/build_gold_audit_input.py --in <answers.json> --provenance run
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARSED = REPO / "data" / "parsed"
VECTOR_MODEL = "voyage-4-large"
DEFAULT_IN = REPO / "evals" / "answers" / "derivability_C_failures.json"
DEFAULT_OUT = PARSED / "gold_audit_input.json"


def _probe(store, rows: list[dict], k: int) -> int:
    """Retrieve for each row and attach ids + text. Returns rows touched.

    Text is attached HERE rather than in build_grading_ui.py so the UI stays a
    pure renderer: it is handed ids and a text map and never needs to load a
    600MB vector store to display a panel.
    """
    for r in rows:
        hits = store.search(r["question"], k)
        r["retrieved_rule_ids"] = [h.chunk.source_id for h in hits]
        r["retrieved_text"] = {h.chunk.source_id: h.chunk.text for h in hits}
    return len(rows)


def _resolve_recorded(store, rows: list[dict]) -> tuple[int, int]:
    """Batch-2 path: keep each row's RECORDED retrieved ids and only look up
    their text. Returns (rows touched, ids that had no chunk).

    A recorded id with no chunk behind it is a real finding -- an id that was
    retrieved when the run happened but is not in the index now -- so it is
    counted and left absent from the map, which renders as the UI's visible
    "(text not found as a chunk)" rather than being quietly dropped.
    """
    by_id = {c.source_id: c.text for c in store.chunks}
    touched = missing = 0
    for r in rows:
        ids = r.get("retrieved_rule_ids") or []
        if not ids:
            continue
        r["retrieved_text"] = {i: by_id[i] for i in ids if i in by_id}
        missing += sum(1 for i in ids if i not in by_id)
        touched += 1
    return touched, missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=DEFAULT_IN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--provenance", choices=("probe", "run"), default="probe",
        help="probe: retrieve now against the current index (rows that recorded "
        "nothing, e.g. the gold-only derivability arms). run: keep each row's "
        "recorded retrieved_rule_ids and only resolve their text (batch 2). "
        "The value is written onto every row and the UI labels the panel with it.",
    )
    ap.add_argument("--k", type=int, default=None,
                    help="probe depth (default: answer.py's TOP_K)")
    args = ap.parse_args()

    from rulesagent.generate.answer import TOP_K
    from rulesagent.index.store import VectorStore

    k = args.k if args.k is not None else TOP_K
    rows = json.loads(args.inp.read_text(encoding="utf-8"))
    pkl = PARSED / f"vector_{VECTOR_MODEL}.pkl"
    store = VectorStore.load(pkl)

    if args.provenance == "probe":
        touched = _probe(store, rows, k)
        missing = 0
        note = (f"vector top-{k}, no rewriter, index {pkl.name}, probed {date.today()}")
    else:
        touched, missing = _resolve_recorded(store, rows)
        note = f"recorded by the run; text resolved from {pkl.name}"

    # Card names, derived the way PRODUCTION derives them.
    #
    # build_grading_ui.py takes them from the questions file's `cards` field,
    # but all 150 RulesGuru questions have `cards: null` -- that set never
    # populated it. answer.py does not use it either: it calls parse_card_refs()
    # on the question text at answer time. So every RulesGuru row has been
    # rendering with no card panel and no Scryfall rulings, not because the data
    # is missing but because the enrichment was keyed to a field this set leaves
    # empty. These 15 questions reference 40 cards between them, and the rulings
    # are the evidence the card-ruling-outranks-gold exception rests on.
    from rulesagent.tools.scryfall import parse_card_refs
    n_refs = 0
    for r in rows:
        r["retrieved_provenance"] = args.provenance
        r["probe_config"] = note
        _, refs = parse_card_refs(r["question"])
        r["card_names"] = refs
        n_refs += len(refs)
    print(f"[cards] {n_refs} card ref(s) parsed from question text across "
          f"{len(rows)} rows")

    args.out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    n_ids = sum(len(r.get("retrieved_rule_ids") or []) for r in rows)
    print(f"Wrote {args.out}  ({len(rows)} rows, {touched} with retrieval, {n_ids} ids)")
    print(f"[provenance] {args.provenance} — {note}")
    if missing:
        print(f"[warn] {missing} recorded id(s) have no chunk in the current index; "
              f"they will render as '(text not found as a chunk)'")


if __name__ == "__main__":
    main()

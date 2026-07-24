"""Attach oracle text to pure-rules eval candidates (Jon's UI request, 2026-07-24).

The approval UI showed each source question with bare `[Card Name]` references,
so checking whether a generalization actually says the same thing meant looking
cards up by hand. This fetches the real oracle text for every card each source
question references and writes it into evals/purerules_candidates.json as
`source_cards`, which the UI then renders inside the collapsed "original"
section.

Card names come from the RulesGuru row's own `cards` field (not parsed out of
the question text), and oracle text comes from Scryfall via
rulesagent.tools.scryfall.get_card -- never from memory, per the repo rule.

Idempotent: re-running refreshes the text in place. Cards that can't be
resolved are recorded with an explicit `"error"` rather than silently dropped,
so a missing card is visible in the UI instead of looking like a card with no
rules text.

Run:  .venv/Scripts/python.exe evals/enrich_purerules_cards.py
"""

from __future__ import annotations

import json
from pathlib import Path

from rulesagent.tools.scryfall import get_card

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "evals" / "purerules_candidates.json"
SLICE = ROOT / "evals" / "_layers_union_slice.jsonl"


def source_rows() -> dict[str, dict]:
    if not SLICE.exists():
        raise SystemExit(f"missing source slice: {SLICE}")
    rows = {}
    with SLICE.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def card_entry(name: str) -> dict:
    """One card's display payload, or an explicit error entry."""
    try:
        card = get_card(name)
    except Exception as e:  # pragma: no cover - network/shape defensive
        return {"name": name, "error": f"lookup failed: {e!r}"}
    if card is None:
        return {"name": name, "error": "not found on Scryfall"}
    pt = None
    power, toughness = getattr(card, "power", None), getattr(card, "toughness", None)
    if power is not None and toughness is not None:
        pt = f"{power}/{toughness}"
    return {
        "name": card.name,
        "type_line": card.type_line,
        "pt": pt,
        "oracle_text": card.oracle_text or "",
    }


def main() -> None:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    rows = source_rows()
    cache: dict[str, dict] = {}
    total = missing = 0

    for cand in data.get("candidates", []):
        row = rows.get(cand["source_qid"])
        if row is None:
            cand["source_cards"] = []
            print(f"  {cand['id']}: source row {cand['source_qid']} not in slice file")
            continue
        entries = []
        for name in row.get("cards") or []:
            if name not in cache:
                cache[name] = card_entry(name)
            entry = cache[name]
            entries.append(entry)
            total += 1
            if "error" in entry:
                missing += 1
        cand["source_cards"] = entries
        names = ", ".join(e["name"] for e in entries) or "(none)"
        print(f"  {cand['id']} <- {cand['source_qid']}: {names}")

    CANDIDATES.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {CANDIDATES}")
    print(f"{total} card references, {len(cache)} unique, {missing} unresolved")


if __name__ == "__main__":
    main()

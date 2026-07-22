"""Adapt OpenRouter arm outputs (and the split sonnet re-grade) into the
review format build_grading_ui.py expects, then build one grading HTML per
arm for Jon's six-arm hand-grading session.

Arm rows carry text/citations but not the gold/cited rule-text panels the
grading UI shows; this resolves them from the CR chunk map exactly the way
run_answer_eval.py does (same {rule_id: chunk_text} dicts). Fields the arm
path never had (rewrite_queries, clarification) are set to their honest
empty values so the UI renders them as absent rather than lying.

Run: `uv run python evals/build_arm_review.py`
Outputs: data/parsed/review_<label>.json + data/parsed/grading_<label>.html
Grade each HTML in a browser; export saves verdicts -- store each as
evals/verdicts_<label>.json for the L2 roll-up.
"""

import json
import subprocess
import sys
from pathlib import Path

EVALS = Path(__file__).parent
ROOT = EVALS.parent
ANS = EVALS / "answers"
PARSED = ROOT / "data" / "parsed"

sys.path.insert(0, str(EVALS))
sys.path.insert(0, str(ROOT / "src"))
from run_eval import CR_PATH  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

ARMS = [
    ("sonnet-v2", None),  # special-cased: merge the two run_answer_eval files
    ("deepseek-v4-pro", "deepseek-deepseek-v4-pro"),
    ("deepseek-v4-flash", "deepseek-deepseek-v4-flash"),
    ("deepseek-v3-2", "deepseek-deepseek-v3-2"),
    ("gemini-flash-lite", "google-gemini-2-5-flash-lite"),
    ("gpt-5-mini", "openai-gpt-5-mini"),
]


def load_meta():
    """id -> {gold, match, kind} from both question files."""
    meta = {}
    for name in ("questions.jsonl", "cards.jsonl"):
        for line in (EVALS / name).open(encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                meta[row["id"]] = {
                    "gold": row.get("gold", []),
                    "match": row.get("match", "any"),
                    "kind": row.get("kind", ""),
                }
    return meta


def main() -> None:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunk_map = {c.source_id: c for c in chunk_rules(rules, glossary)}
    meta = load_meta()

    for label, slug in ARMS:
        if slug is None:
            rows = []
            for f in ("sonnet_v2_rules.json", "sonnet_v2_cards.json"):
                rows += json.loads((ANS / f).read_text(encoding="utf-8"))
        else:
            data = json.loads((ANS / f"openrouter_{slug}.json").read_text(encoding="utf-8"))
            rows = []
            for r in data["results"]:
                if r.get("error"):
                    continue  # error rows have no answer to grade
                m = meta.get(r["id"], {"gold": [], "match": "any", "kind": ""})
                cites = r["citations"] or []
                rows.append({
                    "id": r["id"],
                    "question": r["question"],
                    "match": m["match"],
                    "kind": m["kind"],
                    "answered": r["answered"],
                    "answer": r["text"] or "",
                    "citations": cites,
                    "gold": m["gold"],
                    "gold_text": {g: chunk_map[g].text for g in m["gold"] if g in chunk_map},
                    "cited_text": {c: chunk_map[c].text for c in cites if c in chunk_map},
                    "rewrite_queries": [],
                    "clarification": None,
                    "show_rewrite": False,
                })
        review_path = PARSED / f"review_{label}.json"
        review_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        out_html = PARSED / f"grading_{label}.html"
        subprocess.run(
            [sys.executable, str(EVALS / "build_grading_ui.py"),
             "--in", str(review_path), "--out", str(out_html)],
            check=True,
        )
        print(f"{label}: {len(rows)} answers -> {out_html.name}")


if __name__ == "__main__":
    main()

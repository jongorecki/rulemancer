"""Shared loading/parsing helpers for the prompt-v3 A/B (Task 3).

Bridges two file-naming conventions that Task 2's runners produced:
  - 5 OpenRouter arms: evals/answers/<arm>_<cond>_r<run>.json
    (dict with a "results" list; answer text lives in row["text"]).
  - sonnet (split, old convention): evals/answers/sonnet_<cond>_r<run>_rules.json
    (31 rows) + evals/answers/sonnet_<cond>_r<run>_cards.json (19 rows),
    concatenated to 50; each row is a flat dict, answer text lives in
    row["answer"].

Condition A (the baseline) was never re-run -- it's the verdicts already on
file. Two label families for it:
  - deepseek-v3-2: evals/verdicts_deepseek-v3-2.json (Jon's hand-graded
    ground truth, no "_final" suffix) + data/parsed/review_deepseek-v3-2.json
    for the answer text.
  - the other 5 arms (sonnet-v2, deepseek-v4-pro, deepseek-v4-flash,
    gemini-flash-lite, gpt-5-mini): evals/verdicts_<label>_final.json +
    data/parsed/review_<label>.json.

Nothing here edits judge_arm_pairs.py, judge_bakeoff.py, or any
verdicts_*.json -- this module only normalizes shapes so those frozen
pieces can be driven unchanged.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).parent.parent
EVALS = Path(__file__).parent
PARSED = REPO / "data" / "parsed"

# answers-file label -> condition-A review/verdicts label
REVIEW_LABEL = {
    "deepseek-v3-2": "deepseek-v3-2",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "gemini-flash-lite": "gemini-flash-lite",
    "gpt-5-mini": "gpt-5-mini",
    "sonnet": "sonnet-v2",
}
ARMS = list(REVIEW_LABEL)  # answers-file labels, canonical order
CONDITIONS = ["B", "C", "D"]
RUNS = [1, 2]

# baselines, post-c004-ruling (docs/plan-prompt-tuning.md, task-3 brief)
BASELINE_CORRECT = {
    "sonnet": 46,
    "deepseek-v4-pro": 44,
    "deepseek-v3-2": 43,
    "deepseek-v4-flash": 42,
    "gpt-5-mini": 42,
    "gemini-flash-lite": 38,
}

# q023 was swapped out for q032 at some point before this A/B (confirmed
# against evals/questions.jsonl and _prompts_B/C/D.json -- q023 is absent
# everywhere, q032 present everywhere); the id set is NOT a clean 1..31 run.
ALL_QIDS = sorted(
    {f"q{n:03d}" for n in range(1, 32) if n != 23} | {"q032"}
    | {f"c{n:03d}" for n in range(1, 20)}
)

# Known persistent provider-side failure (task brief): gemini-flash-lite
# condition D, question c003, both runs. Never counts as a silent wrong
# answer, never crashes the pipeline.
KNOWN_EXCEPTIONS = {("gemini-flash-lite", "D", 1, "c003"), ("gemini-flash-lite", "D", 2, "c003")}


def norm_cite(c: str) -> str:
    """Strip one layer of enclosing [] and surrounding whitespace so
    "[702.26d]", "702.26d", and " [702.26d] " all compare equal."""
    c = (c or "").strip()
    if c.startswith("[") and c.endswith("]"):
        c = c[1:-1].strip()
    return c


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------
# Condition-A reference (baseline) -- answer text + Jon-derived verdict
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def review_rows_by_id(arm: str) -> dict[str, dict]:
    """Full condition-A data/parsed/review_<label>.json rows (kind, match,
    gold, gold_text, etc.) indexed by question id -- for building Jon's
    grading-queue rows in the shape build_grading_ui.py expects."""
    label = REVIEW_LABEL[arm]
    review = _load_json(PARSED / f"review_{label}.json")
    return {r["id"]: r for r in review}


@lru_cache(maxsize=None)
def condition_a_reference(arm: str) -> dict[str, dict]:
    """{qid: {"answer": str, "verdict": "correct"|"partial"|"wrong"}} for
    arm's condition-A (v2 baseline) run. Read-only source data."""
    label = REVIEW_LABEL[arm]
    review = _load_json(PARSED / f"review_{label}.json")
    if label == "deepseek-v3-2":
        verdicts_path = EVALS / "verdicts_deepseek-v3-2.json"
    else:
        verdicts_path = EVALS / f"verdicts_{label}_final.json"
    verdicts = _load_json(verdicts_path)
    verdict_by_id = {v["id"]: v["verdict"] for v in verdicts}
    out = {}
    for row in review:
        qid = row["id"]
        out[qid] = {
            "answer": row.get("answer") or "",
            "verdict": verdict_by_id.get(qid),
            "gold": row.get("gold") or [],
        }
    missing = set(ALL_QIDS) - set(out)
    if missing:
        raise ValueError(f"condition_a_reference({arm}): missing ids {sorted(missing)}")
    return out


# ------------------------------------------------------------------
# Condition B/C/D candidate runs
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def load_condition_run(arm: str, cond: str, run: int) -> tuple[dict, ...]:
    """Normalized rows for one (arm, condition, run): tuple of
    {id, question, answered, answer, citations (normalized, no brackets),
    error, exception} sorted by id. 50 rows always (id set == ALL_QIDS)."""
    if arm == "sonnet":
        rules = _load_json(EVALS / "answers" / f"sonnet_{cond}_r{run}_rules.json")
        cards = _load_json(EVALS / "answers" / f"sonnet_{cond}_r{run}_cards.json")
        raw_rows = rules + cards
        text_key = "answer"
    else:
        payload = _load_json(EVALS / "answers" / f"{arm}_{cond}_r{run}.json")
        raw_rows = payload["results"]
        text_key = "text"

    rows = []
    for r in raw_rows:
        qid = r["id"]
        error = r.get("error")
        answer_text = r.get(text_key)
        citations = [norm_cite(c) for c in (r.get("citations") or [])]
        exception = None
        if (arm, cond, run, qid) in KNOWN_EXCEPTIONS:
            exception = "known_provider_error"
        elif error:
            exception = "provider_error"
        elif r.get("answered") is None and answer_text is None:
            exception = "unjudgeable_no_answer"
        rows.append({
            "id": qid,
            "question": r.get("question", ""),
            "answered": r.get("answered"),
            "answer": answer_text,
            "citations": citations,
            "error": error,
            "exception": exception,
        })
    rows.sort(key=lambda r: r["id"])
    ids = {r["id"] for r in rows}
    missing = set(ALL_QIDS) - ids
    if missing:
        raise ValueError(f"load_condition_run({arm},{cond},r{run}): missing ids {sorted(missing)}")
    return tuple(rows)


# ------------------------------------------------------------------
# _prompts_<cond>.json -- provided-context bracket-label sets
# ------------------------------------------------------------------

BRACKET_RE = re.compile(r"\[([^\]\n]{1,80}?)\]")
CARD_DATA_MARKER = "Card data:"


@lru_cache(maxsize=None)
def _prompts(cond: str) -> dict[str, dict]:
    payload = _load_json(EVALS / "answers" / f"_prompts_{cond}.json")
    return payload["prompts"]


def prompt_user_text(cond: str, qid: str) -> str:
    return _prompts(cond)[qid]["user"]


def _bracket_ids(text: str) -> set[str]:
    return {m.strip() for m in BRACKET_RE.findall(text)}


def context_ids(cond: str, qid: str) -> set[str]:
    """All bracket-labeled context anchors available to the model for this
    question under this condition -- numbered rules AND card-ruling/glossary
    labels (both are legitimate grounding; citations reference both)."""
    return _bracket_ids(prompt_user_text(cond, qid))


def rules_section_ids(cond: str, qid: str) -> set[str]:
    """Bracket ids from the 'Rules context:' portion only (before the
    'Card data:' marker, or the whole prompt for rules-only questions)."""
    text = prompt_user_text(cond, qid)
    idx = text.find(CARD_DATA_MARKER)
    section = text if idx == -1 else text[:idx]
    return _bracket_ids(section)


def card_section_ids(cond: str, qid: str) -> set[str]:
    text = prompt_user_text(cond, qid)
    idx = text.find(CARD_DATA_MARKER)
    if idx == -1:
        return set()
    return _bracket_ids(text[idx:])

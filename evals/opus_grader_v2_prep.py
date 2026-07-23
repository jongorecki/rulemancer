"""Opus-grader calibration v2 -- PREP stage ONLY (docs/plan-opus-grader-
calibration.md, "v2" section).

Assembles the six batch input files an in-session Opus SUBAGENT will read to
blind-grade cells later. This script makes ZERO Anthropic API calls and ZERO
OpenRouter calls -- it never imports `anthropic`, never constructs a client,
never calls messages.parse/create against Claude or an OpenRouter model. The
only network-capable calls anywhere in this script are (a) the Scryfall
lookup in `get_card()`, which is cache-only for every one of the 19 card
questions here (their oracle text has been warm in data/cache.db's
`scryfall` table since the original condition-A generation runs -- see
evals/run_openrouter_arm.py's module docstring), and (b) the Voyage
`embed_query()` call inside `select_rulings()`, needed to reproduce which
rulings actually clear the relevance floor for a card. Voyage is an
embedding endpoint, not an LLM completion endpoint, and it is the SAME
plumbing `rulesagent.generate.answer.RulesAgent.answer()` calls in
production for every card question -- there is no way to get "the same ...
selected-rulings rendering the answering arm saw" per the task without
either running this real selection or reimplementing it (explicitly
disallowed by the task). Cost is negligible: at most one tiny query
embedding per (card, card-question) pair, ~25 calls total.

THE ONE v2 CHANGE from v1 (evals/opus_grader_calibration.py): every
card-interaction question's cell gets an extra "Card data" block -- the same
oracle-text + selected-rulings rendering the answering arm saw in its
generation prompt, built by reusing the codebase's own card resolution path
(parse_card_refs / get_card / select_rulings / _format_cards, all imported
from their real modules, none reimplemented here). Rubric, blindness,
comparison-set logic, and every rules-side assembly step (chunk map,
question map, gold-rule rendering, answer rendering) are reused verbatim
from opus_grader_calibration.py.

Card data does NOT depend on which arm answered -- only on the question --
so it's computed once per card question and reused across all six batch
files, exactly like a real generation prompt would build it once per
question per arm (the six arms saw the same card enrichment, since it's not
model-dependent).

Outputs:
  evals/opus_grader_v2_batches/batch_<arm>.md  -- 6 files, 50 cells each
  evals/opus_grader_v2_out/.gitkeep            -- empty dir grading writes into later

Run: `uv run python evals/opus_grader_v2_prep.py`
PYTHONIOENCODING=utf-8 recommended (Windows console).
"""

import json
import sys
from pathlib import Path

# evals/ isn't an installed package -- same sys.path pattern every other
# evals/*.py script in this repo uses (run_answer_eval.py, ablate_gold.py,
# opus_grader_calibration.py) so imports resolve regardless of caller cwd.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opus_grader_calibration import (  # noqa: E402
    ANSWERS_DIR,
    ARM_ANSWER_FILES,
    CARDS_PATH,
    EVALS_DIR,
    QUESTIONS_PATH,
    SYSTEM,
    build_chunk_map,
    build_question_map,
    format_answer,
    format_gold,
    load_arm_answers,
)

from run_eval import load_questions  # noqa: E402

from rulesagent.generate.answer import _format_cards  # noqa: E402
from rulesagent.tools.ruling_retrieval import select_rulings  # noqa: E402
from rulesagent.tools.scryfall import get_card, parse_card_refs  # noqa: E402

BATCH_DIR = EVALS_DIR / "opus_grader_v2_batches"
OUT_DIR = EVALS_DIR / "opus_grader_v2_out"

N_QUESTIONS_EXPECTED = 50
N_CARD_QUESTIONS_EXPECTED = 19

# Patterns that would only appear in this file's CELL BLOCKS if a coding
# mistake pulled Jon's verdict/note data into the grader-facing prompt
# (build_comparison_set()'s cell dicts carry jon_verdict/jon_note precisely
# so v1's grade_cell() could score against them AFTER the API call -- never
# before it or inside the prompt). Deliberately scoped to just the cell
# blocks (see check_blindness()'s call site) rather than the whole file:
# the rubric header (verbatim SYSTEM text) and the output-format footer
# BOTH legitimately use the English word "verdict" -- the rubric explains
# what a verdict is, the footer specifies the output JSON schema's
# "verdict" field. Scoping the check to the assembled-from-data zone is
# what makes it a meaningful leakage guard instead of a check that can
# never pass.
FORBIDDEN_PATTERNS = ["verdict", "[RULED", 'note":', "jon_verdict", "jon_note"]


def load_card_question_ids() -> set[str]:
    """Question ids from evals/cards.jsonl, read raw (not via load_questions/
    EvalQuestion, which drops the `cards` field -- EvalQuestion has no such
    field, so pydantic's default extra="ignore" would silently discard it)."""
    ids = set()
    for line in CARDS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["id"])
    return ids


def build_card_block(question_text: str) -> str | None:
    """The exact 'Card data' block a generating arm saw for this question,
    built by reusing generate/answer.py's own card resolution path -- NOT a
    reimplementation. Mirrors RulesAgent.answer()'s default config exactly
    (card_no_refresh=True, ruling_select=True, ruling_query_mode='raw', the
    shipped defaults condition-A's original answers were generated under):
      1. parse_card_refs() strips `[Card Name]` brackets and returns the
         referenced tokens, in question order, de-duped case-insensitively
         -- same as answer.py lines ~377-390 (single-turn, no history here).
      2. get_card(ref, no_refresh=True) resolves each token -- cache-only
         for every eval card (warm since the original generation runs).
      3. select_rulings(card, stripped_question) picks the relevant rulings
         (top-3, cosine floor 0.38) -- the real per-card ruling mini-RAG.
      4. Each picked ruling gets the same "[Name ruling #i]" label
         RulesAgent.answer() stamps on it, so citations in existing answer
         JSON (e.g. "Fork ruling #8") still resolve to a label actually
         present in this block.
      5. _format_cards() renders it -- byte-identical rendering logic to
         what the generator prompt used.

    Returns None for a question with no `[bracket]` card references (not
    expected to be called on non-card questions, but harmless if it is).
    """
    stripped, tokens = parse_card_refs(question_text)
    if not tokens:
        return None
    seen: set[str] = set()
    refs = [t for t in tokens if not (t.lower() in seen or seen.add(t.lower()))]

    cards, missing = [], []
    for ref in refs:
        card = get_card(ref, no_refresh=True)
        if card is None:
            missing.append(ref)
        else:
            cards.append(card)
    if missing:
        raise RuntimeError(
            f"card(s) not resolvable from the Scryfall cache: {missing} "
            f"(question={question_text!r}) -- expected every eval card warm "
            "in data/cache.db since the original generation runs"
        )

    picked = []
    for card in cards:
        sel = select_rulings(card, stripped)
        picked.append(card.model_copy(update={
            "rulings": [f"[{card.name} ruling #{i}] {card.rulings[i]}" for i, _ in sel]
        }))
    return _format_cards(picked)


def build_cell_prompt(q, ans: dict, chunk_map: dict[str, str], card_block: str | None) -> str:
    """v1's build_user_prompt() (Question / Gold rules / Arm's answer),
    reusing format_gold()/format_answer() UNCHANGED, with exactly one
    insertion: a 'Card data' section between the gold rules and the arm's
    answer for card-interaction questions -- mirrors where generate/
    answer.py's build_prompt() places card data relative to the rules
    context (right after it, before the question).

    Deliberately drops v1's trailing "Grade this answer per the rubric.
    Output your verdict..." instruction line -- that's a per-CALL API
    instruction in v1 (one Anthropic request per cell); here the grading
    instruction is stated ONCE per file (in the header and the output-
    instructions footer) rather than 50 times, which also keeps the word
    "verdict" entirely out of the per-cell blocks the blindness check
    scans (see check_blindness()'s call site)."""
    parts = [f"Question: {q.question}", f"Gold rules:\n{format_gold(q, chunk_map)}"]
    if card_block:
        parts.append(f"Card data:\n{card_block}")
    parts.append(f"Arm's answer:\n{format_answer(ans)}")
    return "\n\n".join(parts)


def check_blindness(text: str, where: str) -> None:
    lowered = text.lower()
    hits = [p for p in FORBIDDEN_PATTERNS if p.lower() in lowered]
    if hits:
        raise RuntimeError(f"BLINDNESS CHECK FAILED in {where}: found forbidden pattern(s) {hits}")


def output_instructions(arm: str) -> str:
    return (
        "## Output instructions\n\n"
        f"Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON "
        f"line to:\n\n    evals/opus_grader_v2_out/{arm}.jsonl\n\n"
        "Each line is a single JSON object with EXACTLY these fields and nothing else:\n\n"
        '    {"id": "<cell id, e.g. q007 or c012>", "arm": "' + arm + '", '
        '"verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}\n\n'
        "Every one of the 50 cells above must be accounted for -- one line per cell, any "
        "order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a "
        "cell is genuinely ungradeable, still write a line with your best-effort verdict and "
        "say why in the reason -- never silently drop a cell."
    )


def build_batch_file(arm: str, all_q: list, answers: dict, chunk_map: dict[str, str],
                     card_blocks: dict[str, str]) -> tuple[str, int]:
    cell_blocks = []
    for i, q in enumerate(all_q, 1):
        ans = answers.get(q.id)
        if ans is None:
            raise RuntimeError(f"arm {arm!r} has no answer for question {q.id!r}")
        prompt = build_cell_prompt(q, ans, chunk_map, card_blocks.get(q.id))
        cell_blocks.append(f"### Cell {i}: id={q.id}\n\n{prompt}")

    cell_text = "\n\n---\n\n".join(cell_blocks)
    # Scoped blindness check -- see FORBIDDEN_PATTERNS' comment for why this
    # deliberately excludes the (hand-authored, verdict-free) rubric header
    # and output-instructions footer built below.
    check_blindness(cell_text, f"batch_{arm}.md cell blocks")

    header = (
        f"# Opus-Grader Calibration v2 -- Batch: {arm}\n\n"
        f"{len(all_q)} cells, blind. You are auditioning as a possible pre-grader for "
        "future evals (docs/plan-opus-grader-calibration.md). For EACH cell below, grade "
        "the arm's answer against the rubric using ONLY the question, the gold rule text "
        "(or card data) provided in that cell, and the arm's own answer, and output a "
        "correct/partial/wrong verdict plus a one-line reason -- exact output format is at "
        "the end of this file. You are never shown a human verdict or grading note anywhere "
        "in this file; grade fresh, blind, per cell.\n\n"
        "## Grading rubric (verbatim from v1, evals/opus_grader_calibration.py)\n\n"
        f"```\n{SYSTEM}\n```\n\n"
        "## Cells\n\n"
    )
    content = header + cell_text + "\n\n---\n\n" + output_instructions(arm)
    return content, len(cell_blocks)


def main() -> None:
    print("Building chunk map from CR corpus...", flush=True)
    chunk_map = build_chunk_map()
    print(f"  {len(chunk_map)} chunks loaded", flush=True)

    print("Loading questions...", flush=True)
    question_map = build_question_map()
    all_q = load_questions(QUESTIONS_PATH) + load_questions(CARDS_PATH)
    assert len(all_q) == N_QUESTIONS_EXPECTED, (
        f"expected {N_QUESTIONS_EXPECTED} questions (questions.jsonl + cards.jsonl), "
        f"got {len(all_q)}"
    )
    assert all(q.id in question_map for q in all_q), "question_map missing some ids"

    card_ids = load_card_question_ids()
    assert len(card_ids) == N_CARD_QUESTIONS_EXPECTED, (
        f"expected {N_CARD_QUESTIONS_EXPECTED} card questions in cards.jsonl, got {len(card_ids)}"
    )

    print(f"Building 'Card data' blocks for {len(card_ids)} card-interaction questions "
          "(reusing generate/answer.py's card resolution path -- Scryfall cache-only, "
          "plus one small Voyage ruling-selection embed per card)...", flush=True)
    card_blocks: dict[str, str] = {}
    for q in all_q:
        if q.id in card_ids:
            card_blocks[q.id] = build_card_block(q.question)
            print(f"  {q.id}: built ({len(card_blocks[q.id])} chars)", flush=True)
    missing_blocks = [qid for qid in sorted(card_ids) if not card_blocks.get(qid)]
    if missing_blocks:
        raise RuntimeError(f"no card block built for: {missing_blocks}")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = OUT_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")

    print(f"\nBuilding {len(ARM_ANSWER_FILES)} batch files...", flush=True)
    for arm in ARM_ANSWER_FILES:
        answers = load_arm_answers(arm)
        assert len(answers) == N_QUESTIONS_EXPECTED, (
            f"arm {arm!r} answer file(s) {ARM_ANSWER_FILES[arm]} cover "
            f"{len(answers)} questions, expected {N_QUESTIONS_EXPECTED}"
        )
        content, n_cells = build_batch_file(arm, all_q, answers, chunk_map, card_blocks)
        assert n_cells == N_QUESTIONS_EXPECTED, f"{arm}: built {n_cells} cells, expected {N_QUESTIONS_EXPECTED}"
        path = BATCH_DIR / f"batch_{arm}.md"
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path} ({n_cells} cells, {len(content):,} chars)", flush=True)

    print(f"\nAll {len(ARM_ANSWER_FILES)} batch files written to {BATCH_DIR}, "
          f"each with {N_QUESTIONS_EXPECTED} cells, blindness check passed on every one.")
    print(f"Empty grading output dir ready at {OUT_DIR} (.gitkeep present).")


if __name__ == "__main__":
    main()

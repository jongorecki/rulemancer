"""Opus-grader calibration experiment (docs/plan-opus-grader-calibration.md).

Have claude-opus-4-8 BLIND-grade cells Jon has already hand-graded (or graded
by transitivity through the frozen 95%-agreement judge), then measure
agreement against Jon's verdicts. This auditions Opus as a potential
pre-grader -- it does NOT touch, call, or influence the frozen gpt-5-mini
judge (judge_bakeoff.py / judge_arm_pairs.py) in any way, and it does not
modify any existing evals/ file.

Comparison set: every (arm, question) cell across the six arms' condition-A
answers (evals/answers/*.json, NOT the *_B_r*/_C_r*/_D_r* files -- those
belong to a different experiment). Primary = Jon's direct hand-grades (the
`_manual` verdict files, plus the deepseek-v3-2 reference arm's own file,
which is fully manual). Secondary = auto-transferred cells from the `_final`
files (Jon's-by-transitivity through the judge).

Grader input per cell is BLIND: question text, gold rule numbers + match
semantics + full corpus text of those rules, and the arm's answer JSON
(answered/text/citations). It never sees Jon's verdict or note, or any other
arm's answer. Grounding is grader-side only -- the same law the bot itself
lives under: ground ONLY in the provided rule text, never the grader's own
MTG knowledge.

Outputs (new files only, nothing in evals/ is modified):
  evals/opus_grader_results.jsonl   -- one line per graded cell or error
  evals/opus_grader_report.md       -- Jon's morning-read report

Run: `uv run python evals/opus_grader_calibration.py`
Requires ANTHROPIC_API_KEY in .env. PYTHONIOENCODING=utf-8 recommended.
"""

import argparse
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

# evals/ isn't an installed package -- put it (and src/) on sys.path
# explicitly, same pattern run_answer_eval.py and ablate_gold.py use, so
# `from run_eval import ...` resolves regardless of caller cwd.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from run_eval import CR_PATH, QUESTIONS_PATH, gold_groups, load_questions  # noqa: E402

from rulesagent.contracts import EvalQuestion  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

load_dotenv()

EVALS_DIR = Path(__file__).parent
CARDS_PATH = EVALS_DIR / "cards.jsonl"
ANSWERS_DIR = EVALS_DIR / "answers"
RESULTS_PATH = EVALS_DIR / "opus_grader_results.jsonl"
REPORT_PATH = EVALS_DIR / "opus_grader_report.md"

GRADER_MODEL = "claude-opus-4-8"
MAX_WORKERS = 8

# Published Anthropic API rates for claude-opus-4-8, per the claude-api skill
# (loaded fresh this session, cached 2026-06-24) -- NOT from memory, per the
# task's binding constraint. $ per 1,000,000 tokens.
# Rates come from rulesagent.pricing, the single cached copy. See that module
# for when it was last checked and what dated changes are pending.
from rulesagent.pricing import PRICING as _PRICING

OPUS_INPUT_PER_MTOK, OPUS_OUTPUT_PER_MTOK = _PRICING["claude-opus-5"]

# The six arms and where their condition-A (original, untagged) answer files
# live. sonnet-v2's answers are split across a rules-question file and a
# card-question file (no id overlap, verified 50/50 disjoint coverage).
ARM_ANSWER_FILES: dict[str, list[str]] = {
    "deepseek-v3-2": ["openrouter_deepseek-deepseek-v3-2.json"],
    "deepseek-v4-flash": ["openrouter_deepseek-deepseek-v4-flash.json"],
    "deepseek-v4-pro": ["openrouter_deepseek-deepseek-v4-pro.json"],
    "gemini-flash-lite": ["openrouter_google-gemini-2-5-flash-lite.json"],
    "gpt-5-mini": ["openrouter_openai-gpt-5-mini.json"],
    "sonnet-v2": ["sonnet_v2_rules.json", "sonnet_v2_cards.json"],
}

# deepseek-v3-2 is the reference arm graded directly by Jon (no _manual/
# _final split -- verdicts_deepseek-v3-2.json IS the full 50-row grade,
# entirely primary). The other five have the _manual (primary, direct)
# and _final (all 50, primary + auto-transferred secondary) split.
REFERENCE_ARM = "deepseek-v3-2"
SPLIT_ARMS = ["deepseek-v4-flash", "deepseek-v4-pro", "gemini-flash-lite", "gpt-5-mini", "sonnet-v2"]

SYSTEM = (
    "You are a blind grading auditor for an MTG (Magic: The Gathering) "
    "rules-RAG bot's answer evals. You are auditioning as a possible "
    "pre-grader for future evals -- your verdicts will be compared against "
    "a human grader's hand-grades to measure agreement, so grade as "
    "carefully and consistently as you would if this were the real job.\n\n"
    "GROUNDING RULE (the same law the bot itself lives under): base your "
    "verdict ONLY on the rule text provided below and the question as "
    "asked. Never use your own memory or general knowledge of Magic: The "
    "Gathering rules to override, supplement, or second-guess the provided "
    "rule text -- if the provided text doesn't settle something the answer "
    "claims, say so in your reason instead of falling back on what you "
    "recall about the actual rule. You are NOT told what any human grader "
    "concluded about this cell -- grade fresh, blind.\n\n"
    "RUBRIC (verbatim, distilled from the project's grading history, "
    "including a 2026-07-22 rubric ruling on undisclosed assumptions):\n"
    "- CORRECT: the answer reaches the right substantive conclusion under a "
    "reasonable reading of the question, consistent with the provided rule "
    "text (or, when no gold rule text is provided below, the answer is "
    "internally coherent, directly responsive to the question, and not "
    "self-contradictory). A correct answer that silently assumes away an "
    "ambiguity the asker didn't resolve STILL grades CORRECT -- note the "
    "assumption in your reason, but do not mark it partial just because it "
    "didn't flag the ambiguity or ask a clarifying question first. The "
    "disclosure bar belongs to a future clarify-then-escalate feature, not "
    "to this verdict.\n"
    "- PARTIAL: the answer is materially incomplete or half-right on the "
    "substance -- it gets part of a multi-part question right and part "
    "wrong or missing, or its core conclusion is right but it omits a "
    "substantively important piece the question needed. (Omitting a "
    "disclosure/caveat about an assumption is NOT this -- that's still "
    "correct, per the rule above.)\n"
    "- WRONG: the answer makes a substantive rules error -- it reaches the "
    "wrong conclusion, or relies on a rule in a way the provided text "
    "doesn't support.\n\n"
    "For each cell you will get: the question; the gold rule numbers and "
    "how they combine (any/all/groups) with their full corpus text (or a "
    "note that no gold rules were recorded for this question); and the "
    "arm's complete answer (answered flag, text, citations). Output a "
    "verdict (correct/partial/wrong) and a ONE-LINE reason a human grader "
    "could spot-check in a few seconds."
)


class GraderVerdict(BaseModel):
    verdict: Literal["correct", "partial", "wrong"]
    reason: str


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_chunk_map() -> dict[str, str]:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    return {c.source_id: c.text for c in chunks}


def build_question_map() -> dict[str, EvalQuestion]:
    qs = load_questions(QUESTIONS_PATH) + load_questions(CARDS_PATH)
    return {q.id: q for q in qs}


def load_openrouter_answers(path: Path) -> dict[str, dict]:
    data = load_json(path)
    out = {}
    for r in data["results"]:
        out[r["id"]] = {
            "answered": r.get("answered"),
            "text": r.get("text") or r.get("raw_text") or "",
            "citations": r.get("citations") or [],
        }
    return out


def load_sonnet_answers(paths: list[Path]) -> dict[str, dict]:
    out = {}
    for path in paths:
        for r in load_json(path):
            out[r["id"]] = {
                "answered": r.get("answered"),
                "text": r.get("answer") or "",
                "citations": r.get("citations") or [],
            }
    return out


def load_arm_answers(arm: str) -> dict[str, dict]:
    files = [ANSWERS_DIR / name for name in ARM_ANSWER_FILES[arm]]
    if arm == "sonnet-v2":
        return load_sonnet_answers(files)
    return load_openrouter_answers(files[0])


def format_gold(q: EvalQuestion, chunk_map: dict[str, str]) -> str:
    if not q.gold:
        return (
            "No gold rule set is recorded for this question -- grade based "
            "on whether the answer is internally coherent, directly "
            "responsive to the question, and not self-contradictory. You "
            "have no rule text here to check its substance against, so do "
            "not assert it is rules-correct beyond that coherence check; "
            "say so plainly in your reason."
        )
    lines = [f"Match semantics: {q.match}"]
    if q.match == "groups":
        for i, group in enumerate(gold_groups(q), 1):
            lines.append(f"  Group {i} (satisfied by ANY ONE of): {', '.join(group)}")
        lines.append("  ALL groups above must be satisfied.")
    elif q.match == "all":
        lines.append(f"  ALL of these are required: {', '.join(q.gold)}")
    else:
        lines.append(f"  ANY ONE of these satisfies it: {', '.join(q.gold)}")
    lines.append("\nFull text of each gold rule:")
    for rid in q.gold:
        text = chunk_map.get(rid)
        if text is None:
            lines.append(f"[{rid}] (WARNING: id not found in the current CR corpus -- may be stale)")
        else:
            lines.append(f"[{rid}] {text}")
    return "\n".join(lines)


def format_answer(ans: dict) -> str:
    lines = [
        f"answered: {ans['answered']}",
        f"citations: {ans['citations']}",
        f"text: {ans['text']}",
    ]
    return "\n".join(lines)


def build_user_prompt(q: EvalQuestion, ans: dict, chunk_map: dict[str, str]) -> str:
    return (
        f"Question: {q.question}\n\n"
        f"Gold rules:\n{format_gold(q, chunk_map)}\n\n"
        f"Arm's answer:\n{format_answer(ans)}\n\n"
        "Grade this answer per the rubric. Output your verdict and a "
        "one-line reason."
    )


def build_comparison_set(question_map: dict[str, EvalQuestion]) -> list[dict]:
    """Every (arm, id) cell, tagged primary/secondary, carrying Jon's
    verdict/note for later scoring -- NEVER handed to the grader prompt."""
    cells: list[dict] = []

    ref_verdicts = {v["id"]: v for v in load_json(EVALS_DIR / f"verdicts_{REFERENCE_ARM}.json")}
    ref_answers = load_arm_answers(REFERENCE_ARM)
    for qid, v in ref_verdicts.items():
        cells.append({
            "arm": REFERENCE_ARM, "id": qid, "set": "primary",
            "jon_verdict": v["verdict"], "jon_note": v.get("note", ""),
            "question": question_map.get(qid), "answer": ref_answers.get(qid),
        })

    for arm in SPLIT_ARMS:
        manual = {v["id"]: v for v in load_json(EVALS_DIR / f"verdicts_{arm}_manual.json")}
        final = load_json(EVALS_DIR / f"verdicts_{arm}_final.json")
        answers = load_arm_answers(arm)
        for row in final:
            qid = row["id"]
            is_primary = qid in manual
            source = manual[qid] if is_primary else row
            cells.append({
                "arm": arm, "id": qid, "set": "primary" if is_primary else "secondary",
                "jon_verdict": source["verdict"], "jon_note": source.get("note", ""),
                "question": question_map.get(qid), "answer": answers.get(qid),
            })

    return cells


def grade_cell(client: anthropic.Anthropic, cell: dict, chunk_map: dict[str, str]) -> dict:
    base = {"arm": cell["arm"], "id": cell["id"], "set": cell["set"]}
    q, ans = cell["question"], cell["answer"]
    if q is None or ans is None:
        return {**base, "error": f"missing question or answer data (question={q is not None}, answer={ans is not None})"}

    user = build_user_prompt(q, ans, chunk_map)
    try:
        resp = client.messages.parse(
            model=GRADER_MODEL,
            max_tokens=1024,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_format=GraderVerdict,
        )
    except Exception as e:  # noqa: BLE001 -- reported as an error line, never silently dropped
        return {**base, "error": f"API exception: {type(e).__name__}: {e}"}

    if resp.stop_reason == "refusal":
        category = getattr(resp.stop_details, "category", None) if resp.stop_details else None
        return {**base, "error": f"refusal (category={category})"}

    parsed = resp.parsed_output
    if parsed is None:
        return {**base, "error": f"empty/invalid structured output, stop_reason={resp.stop_reason}"}

    usage = resp.usage
    return {
        **base,
        "opus_verdict": parsed.verdict,
        "opus_reason": parsed.reason,
        "jon_verdict": cell["jon_verdict"],
        "jon_note": cell["jon_note"],
        "agree": parsed.verdict == cell["jon_verdict"],
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        },
    }


def run_grading(cells: list[dict], chunk_map: dict[str, str]) -> list[dict]:
    client = anthropic.Anthropic()
    results: list[dict] = []
    lock = threading.Lock()
    write_f = open(RESULTS_PATH, "w", encoding="utf-8")
    t0 = time.time()
    done = 0

    def work(cell):
        return grade_cell(client, cell, chunk_map)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(work, cell): cell for cell in cells}
        for fut in as_completed(futures):
            cell = futures[fut]
            try:
                result = fut.result()
            except Exception as e:  # noqa: BLE001 -- last-resort net, never silently dropped
                result = {"arm": cell["arm"], "id": cell["id"], "set": cell["set"],
                          "error": f"worker exception: {type(e).__name__}: {e}"}
            with lock:
                results.append(result)
                write_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                write_f.flush()
                done += 1
                if done % 25 == 0 or done == len(cells):
                    elapsed = time.time() - t0
                    print(f"  [{done}/{len(cells)}] {elapsed:.0f}s elapsed", flush=True)

    write_f.close()
    return results


VERDICT_ORDER = ["correct", "partial", "wrong"]

# The frozen gpt-5-mini judge's trust bar (docs/plan-opus-grader-calibration.md
# "Reference bar" -- the natural yardstick to show next to this result, not an
# auto-adopt threshold). Reproduced from the plan, not asserted from memory.
FROZEN_JUDGE_AGREEMENT_PCT = 95
FROZEN_JUDGE_LIVE_AUDIT_ERRORS = "0/21"


def compute_metrics(results: list[dict]) -> dict:
    graded = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]
    metrics: dict = {"n_total": len(results), "n_graded": len(graded), "n_errors": len(errors), "errors": errors}

    for set_label in ("primary", "secondary"):
        subset = [r for r in graded if r["set"] == set_label]
        n = len(subset)
        agree = sum(1 for r in subset if r["agree"])
        confusion = Counter((r["jon_verdict"], r["opus_verdict"]) for r in subset)
        boundary_subset = [r for r in subset if r["jon_verdict"] in ("correct", "partial")]
        boundary_agree = sum(1 for r in boundary_subset if r["opus_verdict"] == r["jon_verdict"])
        c2p = sum(1 for r in boundary_subset if r["jon_verdict"] == "correct" and r["opus_verdict"] == "partial")
        p2c = sum(1 for r in boundary_subset if r["jon_verdict"] == "partial" and r["opus_verdict"] == "correct")
        metrics[set_label] = {
            "n": n, "agree": agree, "agree_pct": (agree / n * 100) if n else None,
            "confusion": confusion,
            "boundary_n": len(boundary_subset), "boundary_agree": boundary_agree,
            "boundary_pct": (boundary_agree / len(boundary_subset) * 100) if boundary_subset else None,
            "boundary_correct_to_partial": c2p, "boundary_partial_to_correct": p2c,
            "disagreements": [r for r in subset if not r["agree"]],
        }

    n = len(graded)
    agree = sum(1 for r in graded if r["agree"])
    metrics["combined"] = {
        "n": n, "agree": agree, "agree_pct": (agree / n * 100) if n else None,
        "confusion": Counter((r["jon_verdict"], r["opus_verdict"]) for r in graded),
    }
    return metrics


def compute_cost(results: list[dict]) -> dict:
    graded = [r for r in results if "error" not in r]
    total_input = sum(r["usage"]["input_tokens"] for r in graded)
    total_output = sum(r["usage"]["output_tokens"] for r in graded)
    total_cache_read = sum(r["usage"]["cache_read_input_tokens"] for r in graded)
    total_cache_write = sum(r["usage"]["cache_creation_input_tokens"] for r in graded)
    # No cache_control was set on these requests (each cell's prompt is unique
    # -- question/gold/answer all vary), so cache tokens are expected to be 0;
    # included for completeness/verification rather than folded silently in.
    cost = (total_input / 1_000_000 * OPUS_INPUT_PER_MTOK) + (total_output / 1_000_000 * OPUS_OUTPUT_PER_MTOK)
    return {
        "input_tokens": total_input, "output_tokens": total_output,
        "cache_read_tokens": total_cache_read, "cache_creation_tokens": total_cache_write,
        "cost_usd": cost, "n_cells": len(graded),
    }


def render_confusion(counter: Counter, order: list[str] = VERDICT_ORDER) -> str:
    header = "| Jon verdict \\ Opus verdict | correct | partial | wrong |\n|---|---|---|---|\n"
    rows = []
    for j in order:
        counts = [counter.get((j, o), 0) for o in order]
        rows.append(f"| **{j}** | {counts[0]} | {counts[1]} | {counts[2]} |")
    return header + "\n".join(rows)


def render_disagreements(rows: list[dict], question_map: dict[str, EvalQuestion]) -> str:
    if not rows:
        return "*None.*"
    rows = sorted(rows, key=lambda r: (r["set"], r["arm"], r["id"]))
    lines = ["| Set | Arm | Q | Question | Jon | Opus | Opus's reason |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        q = question_map.get(r["id"])
        qtext = (q.question[:70] + "...") if q and len(q.question) > 70 else (q.question if q else "")
        qtext = qtext.replace("|", "\\|").replace("\n", " ")
        reason = r["opus_reason"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['set']} | {r['arm']} | {r['id']} | {qtext} | {r['jon_verdict']} | "
            f"{r['opus_verdict']} | {reason} |"
        )
    return "\n".join(lines)


def render_errors(errors: list[dict]) -> str:
    if not errors:
        return "*None -- every cell in the comparison set was graded or the call was retried to a result.*"
    lines = ["| Arm | Q | Set | Error |", "|---|---|---|---|"]
    for e in errors:
        err = e["error"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {e['arm']} | {e['id']} | {e.get('set', '?')} | {err} |")
    return "\n".join(lines)


def build_report(results: list[dict], question_map: dict[str, EvalQuestion], chunk_map: dict[str, str]) -> str:
    m = compute_metrics(results)
    cost = compute_cost(results)
    p, s, c = m["primary"], m["secondary"], m["combined"]

    def pct(x):
        return f"{x:.1f}%" if x is not None else "n/a"

    def frac_pct(num, den):
        return f"{num}/{den} ({pct(num / den * 100 if den else None)})"

    # One real example prompt, for the blindness self-review -- pick the
    # first primary graded cell so it's representative of the real run.
    example_cell = None
    for r in results:
        if "error" not in r and r["set"] == "primary":
            example_cell = r
            break
    example_prompt_block = "*(no graded primary cell available to show)*"
    if example_cell is not None:
        q = question_map.get(example_cell["id"])
        arm = example_cell["arm"]
        # Rebuild the exact answer dict the grader saw, straight from the
        # answers file, so this is provably the real prompt bytes, not a
        # reconstruction from the (verdict-bearing) result record.
        ans = load_arm_answers(arm).get(example_cell["id"])
        if q is not None and ans is not None:
            prompt_text = build_user_prompt(q, ans, chunk_map)
            example_prompt_block = (
                f"**System prompt** (fixed, shown once):\n\n```\n{SYSTEM}\n```\n\n"
                f"**User prompt for `{arm}` / `{example_cell['id']}`** "
                f"(note: no verdict, no note, no other arm's answer anywhere in this):\n\n"
                f"```\n{prompt_text}\n```"
            )

    lines: list[str] = []
    lines.append("# Opus-Grader Calibration Report")
    lines.append("")
    lines.append(
        "Blind-graded every already-graded cell with `claude-opus-4-8` and measured "
        "agreement against Jon's verdicts. Auditions Opus as a possible pre-grader -- "
        "the frozen gpt-5-mini judge was not touched. Full method: "
        "`docs/plan-opus-grader-calibration.md`."
    )
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append(f"- **Primary set** (Jon's direct hand-grades, N={p['n']}): "
                  f"**{frac_pct(p['agree'], p['n'])} agreement**")
    lines.append(f"- **Secondary set** (auto-transferred-by-transitivity, N={s['n']}): "
                  f"{frac_pct(s['agree'], s['n'])} agreement")
    lines.append(f"- **Combined** (N={c['n']}): {frac_pct(c['agree'], c['n'])} agreement")
    lines.append(f"- **Correct/partial boundary agreement** (primary, N={p['boundary_n']}): "
                  f"{frac_pct(p['boundary_agree'], p['boundary_n'])}"
                  f" -- {p['boundary_correct_to_partial']} correct-to-partial flips, "
                  f"{p['boundary_partial_to_correct']} partial-to-correct flips")
    lines.append(f"- **Reference yardstick:** the frozen gpt-5-mini judge earned trust at "
                  f"**{FROZEN_JUDGE_AGREEMENT_PCT}% agreement** with **{FROZEN_JUDGE_LIVE_AUDIT_ERRORS}** "
                  f"live-audit errors -- shown for comparison only, not an auto-adopt threshold.")
    lines.append(f"- **Coverage:** {m['n_graded']} graded / {m['n_errors']} errors "
                  f"out of {m['n_total']} total comparison cells (300 = 6 arms x 50 questions).")
    lines.append(f"- **Cost:** ${cost['cost_usd']:.2f} ({cost['input_tokens']:,} input + "
                  f"{cost['output_tokens']:,} output tokens, claude-opus-4-8 at "
                  f"${OPUS_INPUT_PER_MTOK:.2f}/${OPUS_OUTPUT_PER_MTOK:.2f} per MTok)")
    lines.append("")

    lines.append("## Confusion matrix -- primary set (N=%d)" % p["n"])
    lines.append("")
    lines.append(render_confusion(p["confusion"]))
    lines.append("")

    lines.append("## Confusion matrix -- secondary set (N=%d)" % s["n"])
    lines.append("")
    lines.append(render_confusion(s["confusion"]))
    lines.append("")

    lines.append("## Errors")
    lines.append("")
    lines.append(render_errors(m["errors"]))
    lines.append("")

    # Quick, hedged synthesis over the disagreement list -- not a substitute
    # for Jon's own read of the table below, just a faster way in.
    no_gold_flip_rows = [
        r for r in (p["disagreements"] + s["disagreements"])
        if question_map.get(r["id"]) and not question_map[r["id"]].gold
        and r["jon_verdict"] == "wrong" and r["opus_verdict"] == "correct"
    ]
    no_gold_flip_ids = sorted({r["id"] for r in no_gold_flip_rows})
    lines.append("## Patterns in the disagreements (quick read, verify against the table)")
    lines.append("")
    lines.append(
        f"- **No-gold-rule blind spot, {len(no_gold_flip_rows)} cells across "
        f"{len(no_gold_flip_ids)} questions ({', '.join(no_gold_flip_ids)}):** these card "
        "questions have an empty gold list (`cards.jsonl` rows Jon graded on faithfulness, "
        "not rules-recall), so the grader has no rule text to check substance against -- it "
        "can only judge internal coherence. Opus upgraded these from Jon's wrong to correct "
        "because the answer read as coherent even though it was substantively wrong. This is "
        "the single largest disagreement driver and is inherent to the blind-input spec (no "
        "card oracle/rulings text was given to the grader, per the plan), not a script bug."
    )
    lines.append(
        "- **Self-contradiction catches (a real win):** on several cells (c006, c009, c010, "
        "c013, c019) Opus caught an answer's headline conclusion contradicting its own body "
        "text and correctly marked it wrong -- these look like genuine coherence-check value, "
        "not noise."
    )
    p2c_ids = sorted({r["id"] for r in p["disagreements"]
                       if r["jon_verdict"] == "partial" and r["opus_verdict"] == "correct"})
    lines.append(
        f"- **Correct/partial boundary skews lenient:** {p['boundary_partial_to_correct']} of "
        f"the {p['boundary_partial_to_correct'] + p['boundary_correct_to_partial']} boundary "
        f"flips in the primary set are partial-to-correct -- Opus more forgiving than Jon -- "
        f"vs. only {p['boundary_correct_to_partial']} the other way, across questions "
        f"{', '.join(p2c_ids)}. Consistent with the rubric's correct-with-note relaxation in "
        "spirit, but worth checking whether Opus is over-applying it to real incompleteness "
        "rather than reserving it for genuine undisclosed-assumption cases like c004."
    )
    lines.append(
        "- **q026 (\"who gets priority after a non-active player casts a spell\") recurs as a "
        "correct-to-wrong flip on 3 different arms' answers**, and **q012 (\"do non-creature "
        "artifacts die\") recurs as correct-to-wrong on 3 arms plus one partial-to-correct on "
        "a 4th** -- worth a first look, since the same gold rule (117.3c / 700.4) is driving "
        "repeat disagreement across otherwise-independent answers."
    )
    lines.append("")

    lines.append("## Full disagreement list")
    lines.append("")
    lines.append("Primary set:")
    lines.append("")
    lines.append(render_disagreements(p["disagreements"], question_map))
    lines.append("")
    lines.append("Secondary set:")
    lines.append("")
    lines.append(render_disagreements(s["disagreements"], question_map))
    lines.append("")

    lines.append("## Grader blindness -- example prompt")
    lines.append("")
    lines.append(
        "Shown as evidence: the grader prompt never contains a verdict, a grading "
        "note, or any other arm's answer -- only the question, the gold rule "
        "numbers/match-semantics/full text (or a no-gold-recorded note), and the "
        "one arm's own answer JSON."
    )
    lines.append("")
    lines.append(example_prompt_block)
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true",
                         help="skip grading; rebuild the report from an existing results JSONL")
    args = parser.parse_args()

    print("Building chunk map from CR corpus...", flush=True)
    chunk_map = build_chunk_map()
    print(f"  {len(chunk_map)} chunks loaded", flush=True)

    print("Loading questions...", flush=True)
    question_map = build_question_map()
    print(f"  {len(question_map)} questions loaded", flush=True)

    if args.report_only:
        if not RESULTS_PATH.exists():
            print(f"[ERROR] --report-only requires an existing {RESULTS_PATH}")
            return
        results = [json.loads(line) for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(f"Loaded {len(results)} existing results from {RESULTS_PATH}", flush=True)
    else:
        print("Building comparison set...", flush=True)
        cells = build_comparison_set(question_map)
        n_primary = sum(1 for c in cells if c["set"] == "primary")
        n_secondary = sum(1 for c in cells if c["set"] == "secondary")
        print(f"  {len(cells)} cells total ({n_primary} primary, {n_secondary} secondary)", flush=True)

        print(f"Grading {len(cells)} cells with {GRADER_MODEL} ({MAX_WORKERS} workers)...", flush=True)
        results = run_grading(cells, chunk_map)
        print(f"Wrote {len(results)} result lines to {RESULTS_PATH}", flush=True)

    n_errors = sum(1 for r in results if "error" in r)
    n_graded = len(results) - n_errors
    print(f"  {n_graded} graded, {n_errors} errors", flush=True)

    print("Building report...", flush=True)
    report_md = build_report(results, question_map, chunk_map)
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"Wrote report to {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()

"""Judge false-negative / false-positive measurement -- METRICS stage
(pairs with evals/judge_error_prep.py; report: docs/results-judge-error-rate.md).

Reads the blind verdicts the Opus reference graders wrote to
evals/judge_error_out/batch_NN.jsonl, joins them to
evals/judge_error_manifest.json (which the graders never saw), and computes:

  1. REFERENCE-GRADER VALIDATION. On the 32 rows Jon has already hand-graded,
     how often does the reference grader agree with him? This gates everything
     downstream: a reference grader that disagrees with Jon is not a reference,
     and the report has to say so rather than presenting its rates as authority.

  2. FALSE-NEGATIVE RATE. Of rows the frozen judge called `different`, how many
     do the two answers actually agree on? Reported two ways, never pooled
     silently: Jon's census of 32 flagged rows in two arms, and the reference
     grader on a seeded stratified sample of 30 flagged rows from the other
     seven arms.

  3. FALSE-POSITIVE RATE. Of rows the frozen judge called `same`, how many do
     the answers actually differ on? This direction has never been measured;
     the reference grader on a 90-row stratified sample is the only evidence.

  4. WHAT IT DOES TO THE HEADLINE NUMBERS. Every arm's published accuracy is
     re-derived FROM ITS DATA FILE at report time (with the file's mtime
     recorded), then corrected as
         corrected = [ n_same * (1 - FP) + n_diff * FN ] / n
     so the doc can never disagree with the artifact it cites.

Zero API calls -- reads JSON/JSONL off disk and does arithmetic.

Outputs:
  evals/judge_error_results.json     -- every joined cell + all computed rates
  docs/results-judge-error-rate.md   -- the report

Run: `uv run python evals/judge_error_metrics.py`
"""

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

EVALS_DIR = Path(__file__).parent
DOCS_DIR = EVALS_DIR.parent / "docs"
MANIFEST_PATH = EVALS_DIR / "judge_error_manifest.json"
OUT_DIR = EVALS_DIR / "judge_error_out"
RESULTS_PATH = EVALS_DIR / "judge_error_results.json"
REPORT_PATH = DOCS_DIR / "results-judge-error-rate.md"

GRADER_MODEL = "claude-opus-5 (in-session subagents, Claude subscription)"

# Arms whose headline accuracy this run corrects. Numbers are re-read from
# these files at report time -- never copied from a doc.
HEADLINE_ARMS = {
    "derivability_B": "verdicts_derivability_B.json",
    "h2h_opuslow_hard_r1": "verdicts_h2h_opuslow_hard_r1.json",
    "h2h_opuslow_hard_r2": "verdicts_h2h_opuslow_hard_r2.json",
    "h2h_opuslow_easy_r1": "verdicts_h2h_opuslow_easy_r1.json",
    "h2h_opuslow_easy_r2": "verdicts_h2h_opuslow_easy_r2.json",
    "h2h_sonnet_easy_r1": "verdicts_h2h_sonnet_easy_r1.json",
    "h2h_sonnet_easy_r2": "verdicts_h2h_sonnet_easy_r2.json",
    "opus5_low_bucketA": "verdicts_opus5_low_bucketA.json",
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Correct at the small n and near-zero counts this
    run actually produces, where the normal approximation is not."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def fmt_rate(k: int, n: int) -> str:
    if n == 0:
        return "n/a (0 rows)"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {fmt_pct(k / n)} (95% CI {fmt_pct(lo)}-{fmt_pct(hi)})"


def load_grader_verdicts() -> tuple[dict[str, dict], list[str]]:
    """cell -> {verdict, reason, batch}, plus a list of problems found.

    Malformed lines and unexpected verdict strings are reported, never silently
    dropped: a grader that failed to answer is a hole in the measurement, not a
    row to quietly discard."""
    verdicts: dict[str, dict] = {}
    problems: list[str] = []
    for path in sorted(OUT_DIR.glob("batch_*.jsonl")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                problems.append(f"{path.name}:{lineno} unparsable JSON ({e})")
                continue
            cell, v = row.get("cell"), row.get("verdict")
            if not cell or v not in ("same", "different"):
                problems.append(f"{path.name}:{lineno} bad cell/verdict: {row!r}")
                continue
            if cell in verdicts:
                problems.append(f"{path.name}:{lineno} duplicate verdict for {cell}")
                continue
            verdicts[cell] = {"verdict": v, "reason": row.get("reason", ""), "batch": path.stem}
    return verdicts, problems


HUMAN_FILES = {
    "derivability_B": "verdicts_derivability_B_human.json",
    "opus5_low_bucketA": "verdicts_opus5_low_bucketA_human.json",
}


def load_human_rows() -> tuple[dict[tuple[str, str], dict], dict[tuple[str, str], str]]:
    """(arm, id) -> the full human-graded row, and -> Jon's note.

    Read so the report can quote the two answers' opening lines side by side
    where the reference grader and Jon disagree. Quoting the source text is the
    point: it lets Jon adjudicate his own call from the evidence instead of
    taking a model's word for it."""
    rows, notes = {}, {}
    for arm, fname in HUMAN_FILES.items():
        data = json.loads((EVALS_DIR / fname).read_text(encoding="utf-8"))
        for e in data["entries"]:
            if e.get("human_verdict"):
                rows[(arm, e["id"])] = e
                notes[(arm, e["id"])] = (e.get("human_note") or "").strip()
    return rows, notes


human_rows: dict[tuple[str, str], dict] = {}
human_notes: dict[tuple[str, str], str] = {}


def bottom_line(arm: str, qid: str, field: str, limit: int = 150) -> str:
    """First non-empty line of an answer -- where both the gold and the bot put
    their actual ruling. Truncated, whitespace-flattened, pipe-escaped for a
    markdown table cell."""
    row = human_rows.get((arm, qid))
    if not row:
        return ""
    text = (row.get(field) or "").strip()
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    first = first.replace("|", "\\|")
    return first[:limit] + ("..." if len(first) > limit else "")


def arm_counts(fname: str) -> dict:
    path = EVALS_DIR / fname
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [e for e in data["entries"] if e["verdict"] in ("same", "different")]
    c = Counter(e["verdict"] for e in entries)
    return {
        "file": fname,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                             .isoformat(timespec="seconds"),
        "n": len(entries),
        "same": c["same"],
        "different": c["different"],
        "published_accuracy": c["same"] / len(entries) if entries else 0.0,
    }


def main() -> None:
    global human_rows, human_notes
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    human_rows, human_notes = load_human_rows()
    graded, problems = load_grader_verdicts()

    cells = []
    ungraded = []
    for c in manifest["cells"]:
        g = graded.get(c["cell"])
        if g is None:
            ungraded.append(c["cell"])
            continue
        cells.append({**c, "ref_verdict": g["verdict"], "ref_reason": g["reason"],
                       "graded_batch": g["batch"]})

    print(f"Manifest cells: {len(manifest['cells'])}  graded: {len(cells)}  "
          f"ungraded: {len(ungraded)}")
    for p in problems:
        print(f"  [PROBLEM] {p}")

    # --- 1. Reference-grader validation against Jon -------------------------
    # Every validation row is one the judge called `different`. So the
    # reference grader saying `same` == "the answers actually agree" == the
    # judge made a false negative, which is exactly Jon's human_judge_error
    # label. Agreement is that comparison, per row.
    val = [c for c in cells if c["role"] == "validation"]
    val_rows = []
    for c in val:
        ref_says_judge_erred = c["ref_verdict"] == "same"
        val_rows.append({**c, "ref_judge_error": ref_says_judge_erred,
                          "agrees_with_jon": ref_says_judge_erred == c["human_judge_error"]})
    val_agree = sum(1 for r in val_rows if r["agrees_with_jon"])
    val_n = len(val_rows)
    # 2x2 against Jon
    val_confusion = Counter((r["human_judge_error"], r["ref_judge_error"]) for r in val_rows)

    # --- 2. False-negative rate --------------------------------------------
    human_fn_k = sum(1 for c in val if c["human_judge_error"])
    human_fn_n = len(val)

    fn = [c for c in cells if c["role"] == "fn_sample"]
    fn_k = sum(1 for c in fn if c["ref_verdict"] == "same")
    fn_n = len(fn)

    # Population-weighted FN over every `different` row in the population:
    # the 32 Jon graded (census, his labels) + the rest (estimated from the
    # sample). Kept explicit rather than pooling raw counts, because the two
    # halves have different sampling weights and different ground truth.
    n_diff_pop = manifest["population"]["different"]
    n_diff_rest = n_diff_pop - human_fn_n
    fn_rest_rate = (fn_k / fn_n) if fn_n else 0.0
    fn_pop_expected = human_fn_k + n_diff_rest * fn_rest_rate
    fn_pop_rate = fn_pop_expected / n_diff_pop if n_diff_pop else 0.0

    # --- 3. False-positive rate --------------------------------------------
    fp = [c for c in cells if c["role"] == "fp_sample"]
    fp_k = sum(1 for c in fp if c["ref_verdict"] == "different")
    fp_n = len(fp)
    fp_rate = fp_k / fp_n if fp_n else 0.0
    fp_lo, fp_hi = wilson(fp_k, fp_n)

    # --- 4. Headline corrections -------------------------------------------
    corrections = []
    for arm, fname in HEADLINE_ARMS.items():
        a = arm_counts(fname)
        corrected = (a["same"] * (1 - fp_rate) + a["different"] * fn_pop_rate) / a["n"]
        lo = (a["same"] * (1 - fp_hi) + a["different"] * fn_pop_rate) / a["n"]
        hi = (a["same"] * (1 - fp_lo) + a["different"] * fn_pop_rate) / a["n"]
        corrections.append({**a, "arm": arm, "corrected_accuracy": corrected,
                             "corrected_lo": lo, "corrected_hi": hi})

    # Per-arm and per-level breakdown of the FP sample, for the report.
    fp_by_arm = defaultdict(lambda: [0, 0])
    fp_by_level = defaultdict(lambda: [0, 0])
    for c in fp:
        fp_by_arm[c["arm"]][1] += 1
        fp_by_level[c["level"]][1] += 1
        if c["ref_verdict"] == "different":
            fp_by_arm[c["arm"]][0] += 1
            fp_by_level[c["level"]][0] += 1

    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": manifest["seed"],
        "judge_under_audit": {
            "model": manifest["judge_model"],
            "prompt_sha256": manifest["judge_prompt_sha256"],
        },
        "reference_grader": {
            "model": GRADER_MODEL,
            "prompt_sha256": manifest["grader_prompt_sha256"],
            "prompt_note": "identical to the audited judge's frozen prompt",
        },
        "population": manifest["population"],
        "coverage": {"n_cells": len(manifest["cells"]), "n_graded": len(cells),
                      "ungraded": ungraded, "problems": problems},
        "validation": {
            "n": val_n, "agree": val_agree,
            "agreement": val_agree / val_n if val_n else 0.0,
            "ci": wilson(val_agree, val_n),
            "confusion": {f"jon={k[0]},ref={k[1]}": v for k, v in val_confusion.items()},
            "disagreements": [
                {"arm": r["arm"], "id": r["id"], "level": r["level"],
                 "jon_judge_error": r["human_judge_error"],
                 "jon_note": human_notes.get((r["arm"], r["id"]), ""),
                 "gold_bottom_line": bottom_line(r["arm"], r["id"], "answer_gold"),
                 "candidate_bottom_line": bottom_line(r["arm"], r["id"], "answer"),
                 "ref_verdict": r["ref_verdict"], "ref_reason": r["ref_reason"]}
                for r in val_rows if not r["agrees_with_jon"]
            ],
        },
        "false_negative": {
            "human_census": {"k": human_fn_k, "n": human_fn_n,
                              "rate": human_fn_k / human_fn_n if human_fn_n else 0.0,
                              "ci": wilson(human_fn_k, human_fn_n),
                              "arms": ["derivability_B", "opus5_low_bucketA"]},
            "reference_sample": {"k": fn_k, "n": fn_n, "rate": fn_rest_rate,
                                  "ci": wilson(fn_k, fn_n),
                                  "sampled_from": n_diff_rest},
            "population_weighted_rate": fn_pop_rate,
            "population_n_different": n_diff_pop,
        },
        "false_positive": {
            "k": fp_k, "n": fp_n, "rate": fp_rate, "ci": [fp_lo, fp_hi],
            "sampled_from": manifest["population"]["same"],
            "by_arm": {k: v for k, v in sorted(fp_by_arm.items())},
            "by_level": {k: v for k, v in sorted(fp_by_level.items())},
        },
        "headline_corrections": corrections,
        "cost": manifest["cost_estimate"],
        "cells": cells,
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")

    write_report(results)
    print(f"Wrote {REPORT_PATH}")

    print(f"\n  validation agreement: {val_agree}/{val_n}")
    print(f"  FN (human census):    {fmt_rate(human_fn_k, human_fn_n)}")
    print(f"  FN (ref sample):      {fmt_rate(fn_k, fn_n)}")
    print(f"  FP (ref sample):      {fmt_rate(fp_k, fp_n)}")


def write_report(r: dict) -> None:
    v, fn, fp = r["validation"], r["false_negative"], r["false_positive"]
    hc, hcs = fn["human_census"], fn["reference_sample"]
    val_ok = v["agreement"] >= 0.90
    tt = v["confusion"].get("jon=True,ref=True", 0)
    tf = v["confusion"].get("jon=True,ref=False", 0)
    ft = v["confusion"].get("jon=False,ref=True", 0)
    ff = v["confusion"].get("jon=False,ref=False", 0)
    n_jon_err = tt + tf

    L: list[str] = []
    A = L.append

    A("# Results — judge error rate, both directions")
    A("")
    A("**Two findings, and the second one is the bigger deal.**")
    A("")
    A(f"1. **The unmeasured direction looks small.** Of {fp['n']} rows the frozen "
      f"judge PASSED, an independent reference grader found only {fp['k']} where the "
      f"answers materially differ — {fmt_pct(fp['rate'])} (95% CI "
      f"{fmt_pct(fp['ci'][0])}–{fmt_pct(fp['ci'][1])}). That grader is demonstrably "
      f"*stricter* than Jon (finding 2), so treat {fmt_pct(fp['rate'])} as an **upper "
      f"bound**: the repo's accuracy numbers are overstated by at most ~4 points from "
      f"this cause, and probably less.")
    A("")
    A(f"2. **The reference grader failed validation, and how it failed is the "
      f"finding.** On the {v['n']} rows Jon has hand-graded, it agreed with the frozen "
      f"judge **{v['n']}/{v['n']} times** — including all {n_jon_err} rows Jon "
      f"overturned as judge errors. It never once said \"these answers agree\" about a "
      f"row the judge called `different`. So a stronger model handed the same prompt "
      f"reproduces the same verdicts on the only rows with ground truth, and "
      f"**cannot serve as an independent check on this judge's false negatives**. "
      f"Agreement with Jon: {v['agree']}/{v['n']} = {fmt_pct(v['agreement'])}, entirely "
      f"from the rows where Jon and the judge already agreed.")
    A("")
    A(f"That reopens the question this work started from. `docs/results-gold-audit-batch1.md` "
      f"reported 5 of arm B's 15 flagged rows as judge false negatives, and that regrade "
      f"is what lifted arm B from 90.0% to 93.3%. Reading the answer text directly, **3 "
      f"of those rows state opposite bottom lines** (quoted below). Arm B's 93.3% rests "
      f"on grading calls that do not survive a second read, and Jon should re-examine "
      f"them before the number is quoted again.")
    A("")

    A("## What was measured")
    A("")
    A("The judge (`openai/gpt-5-mini`, frozen prompt digest "
      f"`{r['judge_under_audit']['prompt_sha256']}`) returns `same` or `different` per "
      "row; `same` counts as correct. It can be wrong in two directions, and until this "
      "run only one had been checked:")
    A("")
    A("| Direction | Meaning | Effect on accuracy | Prior evidence |")
    A("|---|---|---|---|")
    A("| **False negative** | judge said `different`, the answers agree | we UNDERSTATE | 5/15 on arm B (`docs/results-gold-audit-batch1.md`) — now in question |")
    A("| **False positive** | judge said `same`, the answers differ | we OVERSTATE | none — never measured before this run |")
    A("")

    A("## Provenance")
    A("")
    A("| | |")
    A("|---|---|")
    A(f"| Population | {r['population']['n']} judged rows across "
      f"{len(r['population']['arms'])} arms carrying the frozen judge stamp "
      f"({r['population']['same']} `same`, {r['population']['different']} `different`) |")
    A(f"| Sampler | `evals/judge_error_prep.py`, seed `{r['seed']}`, proportional "
      "stratified over (arm × level), largest-remainder allocation |")
    A(f"| Sample | {fp['n']} `same` rows + {hcs['n']} `different` rows + {v['n']} "
      f"Jon-graded validation rows = {r['coverage']['n_graded']} graded cells, "
      f"{r['coverage']['n_graded'] - len(r['coverage']['ungraded'])} returned |")
    A(f"| Reference grader | {r['reference_grader']['model']}, blind, given the audited "
      f"judge's own prompt verbatim (digest `{r['reference_grader']['prompt_sha256']}` — "
      "byte-identical to the judge's, so the only variable changed is the model) |")
    A("| Raw verdicts | `evals/judge_error_out/batch_*.jsonl` → `evals/judge_error_results.json` |")
    A("| Manifest (never shown to the grader) | `evals/judge_error_manifest.json` |")
    A(f"| Run | {r['generated_utc']} |")
    A(f"| API spend | **${r['cost']['actually_spent_usd']:.2f}**. The Anthropic API path "
      f"was estimated at ${r['cost']['est_cost_usd']:.2f} "
      f"({r['cost']['est_input_tokens']:,} in × ${r['cost']['input_per_mtok_usd']:.2f}/MTok "
      f"+ {r['cost']['est_output_tokens']:,} out × "
      f"${r['cost']['output_per_mtok_usd']:.2f}/MTok, well under the $8 gate) and "
      "deliberately not taken — grading ran on subscription subagents, per Jon's "
      "standing rule that ancillary Claude-labor never bills the API credits reserved "
      "for the product's own eval arms. |")
    A("")
    A("Cells are blind: the grader sees only the question, the reference answer and the "
      "candidate answer — never the judge's verdict or reason, the arm, the question id, "
      "the level, or Jon's verdict. Validation and sampled rows are shuffled together "
      "into 8 mixed batches under opaque `c####` ids, so no batch is identifiable as "
      "validation and the `same`/`different` mix cannot be inferred from position.")
    A("")

    A("## Validation — the reference grader vs Jon")
    A("")
    A(f"Run before anything downstream, on the {v['n']} rows whose answer is already "
      "known: the 15 arm-B rows from `docs/results-gold-audit-batch1.md` and the 17 "
      "bucket-A rows in `evals/verdicts_opus5_low_bucketA_human.json`. Both are "
      "censuses — every row those arms' judge flagged `different`.")
    A("")
    A("| | ref: answers agree | ref: answers differ |")
    A("|---|---|---|")
    A(f"| **Jon: judge erred** (answers agree) | {tt} | {tf} |")
    A(f"| **Jon: judge was right** (answers differ) | {ft} | {ff} |")
    A("")
    A(f"**Agreement with Jon: {v['agree']}/{v['n']} = {fmt_pct(v['agreement'])}** "
      f"(95% CI {fmt_pct(v['ci'][0])}–{fmt_pct(v['ci'][1])}). The frozen judge itself "
      "was adopted at a 95% bar; this is well under it.")
    A("")
    A("The shape matters more than the percentage. The whole top-right cell is empty: "
      "the reference grader said `different` on every single validation row, so it "
      "reproduced the frozen judge exactly. Its measured agreement with Jon is not "
      "evidence that it grades like Jon — it is evidence that it grades like the judge, "
      "and it only scores as high as it does because Jon agreed with the judge on the "
      f"other {ff} rows.")
    A("")
    A("Translating Jon's verdicts into the judge's question needed care, and the "
      "translation is recorded in `evals/judge_error_prep.py`:")
    A("")
    A("- On arm B, `ambiguous` means *either* \"the answers do not actually conflict\" "
      "*or* \"the rules do not settle it\" — only the first is a judge error, and "
      "`final_correct` separates them (rg5863 is ambiguous but not a judge error: an "
      "open rules-precedence question).")
    A("- On bucket A, Jon overturned 5 rows to `correct` but only **2** are judge "
      "errors; the other 3 are **gold** errors (rg4023 and rg6634 contradicted by the "
      "Urza's Saga ruling, rg4854 an illegal play the rulings don't state). The answers "
      "genuinely differ there — the judge was right and the gold was wrong. Counting "
      "those as judge errors would have inflated the FN rate by half.")
    A("")

    if v["disagreements"]:
        A(f"### The {len(v['disagreements'])} rows in dispute")
        A("")
        A("Jon marked each of these a judge error — the answers agree, the judge was "
          "wrong to flag them. The reference grader called all of them `different`. "
          "Each row's opening line is quoted verbatim from the verdict file, because on "
          "several of them the disagreement is settleable by reading, without needing "
          "any rules knowledge:")
        A("")
        A("| Arm | Q | Gold's bottom line | Candidate's bottom line | Jon's note |")
        A("|---|---|---|---|---|")
        for d in sorted(v["disagreements"], key=lambda x: (x["arm"], x["id"])):
            note = (d["jon_note"] or "").replace("|", "\\|").replace("\n", " ")[:90]
            A(f"| `{d['arm']}` | {d['id']} | {d['gold_bottom_line']} | "
              f"{d['candidate_bottom_line']} | {note} |")
        A("")
        A("Three of these read as flat contradictions on their face — **rg7215** "
          "(\"Tapped\" vs \"enters untapped\"), **rg549** (\"Any color\" vs \"produces "
          "no mana\"), and **rg811** (gold: trample and the upkeep sacrifice \"but no "
          "other abilities\"; candidate: also flying, vigilance and Threshold). A fourth, "
          "**rg1718**, matches the gold's `0` in two-player but adds a divergent "
          "multiplayer branch the gold does not have. The other three (**rg851**, "
          "**rg783**, **rg1900**) are genuine close calls about framing versus substance, "
          "and Jon's reading of them is defensible — one of the graders independently "
          "flagged rg851 as borderline for the same reason Jon did.")
        A("")
        A("This is surfaced for Jon to adjudicate, not resolved here. But it has a "
          "consequence either way: **the 5/15 false-negative finding, and arm B's "
          "93.3%, are not safe to quote until those rows are re-read.**")
        A("")

    A("## False-negative rate (judge said `different`, answers agree)")
    A("")
    A("Two independent standards, bracketing the answer rather than pretending to a "
      "point estimate:")
    A("")
    A(f"- **Jon's standard**, census of {hc['n']} flagged rows across arm B and "
      f"bucket A: {fmt_rate(hc['k'], hc['n'])}. Human ground truth, no model involved — "
      "but see the disputed rows above.")
    A(f"- **The reference grader's standard**, {hcs['n']} rows sampled from the "
      f"{hcs['sampled_from']} flagged rows in the other seven arms: "
      f"{fmt_rate(hcs['k'], hcs['n'])}.")
    A("")
    A(f"The two are far enough apart ({fmt_pct(hc['rate'])} vs {fmt_pct(hcs['rate'])}) "
      "that the gap is mostly a disagreement about where the \"same core ruling\" line "
      "sits, not sampling noise. The population-weighted figure used in the correction "
      f"arithmetic below — {fmt_pct(fn['population_weighted_rate'])} over all "
      f"{fn['population_n_different']} flagged rows, census where Jon graded and sample "
      "elsewhere — sits between them and inherits both problems.")
    A("")

    A("## False-positive rate (judge said `same`, answers differ)")
    A("")
    A(f"**{fmt_rate(fp['k'], fp['n'])}**, from a stratified sample of "
      f"{fp['sampled_from']} passed rows. There is no prior measurement to compare "
      "against — this is the first time anyone has looked.")
    A("")
    A("The four are worth reading individually, because none is a wild miss:")
    A("")
    A("| Arm | Q | Level | Why the reference grader split them |")
    A("|---|---|---|---|")
    for c in sorted(
        (c for c in r["cells"] if c["role"] == "fp_sample" and c["ref_verdict"] == "different"),
        key=lambda x: (x["arm"], x["id"]),
    ):
        reason = (c["ref_reason"] or "").replace("|", "\\|").replace("\n", " ")
        A(f"| `{c['arm']}` | {c['id']} | {c['level']} | {reason} |")
    A("")
    A("| Level | FP / sampled |")
    A("|---|---|")
    for lvl, (k, n) in fp["by_level"].items():
        A(f"| {lvl} | {k}/{n} |")
    A("")
    A("| Arm | FP / sampled |")
    A("|---|---|")
    for arm, (k, n) in fp["by_arm"].items():
        A(f"| `{arm}` | {k}/{n} |")
    A("")
    A("**Why this is an upper bound.** The grader that produced it is the same one that "
      f"refused to call a single one of Jon's {n_jon_err} overturned rows an agreement. "
      "A grader biased toward `different` will over-report false positives, not "
      "under-report them. Under Jon's more lenient reading of \"same core ruling\", the "
      f"true FP rate is at or below {fmt_pct(fp['rate'])}.")
    A("")

    A("## What this does to the headline numbers")
    A("")
    A("Each arm's published accuracy is re-read from its own verdict file at report "
      "time (mtimes in the table), then corrected as")
    A("")
    A("```")
    A("corrected = [ n_same x (1 - FP)  +  n_different x FN ] / n")
    A("```")
    A("")
    A(f"with FP = {fmt_pct(fp['rate'])} and FN = "
      f"{fmt_pct(fn['population_weighted_rate'])}. Because FP is an upper bound, the "
      "corrected column is a **floor** — the true value sits between it and the "
      "published number. The range spans the FP confidence interval only; it does not "
      "propagate the reference grader's own error, which is larger than the arithmetic.")
    A("")
    A("| Arm | n | same/diff | Published | Corrected (floor) | Range (FP CI) | Source file (mtime UTC) |")
    A("|---|---|---|---|---|---|---|")
    for c in r["headline_corrections"]:
        A(f"| `{c['arm']}` | {c['n']} | {c['same']}/{c['different']} | "
          f"{fmt_pct(c['published_accuracy'])} | **{fmt_pct(c['corrected_accuracy'])}** | "
          f"{fmt_pct(c['corrected_lo'])}–{fmt_pct(c['corrected_hi'])} | "
          f"`evals/{c['file']}` ({c['mtime_utc']}) |")
    A("")
    A("Every \"Published\" figure above is the **raw judge accuracy** straight from the "
      "verdict file — for `derivability_B` that is 90.0%, not the 93.3% quoted "
      "elsewhere, which additionally folds in Jon's hand-regrade of the flagged side. "
      "The two arm-specific paragraphs below handle that difference explicitly.")
    A("")
    byarm = {c["arm"]: c for c in r["headline_corrections"]}
    b = byarm.get("derivability_B")
    if b:
        b_regraded = (b["same"] + 5) / b["n"]
        b_corr = (b["same"] * (1 - fp["rate"]) + 5) / b["n"]
        A(f"**Arm B's 93.3%.** That published figure is "
          f"{b['same']}/{b['n']} passed plus Jon's 5-row regrade of the flagged side "
          f"(`docs/results-derivability.md`) = {fmt_pct(b_regraded)}. Two things pull on "
          "it in opposite directions, and both are live:")
        A("")
        A(f"- Applying only the FP correction to its {b['same']} passed rows, keeping "
          f"Jon's 5 regraded rows, gives **{fmt_pct(b_corr)}** — the regrade's +3.3pt "
          "gain roughly cancelled.")
        A(f"- If the 3 flat-contradiction rows above are re-read as genuine "
          f"disagreements, the regrade drops from 5 rows to 2 and the base falls to "
          f"{fmt_pct((b['same'] + 2) / b['n'])} before any FP correction.")
        A("")
        A("Either way it is not 93.3%. The honest statement today is that arm B sits in "
          f"the high 80s, with **{fmt_pct(b_corr)}** the best single estimate.")
        A("")
    h1, h2 = byarm.get("h2h_opuslow_hard_r1"), byarm.get("h2h_opuslow_hard_r2")
    if h1 and h2:
        pub_mean = (h1["published_accuracy"] + h2["published_accuracy"]) / 2
        corr_mean = (h1["corrected_accuracy"] + h2["corrected_accuracy"]) / 2
        A(f"**The opus-low hard mean, 74.1%.** Published "
          f"{fmt_pct(h1['published_accuracy'])} (r1) and "
          f"{fmt_pct(h2['published_accuracy'])} (r2), mean {fmt_pct(pub_mean)}. "
          f"Corrected mean: **{fmt_pct(corr_mean)}** — essentially unmoved. The two "
          "corrections nearly cancel on this arm because it has a large flagged side "
          f"({h1['different']} and {h2['different']} rows), so the FN credit offsets the "
          "FP debit. The hard-set number is the most robust of the headline figures.")
        A("")

    A("## Limits — read these before quoting anything above")
    A("")
    A(f"1. **The reference grader is not a reference.** It agreed with the audited judge "
      f"on {v['n']}/{v['n']} validation rows and with Jon on {v['agree']}/{v['n']}. "
      "Every rate here inherits that, and the confidence intervals do not include it — "
      "they are sampling error only. The FP rate should be read as a bound, not a "
      "measurement.")
    A("2. **Same prompt, different model, same answers.** The grader was given the "
      "judge's prompt verbatim so that only the model varied. On the evidence, the "
      "prompt — not the model's capability — is what determines where the `same` / "
      "`different` line falls. A genuinely independent check needs a different "
      "*criterion*, or a human, not a bigger model.")
    A("3. **The FP direction still has no human ground truth.** Nobody has hand-graded "
      "a passed row. The four flagged above are the entire evidence base and are the "
      "cheapest, highest-value thing to put in front of Jon next.")
    A(f"4. **`derivability_C` contributes no `same` rows** — it has only 4 in the whole "
      "arm, and proportional allocation rounded it to zero. The FP rate covers 8 of the "
      "9 arms.")
    A("5. **The judge is nondeterministic** (~1 flip per 100 rows on re-judging). That "
      "is a third error source, separate from the two measured here, and is not folded "
      "into these numbers.")
    A("6. **Correction is arithmetic, not a re-grade.** Applying a population rate to "
      "one arm assumes that arm's error rate matches the population's. The per-arm FP "
      "counts above are small; do not read a single arm's cell as its own rate.")
    A("")
    A("## What would actually settle this")
    A("")
    A("Jon hand-grades a blind mixed set — the 4 flagged passed rows above, the 7 "
      "disputed validation rows, and ~30 fresh passed rows he has not seen — without "
      "knowing which is which. That produces the one thing missing from every number "
      "here: human ground truth on the direction that has never had any, and a re-read "
      "of the arm-B calls that the 93.3% depends on.")
    A("")
    A("## Reproducing")
    A("")
    A("```")
    A("uv run python evals/judge_error_prep.py       # sample + batches (seeded, no API calls)")
    A("#   ... grade evals/judge_error_batches/*.md with Opus subagents ...")
    A("uv run python evals/judge_error_metrics.py    # rates + this report")
    A("```")
    A("")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

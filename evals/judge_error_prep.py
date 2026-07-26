"""Judge false-negative / false-positive measurement -- PREP stage ONLY
(docs/results-judge-error-rate.md).

WHY THIS EXISTS. `docs/results-gold-audit-batch1.md` measured the frozen
gpt-5-mini judge in ONE direction only: Jon hand-graded the 15 rows the judge
flagged `different` in derivability arm B, and 5 of them turned out to be rows
where both answers say the same thing. Nobody has ever checked the rows the
judge PASSED. If the judge also wrongly passes rows, every accuracy number in
this repo is overstated by an unknown amount. This script assembles the sample
that answers that.

  false negative  judge said `different`, the answers actually agree
                  -> we UNDERSTATE accuracy
  false positive  judge said `same`, the answers actually differ
                  -> we OVERSTATE accuracy  (never measured before this run)

WHAT IT DOES. Draws a seeded stratified random sample from every judged arm
that carries the frozen judge stamp (`judge_prompt_sha256 == b54fbdb95565abf8`),
shuffles it together with a validation set of rows Jon has already hand-graded,
and writes batch files for a stronger reference grader to grade BLIND.

BLINDNESS. Each cell shows only what the frozen judge itself saw: the question,
the REFERENCE (RulesGuru gold) answer, and the CANDIDATE (bot) answer. The
grader never sees the judge's verdict, the judge's reason, the arm name, the
question id, the level, or -- for validation rows -- Jon's verdict. Cells carry
opaque `c####` ids and are shuffled across batches, so a grader cannot tell a
validation row from a sampled one, or a `same` row from a `different` one.

SAME CRITERION, STRONGER MODEL. The grading instruction is
`judge_rulesguru.RULESGURU_JUDGE_SYS` imported verbatim -- the exact frozen
prompt (digest b54fbdb95565abf8), not a paraphrase. The only variable changed
is which model answers it. Anything else would measure prompt drift instead of
judge error.

BILLING. This script makes ZERO API calls of any kind -- it reads committed
JSON off disk and writes markdown. It PRINTS an Anthropic API cost estimate for
the path it deliberately does NOT take, because the task that commissioned this
run required an explicit tokens x price estimate before any spend. The grading
itself runs as in-session Opus subagents on Jon's Claude subscription, per his
standing instruction that ancillary Claude-labor (grading, judging experiments)
never bills the prepaid API credits reserved for the product's own eval arms.

Outputs:
  evals/judge_error_batches/batch_NN.md   -- blind cells for the reference grader
  evals/judge_error_manifest.json         -- cell -> (arm, id, judge verdict,
                                             human ground truth) -- NEVER shown
                                             to the grader; read by the metrics
                                             stage only
  evals/judge_error_out/                  -- empty dir grading writes into

Run: `uv run python evals/judge_error_prep.py`
PYTHONIOENCODING=utf-8 recommended (Windows console).
"""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

# evals/ isn't an installed package -- same sys.path pattern every other
# evals/*.py script uses so imports resolve regardless of caller cwd.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from judge_rulesguru import RULESGURU_JUDGE_SYS  # noqa: E402

EVALS_DIR = Path(__file__).parent
BATCH_DIR = EVALS_DIR / "judge_error_batches"
OUT_DIR = EVALS_DIR / "judge_error_out"
MANIFEST_PATH = EVALS_DIR / "judge_error_manifest.json"

SEED = 20260726

# The frozen judge under audit. Every arm below was judged by this exact
# model+prompt; the digest is asserted at load time so a silently re-judged
# file can't slip into the population.
FROZEN_JUDGE_MODEL = "openai/gpt-5-mini"
FROZEN_JUDGE_DIGEST = "b54fbdb95565abf8"

# Every arm carrying the frozen stamp, keyed by the short name used in the
# report. r1/r2 pairs are NOT re-judgements of one answer set -- they are
# separate generation runs (verified: 0/50, 0/54, 0/50 identical answers), so
# both are distinct (arm, question) cells and both belong in the population.
ARMS = {
    "derivability_B": "verdicts_derivability_B.json",
    "derivability_C": "verdicts_derivability_C.json",
    "h2h_opuslow_easy_r1": "verdicts_h2h_opuslow_easy_r1.json",
    "h2h_opuslow_easy_r2": "verdicts_h2h_opuslow_easy_r2.json",
    "h2h_opuslow_hard_r1": "verdicts_h2h_opuslow_hard_r1.json",
    "h2h_opuslow_hard_r2": "verdicts_h2h_opuslow_hard_r2.json",
    "h2h_sonnet_easy_r1": "verdicts_h2h_sonnet_easy_r1.json",
    "h2h_sonnet_easy_r2": "verdicts_h2h_sonnet_easy_r2.json",
    "opus5_low_bucketA": "verdicts_opus5_low_bucketA.json",
}

# ---------------------------------------------------------------------------
# Validation ground truth: rows Jon has already hand-graded.
#
# The judge's question is "do these two answers reach the same core ruling?" --
# NOT "is the bot right". So Jon's verdict has to be translated into that
# question, and the translation is not the same for both files.
#
# derivability arm B (docs/results-gold-audit-batch1.md, 15 rows). Jon's
# vocabulary grades WHO is wrong. `ambiguous` means either "the two answers do
# not actually conflict" or "the rules do not settle it" -- only the first is a
# judge error, and `final_correct` separates them (rg5863 is ambiguous but
# final_correct=False: an open rules-precedence question, so the judge calling
# it `different` is defensible). ours-wrong / gold-incomplete / rulesguru-wrong
# all mean the two answers GENUINELY differ -- the judge was right to flag them
# even where the bot beat the gold.
#
# opus5 bucket A (evals/verdicts_opus5_low_bucketA_human.json, 17 rows). Jon
# overturned 5 to `correct`, but only 2 of those are judge errors; the other 3
# are GOLD errors, where the answers really do differ and the gold is the wrong
# one (rg4023 + rg6634 contradicted by the Urza's Saga ruling, rg4854 an
# illegal play the rulings don't state). Jon's own split of this bucket is
# "2 judge errors, 3 gold errors" -- reproduced here from his grading notes,
# not asserted from memory.
JUDGE_ERROR_TRUTH: dict[tuple[str, str], bool] = {
    # derivability_B -- True == answers actually agree == judge false negative
    ("derivability_B", "rg7215"): True,
    ("derivability_B", "rg549"): True,
    ("derivability_B", "rg1718"): True,
    ("derivability_B", "rg851"): True,
    ("derivability_B", "rg811"): True,
    ("derivability_B", "rg5863"): False,
    ("derivability_B", "rg494"): False,
    ("derivability_B", "rg713"): False,
    ("derivability_B", "rg1095"): False,
    ("derivability_B", "rg1208"): False,
    ("derivability_B", "rg842"): False,
    ("derivability_B", "rg241"): False,
    ("derivability_B", "rg559"): False,
    ("derivability_B", "rg6556"): False,
    ("derivability_B", "rg289"): False,
    # opus5_low_bucketA -- 2 judge errors, 3 gold errors, 12 bot errors
    ("opus5_low_bucketA", "rg783"): True,
    ("opus5_low_bucketA", "rg1900"): True,
    ("opus5_low_bucketA", "rg4023"): False,   # gold error
    ("opus5_low_bucketA", "rg4854"): False,   # gold error
    ("opus5_low_bucketA", "rg6634"): False,   # gold error
    ("opus5_low_bucketA", "rg104"): False,
    ("opus5_low_bucketA", "rg132"): False,
    ("opus5_low_bucketA", "rg191"): False,
    ("opus5_low_bucketA", "rg346"): False,
    ("opus5_low_bucketA", "rg614"): False,
    ("opus5_low_bucketA", "rg633"): False,
    ("opus5_low_bucketA", "rg776"): False,
    ("opus5_low_bucketA", "rg811"): False,
    ("opus5_low_bucketA", "rg813"): False,
    ("opus5_low_bucketA", "rg1128"): False,
    ("opus5_low_bucketA", "rg1643"): False,
    ("opus5_low_bucketA", "rg6626"): False,
}

N_SAME = 90        # the unmeasured direction -- weighted heavily
N_DIFFERENT = 30   # extends FN coverage past the arms Jon already graded
BATCH_SIZE = 19

# Published Anthropic API rates for claude-opus-5, per the claude-api skill
# (loaded fresh this session). $ per 1,000,000 tokens. Used ONLY for the
# printed estimate of the path not taken -- see module docstring.
OPUS5_INPUT_PER_MTOK = 5.00
OPUS5_OUTPUT_PER_MTOK = 25.00
EST_OUTPUT_TOKENS_PER_CELL = 60   # "Verdict: x\nReason: <one sentence>"
EST_CHARS_PER_TOKEN = 3.5         # conservative for the current tokenizer


def load_population() -> list[dict]:
    """Every judged row across every frozen-stamp arm, as flat cells.

    Asserts the frozen stamp per file: an arm judged by a different model or a
    reworded prompt is not evidence about THIS judge and must not silently join
    the population.
    """
    rows: list[dict] = []
    for arm, fname in ARMS.items():
        data = json.loads((EVALS_DIR / fname).read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        model, digest = summary.get("judge_model"), summary.get("judge_prompt_sha256")
        if model != FROZEN_JUDGE_MODEL or digest != FROZEN_JUDGE_DIGEST:
            raise SystemExit(
                f"[ABORT] {fname}: judge stamp is {model}/{digest}, expected "
                f"{FROZEN_JUDGE_MODEL}/{FROZEN_JUDGE_DIGEST}. Not the frozen judge."
            )
        for e in data["entries"]:
            if e["verdict"] not in ("same", "different"):
                continue  # unparsed/error rows carry no judge decision to audit
            rows.append({
                "arm": arm,
                "id": e["id"],
                "level": e["level"],
                "complexity": e.get("complexity", ""),
                "verdict": e["verdict"],
                "question": e["question"],
                "answer_gold": e["answer_gold"],
                "answer": e["answer"],
            })
    return rows


def stratified_sample(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Proportional stratified sample over (arm, level).

    Largest-remainder allocation, so the sample's stratum shares track the
    population's instead of being distorted by per-stratum rounding. Every
    non-empty stratum with a positive allocation contributes; strata smaller
    than their allocation contribute all of their rows and the shortfall is
    redistributed by the remainder pass.
    """
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        strata[(r["arm"], r["level"])].append(r)

    total = len(rows)
    exact = {k: n * len(v) / total for k, v in strata.items()}
    alloc = {k: min(int(v), len(strata[k])) for k, v in exact.items()}

    # Largest-remainder pass, capped by stratum size.
    while sum(alloc.values()) < n:
        candidates = [
            (exact[k] - alloc[k], k) for k in strata if alloc[k] < len(strata[k])
        ]
        if not candidates:
            break
        candidates.sort(reverse=True)
        alloc[candidates[0][1]] += 1

    out: list[dict] = []
    for k in sorted(strata):
        picked = rng.sample(strata[k], alloc[k]) if alloc[k] else []
        for r in picked:
            out.append({**r, "stratum": f"{k[0]}|L{k[1]}"})
    return out


def verify_stratification(sample: list[dict], population: list[dict], label: str) -> list[str]:
    """Structural checks are not enough -- confirm the sample is actually
    stratified, not merely that the sampler ran. Reports the worst share drift
    between sample and population across (arm, level) strata, plus per-arm and
    per-level coverage."""
    def shares(rows):
        c = Counter((r["arm"], r["level"]) for r in rows)
        t = len(rows)
        return {k: v / t for k, v in c.items()}

    ps, ss = shares(population), shares(sample)
    drift = sorted(
        ((abs(ss.get(k, 0.0) - ps[k]), k) for k in ps), reverse=True
    )
    lines = [
        f"  [{label}] n={len(sample)} of population {len(population)}",
        f"    arms covered:   {len(set(r['arm'] for r in sample))}/"
        f"{len(set(r['arm'] for r in population))}",
        f"    levels covered: {sorted(set(r['level'] for r in sample))}",
        f"    max stratum share drift: {drift[0][0]*100:.1f}pp "
        f"(stratum {drift[0][1][0]}|L{drift[0][1][1]})",
    ]
    return lines


CELL_TEMPLATE = """### CELL {cell}

**Question**
{question}

**REFERENCE (correct)**
{reference}

**CANDIDATE**
{candidate}

"""


def build_batch_md(batch_id: str, cells: list[dict]) -> str:
    head = f"""# Reference-grading batch {batch_id}

You are the reference grader for an audit of an automated LLM judge. Your
verdicts become ground truth, so grade each cell carefully and independently.

Apply EXACTLY this criterion (the audited judge's own frozen system prompt,
reproduced verbatim -- do not substitute your own standard):

---
{RULESGURU_JUDGE_SYS}
---

Ground every Magic ruling judgement in what the two answers actually say. You
are not being asked which answer is correct in absolute terms -- only whether
the CANDIDATE reaches the SAME core ruling as the REFERENCE. Two answers that
state the same outcome in different words are `same`. An answer that reaches a
different outcome, reverses the ruling, declines to answer, or omits a
materially load-bearing part of the conclusion is `different`.

There are {len(cells)} cells below. Grade every one. Do not skip cells and do
not batch-guess: the cells are a deliberate mix and the proportion of `same` to
`different` is not something you should try to infer.

**Output**: write one JSON object per line to
`evals/judge_error_out/{batch_id}.jsonl` -- nothing else, no prose, no markdown
fence:

    {{"cell": "c0001", "verdict": "same", "reason": "<one sentence>"}}

`verdict` must be exactly `same` or `different`. Write one line per cell, in
the order the cells appear.

---

"""
    body = "".join(
        CELL_TEMPLATE.format(
            cell=c["cell"],
            question=c["question"].strip(),
            reference=c["answer_gold"].strip(),
            candidate=(c["answer"] or "(empty answer)").strip(),
        )
        for c in cells
    )
    return head + body


def estimate_api_cost(cells: list[dict]) -> dict:
    """Tokens x price for the Anthropic API path this run deliberately does not
    take. Token counts are a chars/{EST_CHARS_PER_TOKEN} estimate, not a
    count_tokens() call -- calling count_tokens would itself construct an
    Anthropic client, which this script is explicitly written never to do."""
    sys_chars = len(RULESGURU_JUDGE_SYS)
    body_chars = sum(
        len(c["question"]) + len(c["answer_gold"]) + len(c["answer"] or "") + 200
        for c in cells
    )
    in_tokens = int((sys_chars * len(cells) + body_chars) / EST_CHARS_PER_TOKEN)
    out_tokens = EST_OUTPUT_TOKENS_PER_CELL * len(cells)
    cost = (in_tokens / 1e6 * OPUS5_INPUT_PER_MTOK) + (out_tokens / 1e6 * OPUS5_OUTPUT_PER_MTOK)
    return {
        "model": "claude-opus-5",
        "n_cells": len(cells),
        "est_input_tokens": in_tokens,
        "est_output_tokens": out_tokens,
        "input_per_mtok_usd": OPUS5_INPUT_PER_MTOK,
        "output_per_mtok_usd": OPUS5_OUTPUT_PER_MTOK,
        "est_cost_usd": cost,
        "actually_spent_usd": 0.0,
        "note": "estimate only; grading ran on subscription subagents, no API call",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    population = load_population()
    print(f"Population: {len(population)} judged rows across {len(ARMS)} frozen-stamp arms")
    vc = Counter(r["verdict"] for r in population)
    print(f"  judge verdicts: same={vc['same']}  different={vc['different']}")

    # Validation rows: every row Jon has already hand-graded. A census of two
    # arms' flagged rows, so it is reported separately from the sampled rates
    # rather than pooled into them.
    validation = [
        {**r, "role": "validation", "stratum": f"{r['arm']}|L{r['level']}"}
        for r in population
        if (r["arm"], r["id"]) in JUDGE_ERROR_TRUTH
    ]
    missing = set(JUDGE_ERROR_TRUTH) - {(r["arm"], r["id"]) for r in validation}
    if missing:
        raise SystemExit(f"[ABORT] human-graded rows not found in population: {sorted(missing)}")
    print(f"  validation rows (Jon-graded): {len(validation)}")

    val_keys = {(r["arm"], r["id"]) for r in validation}
    same_pop = [r for r in population if r["verdict"] == "same"]
    diff_pop = [r for r in population if r["verdict"] == "different"
                and (r["arm"], r["id"]) not in val_keys]

    same_sample = [{**r, "role": "fp_sample"} for r in stratified_sample(same_pop, N_SAME, rng)]
    diff_sample = [{**r, "role": "fn_sample"} for r in stratified_sample(diff_pop, N_DIFFERENT, rng)]

    print("\nStratification check (sample share vs population share):")
    for line in verify_stratification(same_sample, same_pop, "same / FP sample"):
        print(line)
    for line in verify_stratification(diff_sample, diff_pop, "different / FN sample"):
        print(line)

    cells = validation + same_sample + diff_sample
    rng.shuffle(cells)  # so no batch is all-validation or all-same
    for i, c in enumerate(cells, 1):
        c["cell"] = f"c{i:04d}"

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / ".gitkeep").write_text("", encoding="utf-8")

    batches = [cells[i:i + BATCH_SIZE] for i in range(0, len(cells), BATCH_SIZE)]
    for n, batch in enumerate(batches, 1):
        bid = f"batch_{n:02d}"
        (BATCH_DIR / f"{bid}.md").write_text(build_batch_md(bid, batch), encoding="utf-8")
        for c in batch:
            c["batch"] = bid

    manifest = {
        "seed": args.seed,
        "judge_model": FROZEN_JUDGE_MODEL,
        "judge_prompt_sha256": FROZEN_JUDGE_DIGEST,
        "grader_prompt_sha256": hashlib.sha256(
            RULESGURU_JUDGE_SYS.encode("utf-8")
        ).hexdigest()[:16],
        "population": {
            "n": len(population),
            "same": vc["same"],
            "different": vc["different"],
            "arms": {a: sum(1 for r in population if r["arm"] == a) for a in ARMS},
        },
        "n_validation": len(validation),
        "n_fp_sample": len(same_sample),
        "n_fn_sample": len(diff_sample),
        "batch_size": BATCH_SIZE,
        "n_batches": len(batches),
        "cost_estimate": estimate_api_cost(cells),
        "cells": [
            {
                "cell": c["cell"], "batch": c["batch"], "role": c["role"],
                "arm": c["arm"], "id": c["id"], "level": c["level"],
                "stratum": c["stratum"], "judge_verdict": c["verdict"],
                "human_judge_error": JUDGE_ERROR_TRUTH.get((c["arm"], c["id"])),
            }
            for c in sorted(cells, key=lambda x: x["cell"])
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    est = manifest["cost_estimate"]
    print(f"\nWrote {len(batches)} batches ({len(cells)} cells) -> {BATCH_DIR}")
    print(f"Wrote manifest -> {MANIFEST_PATH}")
    print("\n--- COST ESTIMATE for the Anthropic API path (NOT taken) ---")
    print(f"  model {est['model']}: {est['est_input_tokens']:,} in x "
          f"${est['input_per_mtok_usd']:.2f}/MTok + {est['est_output_tokens']:,} out x "
          f"${est['output_per_mtok_usd']:.2f}/MTok")
    print(f"  = ${est['est_cost_usd']:.2f} (gate: stop if > $8.00)")
    print("  ACTUAL API SPEND: $0.00 -- grading runs on subscription subagents "
          "(Jon's standing billing instruction).")


if __name__ == "__main__":
    main()

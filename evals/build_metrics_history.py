"""Collect every number we own about every judged arm into one comparable table.

WHY THIS EXISTS. Jon, 2026-07-26: he wants cost, accuracy, weighting, tokens and
config for every arm and iteration **side by side across time**, in one page, to
answer a specific question -- *is it time for the full RulesGuru run on the entire
dataset?* Numbers currently live scattered across `docs/results-*.md`,
`docs/report-*.md` and handoff prose, each written at a different moment against a
file that may have moved since.

THE TWO THINGS THAT MAKE THIS HONEST RATHER THAN IMPRESSIVE:

**1. Arms are not all comparable, so the table says which are.** Different arms
ran on different question sets (the v3 150, a hard 54, an easy 50), so a single
ranked list would invite comparisons that mean nothing. Every arm gets a
`qset` fingerprint -- the first 8 hex of a SHA-256 over its sorted question ids --
and arms sharing a fingerprint are the only ones directly comparable. This is
computed from the ids themselves, not inferred from a filename or a count.

**1b. A shared question set is necessary but NOT sufficient.** Jon, 2026-07-26:
the page implied we were testing things against each other that were never
comparable experiments. Three arms share the 150-question fingerprint and measure
three different quantities -- one runs the product end to end, one is handed the
gold rules with retrieval switched off (it measures whether the answers are
*derivable at all*), and one records no config whatsoever. So every arm also gets
a **kind**, DERIVED FROM THE RECORDED DATA and never from its name: `pipeline`
(retrieval recorded and non-empty), `oracle` (retrieval recorded and empty on
every row -- the model answered without retrieved rules), `unknown` (retrieval
not recorded, so nothing is established). A delta may only be taken between two
arms sharing BOTH the fingerprint AND the kind, and never to or from `unknown`.
Different kinds still render side by side, because that is useful, but each says
what it measures and the page says plainly they are not on the same scale.

**2. Every number carries what produced it -- and there are THREE events, not
one.** This repo has already shipped a results doc that disagreed with its own
verdict file inside one commit, because a number was read at one time and
published at another. Worse, "the run" is ambiguous: the **generation run**
(answers file: when the answers were produced, under which config) and the
**judging run** (verdict file: when those answers were scored, by which judge
model and prompt digest) are separate events, and where a human regraded, the
**human grading pass** is a third. The judge is nondeterministic -- re-judging
identical answers moved one arm by 2 pp -- so an accuracy that does not name its
judging run is not reproducible. All three layers are reported separately for
every number on the page. A row you cannot trace is a row you cannot use to make
a go/no-go call.

**KNOWN PROVENANCE GAP, surfaced rather than papered over.** Verdict files do not
record which answers file they judged -- the link is filename convention
(`verdicts_X.json` <-> `answers/X.json`) plus a small alias table. Every row
reports how its join was made (`exact` / `alias` / `prefix` / `unmatched`), so a
guessed join is visible as a guess. Rows that cannot be joined still appear, with
accuracy and no cost.

COST IS COMPUTED, NOT ASSUMED. Token ratios are not a cost result -- opus costs
more per token than sonnet, so fewer tokens does not establish which is cheaper.
Per-MTok prices below come from the `claude-api` skill (checked 2026-07-26), never
from recall, and cache-tier multipliers are applied separately because a cached
read costs a tenth of a fresh input token. Sonnet 5 is dual-priced: its
introductory rate runs through 2026-08-31, so both are shown and the arm is
costed at BOTH, since which one applies depends on when you re-run it.

Usage:
    python evals/build_metrics_history.py
    python evals/build_metrics_history.py --json evals/_metrics_history.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import weighted_score as ws

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
ANSWERS = EVALS / "answers"

# Per-MTok (input, output). Source: claude-api skill, checked 2026-07-26.
# Never fill these in from memory -- reread the skill when they may have moved.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-sonnet-5": (3.00, 15.00),          # standard rate
    "claude-sonnet-5@intro": (2.00, 10.00),    # introductory, through 2026-08-31
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
SONNET_INTRO_ENDS = "2026-08-31"
CACHE_READ_MULT = 0.10    # cached input bills at ~0.1x
CACHE_WRITE_MULT = 1.25   # 5-minute TTL write premium

# Verdict stems whose answers file is named differently. Kept explicit and small:
# a fuzzy matcher that silently picks the wrong answers file would attach one
# arm's cost to another arm's accuracy, which is worse than reporting no cost.
ALIASES = {
    "derivability_B": "derivability_B_goldonly",
    "derivability_B_human": "derivability_B_goldonly",  # same answers, human-regraded
    "derivability_C": "derivability_C_failures",
    "rulesguru_sonnet": "rulesguru_answers",            # verified: model=claude-sonnet-5, n=150
}


def _mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).astimezone().isoformat(timespec="minutes")


# ---------------------------------------------------------------------------
# ARM KIND. What the arm actually measures -- decided by the recorded data.
#
# The only field that establishes it is `retrieved_rule_ids`, which the answer
# writer records per question. An arm whose every row retrieved nothing yet still
# answered was handed its rules some other way (the derivability runs are handed
# gold); an arm that retrieved on every row ran the product. An arm that does not
# record the field at all establishes NEITHER, and is called `unknown` rather
# than assumed -- guessing here is exactly the error this section exists to stop.
# ---------------------------------------------------------------------------
KIND_RULE = ("Derived per arm from the answers file, never from its name. "
             "`retrieved_rule_ids` non-empty on every row → pipeline (the product path). "
             "Recorded but empty on every row → oracle (the model answered without retrieved "
             "rules; the derivability runs are handed gold instead). "
             "Field absent, mixed, or no answers file joined → unknown.")


def classify_arm(rows: list[dict]) -> tuple[str, str]:
    """(kind, the evidence sentence that justifies it). Never guesses."""
    real = [r for r in rows if "question" in r or "answer" in r]
    if not real:
        return "unknown", ("the answers file holds a run summary, not per-question rows — "
                           "no model, effort or retrieval is recorded for this arm")
    have = [r for r in real if "retrieved_rule_ids" in r]
    if not have:
        return "unknown", (f"the {len(real)} answer rows do not record `retrieved_rule_ids`, "
                           "so whether retrieval ran is not established by any file we own")
    if len(have) != len(real):
        return "unknown", (f"only {len(have)} of {len(real)} rows record `retrieved_rule_ids` — "
                           "mixed, so the arm cannot be classified")
    hit = sum(1 for r in have if r.get("retrieved_rule_ids"))
    if hit == 0:
        return "oracle", (f"retrieval recorded and EMPTY on all {len(have)} rows — the model "
                          "answered without retrieved rules, so this measures whether the answer "
                          "is derivable at all, not what the pipeline scores")
    if hit == len(have):
        avg = sum(len(r["retrieved_rule_ids"]) for r in have) / len(have)
        return "pipeline", (f"retrieval recorded and non-empty on all {len(have)} rows "
                            f"({avg:.1f} rule ids per question on average) — the product path")
    return "unknown", (f"retrieval ran on {hit} of {len(have)} rows — mixed, so the arm "
                       "cannot be classified as either path")


def _row_correct(e: dict) -> bool | None:
    """One row's final correctness, human grading winning where it exists.

    `final_correct` is written by the human-merge step and is the number of
    record; `verdict` is the judge's raw call. Reading `verdict` on a regraded
    file would silently discard the human pass.
    """
    if e.get("final_correct") is not None:
        return bool(e["final_correct"])
    v = e.get("verdict")
    return None if v is None else v == "same"


def _ids_of(path: Path) -> frozenset[str] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = raw if isinstance(raw, list) else list(raw.values()) if isinstance(raw, dict) else []
    ids = {r["id"] for r in rows if isinstance(r, dict) and "id" in r}
    return frozenset(ids) or None


def resolve_answers(stem: str, want: frozenset[str]) -> tuple[Path | None, str]:
    """(answers path, how the join was made) -- and the join is VERIFIED.

    Filename convention alone is a guess: verdict files do not record which
    answers file they judged. So every candidate is confirmed by comparing
    question-id sets against the verdict's, and a name that matches while the ids
    do not is reported as `name-matched-ids-differ` rather than being used. That
    turns "probably the right file" into a checked fact, which is the difference
    between a cost figure you can publish and one you can't.
    """
    candidates: list[tuple[Path, str]] = []
    exact = ANSWERS / f"{stem}.json"
    if exact.exists():
        candidates.append((exact, "exact"))
    if stem in ALIASES and (p := ANSWERS / f"{ALIASES[stem]}.json").exists():
        candidates.append((p, "alias"))
    for p in sorted(ANSWERS.glob(f"{stem}*.json")):
        if not p.name.startswith("_"):
            candidates.append((p, "prefix"))

    named_but_wrong = False
    for path, how in candidates:
        got = _ids_of(path)
        if got == want:
            return path, how
        if got is not None:
            named_but_wrong = True

    # No name matched, or the named file held different questions. Fall back to
    # an id-set search across every answers file -- a slower but strictly
    # stronger join, since it is decided by the data rather than the filename.
    matches = [p for p in sorted(ANSWERS.glob("*.json"))
               if not p.name.startswith("_") and _ids_of(p) == want]
    if len(matches) == 1:
        return matches[0], "id-match"
    if len(matches) > 1:
        return None, f"ambiguous ({len(matches)} files share these ids)"
    return None, "name-matched-ids-differ" if named_but_wrong else "unmatched"


def cost_of(rows: list[dict], model: str) -> dict:
    """Per-question cost, tokens, and cache behaviour. Returns {} if unpriceable."""
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    n = 0
    for r in rows:
        u = r.get("usage") or {}
        if not u:
            continue
        n += 1
        tot["input"] += u.get("input_tokens", 0) or 0
        tot["output"] += u.get("output_tokens", 0) or 0
        tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        tot["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
    if not n:
        return {}

    def price(key: str) -> float | None:
        if key not in PRICING:
            return None
        pin, pout = PRICING[key]
        return (
            tot["input"] * pin
            + tot["cache_write"] * pin * CACHE_WRITE_MULT
            + tot["cache_read"] * pin * CACHE_READ_MULT
            + tot["output"] * pout
        ) / 1_000_000 / n

    out = {
        "n_costed": n,
        "in_per_q": tot["input"] / n,
        "out_per_q": tot["output"] / n,
        "cache_read_per_q": tot["cache_read"] / n,
        "cache_write_per_q": tot["cache_write"] / n,
        "cost_per_q": price(model),
        "priced_as": model if model in PRICING else None,
    }
    # Sonnet's intro rate expires; show both so a re-run decision uses the right one.
    if model == "claude-sonnet-5":
        out["cost_per_q_intro"] = price("claude-sonnet-5@intro")
        out["intro_ends"] = SONNET_INTRO_ENDS
    return out


def collect() -> dict:
    arms, skipped = [], []
    for vpath in sorted(list(EVALS.glob("*verdicts*.json"))):
        try:
            data = json.loads(vpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            skipped.append(f"{vpath.name}: unreadable ({e})")
            continue
        if not isinstance(data, dict):
            # Some *verdicts*.json files are bare arrays of hand-graded rows with
            # no summary at all (e.g. answer_verdicts.json). Nothing to score.
            skipped.append(f"{vpath.name}: bare array, no summary")
            continue
        summary = data.get("summary") or {}
        entries = data.get("entries") or []
        if not summary.get("by_level_counts") or not entries:
            skipped.append(f"{vpath.name}: no summary.by_level_counts")
            continue

        stem = vpath.stem.replace("verdicts_", "").replace("h2h_", "h2h_")
        if vpath.stem.startswith("verdicts_"):
            stem = vpath.stem[len("verdicts_"):]

        ids = sorted(e["id"] for e in entries if "id" in e)
        qset = hashlib.sha256("|".join(ids).encode()).hexdigest()[:8]

        try:
            counts = ws.normalize_counts(summary["by_level_counts"])
            flat = ws.score(counts, ws.WEIGHT_SCHEMES["flat"]["weights"])
            weighted = ws.score(counts, ws.WEIGHT_SCHEMES["corner-half"]["weights"])
        except ws.ScoreError as e:
            skipped.append(f"{vpath.name}: {e}")
            continue

        apath, join = resolve_answers(stem, frozenset(ids))
        cfg, cost = {}, {}
        kind, kind_why = "unknown", ("no answers file could be joined to this verdict file, so "
                                     "nothing records how the arm ran")
        if apath is not None:
            raw = json.loads(apath.read_text(encoding="utf-8"))
            # Answers files come in two shapes: a list of rows, or a dict keyed
            # by question id. Normalize rather than assume, so a shape mismatch
            # can't silently drop an arm's cost.
            rows = raw if isinstance(raw, list) else list(raw.values())
            rows = [r for r in rows if isinstance(r, dict)]
            first = rows[0] if rows else {}
            cfg = {
                "model": first.get("model"),
                "effort": first.get("effort"),
                "rewrite_version": first.get("rewrite_version"),
                "ruling_query_mode": first.get("ruling_query_mode"),
                "system_version": first.get("system_version"),
                "n_answers": len(rows),
            }
            cost = cost_of(rows, first.get("model") or "")
            kind, kind_why = classify_arm(rows)

        arms.append({
            "arm": stem,
            "qset": qset,
            "kind": kind,
            "kind_why": kind_why,
            # Per-row verdicts, kept only long enough to measure rep-to-rep churn
            # and paired head-to-head records. Popped before the file is written --
            # working data, not a result.
            "_verdicts": {e["id"]: e.get("verdict") for e in entries if "id" in e},
            "_correct": {e["id"]: _row_correct(e) for e in entries if "id" in e},
            "n": summary.get("n_total") or len(entries),
            "accuracy_flat": flat,
            "accuracy_weighted": weighted,
            "accuracy_auto": summary.get("accuracy_auto"),
            "human_corrected": bool(summary.get("human_overturned")),
            "grader": summary.get("grader"),
            "by_level": {k: {"correct": c, "n": n_} for k, (c, n_) in counts.items()},
            "judge_model": summary.get("judge_model"),
            "judge_digest": summary.get("judge_prompt_sha256"),
            "config": cfg,
            "cost": cost,
            # THREE separate events, never collapsed into one "Run" column.
            "generation": {
                "file": apath.relative_to(REPO).as_posix() if apath else None,
                "mtime": _mtime(apath) if apath else None,
                "join": join,
                "recorded": apath is not None,
            },
            "judging": {
                "file": vpath.relative_to(REPO).as_posix(),
                "mtime": _mtime(vpath),
                "judge_model": summary.get("judge_model"),
                "judge_digest": summary.get("judge_prompt_sha256"),
                # An accuracy whose judging run names no judge cannot be reproduced.
                "recorded": bool(summary.get("judge_model")),
            },
            "human": ({
                "grader": summary.get("grader"),
                "grading_date": summary.get("grading_date"),
                "n_regraded": len(summary.get("human_regraded") or []),
                "n_overturned": len(summary.get("human_overturned") or []),
                "overturned": summary.get("human_overturned") or [],
                "source_auto": summary.get("source_auto"),
            } if summary.get("grader") or summary.get("human_overturned") else None),
            "provenance": {
                "verdicts": vpath.relative_to(REPO).as_posix(),
                "verdicts_mtime": _mtime(vpath),
                "answers": apath.relative_to(REPO).as_posix() if apath else None,
                "answers_mtime": _mtime(apath) if apath else None,
                "join": join,
            },
        })

    arms.sort(key=lambda a: (a["qset"], -(a["accuracy_flat"] or 0)))
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "arms": arms,
        "skipped": skipped,
        "pricing": {"per_mtok": PRICING, "cache_read_mult": CACHE_READ_MULT,
                    "cache_write_mult": CACHE_WRITE_MULT,
                    "sonnet_intro_ends": SONNET_INTRO_ENDS,
                    "source": "claude-api skill, checked 2026-07-26"},
        "current_config": {
            "GEN_MODEL": "claude-opus-5", "GEN_EFFORT": "low", "REWRITE_N": 3,
            "REWRITE_MODEL": "claude-haiku-4-5", "REWRITE_FUSION_DEPTH": 100,
            "TOP_K": 15, "TOP_N": 5, "COSINE_FLOOR": 0.38,
            "note": ("Current values read from source, NOT what each historical arm ran. "
                     "Per-run retrieval config is not recorded in the answers files."),
        },
        "weighting": {
            "scheme": "corner-half", "weights": ws.WEIGHT_SCHEMES["corner-half"]["weights"],
            "ruled_by": "Jon, 2026-07-26",
        },
    }


# ---------------------------------------------------------------------------
# TIMELINE: what changed at each step, by how much, and whether that is real.
#
# The table above is a snapshot -- where each arm landed. It cannot answer "what
# did that change buy us", because that needs a *baseline* and a *noise floor*,
# and getting either wrong manufactures a result. Three rules keep this honest:
#
# 1. Deltas never cross a question-set fingerprint. Arms ran on a 150, a 68, a
#    54, a 50, a 36 and a 15; a delta between two of those is arithmetic on
#    unrelated numbers.
# 2. Not every arm on a question set is a step on the same road. The
#    derivability arms handed the model its gold instead of retrieving -- an
#    oracle diagnostic, not a pipeline configuration. Chaining a delta from
#    "sonnet with retrieval" to "opus holding the answer key" would read as a
#    +21pp improvement that nobody shipped. Those arms are declared below and
#    render off-chain, labelled, with no delta.
# 3. The noise floor is measured, not assumed. Where the same configuration ran
#    twice (`_r1`/`_r2`), the spread between those reps IS the resolution of
#    this instrument for that question set -- so any step-delta smaller than it
#    is reported as not distinguishable from noise.
# ---------------------------------------------------------------------------

# Kind is DERIVED (see classify_arm). These add context a file cannot carry --
# they never decide the classification, and a step with no note still gets one
# from its evidence sentence.
STEP_NOTES = {
    "derivability_B": "The gold-only derivability probe. docs/results-derivability.md is the writeup.",
    "derivability_C": ("Re-run of the rows arm B got wrong. docs/results-derivability.md withdraws "
                       "its reading — the four 'passes' were the judge changing its mind."),
}

REP_SUFFIX = re.compile(r"_r\d+$")
HUMAN_SUFFIX = re.compile(r"_human$")

# ~1 verdict flip per 100 judged rows, measured in docs/results-easy-regression.md.
JUDGE_FLIPS_PER_ROW = 0.01


def step_key(arm: str) -> str:
    """Arm name minus its rep index and its regrade marker.

    `h2h_opuslow_hard_r1` and `_r2` are two runs of one configuration;
    `opus5_low_bucketA` and `_human` are two gradings of one run. Both collapse
    to a single step, and which of the two it is gets decided by the *answers
    file*, not the name -- reps have different answers files, regrades share one.
    """
    return HUMAN_SUFFIX.sub("", REP_SUFFIX.sub("", arm))


def _run_at(a: dict) -> tuple[str, str]:
    """When the arm ran, and where that came from.

    The answers file's mtime is the closest thing on disk to the run; the
    verdicts mtime is when it was *judged*, which for derivability_B is nearly
    twelve hours later. Arms with no joined answers file fall back to the
    verdict time, and say so.
    """
    p = a["provenance"]
    if p.get("answers_mtime"):
        return p["answers_mtime"], "answers file mtime"
    return p["verdicts_mtime"], "verdict file mtime (no answers file joined)"


def _churn(a: dict, b: dict) -> dict | None:
    """Rows whose verdict differs between two reps of the same configuration.

    This is a different quantity from the accuracy spread and both matter: rows
    can churn heavily while the totals barely move.
    """
    shared = set(a["_verdicts"]) & set(b["_verdicts"])
    if not shared:
        return None
    flipped = sorted(i for i in shared if a["_verdicts"][i] != b["_verdicts"][i])
    return {"n_rows": len(shared), "n_flipped": len(flipped), "ids": flipped[:12]}


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _pool_levels(per_rep: list[dict]) -> dict:
    """Sum correct/n per level across reps of one configuration.

    Reps are the SAME questions answered again, so the pooled denominator is
    rep-count x questions. That is the right base for a per-level *rate* (more
    observations of the same question sharpen the rate) but the wrong base for a
    sampling interval -- the interval is computed on the question count instead,
    and `n_questions` is kept beside `n` so a consumer cannot confuse them.
    """
    out: dict[str, dict] = {}
    for lv in per_rep:
        for level, c in (lv or {}).items():
            slot = out.setdefault(level, {"correct": 0.0, "n": 0.0, "n_questions": 0.0})
            slot["correct"] += c["correct"]
            slot["n"] += c["n"]
    for level, slot in out.items():
        slot["n_questions"] = slot["n"] / len(per_rep) if per_rep else 0.0
        slot["acc"] = slot["correct"] / slot["n"] if slot["n"] else None
    return out


def git_commits() -> list[dict]:
    """Every commit with an ISO author-independent commit time, newest first.

    Association only. Nothing links a commit to an eval run in the data; the
    timeline pairs them by timestamp window and labels that as an inference.
    """
    try:
        out = subprocess.run(["git", "log", "--pretty=%h%x1f%cI%x1f%s"],
                             cwd=REPO, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            rows.append({"sha": parts[0], "at": parts[1], "subject": parts[2]})
    return rows


CONFIG_FIELDS = [("model", "model"), ("effort", "effort"), ("rewrite_version", "rewrite"),
                 ("ruling_query_mode", "ruling mode"), ("system_version", "system ver")]


def build_timeline(arms: list[dict]) -> dict:
    commits = git_commits()

    # --- collapse arms into steps -------------------------------------------
    steps: dict[tuple[str, str], dict] = {}
    for a in arms:
        key = (a["qset"], step_key(a["arm"]))
        steps.setdefault(key, {"qset": a["qset"], "step": key[1], "arms": []})["arms"].append(a)

    built = []
    for (qset, name), s in steps.items():
        members = s["arms"]
        # Reps = distinct answers files. Regrades = several verdict files over one.
        by_answers: dict[str, list[dict]] = {}
        for a in members:
            by_answers.setdefault(a["provenance"]["answers"] or f"__none__{a['arm']}", []).append(a)

        reps = []
        for apath, group in by_answers.items():
            # Within one run, the human-corrected grading is the number of record.
            group.sort(key=lambda a: (not a["human_corrected"], a["arm"]))
            head = group[0]
            reps.append({
                "arm": head["arm"], "answers": head["provenance"]["answers"],
                "flat": head["accuracy_flat"], "weighted": head["accuracy_weighted"],
                "auto": head["accuracy_auto"],
                "run_at": _run_at(head)[0], "run_at_source": _run_at(head)[1],
                "human_corrected": head["human_corrected"],
                "regrade_of": [g["arm"] for g in group[1:]] or None,
                "regrade_pp": ((head["accuracy_flat"] - group[1]["accuracy_flat"]) * 100
                               if len(group) > 1 and head["accuracy_flat"] is not None
                               and group[1]["accuracy_flat"] is not None else None),
                "cost_per_q": (head["cost"] or {}).get("cost_per_q"),
                "in_per_q": (head["cost"] or {}).get("in_per_q"),
                "out_per_q": (head["cost"] or {}).get("out_per_q"),
                "join": head["provenance"]["join"],
                "_v": head,
            })
        reps.sort(key=lambda r: r["run_at"])

        cfgs = [r["_v"]["config"] for r in reps]
        base_cfg = cfgs[0] if cfgs else {}
        # A step is only one step if its reps really shared a configuration.
        heterogeneous = [f for f, _ in CONFIG_FIELDS
                         if len({(c or {}).get(f) for c in cfgs}) > 1]

        spread_pp = churn = None
        if len(reps) > 1:
            flats = [r["flat"] for r in reps if r["flat"] is not None]
            if len(flats) > 1:
                spread_pp = (max(flats) - min(flats)) * 100
            churn = _churn(reps[0]["_v"], reps[1]["_v"])

        # Kind comes from the arms' own recorded data. If the arms under one step
        # disagree, the step is not one experiment and must not be differenced.
        kinds = {a["kind"] for a in members}
        if len(kinds) == 1:
            kind, kind_why = kinds.pop(), members[0]["kind_why"]
        else:
            kind = "unknown"
            kind_why = ("arms under this step classify differently ("
                        + ", ".join(sorted(f"{a['arm']}={a['kind']}" for a in members))
                        + ") — not one experiment")
        built.append({
            "qset": qset, "step": name, "kind": kind, "kind_why": kind_why,
            "kind_note": STEP_NOTES.get(name),
            "n": members[0]["n"],
            "run_at": reps[0]["run_at"] if reps else None,
            "run_at_source": reps[0]["run_at_source"] if reps else None,
            "config": {f: (base_cfg or {}).get(f) for f, _ in CONFIG_FIELDS},
            # No answers file joined means no config was recorded at all. That is
            # not the same as "the config was empty", and rendering it as a set of
            # fields that changed to nothing would invent a change that never
            # happened. Every consumer must check this before reading `config`.
            "config_recorded": bool(base_cfg),
            "heterogeneous_fields": heterogeneous,
            "flat": _mean([r["flat"] for r in reps]),
            "weighted": _mean([r["weighted"] for r in reps]),
            "auto": _mean([r["auto"] for r in reps]),
            "cost_per_q": _mean([r["cost_per_q"] for r in reps]),
            "in_per_q": _mean([r["in_per_q"] for r in reps]),
            "out_per_q": _mean([r["out_per_q"] for r in reps]),
            "n_reps": len(reps), "rep_spread_pp": spread_pp, "rep_churn": churn,
            "reps": [{k: v for k, v in r.items() if k != "_v"} for r in reps],
            "judge_model": members[0]["judge_model"],
            "judge_digest": members[0]["judge_digest"],
            # --- provenance, all three layers, for every view -----------------
            "generation_runs": [{"file": r["_v"]["generation"]["file"],
                                 "mtime": r["_v"]["generation"]["mtime"],
                                 "join": r["_v"]["generation"]["join"],
                                 "arm": r["arm"]} for r in reps],
            "judging_runs": [{"file": a["judging"]["file"], "mtime": a["judging"]["mtime"],
                              "judge_model": a["judging"]["judge_model"],
                              "judge_digest": a["judging"]["judge_digest"],
                              "recorded": a["judging"]["recorded"], "arm": a["arm"]}
                             for a in sorted(members, key=lambda x: x["judging"]["mtime"])],
            "human_passes": [{"arm": a["arm"], **a["human"]} for a in members if a["human"]],
            # Pooled level counts across reps -- the level mix is what the weighting
            # ruling is about, and it is also what a corpus-mix projection needs.
            "by_level": _pool_levels([r["_v"]["by_level"] for r in reps]),
            "_arms": [r["_v"] for r in reps],
        })

    # --- per-question-set noise floor ---------------------------------------
    sets = {}
    for st in built:
        sets.setdefault(st["qset"], []).append(st)

    out_sets = []
    for qset, group in sets.items():
        group.sort(key=lambda s: (s["run_at"] or "", s["step"]))
        n = group[0]["n"]
        # Judge floor: ~1 flip per 100 rows, but accuracy cannot move by less
        # than one row, so on small sets the row is the binding constraint.
        judge_pp = max(JUDGE_FLIPS_PER_ROW * 100, 100.0 / n) if n else None
        observed = [s["rep_spread_pp"] for s in group if s["rep_spread_pp"] is not None]
        if observed:
            floor_pp, floor_src = max(observed), "widest observed spread between reps of one configuration"
        else:
            floor_pp, floor_src = judge_pp, ("judge nondeterminism only (~1 verdict flip per 100 rows, "
                                             "and one row on this set is %.1f pp) — no repeated arm here" % (100.0 / n))

        # --- chain deltas across pipeline steps only -------------------------
        prev = None
        for st in group:
            st["delta"] = None
            if st["kind"] != "pipeline":
                continue
            if prev is not None:
                both_recorded = st["config_recorded"] and prev["config_recorded"]
                changed = ([{"field": f, "label": lab, "from": prev["config"].get(f),
                             "to": st["config"].get(f)}
                            for f, lab in CONFIG_FIELDS
                            if prev["config"].get(f) != st["config"].get(f)]
                           if both_recorded else [])
                d_flat = ((st["flat"] - prev["flat"]) * 100
                          if st["flat"] is not None and prev["flat"] is not None else None)
                d_cost_pct = ((st["cost_per_q"] - prev["cost_per_q"]) / prev["cost_per_q"] * 100
                              if st["cost_per_q"] and prev["cost_per_q"] else None)
                d_out_pct = ((st["out_per_q"] - prev["out_per_q"]) / prev["out_per_q"] * 100
                             if st["out_per_q"] and prev["out_per_q"] else None)
                between = [c for c in commits
                           if prev["run_at"] and st["run_at"] and prev["run_at"] < c["at"] <= st["run_at"]]
                st["delta"] = {
                    "baseline": prev["step"], "baseline_run_at": prev["run_at"],
                    "baseline_flat": prev["flat"], "baseline_cost": prev["cost_per_q"],
                    "changed": changed,
                    "changed_known": both_recorded,
                    "flat_pp": d_flat,
                    "weighted_pp": ((st["weighted"] - prev["weighted"]) * 100
                                    if st["weighted"] is not None and prev["weighted"] is not None else None),
                    "cost_pct": d_cost_pct,
                    "cost_abs": (st["cost_per_q"] - prev["cost_per_q"]
                                 if st["cost_per_q"] and prev["cost_per_q"] else None),
                    "out_tok_pct": d_out_pct,
                    "floor_pp": floor_pp,
                    "beats_noise": (None if d_flat is None or floor_pp is None
                                    else abs(d_flat) >= floor_pp),
                    "commits": between[:14],
                    "commits_total": len(between),
                }
            prev = st

        out_sets.append({
            "qset": qset, "n": n, "n_steps": len(group),
            "floor_pp": floor_pp, "floor_source": floor_src, "judge_floor_pp": judge_pp,
            "steps": group,
        })

    out_sets.sort(key=lambda s: (-s["n_steps"], -s["n"]))
    return {
        "sets": out_sets,
        "commits_indexed": len(commits),
        "notes": {
            "baseline": "Each delta compares a step to the previous PIPELINE step on the same "
                        "question-set fingerprint, ordered by run time. Nothing is compared across "
                        "fingerprints.",
            "ordering": "Run time is the answers file's mtime where one is joined, else the verdict "
                        "file's. Neither is a recorded run timestamp — the answers files do not "
                        "carry one.",
            "commits": "Commits are associated by falling inside the window between the baseline run "
                       "and this run. That is an inference from timestamps, NOT a recorded link — no "
                       "arm records the commit it ran on.",
            "retrieval": "TOP_K / TOP_N / COSINE_FLOOR are not recorded per arm, so they never appear "
                         "as a step change. What is per-arm: model, effort, rewrite_version, "
                         "ruling_query_mode, system_version.",
            "oracle": "Oracle arms are shown on their set but never chained, because they were handed "
                      "gold instead of retrieving it.",
        },
    }


FULL_CORPUS = 1409  # RulesGuru questions imported (docs/report-rulesguru-full-import.md)
CORPUS_FILE = EVALS / "rulesguru_full_v2.jsonl"


# ---------------------------------------------------------------------------
# COMPARISONS: the side-by-side views a go/no-go call actually needs.
#
# Every one of them obeys the same two gates -- same question-set fingerprint AND
# same kind -- because either one alone lets a meaningless number render. A cost
# /accuracy frontier that plots an oracle arm beside pipeline arms is the same
# error as a cross-set delta, just in a different shape.
# ---------------------------------------------------------------------------

def corpus_level_mix() -> dict:
    """How the 1,409-question corpus is distributed across levels.

    This is the difference between a projection and a guess. The 150-question
    set is stratified 30-per-level; the corpus is not (it is 55% L0/L1). So a
    flat score on a stratified sample is NOT the expected score on the corpus,
    and reweighting per-level accuracy by the corpus mix is the only projection
    the data supports.
    """
    if not CORPUS_FILE.exists():
        return {}
    counts: dict[str, int] = {}
    total = 0
    with CORPUS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                level = str(json.loads(line).get("level"))
            except json.JSONDecodeError:
                continue
            counts[level] = counts.get(level, 0) + 1
            total += 1
    return {"file": CORPUS_FILE.relative_to(REPO).as_posix(), "mtime": _mtime(CORPUS_FILE),
            "total": total, "by_level": counts,
            "share": {k: v / total for k, v in counts.items()} if total else {}}


def wilson(p: float | None, n: float | None, z: float = 1.96) -> list[float] | None:
    """95% Wilson interval. Sampling error only -- judge noise is reported apart.

    Wilson rather than normal-approximation because these n are small and
    accuracies run near 1.0, where the normal interval runs past 100% and stops
    being a statement about anything.
    """
    if p is None or not n:
        return None
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _sig(cfg: dict) -> tuple:
    return tuple((cfg or {}).get(f) for f, _ in CONFIG_FIELDS)


def _judge_check(a: dict, b: dict) -> dict:
    """Whether two units' accuracies were produced by comparable judging.

    The judge is nondeterministic, so two arms scored in two judging runs carry
    judge noise in the gap between them even when everything else is identical.
    Two arms scored by DIFFERENT judge models or prompt digests are worse than
    noisy -- they are not the same measurement, and the page says so.
    """
    def keys(u):
        return {(j["judge_model"], j["judge_digest"]) for j in u["judging_runs"]}
    ka, kb = keys(a), keys(b)
    missing = [u["step"] for u in (a, b) if any(not j["recorded"] for j in u["judging_runs"])]
    if missing:
        return {"level": "crit",
                "text": ("no judging run is recorded for " + " and ".join(missing) +
                         " — its verdict file names no judge model or prompt digest, so its "
                         "accuracy is not reproducible and this gap cannot be attributed"),
                "same_judge": False}
    if ka != kb:
        return {"level": "crit",
                "text": ("judged by different judges — " +
                         f"{a['step']} by {'/'.join(str(x) for k in sorted(ka) for x in k)}, " +
                         f"{b['step']} by {'/'.join(str(x) for k in sorted(kb) for x in k)}. " +
                         "Different judges are different measurements, not a gap"),
                "same_judge": False}
    n_runs = len({j["file"] for j in a["judging_runs"]} | {j["file"] for j in b["judging_runs"]})
    return {"level": "warn", "same_judge": True, "n_judging_runs": n_runs,
            "text": (f"same judge and prompt digest, but scored in {n_runs} separate judging runs. "
                     "The judge is nondeterministic (~1 verdict flip per 100 rows), so part of "
                     "this gap is the judge, not the models")}


def _paired(a: dict, b: dict) -> dict | None:
    """Row-level win/loss on the questions both arms answered.

    A paired record survives question difficulty in a way two accuracies do not:
    5 wins against 1 loss on 50 shared rows is a different claim from +8 pp.
    Computed on ONE run of each -- the run of record, human grading first -- and
    that run is named, because a paired record built from a different rep would
    come out differently.
    """
    if not a["_arms"] or not b["_arms"]:
        return None
    ra, rb = a["_arms"][0], b["_arms"][0]
    shared = [i for i in ra["_correct"] if i in rb["_correct"]
              and ra["_correct"][i] is not None and rb["_correct"][i] is not None]
    if not shared:
        return None
    both = sum(1 for i in shared if ra["_correct"][i] and rb["_correct"][i])
    a_only = sum(1 for i in shared if ra["_correct"][i] and not rb["_correct"][i])
    b_only = sum(1 for i in shared if rb["_correct"][i] and not ra["_correct"][i])
    return {"n_shared": len(shared), "both": both, "a_only": a_only, "b_only": b_only,
            "neither": len(shared) - both - a_only - b_only,
            "a_run": ra["arm"], "b_run": rb["arm"],
            "a_judging": ra["judging"]["file"], "b_judging": rb["judging"]["file"]}


def build_comparisons(timeline: dict, corpus: dict) -> dict:
    sets = timeline["sets"]
    mix = corpus.get("share") or {}

    # --- head to head, per set, kind-matched --------------------------------
    h2h = []
    for s in sets:
        units = s["steps"]
        pairs = []
        for i, a in enumerate(units):
            for b in units[i + 1:]:
                if a["kind"] != b["kind"] or a["kind"] == "unknown":
                    continue
                if not a["config_recorded"] or not b["config_recorded"]:
                    continue
                differs = [{"field": f, "label": lab, "a": a["config"].get(f), "b": b["config"].get(f)}
                           for f, lab in CONFIG_FIELDS if a["config"].get(f) != b["config"].get(f)]
                d_flat = ((a["flat"] - b["flat"]) * 100
                          if a["flat"] is not None and b["flat"] is not None else None)
                pairs.append({
                    "a": a["step"], "b": b["step"], "kind": a["kind"], "n": a["n"],
                    "differs": differs,
                    "controlled": len(differs) == 1,
                    "a_flat": a["flat"], "b_flat": b["flat"], "flat_pp": d_flat,
                    "a_weighted": a["weighted"], "b_weighted": b["weighted"],
                    "weighted_pp": ((a["weighted"] - b["weighted"]) * 100
                                    if a["weighted"] is not None and b["weighted"] is not None else None),
                    "a_cost": a["cost_per_q"], "b_cost": b["cost_per_q"],
                    "cost_pct": ((a["cost_per_q"] - b["cost_per_q"]) / b["cost_per_q"] * 100
                                 if a["cost_per_q"] and b["cost_per_q"] else None),
                    "a_in": a["in_per_q"], "b_in": b["in_per_q"],
                    "a_out": a["out_per_q"], "b_out": b["out_per_q"],
                    "paired": _paired(a, b),
                    "judge": _judge_check(a, b),
                    "floor_pp": s["floor_pp"],
                    "beats_noise": (None if d_flat is None or s["floor_pp"] is None
                                    else abs(d_flat) >= s["floor_pp"]),
                })
        # Different kinds on one set are not a head-to-head, but the oracle-vs-rest
        # gap IS informative: it is roughly the headroom retrieval is leaving.
        oracles = [u for u in units if u["kind"] == "oracle" and u["flat"] is not None]
        others = [u for u in units if u["kind"] != "oracle" and u["flat"] is not None]
        headroom = None
        if oracles and others:
            o = max(oracles, key=lambda u: u["flat"])
            p = max(others, key=lambda u: u["flat"])
            headroom = {"oracle": o["step"], "oracle_flat": o["flat"], "oracle_kind_why": o["kind_why"],
                        "other": p["step"], "other_flat": p["flat"], "other_kind": p["kind"],
                        "other_kind_why": p["kind_why"],
                        "gap_pp": (o["flat"] - p["flat"]) * 100,
                        "judge": _judge_check(o, p)}
        if pairs or headroom:
            h2h.append({"qset": s["qset"], "n": s["n"], "floor_pp": s["floor_pp"],
                        "pairs": pairs, "headroom": headroom})

    # --- cost vs accuracy: who is dominated ---------------------------------
    frontier = []
    for s in sets:
        pts = []
        for u in s["steps"]:
            if u["cost_per_q"] is None or u["flat"] is None:
                continue
            pts.append({"step": u["step"], "kind": u["kind"], "flat": u["flat"],
                        "weighted": u["weighted"], "cost": u["cost_per_q"],
                        "model": u["config"].get("model"), "effort": u["config"].get("effort"),
                        "full_run": u["cost_per_q"] * FULL_CORPUS, "dominated_by": None})
        for p in pts:
            for q in pts:
                if q is p or q["kind"] != p["kind"]:
                    continue          # never rank an oracle against the product path
                if q["flat"] >= p["flat"] and q["cost"] <= p["cost"] and (
                        q["flat"] > p["flat"] or q["cost"] < p["cost"]):
                    p["dominated_by"] = q["step"]
                    break
        unpriced = [{"step": u["step"], "kind": u["kind"], "flat": u["flat"],
                     "why": u["reps"][0]["join"] if u["reps"] else "no run"}
                    for u in s["steps"] if u["cost_per_q"] is None]
        if pts or unpriced:
            frontier.append({"qset": s["qset"], "n": s["n"], "points": pts, "unpriced": unpriced})

    # --- per-level ----------------------------------------------------------
    levels = []
    for s in sets:
        order = ["0", "1", "2", "3", "Corner Case"]
        present = [lv for lv in order if any(lv in u["by_level"] for u in s["steps"])]
        present += sorted({lv for u in s["steps"] for lv in u["by_level"]} - set(order))
        rows = [{"step": u["step"], "kind": u["kind"], "flat": u["flat"],
                 "cells": {lv: u["by_level"].get(lv) for lv in present}} for u in s["steps"]]
        if present:
            levels.append({"qset": s["qset"], "n": s["n"], "order": present, "rows": rows,
                           "corpus_share": {lv: mix.get(lv) for lv in present}})

    # --- config matrix: what has been tried, what has not -------------------
    tried: dict[tuple, list] = {}
    for s in sets:
        for u in s["steps"]:
            if not u["config_recorded"]:
                continue
            tried.setdefault(_sig(u["config"]), []).append(
                {"qset": s["qset"], "n": s["n"], "step": u["step"], "kind": u["kind"],
                 "flat": u["flat"], "cost": u["cost_per_q"], "n_reps": u["n_reps"]})
    gen_axis = sorted({(k[0], k[1]) for k in tried}, key=lambda t: (str(t[0]), str(t[1])))
    ret_axis = sorted({(k[2], k[3], k[4]) for k in tried}, key=lambda t: tuple(str(x) for x in t))
    matrix = {
        "gen_axis": [{"model": m, "effort": e} for m, e in gen_axis],
        "ret_axis": [{"rewrite_version": r, "ruling_query_mode": q, "system_version": v}
                     for r, q, v in ret_axis],
        "cells": {f"{m}|{e}||{r}|{q}|{v}": tried.get((m, e, r, q, v), [])
                  for m, e in gen_axis for r, q, v in ret_axis},
        "n_tried": len(tried),
        "n_cells": len(gen_axis) * len(ret_axis),
        "note": ("Axes are the fields the answers files actually record. TOP_K / TOP_N / "
                 "COSINE_FLOOR are NOT recorded per arm, so retrieval tuning cannot appear here "
                 "as a tried or untried combination at all."),
    }

    # --- reproducibility: the measurement noise floor -----------------------
    repro = []
    for s in sets:
        for u in s["steps"]:
            if u["n_reps"] < 2:
                continue
            repro.append({"qset": s["qset"], "n": s["n"], "step": u["step"], "kind": u["kind"],
                          "n_reps": u["n_reps"],
                          "reps": [{"arm": r["arm"], "flat": r["flat"], "run_at": r["run_at"],
                                    "cost": r["cost_per_q"]} for r in u["reps"]],
                          "spread_pp": u["rep_spread_pp"], "churn": u["rep_churn"],
                          "judging_runs": u["judging_runs"]})
    single = [{"qset": s["qset"], "n": s["n"], "step": u["step"], "kind": u["kind"]}
              for s in sets for u in s["steps"] if u["n_reps"] < 2]
    repro.sort(key=lambda r: -(r["spread_pp"] or 0))

    # --- projection to the full corpus --------------------------------------
    by_sig: dict[tuple, dict] = {}
    for s in sets:
        for u in s["steps"]:
            if not u["config_recorded"] or u["kind"] == "unknown":
                continue
            slot = by_sig.setdefault(_sig(u["config"]), {
                "config": dict(u["config"]), "kind": u["kind"], "sets": [], "levels": {},
                "costs": [], "in": [], "out": [], "flats": [], "n_questions": 0,
            })
            slot["sets"].append({"qset": s["qset"], "n": s["n"], "step": u["step"],
                                 "flat": u["flat"], "cost": u["cost_per_q"],
                                 "n_reps": u["n_reps"], "spread_pp": u["rep_spread_pp"]})
            slot["n_questions"] += u["n"]
            for lv, c in u["by_level"].items():
                d = slot["levels"].setdefault(lv, {"correct": 0.0, "n": 0.0, "n_questions": 0.0})
                d["correct"] += c["correct"]
                d["n"] += c["n"]
                d["n_questions"] += c["n_questions"]
            if u["cost_per_q"] is not None:
                slot["costs"].append(u["cost_per_q"])
            if u["in_per_q"] is not None:
                slot["in"].append(u["in_per_q"])
            if u["out_per_q"] is not None:
                slot["out"].append(u["out_per_q"])
            if u["flat"] is not None:
                slot["flats"].append(u["flat"])

    projections = []
    for sig, slot in by_sig.items():
        lv = slot["levels"]
        covered = [k for k in lv if mix.get(k)]
        share = sum(mix[k] for k in covered)
        proj = (sum(mix[k] * (lv[k]["correct"] / lv[k]["n"]) for k in covered if lv[k]["n"]) / share
                if share else None)
        missing = sorted(k for k in mix if k not in lv)
        # Sampling interval on the DISTINCT questions, not on rep-inflated rows.
        nq = sum(lv[k]["n_questions"] for k in covered)
        ci = wilson(proj, nq)
        thin = sorted((k for k in covered if lv[k]["n_questions"] < 10),
                      key=lambda k: lv[k]["n_questions"])
        costs = slot["costs"]
        projections.append({
            "config": slot["config"], "kind": slot["kind"], "sets": slot["sets"],
            "n_questions": int(round(nq)),
            "levels": {k: {"acc": (lv[k]["correct"] / lv[k]["n"]) if lv[k]["n"] else None,
                           "n_questions": lv[k]["n_questions"], "share": mix.get(k)}
                       for k in sorted(lv)},
            "covered_share": share, "missing_levels": missing, "thin_levels": thin,
            "projected_acc": proj, "ci95": ci,
            "cost_lo": min(costs) if costs else None, "cost_hi": max(costs) if costs else None,
            "full_run_lo": min(costs) * FULL_CORPUS if costs else None,
            "full_run_hi": max(costs) * FULL_CORPUS if costs else None,
            "in_per_q": _mean(slot["in"]), "out_per_q": _mean(slot["out"]),
            "max_spread_pp": max([s["spread_pp"] for s in slot["sets"]
                                  if s["spread_pp"] is not None] or [None]),
        })
    projections.sort(key=lambda p: (p["kind"] != "pipeline", -(p["projected_acc"] or 0)))

    # --- what is unresolved, and what each would change ---------------------
    open_items = []
    no_judge = [j["arm"] for s in sets for u in s["steps"] for j in u["judging_runs"]
                if not j["recorded"]]
    if no_judge:
        open_items.append({
            "level": "crit", "what": f"{len(no_judge)} verdict files name no judging model",
            "which": sorted(no_judge),
            "changes": ("Their accuracies cannot be reproduced or attributed, so any comparison "
                        "involving them is blocked. Re-judging them under the recorded judge would "
                        "unblock those comparisons — including the whole 54-question head-to-head."),
        })
    bad_join = [{"step": u["step"], "qset": s["qset"], "join": r["join"]}
                for s in sets for u in s["steps"] for r in u["reps"]
                if r["join"] not in ("exact", "alias", "id-match")]
    if bad_join:
        open_items.append({
            "level": "warn", "what": f"{len(bad_join)} runs have no verified answers file",
            "which": [f"{b['step']} ({b['join']})" for b in bad_join],
            "changes": "No cost, tokens or config for those arms. They can be scored but not priced.",
        })
    unknowns = [u["step"] for s in sets for u in s["steps"] if u["kind"] == "unknown"]
    if unknowns:
        open_items.append({
            "level": "warn", "what": f"{len(unknowns)} configurations cannot be classified",
            "which": sorted(set(unknowns)),
            "changes": ("Nothing records whether retrieval ran, so they may not be differenced "
                        "against anything. Re-running them with the current writer (which records "
                        "`retrieved_rule_ids`) would put them back on the board."),
        })
    if single:
        open_items.append({
            "level": "warn", "what": f"{len(single)} configurations ran only once",
            "which": [f"{x['step']} ({x['n']}q)" for x in single],
            "changes": ("No within-config spread was measured for them, so their question set's "
                        "noise floor falls back to judge nondeterminism alone. A second rep costs "
                        "one run and turns an assumed floor into a measured one."),
        })
    gaps: dict[tuple, list] = {}
    for p in projections:
        if p["kind"] == "pipeline" and p["missing_levels"]:
            gaps.setdefault((tuple(p["missing_levels"]), round(p["covered_share"], 3)), []).append(
                f"{p['config'].get('model')}/{p['config'].get('effort')} "
                f"rewrite {p['config'].get('rewrite_version')}")
    for (missing, cover), who in gaps.items():
        open_items.append({
            "level": "warn",
            "what": f"no pipeline evidence at all on level {', '.join(missing)}",
            "which": who + [f"{round((1 - cover) * 100)}% of the corpus by level"],
            # Say "easiest", not "largest": L0 is 207 of 1,409 questions, while L1
            # is 565. Untested does not mean biggest, and overstating the gap
            # would argue for the run on a claim the corpus mix does not support.
            "changes": ("The projected accuracy covers only the levels tested. The untested levels "
                        "are the corpus's easiest, so the projection is more likely low than "
                        "high — but it is an extrapolation until they are run."),
        })
    thin_note = [p for p in projections if p["kind"] == "pipeline" and p["thin_levels"]]
    for p in thin_note[:1]:
        open_items.append({
            "level": "warn",
            "what": "some level estimates rest on very few questions",
            "which": [f"level {lv}: {int(p['levels'][lv]['n_questions'])} questions"
                      for lv in p["thin_levels"]],
            "changes": ("Each of those questions moves that level's accuracy by a large step, and "
                        "the level is weighted by its corpus share in the projection above."),
        })

    return {
        "head_to_head": h2h, "frontier": frontier, "levels": levels, "matrix": matrix,
        "repro": repro, "single_rep": single, "projections": projections,
        "open_items": open_items, "corpus": corpus, "kind_rule": KIND_RULE,
    }

# Colors are the dataviz reference palette, unchanged. Only a single accent plus
# the reserved status steps are used -- no categorical series -- so there is no
# multi-hue CVD adjacency to validate here.
HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rulemancer — metrics history</title>
<style>
:root{color-scheme:dark;
 --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
 --grid:#2c2c2a; --rule:#383835; --accent:#3987e5;
 --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b;
 /* Same three hues, lightness retuned so small badge/pill TEXT clears WCAG AA
    (4.5:1) against --surface in each theme. Measured, not eyeballed: on the dark
    surface #d03b3b is only 3.6:1, and on the light surface #fab219 is 1.8:1 and
    #0ca30c is 3.3:1. The fill colours above are unchanged. */
 --good-t:#0ca30c; --warn-t:#fab219; --crit-t:#e8615f;
 /* Same rule for the accent. --accent is a MARK colour (meters, rails, fills);
    --accent-t is the only one allowed to carry small text, because the light
    theme's #2a78d6 measures 4.30:1 as 21.6px/600-weight text, which WCAG counts
    as normal text (600 is not bold) and therefore fails 4.5:1. Measured in-page,
    not eyeballed. */
 --accent-t:#3987e5;
 --ring:rgba(255,255,255,.10);
 --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:40px;}
:root[data-theme=light]{color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#6e6c66;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
 --good-t:#0a7a0a; --warn-t:#8f6200; --crit-t:#b32d2d; --accent-t:#1a5fb4;}
@media(prefers-color-scheme:light){:root:not([data-theme=dark]){color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#6e6c66;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
 --good-t:#0a7a0a; --warn-t:#8f6200; --crit-t:#b32d2d; --accent-t:#1a5fb4;}}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;}
.wrap{max-width:1240px;margin:0 auto;padding:var(--s5) var(--s4) var(--s6)}
header{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;justify-content:space-between;
 margin-bottom:var(--s2)}
h1{font-size:1.5rem;margin:0;letter-spacing:-.01em}
h2{font-size:1.0rem;margin:var(--s5) 0 var(--s2);letter-spacing:.04em;text-transform:uppercase;
 color:var(--ink2)}
.sub{color:var(--ink2);margin:0 0 var(--s5);max-width:68ch}
.meta{color:var(--muted);font-size:.8rem}
button{font:inherit;color:var(--ink2);background:var(--surface);border:1px solid var(--ring);
 border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{color:var(--ink)}
button:focus-visible,th[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:var(--s4)}
.tiles{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(190px,100%),1fr));
 margin-bottom:var(--s5)}
.tile .k{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
.tile .v{font-size:1.9rem;line-height:1.15;margin:var(--s1) 0 2px;font-weight:600}
.tile .n{color:var(--ink2);font-size:.82rem}
.decision{border-left:3px solid var(--accent)}
.decision .v{color:var(--accent-t)}
.scroll{overflow-x:auto;border:1px solid var(--ring);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:right;padding:9px var(--s3);border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}
thead th{color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;
 letter-spacing:.05em;border-bottom:1px solid var(--rule);cursor:pointer;user-select:none}
thead th::after{content:"";opacity:.5}
thead th[aria-sort=ascending]::after{content:" \\2191";opacity:1}
thead th[aria-sort=descending]::after{content:" \\2193";opacity:1}
tbody tr:hover{background:color-mix(in oklab,var(--accent) 8%,transparent)}
tbody tr:last-child td{border-bottom:none}
.num{font-variant-numeric:tabular-nums}
.dim{color:var(--muted)}
.badge{display:inline-block;font-size:.68rem;padding:1px 7px;border-radius:999px;
 border:1px solid var(--ring);color:var(--ink2);vertical-align:1px}
.b-good{color:var(--good-t);border-color:color-mix(in oklab,var(--good-t) 45%,transparent)}
.b-warn{color:var(--warn-t);border-color:color-mix(in oklab,var(--warn-t) 45%,transparent)}
.b-crit{color:var(--crit-t);border-color:color-mix(in oklab,var(--crit-t) 45%,transparent)}
.grp{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;margin:var(--s5) 0 var(--s2)}
.grp h3{font-size:.95rem;margin:0}
.note{color:var(--ink2);font-size:.85rem;max-width:74ch}
.empty{padding:var(--s6);text-align:center;color:var(--muted)}

/* --- timeline ------------------------------------------------------------ */
.controls{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:center;
 margin:var(--s2) 0 var(--s4)}
.controls .lbl{color:var(--muted);font-size:.72rem;text-transform:uppercase;
 letter-spacing:.06em;margin-right:var(--s1)}
.chip{font:inherit;font-size:.82rem;padding:5px 11px;border-radius:999px;
 border:1px solid var(--ring);background:var(--surface);color:var(--ink2);cursor:pointer}
.chip:hover{color:var(--ink);border-color:var(--rule)}
.chip[aria-pressed=true]{background:color-mix(in oklab,var(--accent) 20%,var(--surface));
 border-color:var(--accent);color:var(--ink)}
.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rail{position:relative;padding-left:28px;margin-bottom:var(--s5)}
.rail::before{content:"";position:absolute;left:5px;top:10px;bottom:10px;width:2px;
 background:var(--grid)}
.step{position:relative;margin-bottom:var(--s3)}
.step::before{content:"";position:absolute;left:-28px;top:20px;width:12px;height:12px;
 border-radius:50%;background:var(--accent);border:3px solid var(--plane)}
.step.is-oracle::before{background:var(--muted)}
.step .card{display:grid;gap:var(--s3);grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}
.step .card:focus-within{border-color:var(--accent)}
.stephead{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:baseline}
.stephead h4{margin:0;font-size:1rem;letter-spacing:-.01em}
.when{color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums}
.cfg{display:flex;flex-wrap:wrap;gap:var(--s1);margin-top:var(--s2)}
.cfg span{font-size:.72rem;padding:2px 8px;border-radius:6px;border:1px solid var(--grid);
 color:var(--ink2);background:var(--plane)}
.cfg span.chg{border-color:var(--accent);color:var(--ink);
 background:color-mix(in oklab,var(--accent) 14%,var(--plane))}
.cfg span.chg b{font-weight:600}
.cfg span .was{color:var(--muted);text-decoration:line-through;margin-right:4px}
.score{display:flex;align-items:baseline;gap:var(--s2);flex-wrap:wrap}
.score .big{font-size:2rem;font-weight:600;line-height:1.05;font-variant-numeric:tabular-nums}
.meter{height:6px;border-radius:3px;background:var(--grid);margin:var(--s2) 0 var(--s3);
 overflow:hidden}
.meter i{display:block;height:100%;background:var(--accent);border-radius:3px}
.pills{display:flex;flex-wrap:wrap;gap:var(--s1)}
.pill{font-size:.76rem;padding:2px 9px;border-radius:999px;border:1px solid var(--ring);
 color:var(--ink2);font-variant-numeric:tabular-nums;white-space:nowrap}
.pill b{font-weight:600}
.p-good{color:var(--good-t);border-color:color-mix(in oklab,var(--good-t) 45%,transparent)}
.p-bad{color:var(--crit-t);border-color:color-mix(in oklab,var(--crit-t) 45%,transparent)}
.base{color:var(--ink2);font-size:.8rem;margin-top:var(--s3)}
.base code{color:var(--ink)}
.reps{color:var(--muted);font-size:.78rem;margin-top:var(--s2);font-variant-numeric:tabular-nums}
details.commits{margin-top:var(--s3)}
details.commits summary{cursor:pointer;color:var(--ink2);font-size:.8rem;
 list-style:revert;padding:2px 0}
details.commits summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
details.commits ol{margin:var(--s2) 0 0;padding-left:1.3rem;color:var(--ink2);font-size:.78rem;
 max-height:200px;overflow-y:auto}
details.commits code{color:var(--muted)}
.floornote{color:var(--muted);font-size:.78rem;margin:0 0 var(--s3);max-width:76ch}
.setline{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;margin:var(--s5) 0 var(--s1)}
.setline h3{margin:0;font-size:.95rem}
@media(max-width:760px){.step .card{grid-template-columns:1fr}}

/* --- shared: kind + provenance ------------------------------------------- */
.nav{display:flex;flex-wrap:wrap;gap:var(--s1);margin:0 0 var(--s5)}
.nav a{font-size:.78rem;padding:4px 10px;border-radius:999px;border:1px solid var(--ring);
 color:var(--ink2);text-decoration:none;background:var(--surface)}
.nav a:hover{color:var(--ink);border-color:var(--rule)}
.nav a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.b-pipe{color:var(--ink2);border-color:var(--rule)}
.prov{display:grid;gap:2px;margin-top:var(--s2);font-size:.75rem;color:var(--ink2)}
.prov div{display:flex;gap:var(--s2);align-items:baseline;flex-wrap:wrap}
.prov .lab{color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-size:.66rem;
 min-width:8.5em;flex:0 0 auto}
.prov code{font-size:.72rem;color:var(--ink2);word-break:break-all}
.prov .t{font-variant-numeric:tabular-nums;color:var(--ink)}
.prov .miss{color:var(--crit-t)}
.warnline{display:flex;gap:var(--s2);align-items:flex-start;font-size:.8rem;color:var(--ink2);
 margin-top:var(--s2);padding:var(--s2) var(--s3);border-radius:8px;border:1px solid var(--ring);
 background:var(--plane)}
.warnline.crit{border-color:color-mix(in oklab,var(--crit-t) 45%,transparent)}
.warnline.warn{border-color:color-mix(in oklab,var(--warn-t) 45%,transparent)}
.warnline b{flex:0 0 auto}
.warnline.crit b{color:var(--crit-t)}
.warnline.warn b{color:var(--warn-t)}
.sec{margin-top:var(--s6)}
.lede{color:var(--ink2);font-size:.88rem;max-width:76ch;margin:0 0 var(--s3)}

/* --- decision panel ------------------------------------------------------- */
.dec{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr))}
.dec .card h4{margin:0 0 var(--s2);font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;
 color:var(--muted)}
.dec .big{font-size:1.7rem;font-weight:600;line-height:1.1;font-variant-numeric:tabular-nums;
 display:block;margin-bottom:var(--s1)}
.dec .card p{margin:var(--s2) 0 0;font-size:.82rem;color:var(--ink2)}
.band{height:8px;border-radius:4px;background:var(--grid);position:relative;margin:var(--s2) 0}
.band i{position:absolute;top:0;bottom:0;background:color-mix(in oklab,var(--accent) 45%,transparent);
 border-radius:4px}
.band u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);text-decoration:none}
.scale{display:flex;justify-content:space-between;color:var(--muted);font-size:.7rem;
 font-variant-numeric:tabular-nums}

/* --- head to head --------------------------------------------------------- */
.h2h{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(340px,100%),1fr));
 margin-bottom:var(--s4)}
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:var(--s2);align-items:center;
 margin:var(--s3) 0}
.vs .side{min-width:0}
.vs .side .nm{font-size:.82rem;color:var(--ink2);overflow-wrap:anywhere}
.vs .side .sc{font-size:1.35rem;font-weight:600;font-variant-numeric:tabular-nums}
.vs .side.win .sc{color:var(--accent-t)}
.vs .mid{color:var(--muted);font-size:.74rem;text-align:center}
.vs .side:last-child{text-align:right}
.rec{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--grid);
 margin:var(--s2) 0 var(--s1)}
.rec span{display:block;height:100%}
.reclegend{display:flex;flex-wrap:wrap;gap:var(--s3);font-size:.72rem;color:var(--ink2);
 font-variant-numeric:tabular-nums}
.reclegend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;
 vertical-align:-1px}

/* --- matrix / level cells -------------------------------------------------- */
.cellbar{display:block;height:4px;border-radius:2px;background:var(--accent);margin-top:3px;
 min-width:2px}
td.lv{min-width:96px}
td.tried{background:color-mix(in oklab,var(--accent) 12%,transparent)}
td.tried .dim{color:var(--ink2)}
td.gap{color:var(--muted)}
.dominated td{opacity:.62}
.dominated td:first-child{opacity:1}
footer{margin-top:var(--s6);padding-top:var(--s4);border-top:1px solid var(--grid);
 color:var(--muted);font-size:.8rem;max-width:80ch}
footer code{color:var(--ink2)}
ul{margin:var(--s2) 0;padding-left:1.1rem}li{margin:3px 0}
@media(max-width:640px){.wrap{padding:var(--s4) var(--s3)}h1{font-size:1.25rem}.tile .v{font-size:1.5rem}}
</style></head><body><div class="wrap">
<header>
 <div><h1>Rulemancer — metrics history</h1>
 <p class="meta">Generated __GENERATED__ · every number read from its file at build time</p></div>
 <button id="themeBtn" type="button" aria-label="Toggle colour theme">Theme</button>
</header>
<p class="sub">Every judged arm we own, side by side, grouped by the question set it
actually ran on. Arms in different groups are <strong>not</strong> comparable — different
questions. The question this exists to answer: is it time for the full RulesGuru run?</p>
<div id="app"></div>
<footer id="foot"></footer>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const pct = v => v==null ? '—' : (v*100).toFixed(1)+'%';
const usd = v => v==null ? '—' : '$'+v.toFixed(5);
const int = v => v==null ? '—' : Math.round(v).toLocaleString();
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const JOIN = {
  'exact':['b-good','verified'], 'alias':['b-good','verified'], 'id-match':['b-good','verified by ids'],
  'prefix':['b-warn','name-matched'], 'unmatched':['b-crit','no answers file'],
  'name-matched-ids-differ':['b-crit','name matched, ids differ']
};
const joinBadge = j => {
  const hit = JOIN[j] || (j.startsWith('ambiguous') ? ['b-crit', j] : ['b-warn', j]);
  return `<span class="badge ${hit[0]}" title="${esc(j)}">${esc(hit[1])}</span>`;
};

const C = D.comparisons || {};
const pp = v => (v>=0?'+':'−') + Math.abs(v).toFixed(1) + ' pp';
const pctd = v => (v>=0?'+':'−') + Math.abs(v).toFixed(0) + '%';
const arrow = v => v>0 ? '▲' : (v<0 ? '▼' : '▬');
const day = s => (s||'').slice(0,10);
const stamp = s => (s||'').slice(0,16).replace('T',' ');
const money = v => v==null ? '—' : '$'+v.toFixed(0);

/* KIND. Second comparability gate, alongside the question-set fingerprint.
   An oracle arm answered with retrieval switched off, so it is not on the same
   scale as the product path and is never differenced against it. */
const KIND = {
  pipeline:['b-pipe','pipeline', 'the product path: retrieval ran'],
  oracle:  ['b-warn','oracle — not a pipeline score', 'retrieval off, rules handed in'],
  unknown: ['b-crit','unclassified', 'nothing records how this ran']
};
const kindBadge = (k, why) => {
  const h = KIND[k] || KIND.unknown;
  return `<span class="badge ${h[0]}" title="${esc(why||h[2])}">${esc(h[1])}</span>`;
};

/* PROVENANCE. Three separate events, never one "Run" column: the generation run
   made the answers, the judging run scored them, a human pass may have regraded
   them. The judge is nondeterministic, so an accuracy that does not name its
   judging run is not reproducible. */
function provBlock(gens, judges, humans){
  const g = (gens||[]).filter(x=>x.file).map(x =>
    `<code>${esc(x.file)}</code> <span class="t">${esc(stamp(x.mtime))}</span>`).join('<br>')
    || `<span class="miss">no answers file joined — config and cost unknown</span>`;
  const j = (judges||[]).map(x => x.recorded
    ? `<code>${esc(x.file)}</code> <span class="t">${esc(stamp(x.mtime))}</span><br>
       <span class="dim">${esc(x.judge_model)} · prompt sha256 ${esc(x.judge_digest||'not recorded')}</span>`
    : `<code>${esc(x.file)}</code> <span class="t">${esc(stamp(x.mtime))}</span><br>
       <span class="miss">no judge model or prompt digest recorded — not reproducible</span>`
  ).join('<br>') || `<span class="miss">none</span>`;
  const h = (humans||[]).map(x =>
    `<span class="t">${esc(x.grading_date||'date not recorded')}</span> · ${esc(x.grader||'grader not named')}
     · ${x.n_overturned} of ${x.n_regraded} regraded rows overturned`).join('<br>');
  return `<div class="prov">
    <div><span class="lab">Generation run</span><span>${g}</span></div>
    <div><span class="lab">Judging run</span><span>${j}</span></div>
    ${h ? `<div><span class="lab">Human grading</span><span>${h}</span></div>` : ''}
  </div>`;
}

const warnline = w => w ? `<p class="warnline ${esc(w.level)}"><b>${w.level==='crit'?'✕ Blocked':'⚠ Caution'}</b>
  <span>${esc(w.text)}.</span></p>` : '';

/* The decision number. It must be the SAME basis as the decision panel below --
   two different cost ranges on one page, both labelled "the full run", is exactly
   the sort of thing this page exists to stop. Both read HEAD. */
const N = D.full_corpus;
const PROJ = (D.comparisons||{}).projections || [];
const PIPE = PROJ.filter(p => p.kind==='pipeline' && p.projected_acc!=null);
const shipped = PIPE.filter(p => p.config.model===D.current_config.GEN_MODEL
                              && p.config.effort===D.current_config.GEN_EFFORT)
                    .sort((a,b)=>b.n_questions-a.n_questions);
const HEAD = shipped[0] || PIPE[0] || null;
const lo = HEAD ? HEAD.cost_lo : null, hi = HEAD ? HEAD.cost_hi : null;

const tiles = [
  {k:'Full RulesGuru run', v: lo==null?'—':('$'+(lo*N).toFixed(0)+'–'+(hi*N).toFixed(0)),
   n: HEAD ? `${N.toLocaleString()} questions at the measured cost/question of `
             + `${HEAD.config.model} / ${HEAD.config.effort||'default'} `
             + `(${HEAD.sets.length} question set${HEAD.sets.length>1?'s':''}, ${HEAD.n_questions} questions run)`
           : 'no pipeline arm carries both a cost and per-level counts',
   cls:'decision'},
  {k:'Expected accuracy', v: HEAD ? pct(HEAD.projected_acc) : '—',
   n: HEAD ? `corpus-mix reweighted · 95% interval ${pct(HEAD.ci95[0])}–${pct(HEAD.ci95[1])} `
             + `· covers ${(HEAD.covered_share*100).toFixed(0)}% of the corpus by level`
           : 'nothing projectable'},
  {k:'Arms tracked', v: String(D.arms.length),
   n:`${new Set(D.arms.map(a=>a.qset)).size} distinct question sets · `
     + `${D.arms.filter(a=>a.kind==='pipeline').length} pipeline, `
     + `${D.arms.filter(a=>a.kind==='oracle').length} oracle, `
     + `${D.arms.filter(a=>a.kind==='unknown').length} unclassified`},
  {k:'Weighting', v:'Corner ×0.5', n:`flat across L0–L3 · ruled by ${esc(D.weighting.ruled_by)}`},
];

const groups = {};
D.arms.forEach(a => (groups[a.qset] ||= []).push(a));
const order = Object.entries(groups).sort((a,b)=>b[1].length-a[1].length || b[1][0].n-a[1][0].n);

const COLS = [
  ['Arm', a=>`${esc(a.arm)} ${a.human_corrected?'<span class="badge b-good">human-corrected</span>':''}`, a=>a.arm],
  ['Kind', a=>kindBadge(a.kind, a.kind_why), a=>a.kind],
  ['Model', a=>`<span class="dim">${esc((a.config||{}).model||'—')}${(a.config||{}).effort?' / '+esc(a.config.effort):''}</span>`, a=>(a.config||{}).model||''],
  ['Flat', a=>`<span class="num">${pct(a.accuracy_flat)}</span>`, a=>a.accuracy_flat],
  ['Weighted', a=>`<span class="num">${pct(a.accuracy_weighted)}</span>`, a=>a.accuracy_weighted],
  ['Auto', a=>`<span class="num dim">${pct(a.accuracy_auto)}</span>`, a=>a.accuracy_auto??-1],
  ['$/question', a=>`<span class="num">${usd((a.cost||{}).cost_per_q)}</span>`, a=>(a.cost||{}).cost_per_q??-1],
  ['In tok', a=>`<span class="num dim">${int((a.cost||{}).in_per_q)}</span>`, a=>(a.cost||{}).in_per_q??-1],
  ['Out tok', a=>`<span class="num dim">${int((a.cost||{}).out_per_q)}</span>`, a=>(a.cost||{}).out_per_q??-1],
  // GENERATION RUN and JUDGING RUN are separate events and get separate columns.
  // The judge prompt digest is a published-number requirement, not a tooltip.
  ['Generation run', a=>a.generation.file
      ? `<span class="dim num">${esc(stamp(a.generation.mtime))}</span><br>
         <span class="dim" style="font-size:.72rem">${esc(a.generation.file.split('/').pop())}</span>
         ${joinBadge(a.generation.join)}`
      : `<span class="badge b-crit">no answers file</span>`, a=>a.generation.mtime||''],
  ['Judging run', a=>a.judging.recorded
      ? `<span class="dim num">${esc(stamp(a.judging.mtime))}</span><br>
         <span class="dim" style="font-size:.72rem">${esc(a.judging.judge_model)} · sha ${esc(a.judging.judge_digest||'none')}</span>`
      : `<span class="dim num">${esc(stamp(a.judging.mtime))}</span><br>
         <span class="badge b-crit">judge not recorded</span>`, a=>a.judging.mtime||''],
  ['Human grading', a=>a.human
      ? `<span class="badge b-good">graded</span><br><span class="dim num" style="font-size:.72rem">${esc(a.human.grading_date||'')} ${esc(a.human.grader||'')}</span><br>
         <span class="dim" style="font-size:.72rem">${a.human.n_overturned}/${a.human.n_regraded} overturned</span>`
      : `<span class="dim">—</span>`, a=>a.human?1:0],
];

function table(rows, key){
  const head = COLS.map((c,i)=>`<th tabindex="0" role="columnheader" data-c="${i}" data-k="${key}">${c[0]}</th>`).join('');
  const body = rows.map(a=>`<tr>${COLS.map(c=>`<td>${c[1](a)}</td>`).join('')}</tr>`).join('');
  return `<div class="scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/* ======================= THE DECISION =======================================
   Is it time for the full RulesGuru run? Four things decide it: what it costs,
   what accuracy to expect, how much of any difference is measurement error, and
   what is still unresolved. Everything here regenerates from the files. */
const floors = (D.timeline.sets||[]).map(s=>s.floor_pp).filter(v=>v!=null);
const worstFloor = floors.length ? Math.max(...floors) : null;

function decisionHTML(){
  if(!HEAD) return `<section class="sec" id="decision"><h2>The decision</h2>
    <div class="card empty"><strong>No pipeline configuration can be projected.</strong><br>
    A projection needs an arm classified <code>pipeline</code> with both a measured cost and
    per-level counts. None qualified.</div></section>`;

  const cfg = HEAD.config;
  const lo = HEAD.ci95 ? HEAD.ci95[0]*100 : null, hi = HEAD.ci95 ? HEAD.ci95[1]*100 : null;
  const mid = HEAD.projected_acc*100;
  const gap = HEAD.missing_levels.length;

  // Sensitivity: every priced configuration, cheapest full run first.
  const priced = PROJ.filter(p=>p.full_run_lo!=null)
                     .sort((a,b)=>a.full_run_lo-b.full_run_lo);
  const rows = priced.map(p=>{
    const c=p.config, isHead = p===HEAD;
    return `<tr${isHead?' style="outline:1px solid var(--accent);outline-offset:-1px"':''}>
      <td>${esc(c.model||'—')} <span class="dim">/ ${esc(c.effort||'default effort')}</span>
        ${kindBadge(p.kind, p.kind_why)}${isHead?' <span class="badge b-good">shipped config</span>':''}</td>
      <td class="dim">rewrite ${esc(String(c.rewrite_version))} · ${esc(String(c.ruling_query_mode))}</td>
      <td class="num">${usd(p.cost_lo)}${p.cost_hi!==p.cost_lo?'–'+usd(p.cost_hi):''}</td>
      <td class="num"><strong>${money(p.full_run_lo)}${p.full_run_hi!==p.full_run_lo?'–'+money(p.full_run_hi):''}</strong></td>
      <td class="num">${pct(p.projected_acc)}</td>
      <td class="num dim">${p.ci95?pct(p.ci95[0])+'–'+pct(p.ci95[1]):'—'}</td>
      <td class="num dim">${(p.covered_share*100).toFixed(0)}%</td>
      <td class="num dim">${p.n_questions}</td>
      <td class="num dim">${int(p.in_per_q)} / ${int(p.out_per_q)}</td>
    </tr>`;
  }).join('');

  const items = (C.open_items||[]);
  const openHTML = items.length ? items.map(o=>`
    <p class="warnline ${esc(o.level)}"><b>${o.level==='crit'?'✕':'⚠'}</b><span>
      <strong>${esc(o.what)}.</strong> ${esc((o.which||[]).join(', '))}<br>
      <span class="dim">${esc(o.changes)}</span></span></p>`).join('')
    : `<p class="note">Nothing is outstanding. Every arm carries a joined answers file, a named
       judging run, a classification and at least two reps.</p>`;

  return `<section class="sec" id="decision">
   <h2>The decision — is it time for the full run?</h2>
   <p class="lede">Everything below is measured, not asserted. The full corpus is
   <strong>${D.full_corpus.toLocaleString()} questions</strong>; the shipped configuration has been
   run on <strong>${HEAD.n_questions}</strong> of them.</p>
   <div class="dec">
     <div class="card decision">
       <h4>What a full run costs</h4>
       <span class="big">${money(HEAD.full_run_lo)}${HEAD.full_run_hi!==HEAD.full_run_lo?'–'+money(HEAD.full_run_hi):''}</span>
       <div class="n dim">${esc(cfg.model)} / ${esc(cfg.effort||'default')} at
         ${usd(HEAD.cost_lo)}–${usd(HEAD.cost_hi)} per question</div>
       <p>Measured from recorded token usage, not estimated. The range is the spread between the
       question sets this config ran on — harder questions cost more. Config choice moves this a
       long way: see the sensitivity table below.</p>
     </div>
     <div class="card">
       <h4>Accuracy to expect</h4>
       <span class="big">${pct(HEAD.projected_acc)}</span>
       <div class="band" role="img" aria-label="95 percent interval ${lo.toFixed(1)} to ${hi.toFixed(1)} percent">
         <i style="left:${lo}%;width:${Math.max(hi-lo,0.6)}%"></i><u style="left:${mid}%"></u></div>
       <div class="scale"><span>0%</span><span>95% interval ${lo.toFixed(1)}–${hi.toFixed(1)}%</span><span>100%</span></div>
       <p>Per-level accuracy reweighted to the corpus's own level mix
       (${Object.entries(C.corpus.by_level||{}).sort().map(([k,v])=>(k==='Corner Case'?'Corner':'L'+k)+' '+v).join(', ')}).
       A flat score off a stratified sample is not this number — the 150-set is 30 per level, the
       corpus is not.
       ${gap ? `<strong>Covers ${(HEAD.covered_share*100).toFixed(0)}% of the corpus by level</strong>
       — level ${esc(HEAD.missing_levels.join(', '))} is untested, and it is the corpus's easiest
       and largest slice, so this is more likely low than high.` : 'Covers every level in the corpus.'}</p>
     </div>
     <div class="card">
       <h4>Measurement error vs real difference</h4>
       <span class="big">±${worstFloor==null?'—':worstFloor.toFixed(1)} pp</span>
       <div class="n dim">widest noise floor across the question sets</div>
       <p>Where one configuration was run twice, the spread between those two runs IS the
       resolution of this instrument. Any gap smaller than a set's floor is not a result. The judge
       is nondeterministic on top of that — roughly one verdict flip per hundred rows — so two arms
       scored in two judging runs differ a little before either model does anything.</p>
     </div>
   </div>
   <h3 style="font-size:.95rem;margin:var(--s5) 0 var(--s2)">Cost sensitivity to config choice</h3>
   <p class="note">Same corpus, different configuration. Full-run cost is the measured cost per
   question times ${D.full_corpus.toLocaleString()}. Oracle rows are shown because their cost is
   real, but their accuracy is a ceiling, not a product score.</p>
   <div class="scroll"><table aria-label="Projected full-run cost and accuracy by configuration">
     <thead><tr><th>Configuration</th><th>Retrieval config</th><th>$/question</th>
       <th>Full run (${D.full_corpus.toLocaleString()} q)</th><th>Corpus-mix accuracy</th>
       <th>95% interval</th><th>Corpus covered</th><th>Questions run</th><th>In / out tokens</th></tr></thead>
     <tbody>${rows}</tbody></table></div>
   <h3 style="font-size:.95rem;margin:var(--s5) 0 var(--s2)">What is unresolved, and what it would change</h3>
   ${openHTML}
  </section>`;
}

/* ======================= HEAD TO HEAD ======================================= */
function h2hHTML(){
  const sets = (C.head_to_head||[]);
  if(!sets.length) return `<section class="sec" id="h2h"><h2>Head to head</h2>
    <div class="card empty"><strong>No two arms are comparable.</strong><br>
    A pair needs the same question-set fingerprint <em>and</em> the same kind.</div></section>`;

  let h = `<section class="sec" id="h2h"><h2>Head to head — same questions, same kind</h2>
    <p class="lede">Two arms may only be subtracted when they ran the <strong>same questions</strong>
    and measure the <strong>same thing</strong>. Sharing a question set is not enough: an arm handed
    its gold rules with retrieval switched off is not on the same scale as the product path.
    <br><span class="dim">${esc(C.kind_rule||'')}</span></p>`;

  sets.forEach(s=>{
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code> · noise floor ±${s.floor_pp.toFixed(1)} pp</span></div>`;
    if(s.pairs.length){
      h += `<div class="h2h">` + s.pairs.map(p=>{
        const aWin = p.flat_pp!=null && p.flat_pp>0, bWin = p.flat_pp!=null && p.flat_pp<0;
        const r = p.paired;
        const bar = r ? (()=>{
          const w = x => (x/r.n_shared*100).toFixed(1)+'%';
          return `<div class="rec" role="img" aria-label="paired record on ${r.n_shared} shared rows">
            <span style="width:${w(r.both)};background:var(--grid)"></span>
            <span style="width:${w(r.a_only)};background:var(--accent)"></span>
            <span style="width:${w(r.b_only)};background:var(--serious)"></span>
            <span style="width:${w(r.neither)};background:var(--crit)"></span></div>
          <div class="reclegend">
            <span><i style="background:var(--grid)"></i>both right ${r.both}</span>
            <span><i style="background:var(--accent)"></i>${esc(p.a)} only ${r.a_only}</span>
            <span><i style="background:var(--serious)"></i>${esc(p.b)} only ${r.b_only}</span>
            <span><i style="background:var(--crit)"></i>both wrong ${r.neither}</span></div>
          <p class="reps">Paired on the ${r.n_shared} rows both answered, from one run of each:
            <code>${esc(r.a_run)}</code> and <code>${esc(r.b_run)}</code>. A different rep would give
            a different record.</p>`;
        })() : `<p class="reps">No paired record — the two runs share no scorable rows.</p>`;

        const verdict = p.beats_noise===null ? '<span class="badge">no accuracy delta</span>'
          : p.beats_noise ? `<span class="badge b-good">clear of the ±${p.floor_pp.toFixed(1)} pp floor</span>`
                          : `<span class="badge b-warn">inside the ±${p.floor_pp.toFixed(1)} pp floor — not a result</span>`;

        return `<article class="card">
          <div class="stephead"><h4>${esc(p.a)} vs ${esc(p.b)}</h4>${kindBadge(p.kind)}
            ${p.controlled?'<span class="badge b-good">one field differs</span>'
                          :`<span class="badge b-warn">${p.differs.length} fields differ</span>`}</div>
          <p class="reps">Differs in: ${p.differs.length
            ? p.differs.map(d=>`<code>${esc(d.label)}</code> ${esc(String(d.a))} vs ${esc(String(d.b))}`).join(', ')
            : 'no recorded config field — same config, different runs'}</p>
          <div class="vs">
            <div class="side ${aWin?'win':''}"><div class="nm">${esc(p.a)}</div>
              <div class="sc">${pct(p.a_flat)}</div>
              <div class="nm num">${usd(p.a_cost)} / question</div></div>
            <div class="mid">${p.flat_pp==null?'—':arrow(p.flat_pp)+' '+pp(p.flat_pp)}<br>flat</div>
            <div class="side ${bWin?'win':''}"><div class="nm">${esc(p.b)}</div>
              <div class="sc">${pct(p.b_flat)}</div>
              <div class="nm num">${usd(p.b_cost)} / question</div></div>
          </div>
          <div class="pills">
            ${pill('weighted', p.weighted_pp, pp, true, 'Corner-case-weighted, '+p.a+' minus '+p.b)}
            ${pill('$/question', p.cost_pct, pctd, false, p.a+' relative to '+p.b)}
            <span class="pill">out tokens <b>${int(p.a_out)} vs ${int(p.b_out)}</b></span>
            <span class="pill">in tokens <b>${int(p.a_in)} vs ${int(p.b_in)}</b></span>
          </div>
          <p class="base">${verdict}</p>
          ${bar}
          ${warnline(p.judge)}
        </article>`;
      }).join('') + `</div>`;
    } else {
      h += `<div class="card empty"><strong>No kind-matched pair on this set.</strong><br>
        Arms ran here, but no two of them share a kind — so no difference between them would mean
        anything.</div>`;
    }
    if(s.headroom){
      const hr = s.headroom;
      h += `<div class="card" style="margin-top:var(--s3)">
        <div class="stephead"><h4>Retrieval headroom on this set</h4>
          <span class="badge b-warn">not a head-to-head</span></div>
        <p class="note">The oracle arm was handed its rules; the other arm had to find them. The gap
        between them is roughly <strong>what retrieval is leaving on the table</strong> — it is not
        an improvement anyone shipped, and it is not a step delta.</p>
        <div class="vs">
          <div class="side"><div class="nm">${esc(hr.oracle)} ${kindBadge('oracle', hr.oracle_kind_why)}</div>
            <div class="sc">${pct(hr.oracle_flat)}</div>
            <div class="nm">answers derivable when the rules are supplied</div></div>
          <div class="mid">${arrow(hr.gap_pp)} ${pp(hr.gap_pp)}<br>headroom</div>
          <div class="side"><div class="nm">${esc(hr.other)} ${kindBadge(hr.other_kind, hr.other_kind_why)}</div>
            <div class="sc">${pct(hr.other_flat)}</div>
            <div class="nm">best other arm on these questions</div></div>
        </div>
        ${hr.other_kind==='unknown' ? `<p class="warnline warn"><b>⚠ Caution</b><span>
          the counterpart is unclassified — ${esc(hr.other_kind_why)}. Read this gap as indicative,
          not as a measured pipeline-vs-oracle result.</span></p>` : ''}
        ${warnline(hr.judge)}</div>`;
    }
  });
  return h + `</section>`;
}

/* ======================= COST VS ACCURACY =================================== */
function frontierHTML(){
  const sets = (C.frontier||[]).filter(s=>s.points.length||s.unpriced.length);
  if(!sets.length) return '';
  let h = `<section class="sec" id="frontier"><h2>Cost vs accuracy — what is dominated</h2>
    <p class="lede">An arm is <strong>dominated</strong> when another arm on the same questions, of
    the same kind, scored at least as well for no more money. A dominated arm is never the right
    choice. Dominance is only ever computed inside one question set and one kind — an arm with
    retrieval switched off is not on the product's frontier.</p>`;
  sets.forEach(s=>{
    // "On the frontier" is only a claim when something else was in the running.
    // An arm alone on its set-and-kind wins by default, which is not a result.
    const rivals = k => s.points.filter(x=>x.kind===k).length;
    const rows = s.points.slice().sort((a,b)=>b.flat-a.flat).map(p=>`
      <tr class="${p.dominated_by?'dominated':''}">
        <td>${esc(p.step)} ${kindBadge(p.kind)}</td>
        <td class="dim">${esc(p.model||'—')} / ${esc(p.effort||'default')}</td>
        <td class="num">${pct(p.flat)}</td>
        <td class="num dim">${pct(p.weighted)}</td>
        <td class="num">${usd(p.cost)}</td>
        <td class="num">${money(p.full_run)}</td>
        <td>${p.dominated_by
          ? `<span class="badge b-crit">▼ dominated by ${esc(p.dominated_by)}</span>`
          : rivals(p.kind) > 1
            ? `<span class="badge b-good">▲ on the frontier</span>`
            : `<span class="badge" title="Nothing else of this kind was priced on this question set, so there is nothing to be better than.">— only priced ${esc(p.kind)} arm here</span>`}</td></tr>`).join('');
    const un = s.unpriced.map(u=>`<tr><td>${esc(u.step)} ${kindBadge(u.kind)}</td>
      <td class="dim" colspan="2">accuracy ${pct(u.flat)}</td>
      <td class="dim" colspan="4">not priced — ${esc(u.why)}, so no token usage to cost</td></tr>`).join('');
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code></span></div>
      <div class="scroll"><table aria-label="Cost versus accuracy, ${s.n} question set">
        <thead><tr><th>Arm</th><th>Model</th><th>Flat</th><th>Weighted</th><th>$/question</th>
          <th>Full run</th><th>Frontier</th></tr></thead>
        <tbody>${rows||''}${un}</tbody></table></div>`;
  });
  return h + `</section>`;
}

/* ======================= PER-LEVEL ========================================== */
function levelsHTML(){
  const sets = (C.levels||[]);
  if(!sets.length) return '';
  let h = `<section class="sec" id="levels"><h2>Per-level accuracy</h2>
    <p class="lede">Level mix is exactly what the weighting ruling is about, and it is also why a
    flat score off one question set does not transfer to the corpus. Each set's own mix is shown
    against the corpus mix, so you can see which levels an arm is actually evidence for.</p>`;
  sets.forEach(s=>{
    const head = s.order.map(lv=>`<th>${lv==='Corner Case'?'Corner':'L'+lv}
      <br><span class="dim" style="font-weight:400;text-transform:none;letter-spacing:0">${
        s.corpus_share[lv]==null?'not in corpus':(s.corpus_share[lv]*100).toFixed(0)+'% of corpus'}</span></th>`).join('');
    const rows = s.rows.map(r=>`<tr><td>${esc(r.step)} ${kindBadge(r.kind)}</td>
      <td class="num">${pct(r.flat)}</td>` + s.order.map(lv=>{
        const c = r.cells[lv];
        if(!c) return `<td class="lv dim">no rows</td>`;
        const a = c.acc;
        return `<td class="lv num">${a==null?'—':(a*100).toFixed(0)+'%'}
          <span class="dim" style="font-size:.72rem"> ${c.correct.toFixed(c.correct%1?1:0)}/${c.n}</span>
          <i class="cellbar" style="width:${a==null?0:(a*100).toFixed(0)}%"></i></td>`;
      }).join('') + `</tr>`).join('');
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code> · counts are pooled across reps</span></div>
      <div class="scroll"><table aria-label="Per-level accuracy, ${s.n} question set">
        <thead><tr><th>Arm</th><th>Flat</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  });
  return h + `</section>`;
}

/* ======================= CONFIG MATRIX ====================================== */
function matrixHTML(){
  const M = C.matrix;
  if(!M || !M.gen_axis.length) return '';
  const head = M.ret_axis.map(r=>`<th>rewrite ${esc(String(r.rewrite_version))}<br>
    <span class="dim" style="font-weight:400;text-transform:none;letter-spacing:0">${esc(String(r.ruling_query_mode))} · system v${esc(String(r.system_version))}</span></th>`).join('');
  const rows = M.gen_axis.map(g=>`<tr>
    <td>${esc(String(g.model))} <span class="dim">/ ${esc(String(g.effort??'default'))}</span></td>` +
    M.ret_axis.map(r=>{
      const cell = M.cells[`${g.model}|${g.effort}||${r.rewrite_version}|${r.ruling_query_mode}|${r.system_version}`] || [];
      if(!cell.length) return `<td class="gap">— untested</td>`;
      return `<td class="tried">` + cell.map(x=>`<div>${esc(x.step)}
        <span class="dim">${x.n}q · ${pct(x.flat)} · ${x.n_reps} rep${x.n_reps>1?'s':''}</span>
        ${kindBadge(x.kind)}</div>`).join('') + `</td>`;
    }).join('') + `</tr>`).join('');
  return `<section class="sec" id="matrix"><h2>Config matrix — what has been tried</h2>
    <p class="lede">${M.n_tried} of ${M.n_cells} combinations have been run. Blank cells are not
    failures, they are untested. ${esc(M.note)}</p>
    <div class="scroll"><table aria-label="Configuration coverage matrix">
      <thead><tr><th>Model / effort</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>
    </section>`;
}

/* ======================= REPRODUCIBILITY ==================================== */
function reproHTML(){
  const R = (C.repro||[]);
  if(!R.length && !(C.single_rep||[]).length) return '';
  const rows = R.map(r=>`<tr>
    <td>${esc(r.step)} ${kindBadge(r.kind)}</td>
    <td class="num dim">${r.n}</td>
    <td class="num">${r.reps.map(x=>pct(x.flat)).join(' / ')}</td>
    <td class="num"><strong>${r.spread_pp==null?'—':r.spread_pp.toFixed(1)+' pp'}</strong></td>
    <td class="num">${r.churn?`${r.churn.n_flipped} / ${r.churn.n_rows}`:'—'}</td>
    <td class="dim" style="white-space:normal">${r.judging_runs.map(j=>
      `${esc(stamp(j.mtime))} ${j.recorded?esc(j.judge_model):'<span class="prov"><span class="miss">judge not recorded</span></span>'}`).join('<br>')}</td>
  </tr>`).join('');
  const singles = (C.single_rep||[]);
  return `<section class="sec" id="repro"><h2>Reproducibility — the noise floor</h2>
    <p class="lede">Every configuration that ran more than once, and how far apart those runs
    landed. That spread is the instrument's resolution: a difference smaller than it is not a
    finding. Rows flipped counts questions whose verdict changed between two runs of the
    <em>identical</em> configuration — rows can churn heavily while the totals barely move.</p>
    ${rows ? `<div class="scroll"><table aria-label="Rep-to-rep reproducibility">
      <thead><tr><th>Configuration</th><th>Questions</th><th>Reps</th><th>Spread</th>
        <th>Rows flipped</th><th>Judging runs</th></tr></thead><tbody>${rows}</tbody></table></div>`
    : `<div class="card empty"><strong>No configuration has been run twice.</strong><br>
        Without a repeat there is no measured noise floor, only the judge's assumed flip rate.</div>`}
    ${singles.length ? `<p class="note" style="margin-top:var(--s3)"><strong>Run once only:</strong>
      ${singles.map(x=>`<code>${esc(x.step)}</code> (${x.n}q)`).join(', ')} — no within-config spread
      was measured for these, so their set falls back to the assumed judge floor.</p>` : ''}
    </section>`;
}

/* ---- timeline: what changed, by how much, and whether it beat the noise ---- */
const TL = D.timeline || {sets:[], notes:{}};
let tlSet = 'all', tlSort = 'time';

// Colour is never the only signal: every pill also carries an arrow and a sign.
function pill(label, val, fmt, betterIsUp, title){
  if(val==null) return '';
  const good = val===0 ? null : (val>0)===betterIsUp;
  const cls = good===null ? '' : (good ? 'p-good' : 'p-bad');
  return `<span class="pill ${cls}" title="${esc(title||'')}">${esc(label)}
    <b>${arrow(val)} ${fmt(val)}</b></span>`;
}

function cfgChips(st){
  if(!st.config_recorded)
    return `<div class="cfg"><span title="No answers file joined, so this arm records no config.">config not recorded for this arm</span></div>`;
  const chg = {};
  if(st.delta && st.delta.changed_known) st.delta.changed.forEach(c => chg[c.field] = c);
  const F = [['model','model'],['effort','effort'],['rewrite_version','rewrite'],
             ['ruling_query_mode','ruling mode'],['system_version','system ver']];
  return `<div class="cfg">` + F.map(([f,lab])=>{
    const v = st.config[f], c = chg[f];
    const shown = v==null ? '—' : v;
    if(!c) return `<span>${esc(lab)} ${esc(shown)}</span>`;
    const was = c.from==null ? '—' : c.from;
    return `<span class="chg" title="changed from ${esc(was)}">${esc(lab)}
      <span class="was">${esc(was)}</span><b>${esc(shown)}</b></span>`;
  }).join('') + `</div>`;
}

function stepCard(st, floor){
  const d = st.delta;
  const acc = st.flat==null ? '—' : pct(st.flat);
  const oracle = st.kind !== 'pipeline';

  let deltaBlock;
  if(oracle){
    deltaBlock = `<p class="base">${kindBadge(st.kind, st.kind_why)}
      <span class="badge">no delta — measures something else</span><br>
      ${esc(st.kind_why)}.${st.kind_note?' '+esc(st.kind_note):''}<br>
      A delta needs the same question set <em>and</em> the same kind, so this step is never
      subtracted from a pipeline step and never used as one's baseline.</p>`;
  } else if(!d){
    deltaBlock = `<p class="base"><span class="badge">first run on this question set</span><br>
      Nothing earlier ran these ${st.n} questions, so there is no baseline to subtract.</p>`;
  } else {
    const real = d.beats_noise;
    const badge = real===null ? '<span class="badge">no accuracy delta</span>'
      : real ? `<span class="badge b-good">clear of noise</span>`
             : `<span class="badge b-warn">within noise — not a result</span>`;
    const changed = !d.changed_known
      ? `<em>what changed is not recorded</em> — one of the two arms has no answers file, so its config is unknown. The accuracy delta still holds; the cause does not.`
      : (d.changed.length
          ? d.changed.map(c=>`<code>${esc(c.label)}</code> ${esc(c.from==null?'—':c.from)} → ${esc(c.to==null?'—':c.to)}`).join(', ')
          : 'no recorded config field changed');
    deltaBlock = `
      <div class="pills">
        ${pill('accuracy', d.flat_pp, pp, true, 'Flat accuracy vs '+d.baseline)}
        ${pill('weighted', d.weighted_pp, pp, true, 'Corner-case-weighted accuracy vs '+d.baseline)}
        ${pill('$/question', d.cost_pct, pctd, false, d.cost_abs==null?'':('absolute '+usd(Math.abs(d.cost_abs))+' per question'))}
        ${pill('out tokens', d.out_tok_pct, pctd, false, 'Output tokens per question')}
      </div>
      <p class="base">${badge}<br>
        <strong>Changed:</strong> ${changed}<br>
        <strong>Compared against:</strong> <code>${esc(d.baseline)}</code>
        (${esc(day(d.baseline_run_at))}, ${pct(d.baseline_flat)}) — the previous pipeline step
        on these same ${st.n} questions.<br>
        <strong>Resolution floor:</strong> ±${d.floor_pp.toFixed(1)} pp.
        ${real===false ? 'This move is smaller than that, so it is not distinguishable from a re-run of the same config.' : ''}
      </p>
      ${d.commits_total ? `<details class="commits"><summary>${d.commits_total} commit${d.commits_total>1?'s':''} landed between the two runs (association by timestamp, not a recorded link)</summary>
        <ol>${d.commits.map(c=>`<li><code>${esc(c.sha)}</code> ${esc(c.subject)}</li>`).join('')}
        ${d.commits_total>d.commits.length?`<li class="dim">… ${d.commits_total-d.commits.length} more</li>`:''}</ol></details>` : ''}`;
  }

  const regrade = st.reps.filter(r=>r.regrade_pp!=null).map(r=>
    `<div class="reps">Human regrade: <strong>${pp(r.regrade_pp)}</strong> over the auto verdict
     (<code>${esc((r.regrade_of||[]).join(', '))}</code>) — the judge, not the pipeline.</div>`).join('');

  const repline = st.n_reps > 1
    ? `<div class="reps">${st.n_reps} reps: ${st.reps.map(r=>pct(r.flat)).join(' / ')}
       · spread ${st.rep_spread_pp==null?'—':st.rep_spread_pp.toFixed(1)+' pp'}
       ${st.rep_churn?`· ${st.rep_churn.n_flipped}/${st.rep_churn.n_rows} rows flipped verdict between reps`:''}</div>`
    : `<div class="reps">1 rep — no within-config spread measured here</div>`;

  const hetero = st.heterogeneous_fields.length
    ? `<div class="reps"><span class="badge b-crit">reps differ in ${esc(st.heterogeneous_fields.join(', '))}</span> — treat as separate runs, not reps.</div>` : '';

  return `<article class="step ${oracle?'is-oracle':''}" data-qset="${esc(st.qset)}"
      data-move="${d && d.flat_pp!=null ? Math.abs(d.flat_pp) : -1}" tabindex="0"
      aria-label="${esc(st.step)}, ${acc} on ${st.n} questions">
    <div class="card">
      <div>
        <div class="stephead"><h4>${esc(st.step)}</h4>
          <span class="when">${esc(day(st.run_at))}</span>
          ${kindBadge(st.kind, st.kind_why)}</div>
        ${cfgChips(st)}
        <div class="score"><span class="big">${acc}</span>
          <span class="dim">flat · ${st.n} questions</span></div>
        <div class="meter"><i style="width:${st.flat==null?0:(st.flat*100).toFixed(1)}%"></i></div>
        ${repline}${hetero}${regrade}
        ${provBlock(st.generation_runs, st.judging_runs, st.human_passes)}
      </div>
      <div>${deltaBlock}</div>
    </div></article>`;
}

function timelineHTML(){
  if(!TL.sets || !TL.sets.length)
    return `<h2>Timeline</h2><div class="card empty"><strong>No steps to plot.</strong><br>
      No arm carried both a question set and a run time.</div>`;

  const chips = [['all','All sets']].concat(TL.sets.map(s=>[s.qset, s.n+' questions']));
  let h = `<h2>Timeline — what changed at each step</h2>
   <p class="note">Each card is one configuration. The delta beside it is measured against the
   <strong>previous pipeline step on the same question set</strong>, and against a noise floor taken
   from how far apart two runs of one identical config landed. Steps on different question sets are
   never subtracted from each other.</p>
   <div class="controls" role="group" aria-label="Timeline filters">
     <span class="lbl">Question set</span>
     ${chips.map(c=>`<button type="button" class="chip" data-set="${esc(c[0])}"
        aria-pressed="${c[0]===tlSet}">${esc(c[1])}</button>`).join('')}
     <span class="lbl" style="margin-left:auto">Order</span>
     <button type="button" class="chip" data-sort="time" aria-pressed="${tlSort==='time'}">Chronological</button>
     <button type="button" class="chip" data-sort="move" aria-pressed="${tlSort==='move'}">Biggest move</button>
   </div>`;

  const sets = TL.sets.filter(s => tlSet==='all' || s.qset===tlSet);
  if(!sets.length)
    return h + `<div class="card empty"><strong>Nothing matches that filter.</strong><br>
      Pick another question set.</div>`;

  sets.forEach(s=>{
    let steps = s.steps.slice();
    if(tlSort==='move')
      steps.sort((a,b)=>{
        const av = a.delta && a.delta.flat_pp!=null ? Math.abs(a.delta.flat_pp) : -1;
        const bv = b.delta && b.delta.flat_pp!=null ? Math.abs(b.delta.flat_pp) : -1;
        return bv-av;
      });
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code> · ${s.n_steps} step${s.n_steps>1?'s':''}</span></div>
      <p class="floornote"><strong>Noise floor ±${s.floor_pp.toFixed(1)} pp</strong> — ${esc(s.floor_source)}.
      A step-delta smaller than this is not a result on this set.</p>
      <div class="rail">${steps.map(st=>stepCard(st, s.floor_pp)).join('')}</div>`;
  });
  return h;
}

function wireTimeline(){
  document.querySelectorAll('.controls .chip').forEach(b=>{
    b.addEventListener('click', ()=>{
      if(b.dataset.set!==undefined) tlSet = b.dataset.set; else tlSort = b.dataset.sort;
      document.getElementById('tl').innerHTML = timelineHTML();
      wireTimeline();
      const again = document.querySelector(`.controls .chip[data-${b.dataset.set!==undefined?'set':'sort'}="${b.dataset.set!==undefined?tlSet:tlSort}"]`);
      if(again) again.focus();
    });
  });
}

function render(){
  if(!D.arms.length){
    document.getElementById('app').innerHTML =
      '<div class="card empty"><strong>No scorable arms found.</strong><br>'+
      'Every verdict file lacked a <code>summary.by_level_counts</code>. '+
      'Re-run the judge, then rebuild.</div>';
    return;
  }
  let html = `<nav class="nav" aria-label="Sections">
    ${[['#decision','The decision'],['#h2h','Head to head'],['#frontier','Cost vs accuracy'],
       ['#levels','Per level'],['#matrix','Config matrix'],['#repro','Reproducibility'],
       ['#tl','Timeline'],['#arms','Every arm']]
      .map(([href,label])=>`<a href="${href}">${label}</a>`).join('')}</nav>`;

  html += `<div class="tiles">${tiles.map(t=>
    `<div class="card tile ${t.cls||''}"><div class="k">${esc(t.k)}</div>
     <div class="v num">${t.v}</div><div class="n">${t.n}</div></div>`).join('')}</div>`;

  html += decisionHTML();
  html += h2hHTML();
  html += frontierHTML();
  html += levelsHTML();
  html += matrixHTML();
  html += reproHTML();

  html += `<section class="sec" id="tl">${timelineHTML()}</section>`;

  html += `<section class="sec" id="arms"><h2>Every arm, side by side</h2>
    <p class="lede">One row per verdict file. <strong>Generation run</strong> is when the answers
    were produced; <strong>judging run</strong> is when they were scored, by which judge and under
    which prompt digest; <strong>human grading</strong> is a third pass on top. Two arms judged in
    different judging runs differ a little before their models do anything.</p>`;
  order.forEach(([qset, rows], gi) => {
    html += `<div class="grp"><h3>${rows[0].n} questions</h3>
      <span class="meta">fingerprint <code>${esc(qset)}</code> — ${rows.length} arm${rows.length>1?'s':''}; comparable only to each other, and only where the Kind matches too</span></div>`;
    html += table(rows, 'g'+gi);
  });
  html += `</section>`;
  document.getElementById('app').innerHTML = html;
  wireTimeline();

  document.querySelectorAll('th[data-c]').forEach(th => {
    const go = () => sort(th);
    th.addEventListener('click', go);
    th.addEventListener('keydown', e => { if(e.key==='Enter'||e.key===' '){ e.preventDefault(); go(); }});
  });
}

function sort(th){
  const tbl = th.closest('table'), ci = +th.dataset.c;
  const asc = th.getAttribute('aria-sort') !== 'ascending';
  tbl.querySelectorAll('th').forEach(o=>o.removeAttribute('aria-sort'));
  th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
  const tb = tbl.tBodies[0];
  const rows = [...tb.rows];
  rows.sort((x,y)=>{
    const a = x.cells[ci].textContent.trim(), b = y.cells[ci].textContent.trim();
    const na = parseFloat(a.replace(/[$%,]/g,'')), nb = parseFloat(b.replace(/[$%,]/g,''));
    const cmp = (!isNaN(na)&&!isNaN(nb)) ? na-nb : a.localeCompare(b);
    return asc ? cmp : -cmp;
  });
  rows.forEach(r=>tb.appendChild(r));
}

document.getElementById('foot').innerHTML = `
 <strong>How to read this.</strong>
 <ul>
  <li><strong>Two gates, not one.</strong> Arms may only be differenced when they share a question-set
      fingerprint <em>and</em> a kind. ${esc(C.kind_rule||'')} Arms of different kinds still appear
      side by side — that is useful — but their numbers are not on the same scale, and nothing
      subtracts one from the other.</li>
  <li><strong>Generation run vs judging run.</strong> They are separate events. The generation run is
      the answers file that produced the answers; the judging run is the verdict file that scored
      them, named with its judge model and prompt digest. Re-judging identical answers has moved an
      arm by 2 pp in this repo, so an accuracy that does not name its judging run is not
      reproducible. Human grading is a third layer on top and is labelled separately wherever it
      applies.</li>
  <li><strong>Corpus-mix projection.</strong> The full corpus is
      ${esc(JSON.stringify(C.corpus&&C.corpus.by_level||{}))} by level, read from
      <code>${esc((C.corpus||{}).file||'—')}</code>; the 150-question set is 30 per level. A flat
      score off a stratified sample is therefore not the expected score on the corpus, so the
      projection reweights each arm's per-level accuracy by the corpus's own mix and reports how
      much of the corpus that covers.</li>
  <li><strong>Every delta names its baseline.</strong> ${esc(TL.notes.baseline||'')}</li>
  <li><strong>Run order.</strong> ${esc(TL.notes.ordering||'')}</li>
  <li><strong>Commits are an inference.</strong> ${esc(TL.notes.commits||'')}</li>
  <li><strong>Oracle arms never chain.</strong> ${esc(TL.notes.oracle||'')}</li>
  <li><strong>Flat vs Weighted.</strong> Flat is how every prior result in this repo is stated.
      Weighted applies Jon's ruling — flat across L0–L3, Corner Case ×0.5. Flat is the number to quote.</li>
  <li><strong>Auto</strong> is the judge's own score before human regrading; where it differs from Flat,
      a human overturned rows. The judge is <em>nondeterministic</em> (~1 verdict flip per 100 rows),
      so treat ±1–2 rows as noise before reading a difference as real.</li>
  <li><strong>$/question</strong> is computed from recorded token usage at
      ${esc(D.pricing.source)}: input, output, cache-write ×${D.pricing.cache_write_mult},
      cache-read ×${D.pricing.cache_read_mult}. Sonnet 5 is shown at its standard rate —
      its introductory rate runs to ${esc(D.pricing.sonnet_intro_ends)}.</li>
  <li><strong>Join</strong> says how an arm's accuracy was linked to its cost. Verdict files do not
      record which answers file they judged, so each link is confirmed by comparing question-id sets.
      Anything not marked <span class="badge b-good">verified</span> should not be used for a cost claim.</li>
  <li><strong>Retrieval config is not per-arm.</strong> The answers files record model and rewrite
      version but not TOP_K / TOP_N / COSINE_FLOOR. Current values —
      TOP_K ${D.current_config.TOP_K}, TOP_N ${D.current_config.TOP_N},
      COSINE_FLOOR ${D.current_config.COSINE_FLOOR}, REWRITE_N ${D.current_config.REWRITE_N} —
      describe the code today, not what each historical arm ran.</li>
 </ul>`;

const btn = document.getElementById('themeBtn');
btn.addEventListener('click', () => {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  document.documentElement.setAttribute('data-theme', dark ? 'light' : 'dark');
});
render();
</script></body></html>
"""


def render_html(data: dict) -> str:
    return (HTML
            .replace("__GENERATED__", data["generated_at"])
            .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", dest="json_out", default="evals/_metrics_history.json")
    ap.add_argument("--html", dest="html_out", default="evals/metrics_history.html")
    args = ap.parse_args()

    data = collect()
    data["full_corpus"] = FULL_CORPUS
    data["timeline"] = build_timeline(data["arms"])
    data["comparisons"] = build_comparisons(data["timeline"], corpus_level_mix())
    for s in data["timeline"]["sets"]:   # working data, not a result
        for st in s["steps"]:
            st.pop("_arms", None)
    for a in data["arms"]:
        a.pop("_verdicts", None)
        a.pop("_correct", None)
    Path(args.json_out).write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    Path(args.html_out).write_text(render_html(data), encoding="utf-8")
    print(f"wrote {args.html_out}")
    print(f"wrote {args.json_out}: {len(data['arms'])} arms, "
          f"{len({a['qset'] for a in data['arms']})} question sets, "
          f"{len(data['skipped'])} skipped")
    groups: dict[str, list] = {}
    for a in data["arms"]:
        groups.setdefault(a["qset"], []).append(a)
    for qset, members in groups.items():
        print(f"\n  qset {qset}  n={members[0]['n']}  ({len(members)} arms)")
        for a in members:
            c = a["cost"].get("cost_per_q")
            cost = f"${c:.5f}" if c else "  --   "
            print(f"    {a['arm']:<34} {a['kind']:<8} flat {a['accuracy_flat']:>6.1%}  "
                  f"wtd {a['accuracy_weighted']:>6.1%}  {cost}  "
                  f"{a['config'].get('model') or '?'}/{a['config'].get('effort') or '?'}"
                  f"  gen[{a['generation']['join']}] judge[{a['judging']['judge_model'] or 'NOT RECORDED'}]")
    for s in data["skipped"]:
        print(f"  SKIP {s}")

    print(f"\n  timeline: {len(data['timeline']['sets'])} question sets, "
          f"{sum(len(s['steps']) for s in data['timeline']['sets'])} steps, "
          f"{data['timeline']['commits_indexed']} commits indexed")
    for s in data["timeline"]["sets"]:
        print(f"\n  qset {s['qset']} n={s['n']}  floor +/-{s['floor_pp']:.1f}pp ({s['floor_source'][:44]})")
        for st in s["steps"]:
            d = st["delta"]
            tag = "" if st["kind"] == "pipeline" else f"  [{st['kind']}, off-chain]"
            spread = f" spread {st['rep_spread_pp']:.1f}pp" if st["rep_spread_pp"] is not None else ""
            line = (f"    {(st['run_at'] or '')[:16]}  {st['step']:<30} "
                    f"flat {(st['flat'] or 0):>6.1%}{spread}{tag}")
            if d:
                verdict = "REAL" if d["beats_noise"] else "within noise"
                cost = f", cost {d['cost_pct']:+.0f}%" if d["cost_pct"] is not None else ""
                line += (f"\n        vs {d['baseline']}: {d['flat_pp']:+.1f}pp{cost} "
                         f"-> {verdict} (floor {d['floor_pp']:.1f}pp)")
            print(line)

    C = data["comparisons"]
    print(f"\n  head-to-head: {sum(len(h['pairs']) for h in C['head_to_head'])} kind-matched pairs, "
          f"{sum(1 for h in C['head_to_head'] if h['headroom'])} oracle-headroom readings")
    for h in C["head_to_head"]:
        for p in h["pairs"]:
            print(f"    n={p['n']:<4} {p['a']} vs {p['b']}  {p['flat_pp']:+.1f}pp "
                  f"cost {p['cost_pct']:+.0f}%" if p["cost_pct"] is not None else
                  f"    n={p['n']:<4} {p['a']} vs {p['b']}  {p['flat_pp']:+.1f}pp")
            print(f"          judge[{p['judge']['level']}] {p['judge']['text'][:96]}")
    print(f"\n  projections ({len(C['projections'])} configurations):")
    for p in C["projections"]:
        c = p["config"]
        acc = f"{p['projected_acc']:.1%}" if p["projected_acc"] is not None else "--"
        ci = f"[{p['ci95'][0]:.1%}-{p['ci95'][1]:.1%}]" if p["ci95"] else ""
        run = (f"${p['full_run_lo']:.0f}-{p['full_run_hi']:.0f}"
               if p["full_run_lo"] is not None else "unpriced")
        print(f"    {p['kind']:<8} {c.get('model')}/{c.get('effort')} rw={c.get('rewrite_version')} "
              f"rq={c.get('ruling_query_mode')}  corpus-mix {acc} {ci}  cover "
              f"{p['covered_share']:.0%}  full run {run}")
    print(f"\n  config matrix: {C['matrix']['n_tried']} of {C['matrix']['n_cells']} cells tried")
    print(f"  open items: {len(C['open_items'])}")
    for o in C["open_items"]:
        print(f"    [{o['level']}] {o['what']}")


if __name__ == "__main__":
    main()

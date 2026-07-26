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

**2. Every number carries what produced it.** This repo has already shipped a
results doc that disagreed with its own verdict file inside one commit, because a
number was read at one time and published at another. So each row records its
source files, their mtimes, the judging model and prompt digest, and whether the
accuracy is auto-judged or human-corrected. A row you cannot trace is a row you
cannot use to make a go/no-go call.

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

        arms.append({
            "arm": stem,
            "qset": qset,
            # Per-row verdicts, kept only long enough to measure rep-to-rep churn.
            # Popped before the file is written -- it is working data, not a result.
            "_verdicts": {e["id"]: e.get("verdict") for e in entries if "id" in e},
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

# Hand-declared, deliberately small, and stated rather than inferred: nothing in
# an answers file says "this arm was an oracle". Default is "pipeline".
ARM_KIND = {
    "derivability_B": ("oracle", "Gold rules handed to the model, no retrieval — measures whether "
                                 "the answers are derivable at all, not what the pipeline scores."),
    "derivability_B_human": ("oracle", "Same gold-only run as derivability_B, re-graded by Jon."),
    "derivability_C": ("oracle", "Gold plus retrieval, on the 15 rows arm B got wrong. "
                                 "docs/results-derivability.md withdraws its reading — the four "
                                 "'passes' were the judge changing its mind, not retrieval closing a gap."),
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

        kind, kind_why = ARM_KIND.get(name, ("pipeline", ""))
        built.append({
            "qset": qset, "step": name, "kind": kind, "kind_why": kind_why,
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
 --ring:rgba(255,255,255,.10);
 --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:40px;}
:root[data-theme=light]{color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#6e6c66;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
 --good-t:#0a7a0a; --warn-t:#8f6200; --crit-t:#b32d2d;}
@media(prefers-color-scheme:light){:root:not([data-theme=dark]){color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#6e6c66;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
 --good-t:#0a7a0a; --warn-t:#8f6200; --crit-t:#b32d2d;}}
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
.tiles{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
 margin-bottom:var(--s5)}
.tile .k{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
.tile .v{font-size:1.9rem;line-height:1.15;margin:var(--s1) 0 2px;font-weight:600}
.tile .n{color:var(--ink2);font-size:.82rem}
.decision{border-left:3px solid var(--accent)}
.decision .v{color:var(--accent)}
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

// The decision number: measured cost per question x the full corpus.
const costed = D.arms.filter(a => a.cost && a.cost.cost_per_q != null);
const cur = costed.filter(a => (a.config||{}).model === 'claude-opus-5' && (a.config||{}).effort === 'low');
const basis = cur.length ? cur : costed;
const lo = basis.length ? Math.min(...basis.map(a=>a.cost.cost_per_q)) : null;
const hi = basis.length ? Math.max(...basis.map(a=>a.cost.cost_per_q)) : null;
const N = D.full_corpus;

const tiles = [
  {k:'Full RulesGuru run', v: lo==null?'—':('$'+(lo*N).toFixed(0)+'–'+(hi*N).toFixed(0)),
   n:`${N.toLocaleString()} questions at the measured cost/question of the shipped config`
      + (cur.length?` (${cur.length} opus-5/low arms)`:' (no opus-5/low arm — using all priced arms)'),
   cls:'decision'},
  {k:'Cost per question', v: lo==null?'—':usd(lo), n: lo==null?'no priced arm':`to ${usd(hi)} across those arms`},
  {k:'Arms tracked', v: String(D.arms.length),
   n:`${new Set(D.arms.map(a=>a.qset)).size} distinct question sets · ${D.skipped.length} files skipped`},
  {k:'Weighting', v:'Corner ×0.5', n:`flat across L0–L3 · ruled by ${esc(D.weighting.ruled_by)}`},
];

const groups = {};
D.arms.forEach(a => (groups[a.qset] ||= []).push(a));
const order = Object.entries(groups).sort((a,b)=>b[1].length-a[1].length || b[1][0].n-a[1][0].n);

const COLS = [
  ['Arm', a=>`${esc(a.arm)} ${a.human_corrected?'<span class="badge b-good">human-corrected</span>':''}`, a=>a.arm],
  ['Model', a=>`<span class="dim">${esc((a.config||{}).model||'—')}${(a.config||{}).effort?' / '+esc(a.config.effort):''}</span>`, a=>(a.config||{}).model||''],
  ['Flat', a=>`<span class="num">${pct(a.accuracy_flat)}</span>`, a=>a.accuracy_flat],
  ['Weighted', a=>`<span class="num">${pct(a.accuracy_weighted)}</span>`, a=>a.accuracy_weighted],
  ['Auto', a=>`<span class="num dim">${pct(a.accuracy_auto)}</span>`, a=>a.accuracy_auto??-1],
  ['$/question', a=>`<span class="num">${usd((a.cost||{}).cost_per_q)}</span>`, a=>(a.cost||{}).cost_per_q??-1],
  ['In tok', a=>`<span class="num dim">${int((a.cost||{}).in_per_q)}</span>`, a=>(a.cost||{}).in_per_q??-1],
  ['Out tok', a=>`<span class="num dim">${int((a.cost||{}).out_per_q)}</span>`, a=>(a.cost||{}).out_per_q??-1],
  ['Judge', a=>`<span class="dim" title="prompt digest ${esc(a.judge_digest||'?')}">${esc(a.judge_model||'—')}</span>`, a=>a.judge_model||''],
  ['Join', a=>joinBadge(a.provenance.join), a=>a.provenance.join],
  ['Run', a=>`<span class="dim">${esc((a.provenance.verdicts_mtime||'').slice(0,10))}</span>`, a=>a.provenance.verdicts_mtime||''],
];

function table(rows, key){
  const head = COLS.map((c,i)=>`<th tabindex="0" role="columnheader" data-c="${i}" data-k="${key}">${c[0]}</th>`).join('');
  const body = rows.map(a=>`<tr>${COLS.map(c=>`<td>${c[1](a)}</td>`).join('')}</tr>`).join('');
  return `<div class="scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/* ---- timeline: what changed, by how much, and whether it beat the noise ---- */
const TL = D.timeline || {sets:[], notes:{}};
let tlSet = 'all', tlSort = 'time';

const pp = v => (v>=0?'+':'−') + Math.abs(v).toFixed(1) + ' pp';
const pctd = v => (v>=0?'+':'−') + Math.abs(v).toFixed(0) + '%';
const arrow = v => v>0 ? '▲' : (v<0 ? '▼' : '▬');
const day = s => (s||'').slice(0,10);

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
    deltaBlock = `<p class="base"><span class="badge b-warn">${esc(st.kind)} — no delta</span><br>
      ${esc(st.kind_why)}</p>`;
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
          ${oracle?`<span class="badge b-warn">${esc(st.kind)}</span>`:''}</div>
        ${cfgChips(st)}
        <div class="score"><span class="big">${acc}</span>
          <span class="dim">flat · ${st.n} questions</span></div>
        <div class="meter"><i style="width:${st.flat==null?0:(st.flat*100).toFixed(1)}%"></i></div>
        ${repline}${hetero}${regrade}
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
  let html = `<div class="tiles">${tiles.map(t=>
    `<div class="card tile ${t.cls||''}"><div class="k">${esc(t.k)}</div>
     <div class="v num">${t.v}</div><div class="n">${t.n}</div></div>`).join('')}</div>`;

  html += `<section id="tl">${timelineHTML()}</section>`;

  html += `<h2>Every arm, side by side</h2>`;
  order.forEach(([qset, rows], gi) => {
    html += `<div class="grp"><h3>${rows[0].n} questions</h3>
      <span class="meta">fingerprint <code>${esc(qset)}</code> — ${rows.length} arm${rows.length>1?'s':''}, directly comparable to each other and to nothing else</span></div>`;
    html += table(rows, 'g'+gi);
  });
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
    for a in data["arms"]:          # working data, not a result
        a.pop("_verdicts", None)
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
            print(f"    {a['arm']:<34} flat {a['accuracy_flat']:>6.1%}  "
                  f"wtd {a['accuracy_weighted']:>6.1%}  {cost}  "
                  f"{a['config'].get('model') or '?'}/{a['config'].get('effort') or '?'}"
                  f"  [{a['provenance']['join']}]")
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


if __name__ == "__main__":
    main()

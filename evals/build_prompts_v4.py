"""Derive evals/answers/_prompts_v4.json from the condition-C capture by
swapping ONLY the system string (docs/plan-v4e-execution-tasks.md Task 3).

Why a swap instead of a fresh capture pass: prompt v4 is a SYSTEM-string-only
change (docs/plan-prompt-v4.md Sec 8 -- no retrieval, TOP_K, rewriter, or
context-assembly changes), and retrieval embedding is nondeterministic
(~30-34% chunk drift, Voyage embed_query has no cache on the live path). A
fresh capture would re-draw retrieval, so some v3-vs-v4 flips would be
unattributable. Reusing condition C's `user` blocks byte for byte makes the
SYSTEM string the ONLY variable between the v3 baselines (sonnet 46 /
gpt-5-mini 45) and the v4 arms.

The per-question byte-equality report this prints is the entire basis for
claiming a flip is attributable to the prompt. Read it, don't skim it.

Usage:  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/build_prompts_v4.py
        (add --check to verify an existing file without rewriting it)
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "evals"))

import lib_v3ab as L  # noqa: E402
from rulesagent.generate.answer import SYSTEM as SYSTEM_V4  # noqa: E402
from rulesagent.generate.answer import PROMPT_VERSION  # noqa: E402

SRC = REPO / "evals" / "answers" / "_prompts_C.json"
OUT = REPO / "evals" / "answers" / "_prompts_v4.json"

# Recorded before the v4 edit (Task 1, commit 8c7550f). The captured condition-C
# prompts must still carry exactly this system string, or the capture is not the
# v3 baseline we think it is.
V3_SYSTEM_SHA256 = "25aa69e19208da80b033c15a19d11a3cafa90e23ee807552f17f758bedde06cc"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load(path: Path) -> dict:
    return json.loads(io.open(path, encoding="utf-8").read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the existing output file instead of rewriting it")
    args = ap.parse_args()

    src = load(SRC)
    prompts = src["prompts"]
    failures: list[str] = []

    print(f"source          : {SRC.name}")
    print(f"rewrite_version : {src.get('rewrite_version')!r}")
    print(f"ruling_query_mode: {src.get('ruling_query_mode')!r}")

    # --- gate 1: the capture carries exactly one system string, and it is v3 ---
    systems = {e["system"] for e in prompts.values()}
    print(f"\n[gate 1] distinct system strings in capture: {len(systems)} (expect 1)")
    if len(systems) != 1:
        failures.append(f"capture holds {len(systems)} distinct system strings")
    captured = next(iter(systems))
    captured_sha = sha(captured)
    ok_v3 = captured_sha == V3_SYSTEM_SHA256
    print(f"[gate 1] captured system sha256: {captured_sha}")
    print(f"[gate 1] matches recorded v3 digest: {'PASS' if ok_v3 else 'FAIL'}")
    if not ok_v3:
        failures.append("captured system is not the recorded v3 SYSTEM")

    # --- gate 2: id set is the full 50-question eval ---
    ids = set(prompts)
    missing, extra = set(L.ALL_QIDS) - ids, ids - set(L.ALL_QIDS)
    print(f"\n[gate 2] question ids: {len(ids)} (expect {len(L.ALL_QIDS)})")
    print(f"[gate 2] missing={sorted(missing) or 'none'} extra={sorted(extra) or 'none'}"
          f" -> {'PASS' if not (missing or extra) else 'FAIL'}")
    if missing or extra:
        failures.append("id set does not match ALL_QIDS")

    if failures:
        print("\nABORT (pre-write gates failed):")
        for f in failures:
            print(f"  - {f}")
        return 1

    # --- build (or load, under --check) ---
    if args.check:
        if not OUT.exists():
            print(f"\n--check: {OUT.name} does not exist")
            return 1
        out = load(OUT)
        print(f"\n--check mode: verifying existing {OUT.name}")
    else:
        out = {
            "derived_from": SRC.name,
            "prompt_version": PROMPT_VERSION,
            "system_sha256_v3": V3_SYSTEM_SHA256,
            "system_sha256_v4": sha(SYSTEM_V4),
            # preserved from condition C -- run_answer_eval.py validates these
            # against the run's own flags and refuses to start on a mismatch.
            "rewrite_version": src["rewrite_version"],
            "ruling_query_mode": src["ruling_query_mode"],
            "n_questions": src["n_questions"],
            "prompts": {qid: {"system": SYSTEM_V4, "user": e["user"]}
                        for qid, e in prompts.items()},
        }

    # --- gate 3: every user block byte-identical to condition C ---
    print(f"\n[gate 3] per-question user-block byte equality (v4 vs condition C):")
    equal = 0
    for qid in sorted(prompts):
        same = out["prompts"][qid]["user"] == prompts[qid]["user"]
        equal += same
        if not same:
            print(f"    {qid}: FAIL  (user block differs)")
            failures.append(f"{qid} user block differs")
    print(f"    {equal}/{len(prompts)} byte-identical"
          f" -> {'PASS' if equal == len(prompts) else 'FAIL'}")

    # --- gate 4: exactly one system string out, and it is v4 ---
    out_systems = {e["system"] for e in out["prompts"].values()}
    ok_one = len(out_systems) == 1 and next(iter(out_systems)) == SYSTEM_V4
    print(f"\n[gate 4] distinct system strings written: {len(out_systems)}"
          f" | all == current v4 SYSTEM: {'PASS' if ok_one else 'FAIL'}")
    print(f"[gate 4] v4 system sha256: {sha(SYSTEM_V4)}")
    if not ok_one:
        failures.append("output system strings are not a single current v4 SYSTEM")

    if failures:
        print("\nFAIL -- not written:" if not args.check else "\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1

    if not args.check:
        io.open(OUT, "w", encoding="utf-8").write(
            json.dumps(out, ensure_ascii=False, indent=1))
        print(f"\nwrote {OUT}")

    print(f"\nDONE -- all gates PASS. v3 {len(captured)} chars -> v4 "
          f"{len(SYSTEM_V4)} chars; {equal} user blocks carried over unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

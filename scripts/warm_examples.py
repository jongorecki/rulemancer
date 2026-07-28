"""Pre-warm the four demo example questions into the answer cache
(.superpowers/sdd/2026-07-27-gated-demo/task-caching-report.md, Change 1).

The frontend's four clickable example questions (frontend/index.html's
EXAMPLES) get clicked more than anything else on the demo, are identical
every time, and each currently costs a full opus-5 generation -- the measured
$/query is ~$0.0485 and essentially all of it is this call. This script runs
each one through the real /answer route once (no gating, no HTTP -- calls
rulesagent.api.main.answer() in-process the same way tests/test_api_debug.py
does) and stores the resulting response in the SAME data/cache.db warmed-cache
table the running server reads, so a demo visitor's first click on an example
is served instantly and for free.

SPENDS REAL ANTHROPIC API CREDITS: ~$0.05 x 4 questions = ~$0.20 total.
Approved ceiling for a single run of this script is $0.40 -- it stops and
reports if a run would exceed that instead of continuing past it. Requires
Jon's explicit go-ahead per run (the same posture as scripts/measure_demo_cost
.py, which this is modeled on). NOT run as part of any test suite or CI, and
does not run on boot -- manual only, re-run whenever the generator model,
effort, system prompt, rewrite version, or corpus changes (the cache key
already includes all of those, so a stale cache is simply a permanent miss,
never a silently wrong hit -- but re-running keeps the demo's first click
fast after a real pipeline change).

    .venv/Scripts/python.exe scripts/warm_examples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rulesagent.api import main as api_main  # noqa: E402
from rulesagent.generate.answer import GEN_EFFORT, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.pricing import cost_usd, check_freshness  # noqa: E402

VECTOR_MODEL = "voyage-4-large"

APPROVED_CEILING_USD = 0.40
# Jon's approval for this task (task-caching brief): "You are approved to run
# it once, up to $0.40." This is a stop-and-report guard, not a hard abort
# mid-run -- see main() below.

# Must match frontend/index.html's EXAMPLES exactly (byte-for-byte): the
# cache key is built from _normalize_question(), which only folds case and
# whitespace, not paraphrase -- a visitor's click sends this exact text.
EXAMPLES = [
    "If my creature has trample and deathtouch, how much damage can trample "
    "over the blocker?",
    "Can I respond to a land being played?",
    "How does cascade interact with the stack?",
    "If I copy [Emrakul, the Promised End]'s cast trigger, do I control two turns?",
]


def main() -> int:
    print("This spends real Anthropic API credits: ~$0.05 x "
          f"{len(EXAMPLES)} question(s) = ~${0.05 * len(EXAMPLES):.2f} total. "
          f"Approved ceiling for this run: ${APPROVED_CEILING_USD:.2f}.")

    for warning in check_freshness():
        print(f"WARNING: {warning}", file=sys.stderr)

    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    # Same construction lifespan() uses in production: ruling_select on, live
    # Scryfall, effort=GEN_EFFORT -- so the cached answers match what a real
    # request would generate right now, and _example_cache_key's config
    # fields (model/effort/system_version/rewrite_version) match production's
    # defaults.
    agent = RulesAgent(store, effort=GEN_EFFORT)
    api_main._state["agent"] = agent
    api_main._state["chunk_map"] = agent.chunk_map

    total = 0.0
    warmed = 0
    for q in EXAMPLES:
        if total >= APPROVED_CEILING_USD:
            print(f"\nSTOPPING: spent ${total:.4f} so far, at/over the "
                  f"${APPROVED_CEILING_USD:.2f} approved ceiling, with "
                  f"{len(EXAMPLES) - warmed} question(s) left unwarmed.")
            return 1
        req = api_main.AnswerRequest(question=q, history=[])
        resp = api_main.answer(req)
        usage = dict(getattr(agent, "last_usage", None) or {})
        cost = cost_usd(
            agent.model,
            input_tokens=usage.get("input_tokens") or 0,
            output_tokens=usage.get("output_tokens") or 0,
            cache_read_tokens=usage.get("cache_read_input_tokens") or 0,
            cache_write_tokens=usage.get("cache_creation_input_tokens") or 0,
        ) or 0.0
        total += cost
        warmed += 1
        payload = api_main._response_to_cache_payload(resp, agent)
        api_main._store_example_cache(q, agent, payload)
        print(f"[{warmed}/{len(EXAMPLES)}] ${cost:.4f}  answered={resp.answered}  {q[:60]}")

    print(f"\nwarmed {warmed}/{len(EXAMPLES)} example(s), total spent: ${total:.4f}")
    if total > APPROVED_CEILING_USD:
        print(f"NOTE: total exceeded the ${APPROVED_CEILING_USD:.2f} approved "
              f"ceiling -- report this before running again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Phase 1 of the production-fidelity (v2/raw) prompt-cache build (Jon,
2026-07-27): warm data/cache.db's `rewrite` table with REAL claude-haiku-4-5
query rewrites for every question in evals/questions_rules86.jsonl (86 rows)
and evals/rulesguru_full_v2.jsonl (1409 rows), under rewrite_version="v2".

WHY THIS SCRIPT EXISTS, SEPARATELY FROM THE CACHE BUILDERS: the two model
scripts (build_ab_real_prompts.py, build_purerules_real_prompts.py) both
stamp rewrite_version="none" specifically because production's v2 rewrite is
a live claude-haiku-4-5 call, and those experiments were zero-Anthropic-call
by design. This run is DIFFERENT: the coordinator explicitly authorized up to
$3.00 of Anthropic spend on claude-haiku-4-5 rewrite calls ONLY, because the
whole point of this cache is to match the shipped v2/raw config, and a stamp
of "v2" without the rewrite actually having run would be a lie baked into the
eval.

SAFETY -- why the actual cache-building scripts (build_rules86_real_prompts_
v2raw.py, build_rulesguru_full_prompts_v2raw.py) can stay 100% Anthropic-free
even though they build a v2-rewritten cache: rewrite_query()
(rulesagent/retrieve/rewrite.py) checks its own SQLite cache FIRST and
returns immediately on a hit, never touching the `client` argument at all.
So once this script has warmed every question's (model, version, n, question)
key, running RulesAgent.answer() against a fake client that raises the
instant .messages.parse() is called (the _RecordingClient/_Recorded pattern
run_openrouter_arm.py's _capture_prompt() already uses) is safe: the rewrite
call is served from cache before the fake client is ever touched, and the
fake client only intercepts the FINAL generation call, which this script
neither reaches nor pays for.

BUDGET: hard stops (raises SystemExit) if running actual spend would exceed
$3.00, computed from REAL per-call token usage via rulesagent.pricing.cost_usd
-- never estimated in advance.

Run: uv run python evals/warm_rewrite_cache_v2.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import anthropic  # noqa: E402

from rulesagent.cache import KVCache  # noqa: E402
from rulesagent.generate.answer import REWRITE_MODEL, REWRITE_N  # noqa: E402
from rulesagent.pricing import cost_usd  # noqa: E402
from rulesagent.retrieve.rewrite import rewrite_query  # noqa: E402
from rulesagent.tools.scryfall import parse_card_refs  # noqa: E402

REPO = Path(__file__).parent.parent
RULES86 = REPO / "evals" / "questions_rules86.jsonl"
RULESGURU = REPO / "evals" / "rulesguru_full_v2.jsonl"
REWRITE_VERSION = "v2"
BUDGET_USD = 3.00
# Incremental, IMMEDIATELY-FLUSHED per-call cost log (fixes a real bug hit
# 2026-07-27: the first run of this script piped stdout to a file, which is
# BLOCK-buffered on a piped subprocess -- when the harness killed the process
# mid-run, every print() since the last OS-level flush was lost, including
# the final "Actual spend" summary, even though the SQLite cache writes
# themselves were already durable (KVCache.put() commits per row). This file
# is opened in line-buffered append mode and written+flushed after EVERY
# call, so a kill at any point leaves an accurate, resumable record of real
# spend -- never trust a buffered stdout print alone for money accounting.
COST_LOG = REPO / "evals" / "answers" / "_rewrite_warm_cost_log.jsonl"


class _UsageTrackingClient:
    """Wraps a real anthropic.Anthropic client. Passes every call straight
    through unchanged -- rewrite_query() only ever calls
    client.messages.parse(**kwargs) -- but records the real usage off each
    response so this script can compute and enforce actual spend, not an
    estimate."""

    def __init__(self, real_client: anthropic.Anthropic, log_path: Path):
        self._real = real_client
        self.messages = self
        self.total_cost = 0.0
        self.n_calls = 0
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        # Line-buffered (buffering=1) + explicit flush per write below --
        # belt and suspenders, since this is the one record that must
        # survive a kill.
        self._log_f = open(self._log_path, "a", encoding="utf-8", buffering=1)

    def parse(self, **kwargs):
        response = self._real.messages.parse(**kwargs)
        u = response.usage
        in_tok = getattr(u, "input_tokens", 0) or 0
        out_tok = getattr(u, "output_tokens", 0) or 0
        cr_tok = getattr(u, "cache_read_input_tokens", 0) or 0
        cw_tok = getattr(u, "cache_creation_input_tokens", 0) or 0
        c = cost_usd(
            REWRITE_MODEL, input_tokens=in_tok, output_tokens=out_tok,
            cache_read_tokens=cr_tok, cache_write_tokens=cw_tok,
        )
        self.total_cost += c or 0.0
        self.n_calls += 1
        self._log_f.write(json.dumps({
            "n": self.n_calls, "input_tokens": in_tok, "output_tokens": out_tok,
            "cache_read_tokens": cr_tok, "cache_write_tokens": cw_tok,
            "cost_usd": c, "running_total_usd": self.total_cost,
        }) + "\n")
        self._log_f.flush()
        if self.total_cost > BUDGET_USD:
            raise SystemExit(
                f"[BUDGET STOP] cumulative real spend ${self.total_cost:.4f} exceeds "
                f"${BUDGET_USD:.2f} authorized -- stopping immediately, "
                f"{self.n_calls} calls made so far"
            )
        return response


def load_stripped(path: Path) -> list[str]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            stripped, _refs = parse_card_refs(row["question"])
            out.append(stripped)
    return out


def main() -> None:
    questions = load_stripped(RULES86) + load_stripped(RULESGURU)
    # Dedupe -- rewrite_query's cache key is purely (model, version, n,
    # question text), so identical stripped text across the two files (or
    # within one) only needs to be paid for once.
    unique = list(dict.fromkeys(questions))
    print(f"{len(questions)} question rows -> {len(unique)} unique stripped questions")

    cache = KVCache("rewrite")

    def cache_key(q: str) -> str:
        return json.dumps([REWRITE_MODEL, REWRITE_VERSION, REWRITE_N, q])

    missing = [q for q in unique if cache.get(cache_key(q)) is None]
    print(f"already warm: {len(unique) - len(missing)}/{len(unique)}")
    print(f"to warm now: {len(missing)}")

    if not missing:
        print("nothing to do -- every question already has a v2/n=3 rewrite cached")
        return

    real_client = anthropic.Anthropic()
    tracking_client = _UsageTrackingClient(real_client, COST_LOG)
    print(f"cost log: {COST_LOG}")

    def is_degenerate(queries: list[str]) -> bool:
        # Two distinct failure shapes rewrite_query() can hand back that a
        # naive "queries == [question]" check misses:
        # (1) the documented fallback (queries == [original question] -- not
        #     cached by rewrite_query() itself, so a re-run just retries), and
        # (2) a genuinely PARSED-but-degenerate structured response -- e.g.
        #     the model returns fewer than n queries and/or one is an empty
        #     string (rg6547 "Who would win: Deadpool vs. Spider-Man?" did
        #     exactly this: parsed.queries == [""], which passed
        #     _Rewrites' schema, got cached as a "real" rewrite by
        #     rewrite_query(), and later crashed embed_query() -- Voyage
        #     rejects empty-string input outright). This IS cached by
        #     rewrite_query() (parsed.queries was truthy), so unlike (1) it
        #     needs to be actively detected and purged here, not just
        #     retried.
        return any((not s) or not s.strip() for s in queries)

    n_ok, n_fallback, n_degenerate = 0, 0, 0
    for i, q in enumerate(missing, 1):
        result = rewrite_query(
            q, REWRITE_MODEL, REWRITE_N, tracking_client,
            context=None, version=REWRITE_VERSION,
        )
        # A fallback (queries == [original question]) after a REAL call means
        # the model call itself failed/parsed-empty -- rewrite_query() does
        # NOT cache that, so the next attempt would just retry (and re-pay).
        # Flag it loudly rather than silently accepting a degraded rewrite as
        # "done".
        if result.queries == [q] and REWRITE_N != 1:
            n_fallback += 1
            print(f"  [{i}/{len(missing)}] [WARN] fallback (no real rewrite) for: {q[:80]!r}")
        elif is_degenerate(result.queries):
            # This one WAS cached (a truthy-but-empty queries list is still
            # truthy) -- purge it immediately so a re-run of this script
            # retries it for real instead of reading the same degenerate
            # cache entry back forever.
            n_degenerate += 1
            key = cache_key(q)
            cache.get(key)  # no-op read, just documents the key being purged
            import sqlite3 as _sqlite3
            _conn = _sqlite3.connect(cache.db_path)
            _conn.execute(f'DELETE FROM "{cache.table}" WHERE key = ?', (key,))
            _conn.commit()
            _conn.close()
            print(f"  [{i}/{len(missing)}] [WARN] DEGENERATE rewrite (empty/blank query) for: "
                  f"{q[:80]!r} -> queries={result.queries!r} -- purged from cache, will retry")
        else:
            n_ok += 1
        if i % 50 == 0 or i == len(missing):
            print(f"  [{i}/{len(missing)}] warmed | running cost ${tracking_client.total_cost:.4f} "
                  f"| calls={tracking_client.n_calls}")

    print(f"\nDone. {n_ok} real rewrites cached, {n_fallback} fallbacks (uncached, will retry), "
          f"{n_degenerate} degenerate (purged, will retry).")
    print(f"Actual Anthropic calls: {tracking_client.n_calls}")
    print(f"Actual spend: ${tracking_client.total_cost:.4f} (budget ${BUDGET_USD:.2f})")

    still_missing = [q for q in unique if cache.get(cache_key(q)) is None]
    print(f"still missing after this run: {len(still_missing)}")


if __name__ == "__main__":
    main()

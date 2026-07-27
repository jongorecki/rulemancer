"""Shared capture helper for the production-fidelity (v2/raw) cache builders
(evals/build_rules86_real_prompts_v2raw.py, evals/build_rulesguru_full_
prompts_v2raw.py). Jon, 2026-07-27.

Runs the REAL RulesAgent.answer() pipeline -- rewrite, card resolution,
per-card raw-mode ruling selection, retrieval, cross-ref expansion,
build_prompt() -- against a fake client that raises the instant the
generation call would go out (same _RecordingClient/_Recorded pattern
evals/run_openrouter_arm.py's _capture_prompt() uses), and returns everything
a builder needs to both write the cache row and verify it.

SAFETY: this NEVER makes a live Anthropic call, for two independent reasons:
(1) the client passed to RulesAgent is a fake that only raises, never sends
HTTP; (2) rewrite_query() (rulesagent/retrieve/rewrite.py) checks its own
SQLite cache BEFORE ever touching the client argument, so as long as
evals/warm_rewrite_cache_v2.py has already warmed every question's
(claude-haiku-4-5, "v2", 3, question) rewrite, the rewrite step here is a
pure cache read. If a question's rewrite is NOT warm, rewrite_query()'s own
broad `except Exception` will catch the fake client's _Recorded exception and
silently degrade to a same-as-original fallback rewrite -- so this module's
capture() raises loudly if it detects that (rewritten.queries == [question],
i.e. no real rewrite happened) rather than letting a silently-degraded cache
row through.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import rulesagent.index.store as _store_mod  # noqa: E402
import rulesagent.tools.ruling_retrieval as _ruling_mod  # noqa: E402
from rulesagent.generate.answer import RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402

# --- Voyage call instrumentation (verification req #7) ---------------------
# store.search() and ruling_retrieval.select_rulings() each imported
# embed_query/embed_documents with `from ... import ...`, which binds a LOCAL
# name in THEIR module namespace at import time -- patching
# rulesagent.index.embed.embed_query after that point would not affect either
# call site. So the counting wrappers are installed directly on the two
# consuming modules' own namespaces instead, capturing the exact call shape
# (query text, count) each site actually issues.
VOYAGE_QUERY_CALLS = {"retrieval": 0, "ruling_select": 0}
VOYAGE_DOCUMENT_CALLS = {"ruling_docs_new": 0, "ruling_docs_texts": 0}

_real_store_embed_query = _store_mod.embed_query
_real_ruling_embed_query = _ruling_mod.embed_query
_real_ruling_embed_documents = _ruling_mod.embed_documents


def _counting_store_embed_query(text, model):
    VOYAGE_QUERY_CALLS["retrieval"] += 1
    return _real_store_embed_query(text, model)


def _counting_ruling_embed_query(text, model):
    VOYAGE_QUERY_CALLS["ruling_select"] += 1
    return _real_ruling_embed_query(text, model)


def _counting_ruling_embed_documents(texts, model):
    VOYAGE_DOCUMENT_CALLS["ruling_docs_new"] += 1
    VOYAGE_DOCUMENT_CALLS["ruling_docs_texts"] += len(texts)
    return _real_ruling_embed_documents(texts, model)


_store_mod.embed_query = _counting_store_embed_query
_ruling_mod.embed_query = _counting_ruling_embed_query
_ruling_mod.embed_documents = _counting_ruling_embed_documents
# ----------------------------------------------------------------------------


class _Recorded(Exception):
    pass


class _RecordingClient:
    def __init__(self):
        self.messages = self

    def parse(self, **kwargs):
        self.kwargs = kwargs
        raise _Recorded


class CaptureResult:
    __slots__ = (
        "system", "user", "retrieved_rule_ids", "rewritten_queries",
        "n_cards", "unresolved_refs", "has_card_data_block",
    )

    def __init__(self, system, user, retrieved_rule_ids, rewritten_queries,
                 n_cards, unresolved_refs, has_card_data_block):
        self.system = system
        self.user = user
        self.retrieved_rule_ids = retrieved_rule_ids
        self.rewritten_queries = rewritten_queries
        self.n_cards = n_cards
        self.unresolved_refs = unresolved_refs
        self.has_card_data_block = has_card_data_block


# rg6547 ("Who would win: Deadpool vs. Spider-Man?", evals/rulesguru_full_v2
# .jsonl) is a confirmed, reproducible exception: 8 separate REAL
# claude-haiku-4-5 v2-rewrite attempts (2026-07-27, evals/
# warm_rewrite_cache_v2.py) never produced a usable rewrite -- 6 hit the
# documented empty-parse fallback (queries==[question]), 2 produced a
# distinct degenerate shape (queries==['']) that also can't reach embed_query
# (Voyage rejects empty-string input). This is a genuine, stable property of
# this off-topic joke question against the shipped rewriter, not a cold-cache
# artifact -- so unlike every other row, a fallback-shaped result here is
# EXPECTED and gets waved through rather than raising. Any OTHER qid landing
# on this shape still raises loudly (see the check below) -- this allowlist
# is deliberately a single confirmed id, not a general escape hatch.
_KNOWN_REWRITE_FALLBACK_QIDS = {"rg6547"}


def capture(store: VectorStore, question: str, qid: str) -> CaptureResult:
    """Capture the exact production v2/raw prompt for `question`. Raises
    RuntimeError loudly (never silently degrades) if:
    - the generation call never fires (fake client not reached -- would mean
      the agent errored out before generation, which should never happen on
      these clean rows), or
    - rewrite_version="v2" silently fell back to a same-as-original rewrite,
      which only happens when the rewrite cache was cold (a sign
      warm_rewrite_cache_v2.py needs to run again for this question)."""
    client = _RecordingClient()
    agent = RulesAgent(
        store, client=client, card_no_refresh=True,
        rewrite=True, rewrite_version="v2", ruling_query_mode="raw",
    )
    try:
        agent.answer(question)
    except _Recorded:
        pass
    else:
        raise RuntimeError(
            f"{qid}: expected _Recorded but answer() returned normally -- "
            "the fake client never intercepted a generation call"
        )

    kw = client.kwargs
    system = kw["system"]
    user = kw["messages"][0]["content"]

    rewritten = agent.last_rewritten
    if rewritten is None:
        raise RuntimeError(f"{qid}: agent.last_rewritten is None -- rewrite=True but no rewrite ran")
    if rewritten.queries == [question]:
        if qid not in _KNOWN_REWRITE_FALLBACK_QIDS:
            raise RuntimeError(
                f"{qid}: rewrite fell back to the original question -- this means "
                f"the v2 rewrite cache was COLD for this question and rewrite_query() "
                f"silently degraded (its own broad except-Exception swallowed the fake "
                f"client's interception). Run evals/warm_rewrite_cache_v2.py again -- "
                f"this question is not actually covered yet. question={question!r}"
            )
        # else: a confirmed, documented exception (see
        # _KNOWN_REWRITE_FALLBACK_QIDS above) -- proceed with the fallback
        # single-query retrieval, exactly what a live production call would
        # also do for this row.

    retrieved_ids = [r.chunk.source_id for r in agent.last_retrieved] if agent.last_retrieved else []
    unresolved = agent.last_unresolved_refs or []
    n_cards = len(agent.last_cards or [])
    has_card_block = "\n\nCard data:\n" in user

    return CaptureResult(
        system=system, user=user, retrieved_rule_ids=retrieved_ids,
        rewritten_queries=list(rewritten.queries), n_cards=n_cards,
        unresolved_refs=unresolved, has_card_data_block=has_card_block,
    )

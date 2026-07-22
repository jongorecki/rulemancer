"""Query rewriting -- translate a casual question into the Comprehensive
Rules' own vocabulary before retrieval. Plan #3a
(docs/plan-3a-query-rewriting.md).

The problem this fixes (proven in the pre-build spike, see the plan): a
question and the rule that answers it can share almost no vocabulary --
"can I respond to a cost being paid?" never says "priority" or "casting a
spell is a single action," so it barely embeds near the rule that actually
answers it. Rewriting into the corpus's own words before embedding closes
that gap; the spike measured a 50x rank improvement on one rule (108 -> 2).

Rewriting is a small translation task, not the reasoning step -- the
generator (RulesAgent) stays pinned to claude-sonnet-5 regardless of which
model rewrites. See evals/run_eval.py for the model/rewrite-count comparison
this module feeds, and generate/answer.py for the shipped config.
"""

import json

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from rulesagent.cache import KVCache
from rulesagent.contracts import RewrittenQuery

load_dotenv()

# Models that accept the temperature sampling parameter. claude-sonnet-5,
# Opus 4.7+, and Fable reject it with a 400; Haiku 4.5 (an older tier) accepts
# it. Used to pin temperature=0 on the shipped Haiku rewriter for stability
# without breaking the eval's Sonnet comparison arms.
TEMPERATURE_OK = {"claude-haiku-4-5"}

PROMPT_VERSION = "v1"
# v2 (scope-preservation + keep-defined-term bullets) was A/B'd and REVERTED
# for the shipped rw1-haiku config: it lifted the sonnet arms but cost the
# haiku-n=1 arm 9 pts of recall@5 (77% -> 68%). It fixed q025's glossary miss
# but reintroduced a q010 miss and zeroed out clarification-field population.
# Net negative for the cell we ship. Kept documented in DECISIONS.md as a
# measured finding, not carried in the code.
# Part of the disk-cache key below (see rewrite_query) -- editing SYSTEM
# changes what a cached entry actually means, so bumping/changing this
# busts the cache automatically instead of silently serving rewrites made
# under a different prompt.

# Copied verbatim from the pre-build spike (scratch script, never committed)
# that validated this approach -- see the plan's "Step 0 -- the spike".
# Deliberately general: no MTG examples, no rule numbers, no wording drawn
# from evals/questions.jsonl, so this can't be overfit to the 31-question
# eval set (see the plan's "Anti-overfit guards").
SYSTEM = """You rewrite casual Magic: The Gathering rules questions into the \
vocabulary the official Comprehensive Rules actually use, so that a semantic \
search over the rules text finds the rules that answer them.

The rules use precise technical language that players rarely say out loud. \
Rewrite the question the way the rules themselves would phrase it, and name \
the underlying game concepts likely at issue (for example: priority, the \
stack, zones, steps and phases, timing, state-based actions, or the discrete \
parts of casting a spell or activating an ability).

Requirements:
- Produce exactly {n} distinct rewrite(s). With more than one, each must \
attack the question from a genuinely different angle rather than restating \
the same phrasing.
- Never include rule numbers. You do not know them, and a wrong number \
poisons the search.
- Each rewrite is a self-contained question or statement, not a keyword list.
- Set clarification ONLY if the correct answer would materially differ \
between readings (player count, which of two cards is meant, a named \
format). Most questions need none -- leave it null."""


class _Rewrites(BaseModel):
    """Wire schema for the structured-output call -- just the two fields the
    model actually produces. `original` isn't asked of it (the question is
    already the user-turn content); rewrite_query() below fills that in when
    it builds the public RewrittenQuery."""

    queries: list[str]
    clarification: str | None = None


_cache = KVCache("rewrite")
# L3 (docs/plan-l3-sqlite-caches.md): one row per (model, PROMPT_VERSION, n,
# question) in data/cache.db's `rewrite` table. Per-op connections -- no
# module-level dict layer to go stale under a concurrent writer.


def rewrite_query(
    question: str,
    model: str,
    n: int,
    client: anthropic.Anthropic | None = None,
    context: str | None = None,
) -> RewrittenQuery:
    """Rewrite `question` into `n` Comprehensive-Rules-vocabulary rewrites.

    SQLite-cached (data/cache.db, `rewrite` table) by (model, PROMPT_VERSION,
    n, question) -- same discipline as the query-embedding and rerank caches
    in evals/run_eval.py. A second call with the same key makes zero API
    calls; a row is only written when a new entry is actually added, so
    re-runs with unchanged inputs touch disk but never rewrite it.

    `context` (optional) is a condensed transcript of earlier conversation
    turns. When present, the model is asked to resolve the FINAL question's
    references against it ("what if it's phased out?" -> a standalone query),
    and the cache is BYPASSED entirely -- read and write. Conversational
    rewrites are interactive one-offs: caching them would either collide with
    the single-turn key for the same question text or bloat the eval cache
    with keys the eval never uses. The evals are single-turn (context=None),
    so their cache behavior is byte-identical to before this parameter.

    Never raises and never returns an empty `queries` list: a failed or
    unparseable response (refusal, truncation, network error) falls back to
    RewrittenQuery(original, [original], None) so retrieval always has
    something to search for -- rewriting must never block or crash the
    agent, only help it when it can.
    """
    key = json.dumps([model, PROMPT_VERSION, n, question])
    if context is None:
        cached = _cache.get(key)
        if cached is not None:
            queries, clarification = json.loads(cached)
            return RewrittenQuery(original=question, queries=queries, clarification=clarification)

    client = client or anthropic.Anthropic()
    parsed = None
    # temperature=0 cuts (does not eliminate) the run-to-run variance in the
    # rewrites -- measured: without it, rw1-haiku recall@5 swung 68-77% across
    # clean re-runs because each run drew different rewrites. But sampling
    # params are REJECTED (400) on claude-sonnet-5 / Opus 4.7+ / Fable, and
    # ACCEPTED on Haiku 4.5 (an older tier). We ship Haiku, so this stabilizes
    # the shipped path; the eval's sonnet arms stay at default sampling and are
    # only used for comparison. Gate by model rather than pass it blindly.
    extra = {"temperature": 0} if model in TEMPERATURE_OK else {}
    try:
        # 2048: smaller than answer.py's 4096 since there's no retrieved-rules
        # context to read here, just the bare question -- but still enough
        # headroom that claude-sonnet-5's default adaptive thinking doesn't
        # eat the whole budget and truncate the structured output to nothing
        # (the same failure mode answer.py's max_tokens comment documents).
        content = question
        if context is not None:
            # Contextualize a conversational follow-up: the rewrites must stand
            # alone (retrieval sees only the rewrite string, never the thread).
            content = (
                "Conversation so far, for context only:\n"
                f"{context}\n\n"
                "Rewrite ONLY this final follow-up question. Use the "
                "conversation above ONLY to resolve pronouns and references "
                "(\"it\", \"that card\", \"the trigger\") into their concrete "
                "names -- do NOT import earlier turns' topics. The rewrites "
                "must target what THIS question asks about; if it shifts to a "
                "new topic, follow the shift and drop the old topic entirely. "
                "Each rewrite must be fully standalone:\n"
                f"{question}"
            )
        response = client.messages.parse(
            model=model,
            max_tokens=2048,
            system=SYSTEM.format(n=n),
            messages=[{"role": "user", "content": content}],
            **extra,
            output_format=_Rewrites,
        )
        parsed = response.parsed_output
    except Exception:
        # Broad on purpose: any failure here (API error, network error,
        # refusal, malformed output) degrades to the fallback below rather
        # than propagating -- a rewriter outage must never take retrieval
        # down with it.
        parsed = None

    if parsed is None or not parsed.queries:
        # NOT cached, deliberately. Caching a fallback would freeze a transient
        # failure (network blip, refusal, truncation) into the eval forever:
        # that question would silently never be rewritten again, and because
        # the cache makes it reproducible, the degradation would look
        # deterministic and correct. Leaving it uncached means the next run
        # retries. The cost of that choice is that a persistently failing
        # question re-hits the API every run -- which is the loud failure
        # mode, and the one we want.
        return RewrittenQuery(original=question, queries=[question], clarification=None)

    result = RewrittenQuery(
        original=question, queries=parsed.queries, clarification=parsed.clarification
    )
    if context is None:  # conversational rewrites are never cached (see docstring)
        _cache.put(key, json.dumps([result.queries, result.clarification]).encode("utf-8"))
    return result

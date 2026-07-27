"""Model pricing — cached from the `claude-api` skill, with an expiry.

WHY THIS EXISTS. Pricing must never be asserted from memory; the authority is the
`claude-api` skill. But loading that skill costs tens of thousands of tokens, and
we were paying it repeatedly to re-confirm two numbers that change rarely. This
module is the cache: check the skill once, record what it said and when, and let
every caller import from here.

WHY A CACHE IS SAFE HERE BUT MEMORY IS NOT. Recalled pricing is stale silently --
there is no timestamp on a memory and nothing forces a re-check. A cache is only
better if it *knows when it is old*, so this one carries `CHECKED_ON`, the source
it came from, and two expiry mechanisms:

**1. A staleness horizon.** Past `STALE_AFTER_DAYS`, `check_freshness()` reports
that the cache needs re-confirming against the skill.

**2. Scheduled changes, which matter more.** A generic "is it old?" check would
have missed the live case: Claude Sonnet 5 runs on introductory pricing that ends
2026-08-31, after which input goes $2 -> $3 and output $10 -> $15 per MTok. That
is a *known future* change, not staleness -- a cache refreshed the day before
would still be wrong the day after. `SCHEDULED_CHANGES` records dated changes we
already know about so a caller is warned before the date, not after.

HOW TO REFRESH. Load the `claude-api` skill, read the current-models table,
update `PRICING` and `SCHEDULED_CHANGES`, and set `CHECKED_ON` to today. That is
the only sanctioned way to change these numbers -- not from recall, and not from
a web search.
"""
from __future__ import annotations

from datetime import date

# --- the cache -------------------------------------------------------------

CHECKED_ON = date(2026, 7, 26)
SOURCE = "claude-api skill, Current Models table"
STALE_AFTER_DAYS = 90

# model id -> (input $/MTok, output $/MTok)
PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.00, 50.00),
    "claude-mythos-5": (10.00, 50.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),          # standard; see intro rate below
    "claude-sonnet-5@intro": (2.00, 10.00),    # introductory, ends 2026-08-31
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Prompt-caching tiers. A cached read bills at ~0.1x the input rate; a 5-minute
# TTL cache write bills at 1.25x (a 1-hour TTL write is 2x -- add it here if we
# ever use one).
CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25

# Message Batches API: a 50% discount on ALL token usage for a request run
# through the batch endpoint instead of a synchronous call -- confirmed via
# the claude-api skill's Batches API quick reference ("processes Messages API
# requests asynchronously at 50% of standard prices") and
# python/claude-api/batches.md ("Key Facts: 50% cost reduction on all token
# usage"). This module had no batch-rate concept before evals/run_answer_eval.py
# grew --batch support; applies uniformly to input, output, and both cache
# tiers, same as the skill describes -- there's no separate batch-cache rate.
BATCH_DISCOUNT = 0.5

# Dated changes we already know are coming. Each: (effective date, what changes).
SCHEDULED_CHANGES: list[tuple[date, str]] = [
    (date(2026, 8, 31),
     "claude-sonnet-5 introductory pricing ends: $2/$10 -> $3/$15 per MTok. "
     "Any sonnet cost comparison computed before this date understates it."),
]


def check_freshness(today: date | None = None) -> list[str]:
    """Warnings a caller should surface. Empty list means the cache is trustworthy.

    Returns strings rather than raising: a stale price should make a report say
    so, not crash a run that is doing something else.
    """
    today = today or date.today()
    out: list[str] = []
    age = (today - CHECKED_ON).days
    if age > STALE_AFTER_DAYS:
        out.append(
            f"pricing cache is {age} days old (checked {CHECKED_ON}, horizon "
            f"{STALE_AFTER_DAYS}d) — re-confirm against the claude-api skill"
        )
    for when, what in SCHEDULED_CHANGES:
        if today >= when:
            out.append(f"scheduled price change took effect {when}: {what}")
        elif (when - today).days <= 30:
            out.append(f"price change in {(when - today).days} days ({when}): {what}")
    return out


def rate(model: str, today: date | None = None) -> tuple[float, float] | None:
    """(input, output) $/MTok for `model`, or None if we have no price for it.

    Returning None rather than guessing is deliberate: an unpriced model must
    render as "unknown", never as a plausible number.

    Sonnet 5 resolves to its introductory rate until the scheduled end date and
    the standard rate afterwards, so a cost computed today and the same cost
    computed in September do not silently disagree.
    """
    today = today or date.today()
    if model == "claude-sonnet-5":
        intro_ends = next((d for d, _ in SCHEDULED_CHANGES if "sonnet-5" in _), None)
        if intro_ends and today < intro_ends:
            return PRICING["claude-sonnet-5@intro"]
    return PRICING.get(model)


def cost_usd(model: str, *, input_tokens: int = 0, output_tokens: int = 0,
             cache_read_tokens: int = 0, cache_write_tokens: int = 0,
             batch: bool = False, today: date | None = None) -> float | None:
    """Total USD for one call's token usage, or None if the model is unpriced.

    Cache tiers are billed separately because a cached read costs a tenth of a
    fresh input token -- folding them together overstates cost on any arm using
    prompt caching, which is all of ours.

    `batch=True` applies BATCH_DISCOUNT (50% off) to the whole total -- pass it
    for any row generated through the Message Batches API (evals/
    run_answer_eval.py --batch stamps a `"batch"` field on each row precisely
    so callers here know which rate applies). Getting this wrong in either
    direction misreports spend: omitting it on a batch row overstates cost by
    2x, and passing it for a synchronous row understates cost by half.
    """
    r = rate(model, today)
    if r is None:
        return None
    pin, pout = r
    total = (
        input_tokens * pin
        + cache_write_tokens * pin * CACHE_WRITE_MULT
        + cache_read_tokens * pin * CACHE_READ_MULT
        + output_tokens * pout
    ) / 1_000_000
    if batch:
        total *= BATCH_DISCOUNT
    return total

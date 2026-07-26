"""rulesagent.pricing: the cached model-price table and its expiry.

The cache exists so we stop reloading the large `claude-api` skill to re-confirm
numbers that change rarely. It is only safer than recall if it *knows when it is
old*, so these tests hold the two expiry mechanisms rather than the numbers:

- a staleness horizon, so an unrefreshed cache eventually says so;
- dated scheduled changes, which a generic staleness check would miss entirely --
  Sonnet 5's introductory pricing ends 2026-08-31, so a cache refreshed the day
  before is still wrong the day after.

The price *values* are deliberately not asserted one-by-one; that would just
duplicate the table and make a legitimate refresh fail the suite. What is
asserted is that every entry is well-formed and that unknown models return None
rather than a plausible-looking guess.
"""
from datetime import date, timedelta

import pytest

from rulesagent import pricing as p


def test_every_entry_is_well_formed():
    for model, r in p.PRICING.items():
        assert isinstance(r, tuple) and len(r) == 2, model
        pin, pout = r
        assert pin > 0 and pout > 0, model
        assert pout > pin, f"{model}: output should cost more than input"


def test_unknown_model_returns_none_not_a_guess():
    """An unpriced model must render as 'unknown', never as a number."""
    assert p.rate("some-model-that-does-not-exist") is None
    assert p.cost_usd("some-model-that-does-not-exist", input_tokens=1000) is None


def test_fresh_cache_reports_nothing():
    just_checked = p.CHECKED_ON + timedelta(days=1)
    assert [w for w in p.check_freshness(just_checked) if "days old" in w] == []


def test_stale_cache_says_so():
    old = p.CHECKED_ON + timedelta(days=p.STALE_AFTER_DAYS + 1)
    assert any("days old" in w for w in p.check_freshness(old))


def test_scheduled_change_warns_before_and_after():
    when, _ = p.SCHEDULED_CHANGES[0]
    before = [w for w in p.check_freshness(when - timedelta(days=7)) if "price change in" in w]
    after = [w for w in p.check_freshness(when + timedelta(days=1)) if "took effect" in w]
    assert before, "should warn ahead of a known change"
    assert after, "should say a known change has landed"


def test_a_freshly_refreshed_cache_still_warns_about_a_scheduled_change():
    """The case a staleness horizon alone would miss: refreshed yesterday, wrong
    tomorrow. This is why SCHEDULED_CHANGES exists separately from CHECKED_ON."""
    when, _ = p.SCHEDULED_CHANGES[0]
    day_before = when - timedelta(days=1)
    warnings = p.check_freshness(day_before)
    assert not any("days old" in w for w in warnings), "cache is not stale here"
    assert any("price change in" in w for w in warnings), "but the change is imminent"


def test_sonnet_resolves_intro_then_standard():
    when, _ = p.SCHEDULED_CHANGES[0]
    assert p.rate("claude-sonnet-5", when - timedelta(days=1)) == p.PRICING["claude-sonnet-5@intro"]
    assert p.rate("claude-sonnet-5", when + timedelta(days=1)) == p.PRICING["claude-sonnet-5"]


def test_sonnet_costs_more_after_the_intro_period_ends():
    """Direction check: the scheduled change must raise sonnet's cost, not lower
    it. A sign error here would silently flip a model-choice recommendation."""
    when, _ = p.SCHEDULED_CHANGES[0]
    kw = dict(input_tokens=10_000, output_tokens=2_000)
    before = p.cost_usd("claude-sonnet-5", today=when - timedelta(days=1), **kw)
    after = p.cost_usd("claude-sonnet-5", today=when + timedelta(days=1), **kw)
    assert after > before


def test_cache_tiers_are_billed_separately():
    """A cached read costs ~0.1x a fresh input token. Folding them together would
    overstate cost on every arm we run, since all of them use prompt caching."""
    fresh = p.cost_usd("claude-opus-5", input_tokens=1_000_000)
    cached = p.cost_usd("claude-opus-5", cache_read_tokens=1_000_000)
    written = p.cost_usd("claude-opus-5", cache_write_tokens=1_000_000)
    assert cached == pytest.approx(fresh * p.CACHE_READ_MULT)
    assert written == pytest.approx(fresh * p.CACHE_WRITE_MULT)
    assert cached < fresh < written


def test_zero_usage_costs_nothing():
    assert p.cost_usd("claude-opus-5") == 0.0


def test_opus_5_is_priced_and_is_the_shipped_model():
    """Guards the one entry the shipped config depends on (GEN_MODEL)."""
    assert p.rate("claude-opus-5") is not None


def test_checked_on_is_not_in_the_future():
    assert p.CHECKED_ON <= date.today(), "a cache cannot have been checked tomorrow"

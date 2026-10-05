"""
Market Pulse cache freshness/session-isolation (2026-09-22, cache-
freshness audit — the follow-up review on top of the canonical-core
work). Covers every item that audit asked to be verified before the
Market Pulse slice is considered closed: dedicated namespace, no
collision with a normal research query, explicit short TTLs, structural
session/date-boundary isolation, as_of stability across a cache hit, the
cache hit still passing through the shared finalizer + AEV2 dispatch
without mutating the cached object, graceful Redis-adjacent failure
handling, and synthesis_status staying accurate on a cached response.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_search import cache as cache_mod
from app.services.ai_search import pipeline
from app.services.ai_search.core_market_pulse import CoreMarketPulse
from app.services.ai_search.response_finalize import finalize_v3_response

_IST = timezone(timedelta(hours=5, minutes=30))

_MP_RESULT = {
    "type": "market_pulse", "query": "top gainers today", "synthesis_incomplete": False,
    "generated_at": "2026-09-22T10:06:08+00:00", "market_session": "live",
    "market_status": {"status": "open"}, "indices": [{"name": "NIFTY 50", "ticker": "^NSEI", "value": "23,329.00", "change": "-0.43%", "chart": []}],
    "market_mood": "Neutral", "market_direction": "sideways",
    "market_summary": "Markets traded flat today.", "sector_narrative": "", "leading_sectors": [], "lagging_sectors": [],
    "top_gainers": [], "top_losers": [], "most_active": [], "theme_momentum": [],
    "biggest_opportunity": {"title": "IPO rush", "href": "/opportunity-radar/36", "opportunity_score": 98.0},
    "biggest_risk": None, "ai_conclusion": "", "what_to_watch_next": [],
    "what_to_watch_summary": "", "scores": {},
}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache_mod._CACHE.clear()
    yield
    cache_mod._CACHE.clear()


# ── Dedicated namespace — no collision with a normal research query ────────

def test_market_pulse_cache_key_never_collides_with_a_research_query_for_identical_text():
    query = "top gainers today"
    cache_mod.set_response(query, {"type": "research", "marker": "research-answer"})
    cache_mod.set_market_pulse_response(query, {"type": "market_pulse", "marker": "pulse-answer"})

    assert cache_mod.get_response(query)["marker"] == "research-answer"
    assert cache_mod.get_market_pulse_response(query)["marker"] == "pulse-answer"


def test_market_pulse_cache_uses_its_own_key_prefix():
    with patch("app.services.ai_search.cache._set") as set_spy:
        cache_mod.set_market_pulse_response("top gainers today", dict(_MP_RESULT))
    key = set_spy.call_args.args[0]
    assert key.startswith("v3:mp:exact:")
    assert not key.startswith("v3:exact:")


# ── TTLs are short and explicit ─────────────────────────────────────────────

def test_ttls_are_short_and_bounded():
    """Locks in the exact bounds this audit approved — a future change
    that widens either constant should have to consciously edit this
    test, not silently regress cache freshness or Opportunity-staleness
    risk (see cache.py's own docstring for why CLOSED stays far shorter
    than the research-answer EXACT_TTL)."""
    assert cache_mod.MARKET_PULSE_TTL_LIVE == 45
    assert cache_mod.MARKET_PULSE_TTL_CLOSED == 300
    assert cache_mod.MARKET_PULSE_TTL_LIVE < cache_mod.MARKET_PULSE_TTL_CLOSED < cache_mod.EXACT_TTL


# ── Structural session/date-boundary isolation ──────────────────────────────

def _at(hour: int, minute: int, day: int = 22) -> datetime:
    # 2026-09-22 is a real Tuesday (a normal trading weekday) in this
    # engagement's own established "today" — used as the anchor so these
    # times land on genuinely real, already-verified trading/non-trading
    # dates rather than an arbitrary invented calendar.
    return datetime(2026, 9, day, hour, minute, tzinfo=_IST)


def _session_for(dt: datetime) -> str:
    from app.services.intelligence.engine import _market_session
    return _market_session(dt)


@pytest.mark.parametrize("hour_a,minute_a,hour_b,minute_b,label", [
    (9, 0, 9, 30, "pre_market -> live"),
    (15, 20, 15, 40, "live -> post_market"),
])
def test_cache_cannot_cross_a_session_boundary_same_day(hour_a, minute_a, hour_b, minute_b, label):
    session_a = _session_for(_at(hour_a, minute_a))
    session_b = _session_for(_at(hour_b, minute_b))
    assert session_a != session_b, f"test setup assumes {label} is a real session change"

    with patch("app.services.ai_search.cache.datetime") as mock_dt:
        mock_dt.now.return_value = _at(hour_a, minute_a)
        cache_mod.set_market_pulse_response("top gainers today", {"marker": "before-boundary"})

        mock_dt.now.return_value = _at(hour_b, minute_b)
        result = cache_mod.get_market_pulse_response("top gainers today")

    assert result is None, f"a cached entry must not survive {label}"


def test_cache_cannot_cross_weekday_to_weekend():
    # 2026-09-25 (Friday) -> 2026-09-26 (Saturday) — a real weekday/weekend
    # pair adjacent to this engagement's own anchor date.
    friday_close = datetime(2026, 9, 25, 15, 40, tzinfo=_IST)
    saturday_morning = datetime(2026, 9, 26, 10, 0, tzinfo=_IST)

    with patch("app.services.ai_search.cache.datetime") as mock_dt:
        mock_dt.now.return_value = friday_close
        cache_mod.set_market_pulse_response("top gainers today", {"marker": "friday"})

        mock_dt.now.return_value = saturday_morning
        result = cache_mod.get_market_pulse_response("top gainers today")

    assert result is None


def test_cache_cannot_cross_one_trading_date_to_another_even_within_the_closed_ttl():
    """The scenario the audit specifically flagged: two moments 20 minutes
    apart, both classified "weekend" by the coarse session label alone,
    but on DIFFERENT calendar dates — the bucket must still differ
    because it also encodes the IST date, not session label alone."""
    saturday_late = datetime(2026, 9, 26, 23, 59, tzinfo=_IST)
    sunday_early = datetime(2026, 9, 27, 0, 19, tzinfo=_IST)  # 20 minutes later, within a 300s TTL many times over... but truly a different date

    with patch("app.services.ai_search.cache.datetime") as mock_dt:
        mock_dt.now.return_value = saturday_late
        cache_mod.set_market_pulse_response("top gainers today", {"marker": "saturday"})

        mock_dt.now.return_value = sunday_early
        result = cache_mod.get_market_pulse_response("top gainers today")

    assert result is None


def test_cache_hit_within_the_same_session_and_date_still_works():
    """The positive case — proves the isolation tests above are actually
    testing boundary-crossing, not just "the cache never hits."""
    live_a = datetime(2026, 9, 22, 10, 0, tzinfo=_IST)
    live_b = datetime(2026, 9, 22, 10, 0, 20, tzinfo=_IST)  # 20s later, same session+date, within the 45s live TTL

    with patch("app.services.ai_search.cache.datetime") as mock_dt:
        mock_dt.now.return_value = live_a
        cache_mod.set_market_pulse_response("top gainers today", {"marker": "fresh"})

        mock_dt.now.return_value = live_b
        result = cache_mod.get_market_pulse_response("top gainers today")

    assert result == {"marker": "fresh"}


# ── Fake-clock TTL expiration (the underlying time.time() bookkeeping,
# independent of the session/date bucket above). ────────────────────────────

def test_ttl_expiration_with_a_fake_clock():
    """Pins the session to "live" (fixed datetime.now()) so the bucket
    key never itself changes across this test — isolating exactly the
    time.time()-based TTL bookkeeping from the session/date bucketing
    covered by the tests above. Without pinning datetime.now(), this
    test would silently use whichever TTL the REAL wall-clock session
    happens to be at test-run time (live=45s vs closed=300s) — flaky by
    construction, not a real assertion about TTL expiry."""
    fake_time = {"now": 1_000_000.0}
    with patch("app.services.ai_search.cache.time.time", side_effect=lambda: fake_time["now"]), \
         patch("app.services.ai_search.cache.datetime") as mock_dt:
        mock_dt.now.return_value = _at(10, 0)  # a real Tuesday, mid-session -> "live"
        assert _session_for(_at(10, 0)) == "live"

        cache_mod.set_market_pulse_response("top gainers today", {"marker": "v1"})
        assert cache_mod.get_market_pulse_response("top gainers today") == {"marker": "v1"}

        fake_time["now"] += cache_mod.MARKET_PULSE_TTL_LIVE - 1
        assert cache_mod.get_market_pulse_response("top gainers today") == {"marker": "v1"}, "still within TTL"

        fake_time["now"] += 5  # now well past the 45s live TTL
        assert cache_mod.get_market_pulse_response("top gainers today") is None, "TTL must have expired"


# ── as_of stability, shared finalizer, no mutation of the cached object ─────

async def test_as_of_remains_the_original_collection_timestamp_on_a_cache_hit():
    async def _fake_run_market_pulse_search(query: str) -> dict:
        return dict(_MP_RESULT)

    with patch("app.services.ai_search.market_pulse._run_market_pulse_search", new=_fake_run_market_pulse_search), \
         patch("app.services.ai_search.market_pulse._detect_market_pulse_async", new=AsyncMock(return_value=True)):
        db = MagicMock()
        first_result = None
        async for _stage, _label, payload in pipeline._run_v3_steps("top gainers today", db):
            if payload is not None:
                first_result = payload
        second_result = None
        async for _stage, _label, payload in pipeline._run_v3_steps("top gainers today", db):
            if payload is not None:
                second_result = payload

    assert first_result["generated_at"] == _MP_RESULT["generated_at"]
    assert second_result["generated_at"] == _MP_RESULT["generated_at"]
    from app.services.ai_search.core_market_pulse import from_market_pulse_response
    assert from_market_pulse_response(second_result).as_of == _MP_RESULT["generated_at"]


def test_cache_hit_still_passes_through_the_shared_finalizer_and_aev2_dispatch():
    cache_mod.set_market_pulse_response("top gainers today", dict(_MP_RESULT))
    cached = cache_mod.get_market_pulse_response("top gainers today")
    assert cached is not None

    with patch("app.services.ai_search.response_finalize.assemble_aev2", return_value=None) as assemble_spy, \
         patch("app.services.ai_search.response_finalize.should_assemble", return_value=True):
        result = finalize_v3_response("top gainers today", cached, was_cached=True)

    assert assemble_spy.call_count == 1
    core_arg = assemble_spy.call_args.args[0]
    assert isinstance(core_arg, CoreMarketPulse)
    assert result["query"] == "top gainers today"


def test_aev2_assembly_never_mutates_the_cached_object_even_when_attached():
    cache_mod.set_market_pulse_response("top gainers today", dict(_MP_RESULT))
    cached = cache_mod.get_market_pulse_response("top gainers today")
    before = copy.deepcopy(cached)

    # mode PUBLIC + build-complete latch forced True only for this
    # assertion's own scope, to prove attaching answer_experience_v2
    # still never mutates the object the cache holds.
    with patch("app.services.ai_search.response_finalize.get_aev2_mode") as mode_spy, \
         patch("app.services.ai_search.aev2.mode.AEV2_BUILD_COMPLETE", True), \
         patch("app.core.security.has_valid_admin_key", return_value=True):
        from app.services.ai_search.aev2.mode import AEV2Mode
        mode_spy.return_value = AEV2Mode.PUBLIC
        finalize_v3_response("top gainers today", cached, was_cached=True)

    # The dict retrieved from the cache store itself (a second, independent
    # read) must still equal what was written — finalize_v3_response
    # returns a NEW dict when it attaches AEV2, it never writes back into
    # the cache.
    still_cached = cache_mod.get_market_pulse_response("top gainers today")
    assert still_cached == before


# ── synthesis_status stays accurate on a cached, structured-only response ──

def test_synthesis_status_is_recomputed_fresh_on_every_read_not_cached_stale():
    from app.services.ai_search.aev2.assemble import assemble_aev2
    from app.services.ai_search.aev2.mode import AEV2Mode
    from app.services.ai_search.core_market_pulse import from_market_pulse_response

    degraded = {**_MP_RESULT, "market_summary": "", "ai_conclusion": ""}
    cache_mod.set_market_pulse_response("top gainers today", degraded)
    cached = cache_mod.get_market_pulse_response("top gainers today")

    core = from_market_pulse_response(cached)
    aev2 = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert aev2["synthesis_status"] == "unavailable"
    assert len(aev2["indices"]) == 1  # structured data present regardless


# ── Data-collection failure degrades honestly, same shape, still cacheable ──

async def test_upstream_collection_failure_still_yields_a_well_shaped_cacheable_result():
    """If get_market_pulse() itself raises (e.g. an underlying Redis-backed
    state cache is unavailable), _run_market_pulse_search's own existing
    try/except already falls back to pulse={} — every field defaults
    honestly (empty lists/None), the shape never changes, and the result
    is still a normal dict this cache can store and later serve without
    special-casing."""
    from app.services.ai_search import market_pulse as market_pulse_mod

    async def _boom():
        raise RuntimeError("intelligence state cache unavailable")

    with patch("app.services.market_intelligence_service.get_market_pulse", new=_boom), \
         patch("app.services.ai_search.market_pulse._call_with_fallback", new=AsyncMock(return_value=None)):
        result = await market_pulse_mod._run_market_pulse_search("market summary today")

    assert result["type"] == "market_pulse"
    assert result["indices"] == []
    assert result["top_gainers"] == []
    assert result["biggest_opportunity"] is None
    assert isinstance(result["market_summary"], str) and result["market_summary"]

    # And it's still perfectly cacheable/servable through the same path.
    cache_mod.set_market_pulse_response("market summary today", result)
    assert cache_mod.get_market_pulse_response("market summary today") == result

"""
Step 3 closure: the macro-rate fetch behind historical retrieval (cold: 10 to 20 s on three external sources) must not be discarded when a request deadline cancels the waiter, and an interactive request
must not wait for it. Found by H.4: CR1 retrieval was cut off at the 14 s cap on EVERY attempt because each cancelled cold fetch was thrown away and restarted. Model-free; sources are fakes.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from app.services import request_deadline as RD
from app.services.macro_rates import service as MS
from app.services.weekend_intelligence import historical_integration as HI


@pytest.fixture
def sources(monkeypatch):
    st = {"calls": 0, "delay": 0.6, "fail": False}

    async def slow_source():
        st["calls"] += 1
        await asyncio.sleep(st["delay"])
        if st["fail"]:
            raise RuntimeError("source down")
        return "ok"

    monkeypatch.setattr(MS, "get_us_treasury_state", slow_source)
    monkeypatch.setattr(MS, "get_fed_funds_rate", slow_source)
    monkeypatch.setattr(MS, "get_rbi_wss_state", slow_source)
    monkeypatch.setattr(MS, "build_macro_rate_state", lambda t, f, w: SimpleNamespace(interest_rate_trend="easing", marker=(t, f, w)))
    MS._CACHE.clear()
    MS._inflight = None
    MS._inflight_loop = None
    yield st
    MS._CACHE.clear()
    MS._inflight = None


def run(coro):
    return asyncio.run(coro)


def test_a_bounded_waiter_gives_up_quickly_but_the_fetch_completes_and_warms_the_cache(sources):
    async def go():
        t = time.monotonic()
        with pytest.raises(asyncio.TimeoutError):
            await MS.get_macro_rate_state(max_wait_s=0.15)
        waited = time.monotonic() - t
        await asyncio.sleep(0.8)                                   # the background fetch finishes on its own
        t2 = time.monotonic()
        state = await MS.get_macro_rate_state(max_wait_s=0.15)
        return waited, state, time.monotonic() - t2

    waited, state, again = run(go())
    assert waited < 0.4 and state.interest_rate_trend == "easing" and again < 0.05      # the discarded-work loop is gone: the next call is a cache hit
    assert sources["calls"] == 3                                    # one fetch (three sources), never restarted


def test_cancelling_a_waiter_does_not_cancel_the_shared_fetch(sources):
    async def go():
        w = asyncio.ensure_future(MS.get_macro_rate_state())
        await asyncio.sleep(0.1)
        task = MS._inflight
        w.cancel()
        with pytest.raises(asyncio.CancelledError):
            await w
        assert not task.done()
        return (await task).interest_rate_trend

    assert run(go()) == "easing"


def test_concurrent_callers_share_one_fetch(sources):
    async def go():
        return await asyncio.gather(*[MS.get_macro_rate_state() for _ in range(10)])

    outs = run(go())
    assert len({id(o) for o in outs}) == 1 and sources["calls"] == 3


def test_a_warm_cache_is_immediate_and_a_failed_fetch_never_blocks_the_next(sources):
    sources["fail"] = True

    async def go():
        s1 = await MS.get_macro_rate_state()                       # every source raises: the existing "unavailable" isolation applies, nothing propagates
        assert MS._inflight is None                                # a finished fetch is not "already running"
        sources["fail"] = False
        MS._CACHE.clear()
        s2 = await MS.get_macro_rate_state()
        return s1, s2

    s1, s2 = run(go())
    assert s2.interest_rate_trend == "easing" and sources["calls"] == 6


def test_an_interactive_request_does_not_wait_for_the_optional_rate_trend(sources, monkeypatch):
    sources["delay"] = 1.5
    monkeypatch.setattr("app.core.config.settings.macro_rate_interactive_wait_seconds", 0.2)

    async def go():
        with RD.scope(total=10, reserve=1, min_attempt=1, attempt_cap=3):
            t = time.monotonic()
            trend = await HI._real_interest_rate_trend()
            dt = time.monotonic() - t
        await asyncio.sleep(1.8)
        with RD.scope(total=10, reserve=1, min_attempt=1, attempt_cap=3):
            warm = await HI._real_interest_rate_trend()
        return trend, dt, warm

    trend, dt, warm = run(go())
    assert trend is None and dt < 0.5                              # dimension left unset, never guessed
    assert warm == "easing"                                        # the background fetch warmed it for the next request


def test_background_callers_without_a_deadline_still_wait_for_the_real_value(sources):
    sources["delay"] = 0.4

    async def go():
        return await HI._real_interest_rate_trend()

    assert run(go()) == "easing"

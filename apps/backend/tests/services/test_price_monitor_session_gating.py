"""
CR-3 (2026-09-13) — regression tests for per-instrument session gating in
price_monitor.py's threshold loop.

Locked policy under test:
  NIFTY/BANKNIFTY/VIX ("nse" session_class): fetch only when
    _market_session() == "live".
  USDINR/BRENT ("weekday_continuous"): fetch on any weekday session
    (pre_market/live/post_market), skip only on "weekend".

capture_close_snapshot() and capture_market_observations_if_due() must
receive zero behavior changes -- both already have their own,
independent gating and are asserted to still run unconditionally from
run_price_monitor_cycle() regardless of the NSE session.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.intelligence import price_monitor as pm


@pytest.fixture(autouse=True)
def _isolate_last_prices():
    """_last_prices is module-level shared state -- reset around every
    test so runs don't leak into each other."""
    original = dict(pm._last_prices)
    pm._last_prices.clear()
    yield
    pm._last_prices.clear()
    pm._last_prices.update(original)


def _patched_common(session: str, price_map: dict[str, float], is_calendar_weekend: bool = False):
    """Common patch set for a run_price_monitor_cycle() call: mocks the
    session, the price fetch (by ticker), the event bus, and both
    already-gated sub-tasks (so we can assert they still ran, and so
    they don't hit the real DB/network in these unit tests).

    is_calendar_weekend defaults False (a plain weekday) and is mocked
    independently of `session` -- 2026-09-14's fix made `session` itself
    holiday-aware (an NSE holiday now also reports "weekend"), so a test
    asserting "weekend" behavior for the nse branch must not silently
    also assert a real Sat/Sun for weekday_continuous; the two are
    deliberately decoupled here exactly as they are in the real code."""
    def _fake_fetch(ticker: str):
        return price_map.get(ticker)

    bus_mock = AsyncMock()
    return (
        patch("app.services.intelligence.engine._market_session", return_value=session),
        patch.object(pm, "_fetch_price_sync", side_effect=_fake_fetch),
        patch("app.services.intelligence.event_bus.get_event_bus", return_value=bus_mock),
        patch.object(pm, "capture_close_snapshot", AsyncMock()),
        patch("app.services.warehouse.market_observations.capture_market_observations_if_due", AsyncMock(return_value={"skipped": True})),
        patch.object(pm, "_is_calendar_weekend", return_value=is_calendar_weekend),
        bus_mock,
    )


_ALL_TICKERS = {"^NSEI": 25000.0, "^NSEBANK": 55000.0, "USDINR=X": 83.5, "BZ=F": 80.0, "^INDIAVIX": 13.0}


@pytest.mark.asyncio
async def test_weekday_live_session_fetches_all_five_instruments():
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("live", _ALL_TICKERS)
    with p1, p2 as fetch_mock, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()
    fetched_tickers = {call.args[0] for call in fetch_mock.call_args_list}
    assert fetched_tickers == set(_ALL_TICKERS.keys())


@pytest.mark.asyncio
async def test_weekday_after_close_skips_nse_instruments_fetches_continuous():
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("post_market", _ALL_TICKERS)
    with p1, p2 as fetch_mock, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()
    fetched_tickers = {call.args[0] for call in fetch_mock.call_args_list}
    assert fetched_tickers == {"USDINR=X", "BZ=F"}, "only USDINR/BRENT should fetch after NSE close on a weekday"


@pytest.mark.asyncio
async def test_weekday_pre_market_skips_nse_instruments_fetches_continuous():
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("pre_market", _ALL_TICKERS)
    with p1, p2 as fetch_mock, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()
    fetched_tickers = {call.args[0] for call in fetch_mock.call_args_list}
    assert fetched_tickers == {"USDINR=X", "BZ=F"}


@pytest.mark.asyncio
async def test_weekend_fetches_zero_instruments_from_the_threshold_loop():
    """The locked correction: USDINR/BRENT must also be skipped on a
    real Sat/Sun calendar weekend, unlike weekday-closed hours. Passes
    is_calendar_weekend=True explicitly -- this is testing a literal
    weekend, not merely session=="weekend" (which, since the 2026-09-14
    fix, can also mean an NSE holiday that must NOT skip these two)."""
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("weekend", _ALL_TICKERS, is_calendar_weekend=True)
    with p1, p2 as fetch_mock, p3, p4 as close_mock, p5 as obs_mock, p6:
        await pm.run_price_monitor_cycle()
    assert fetch_mock.call_count == 0, "zero threshold-loop market-data calls for all five instruments on weekends"
    # the two already-gated sub-tasks must still run unconditionally --
    # their OWN internal logic decides whether to do anything, not this
    # loop's session check.
    close_mock.assert_awaited_once()
    obs_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_capture_close_snapshot_and_market_observations_run_regardless_of_nse_session():
    """Regression: these two sub-tasks' own independent gating is
    untouched by CR-3 -- they must be invoked from every
    run_price_monitor_cycle() call no matter what the NSE session is,
    since their internal logic (not this loop) decides whether to act."""
    for session in ("live", "pre_market", "post_market", "weekend"):
        p1, p2, p3, p4, p5, p6, bus_mock = _patched_common(session, _ALL_TICKERS, is_calendar_weekend=(session == "weekend"))
        with p1, p2, p3, p4 as close_mock, p5 as obs_mock, p6:
            await pm.run_price_monitor_cycle()
        close_mock.assert_awaited_once()
        obs_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_reopen_after_weekend_gap_compares_against_last_live_close_not_suppressed():
    """Reopen semantics: seed _last_prices with Friday's close (as the
    last LIVE-session tick would have left it), simulate the weekend
    (NIFTY skipped entirely, _last_prices untouched for it), then the
    first Monday live tick with a materially different price -- the
    threshold comparison must behave exactly as it does today (compare
    against the last live value), not be suppressed or reset by gating."""
    pm._last_prices["NIFTY"] = 25000.0  # Friday's close

    # Weekend: NIFTY must not be touched at all.
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("weekend", _ALL_TICKERS, is_calendar_weekend=True)
    with p1, p2 as fetch_mock, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()
    assert pm._last_prices["NIFTY"] == 25000.0
    assert not any(c.args[0] == "^NSEI" for c in fetch_mock.call_args_list)

    # Monday live tick: a genuine 2% gap-open (above NIFTY's 0.75% threshold).
    monday_prices = dict(_ALL_TICKERS)
    monday_prices["^NSEI"] = 25500.0  # +2.0% vs the seeded 25000.0 close
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("live", monday_prices)
    with p1, p2, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()

    assert pm._last_prices["NIFTY"] == 25500.0
    pushed = [c.args[0] if c.args else c.kwargs.get("event") for c in bus_mock.push.call_args_list]
    assert any(getattr(ev, "meta", {}).get("instrument") == "NIFTY" for ev in pushed), \
        "a real weekend gap crossing the threshold must still surface as an event -- CR-3 doesn't change this"


# ── 2026-09-14 fix: NSE holiday must not leak into weekday_continuous ──────
# The real, verified case: Ganesh Chaturthi, a Monday. NSE/BSE equity, F&O
# and currency cash markets are closed (market_session() correctly reports
# "weekend" for this), but commodity markets resume an evening session --
# BRENT/USDINR must keep fetching exactly as on any other weekday.

@pytest.mark.asyncio
async def test_nse_holiday_skips_nse_instruments_but_not_continuous_ones():
    """session=="weekend" here comes from a real NSE holiday (not a
    literal Sat/Sun) -- is_calendar_weekend stays False. NIFTY/BANKNIFTY/
    VIX must be skipped (the nse branch correctly treats a holiday like
    a closed market); USDINR/BRENT must NOT be skipped (they are not
    governed by NSE equity holidays)."""
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("weekend", _ALL_TICKERS, is_calendar_weekend=False)
    with p1, p2 as fetch_mock, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()
    fetched_tickers = {call.args[0] for call in fetch_mock.call_args_list}
    assert fetched_tickers == {"USDINR=X", "BZ=F"}, \
        "an NSE holiday must skip NIFTY/BANKNIFTY/VIX but not BRENT/USDINR"


@pytest.mark.asyncio
async def test_real_calendar_weekend_still_skips_continuous_instruments_too():
    """Contrast case: a literal Sat/Sun (is_calendar_weekend=True) must
    still skip USDINR/BRENT -- the fix narrows what counts as a closure
    for the continuous branch, it does not remove the closure entirely."""
    p1, p2, p3, p4, p5, p6, bus_mock = _patched_common("weekend", _ALL_TICKERS, is_calendar_weekend=True)
    with p1, p2 as fetch_mock, p3, p4, p5, p6:
        await pm.run_price_monitor_cycle()
    assert fetch_mock.call_count == 0, "a real Sat/Sun must still skip all five instruments"

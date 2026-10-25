"""
Candidate 4 G3 — pure mapper tests for build_us_10y_trigger.

No network, no DB. Constructs UsTreasuryState directly and asserts the
material-move gate, the tz-aware observed_at contract, the freshness guard, and
graceful handling of unavailable / malformed readings.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.global_markets.us_10y_trigger import build_us_10y_trigger
from app.services.macro_rates.us_treasury_source import UsTreasuryState

_NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def test_live_rising_fresh_emits_trigger():
    state = UsTreasuryState(status="live", latest_date=date(2026, 10, 24), y10=4.52, y10_trend="rising")
    trig = build_us_10y_trigger(state, _NOW)
    assert trig is not None
    assert trig["factor"] == "US_10Y_YIELD"
    assert trig["value"] == 4.52
    assert trig["source"] == "us_treasury_par_yield_curve"
    # observed_at MUST be a timezone-aware datetime (downstream subtracts it)
    assert isinstance(trig["observed_at"], datetime)
    assert trig["observed_at"].tzinfo is not None
    assert trig["observed_at"] == datetime(2026, 10, 24, tzinfo=timezone.utc)


def test_stable_trend_no_trigger():
    state = UsTreasuryState(status="live", latest_date=date(2026, 10, 24), y10=4.52, y10_trend="stable")
    assert build_us_10y_trigger(state, _NOW) is None


def test_falling_trend_no_trigger():
    state = UsTreasuryState(status="live", latest_date=date(2026, 10, 24), y10=4.52, y10_trend="falling")
    assert build_us_10y_trigger(state, _NOW) is None


def test_unavailable_source_no_trigger():
    state = UsTreasuryState(status="unavailable", reason="source_fetch_failed")
    assert build_us_10y_trigger(state, _NOW) is None


def test_missing_y10_no_trigger():
    state = UsTreasuryState(status="live", latest_date=date(2026, 10, 24), y10=None, y10_trend="rising")
    assert build_us_10y_trigger(state, _NOW) is None


def test_missing_latest_date_no_trigger():
    state = UsTreasuryState(status="live", latest_date=None, y10=4.52, y10_trend="rising")
    assert build_us_10y_trigger(state, _NOW) is None


def test_stale_reading_no_trigger():
    # 20 days old — beyond the widest (10-day) lag window, so not a live trigger
    state = UsTreasuryState(status="live", latest_date=(_NOW - timedelta(days=20)).date(),
                            y10=4.52, y10_trend="rising")
    assert build_us_10y_trigger(state, _NOW) is None


def test_edge_of_freshness_window_still_emits():
    # exactly 10 days old — still inside the window (guard is > 10)
    state = UsTreasuryState(status="live", latest_date=(_NOW - timedelta(days=10)).date(),
                            y10=4.52, y10_trend="rising")
    assert build_us_10y_trigger(state, _NOW) is not None

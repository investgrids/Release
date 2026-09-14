"""Holiday-awareness fix (2026-09-14): both real session sources --
engine.py's _market_session() (drives /api/mie/status's market_session /
is_market_open) and market.py's /session endpoint (drives the frontend's
isWeekendSession() weekend-homepage gate) -- must report a verified NSE
holiday the same way they already report a weekend, not a normal trading
session. 2026-09-14 is the real, verified case that surfaced this gap
(Ganesh Chaturthi, a Monday)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from app.services.intelligence.engine import _market_session

_IST = timezone(timedelta(hours=5, minutes=30))


def test_engine_market_session_reports_weekend_on_a_real_holiday():
    assert _market_session(datetime(2026, 9, 14, 12, 0, tzinfo=_IST)) == "weekend"


def test_engine_market_session_still_reports_live_on_the_next_trading_day():
    assert _market_session(datetime(2026, 9, 15, 12, 0, tzinfo=_IST)) == "live"


def test_engine_market_session_unaffected_for_a_year_with_no_holiday_list():
    # Same calendar date pattern one year later must NOT be miscaptured
    # as a holiday just because 2026-09-14 is one -- market_calendar
    # never guesses beyond its verified list.
    assert _market_session(datetime(2027, 9, 14, 12, 0, tzinfo=_IST)) == "live"


def test_market_api_session_endpoint_reports_weekend_on_a_real_holiday(monkeypatch):
    from app.api import market as market_api

    class _FixedDatetime(market_api.datetime):
        @classmethod
        def now(cls, tz=None):
            return market_api.datetime(2026, 9, 14, 12, 0, tzinfo=tz)

    monkeypatch.setattr(market_api, "datetime", _FixedDatetime)
    result = asyncio.run(market_api.market_session())
    assert result["session"] == "weekend"
    assert result["is_open"] is False

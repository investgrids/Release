"""Canonical NSE equity session state, the one place that answers "what session is it, which
session's data is on screen, and which session would a forecast be about".

It reuses the verified holiday calendar (market_calendar.is_valid_nse_trading_session), so a
holiday is never reported as an open or pre-open day. Pure and clock-injectable: no network, no DB.

States: pre_open (a trading day before 09:15 IST), open (09:15-15:30), after_close (a trading day
after 15:30), weekend, holiday.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.market_calendar import is_valid_nse_trading_session

IST = ZoneInfo("Asia/Kolkata")

PRE_OPEN, OPEN, AFTER_CLOSE, WEEKEND, HOLIDAY = "pre_open", "open", "after_close", "weekend", "holiday"

_OPEN_MIN = 9 * 60 + 15
_CLOSE_MIN = 15 * 60 + 30


def ist_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(IST)


def ist_today() -> date:
    return ist_now().date()


def previous_trading_day(d: date) -> date:
    """Latest NSE trading day strictly before d."""
    cur = d - timedelta(days=1)
    for _ in range(15):
        if is_valid_nse_trading_session(cur):
            return cur
        cur -= timedelta(days=1)
    return cur


def next_trading_day(d: date) -> date:
    """Earliest NSE trading day strictly after d."""
    cur = d + timedelta(days=1)
    for _ in range(15):
        if is_valid_nse_trading_session(cur):
            return cur
        cur += timedelta(days=1)
    return cur


@dataclass(frozen=True)
class MarketSession:
    state: str
    ist_date: date
    # The session whose figures the page describes: today once it has started (live or closed),
    # otherwise the last completed session.
    reference_session_date: date
    # The session an opening forecast is about: today before the open, else the next trading day.
    forecast_target_date: date
    is_trading_day: bool

    @property
    def shows_forecast(self) -> bool:
        """An opening forecast is only meaningful before the open. After the close, on weekends and on holidays the
        page reports what happened, not a prediction."""
        return self.state == PRE_OPEN

    @property
    def shows_realized(self) -> bool:
        return self.state != PRE_OPEN

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "ist_date": self.ist_date.isoformat(),
            "reference_session_date": self.reference_session_date.isoformat(),
            "forecast_target_date": self.forecast_target_date.isoformat(),
            "is_trading_day": self.is_trading_day,
        }


def classify_session(now: datetime | None = None) -> MarketSession:
    now = (now or ist_now())
    now = now.astimezone(IST) if now.tzinfo else now.replace(tzinfo=IST)
    today = now.date()
    minutes = now.hour * 60 + now.minute

    if not is_valid_nse_trading_session(today):
        state = WEEKEND if today.weekday() >= 5 else HOLIDAY
        return MarketSession(state, today, previous_trading_day(today), next_trading_day(today), False)
    if minutes < _OPEN_MIN:
        return MarketSession(PRE_OPEN, today, previous_trading_day(today), today, True)
    if minutes <= _CLOSE_MIN:
        return MarketSession(OPEN, today, today, next_trading_day(today), True)
    return MarketSession(AFTER_CLOSE, today, today, next_trading_day(today), True)

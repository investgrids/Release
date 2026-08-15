"""Trading-session date resolution — pure functions, no DB."""
from __future__ import annotations

from datetime import date

from app.services.weekend_intelligence.session_resolution import (
    is_weekday_trading_day,
    last_trading_date,
    next_trading_date,
    resolve_weekend_session,
)


def test_saturday_resolves_to_friday_and_monday():
    saturday = date(2026, 8, 15)
    assert last_trading_date(saturday) == date(2026, 8, 14)
    assert next_trading_date(saturday) == date(2026, 8, 17)


def test_sunday_resolves_same_as_saturday():
    sunday = date(2026, 8, 16)
    assert last_trading_date(sunday) == date(2026, 8, 14)
    assert next_trading_date(sunday) == date(2026, 8, 17)


def test_monday_last_trading_date_is_prior_friday():
    monday = date(2026, 8, 17)
    assert last_trading_date(monday) == date(2026, 8, 14)


def test_midweek_wednesday_resolves_to_adjacent_weekdays():
    wednesday = date(2026, 8, 19)
    assert last_trading_date(wednesday) == date(2026, 8, 18)
    assert next_trading_date(wednesday) == date(2026, 8, 20)


def test_resolve_weekend_session_returns_iso_strings():
    last, target = resolve_weekend_session(date(2026, 8, 15))
    assert last == "2026-08-14"
    assert target == "2026-08-17"


def test_is_weekday_trading_day():
    assert is_weekday_trading_day(date(2026, 8, 14)) is True   # Friday
    assert is_weekday_trading_day(date(2026, 8, 15)) is False  # Saturday
    assert is_weekday_trading_day(date(2026, 8, 16)) is False  # Sunday

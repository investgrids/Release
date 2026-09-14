"""app.services.market_calendar — the verified 2026 NSE/BSE holiday list."""
from __future__ import annotations

from datetime import date

from app.services.market_calendar import is_nse_trading_holiday


def test_ganesh_chaturthi_2026_is_a_holiday():
    # The real case that surfaced this gap: 2026-09-14 is a Monday, and
    # /api/mie/status reported market_session="live" on this actual holiday.
    assert is_nse_trading_holiday(date(2026, 9, 14)) is True


def test_a_handful_of_other_verified_2026_holidays():
    assert is_nse_trading_holiday(date(2026, 1, 26)) is True   # Republic Day
    assert is_nse_trading_holiday(date(2026, 3, 3)) is True    # Holi
    assert is_nse_trading_holiday(date(2026, 12, 25)) is True  # Christmas


def test_an_ordinary_2026_trading_day_is_not_a_holiday():
    assert is_nse_trading_holiday(date(2026, 9, 15)) is False  # Tuesday after Ganesh Chaturthi


def test_a_weekend_is_not_reported_as_a_holiday():
    # This module only answers holiday-or-not; weekend detection is the
    # caller's own, separate weekday check.
    assert is_nse_trading_holiday(date(2026, 9, 13)) is False  # Sunday


def test_a_year_with_no_populated_list_never_guesses():
    assert is_nse_trading_holiday(date(2027, 1, 26)) is False

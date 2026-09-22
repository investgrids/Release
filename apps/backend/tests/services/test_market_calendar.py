"""app.services.market_calendar — the verified 2026 NSE/BSE holiday list."""
from __future__ import annotations

from datetime import date, datetime, timezone

import app.services.market_calendar as market_calendar
from app.services.market_calendar import is_nse_trading_holiday, is_valid_nse_trading_session


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


# ── is_valid_nse_trading_session (2026-09-22, price-bar ingestion guard) ──

def test_ganesh_chaturthi_2026_is_rejected_as_a_trading_session():
    assert is_valid_nse_trading_session(date(2026, 9, 14)) is False


def test_normal_weekday_is_accepted():
    assert is_valid_nse_trading_session(date(2026, 9, 15)) is True  # Tuesday after Ganesh Chaturthi
    assert is_valid_nse_trading_session(date(2026, 9, 11)) is True  # ordinary Friday


def test_saturday_is_rejected():
    assert is_valid_nse_trading_session(date(2026, 9, 12)) is False  # Saturday


def test_sunday_is_rejected():
    assert is_valid_nse_trading_session(date(2026, 9, 13)) is False  # Sunday


def test_exceptional_weekend_session_is_accepted_when_configured(monkeypatch):
    # No real Muhurat/special-session date is hardcoded yet (see the
    # module's own docstring — never guessed without 2-source
    # verification), so this proves the MECHANISM using a synthetic
    # configured date rather than asserting an unverified real one.
    a_saturday = date(2026, 9, 12)
    assert is_valid_nse_trading_session(a_saturday) is False
    monkeypatch.setattr(market_calendar, "_NSE_EXCEPTIONAL_TRADING_DATES", frozenset({a_saturday}))
    assert is_valid_nse_trading_session(a_saturday) is True


def test_valid_muhurat_style_special_session_is_accepted(monkeypatch):
    # Same mechanism as above, framed as the real-world case it exists
    # for: a special Sunday session (e.g. Diwali Muhurat trading).
    a_sunday = date(2026, 11, 8)
    assert is_valid_nse_trading_session(a_sunday) is False
    monkeypatch.setattr(market_calendar, "_NSE_EXCEPTIONAL_TRADING_DATES", frozenset({a_sunday}))
    assert is_valid_nse_trading_session(a_sunday) is True


def test_utc_timestamp_is_converted_to_the_correct_ist_trading_date():
    # 2026-09-14 18:35 UTC = 2026-09-15 00:05 IST (+5:30) -- a real
    # trading day, even though the UTC calendar date is still the
    # holiday. Proves classification happens on the IST date, not the
    # raw UTC one.
    utc_dt = datetime(2026, 9, 14, 18, 35, tzinfo=timezone.utc)
    assert is_valid_nse_trading_session(utc_dt) is True

    # Conversely, 2026-09-13 19:00 UTC = 2026-09-14 00:30 IST -- the
    # actual holiday, even though the UTC calendar date is still the 13th.
    utc_dt_holiday = datetime(2026, 9, 13, 19, 0, tzinfo=timezone.utc)
    assert is_valid_nse_trading_session(utc_dt_holiday) is False


def test_naive_datetime_is_treated_as_utc_before_ist_conversion():
    naive_dt = datetime(2026, 9, 14, 18, 35)  # no tzinfo
    assert is_valid_nse_trading_session(naive_dt) is True

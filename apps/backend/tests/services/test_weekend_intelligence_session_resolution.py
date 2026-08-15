"""Trading-session date resolution — pure functions, no DB."""
from __future__ import annotations

from datetime import date, datetime

from app.services.weekend_intelligence.session_resolution import (
    is_weekday_trading_day,
    last_trading_date,
    next_trading_date,
    resolve_opening_prediction_session,
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


# ── resolve_opening_prediction_session — Phase 1C correctness fix ──────────
# 2026-08-14 = Friday, -15 = Saturday, -16 = Sunday, -17 = Monday, -18 = Tuesday.

def test_saturday_targets_monday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 15, 10, 0)) == "2026-08-17"


def test_sunday_targets_monday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 16, 10, 0)) == "2026-08-17"


def test_monday_early_morning_before_premarket_cutoff_targets_monday():
    """The exact scenario the review flagged as broken: a real Monday
    pre-market call (08:30 IST) must resolve to THAT Monday, not
    Tuesday."""
    assert resolve_opening_prediction_session(datetime(2026, 8, 17, 8, 30)) == "2026-08-17"


def test_monday_pre_open_at_9am_targets_monday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 17, 9, 0)) == "2026-08-17"


def test_monday_during_live_session_targets_monday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 17, 12, 0)) == "2026-08-17"


def test_monday_after_market_close_targets_tuesday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 17, 16, 0)) == "2026-08-18"


def test_friday_after_market_close_targets_monday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 14, 16, 0)) == "2026-08-17"


def test_tuesday_before_open_targets_tuesday():
    assert resolve_opening_prediction_session(datetime(2026, 8, 18, 8, 0)) == "2026-08-18"


def test_no_arg_call_defers_to_real_market_session(monkeypatch):
    """Production path (no now_ist supplied) must classify via the REAL
    engine.py::_market_session() — true reuse, not a parallel
    implementation that could silently drift from it."""
    called = {"hit": False}

    def _fake_market_session():
        called["hit"] = True
        return "live"

    monkeypatch.setattr("app.services.intelligence.engine._market_session", _fake_market_session)
    resolve_opening_prediction_session()
    assert called["hit"] is True

"""
Trading-session date resolution — last_trading_date / target_trading_date.

Deliberately NOT "friday"/"monday" (design doc §18, Phase 1B brief §3):
pure weekday arithmetic (Mon-Fri = trading days), generic enough that
"Thursday close -> Friday holiday -> weekend -> Monday target" or
"Friday close -> Monday holiday -> Tuesday target" resolve correctly once
a real NSE/BSE holiday calendar exists — nothing else in Weekend
Intelligence hardcodes a day name; only the two functions below would
need to change.

Reuses engine.py's _IST timezone constant (the same one _market_session
already uses) rather than redefining IST — no new session implementation,
per the brief's explicit instruction to reuse the existing convention.

KNOWN LIMITATION (tracked, not solved here — same gap Phase 1A's
docstrings already flag): there is no real NSE/BSE trading-holiday
calendar anywhere in this codebase (confirmed dead:
app/providers/economic_calendar_provider.py is never called;
app/db/seed.py's CalendarEvent data is hardcoded and skipped in
production — see WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §19). A
market holiday on a weekday is currently resolved as if it were a normal
trading day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.services.intelligence.engine import _IST


def is_weekday_trading_day(d: date) -> bool:
    """Monday=0 ... Sunday=6. Not holiday-aware — see module docstring."""
    return d.weekday() < 5


def last_trading_date(reference: date | None = None) -> date:
    """The most recent completed trading day strictly before `reference`
    (defaults to today, IST). On a Saturday this resolves to Friday; on a
    Sunday or Monday it also resolves to Friday (the prior trading day,
    since Saturday/Sunday aren't trading days)."""
    d = (reference or datetime.now(_IST).date()) - timedelta(days=1)
    while not is_weekday_trading_day(d):
        d -= timedelta(days=1)
    return d


def next_trading_date(reference: date | None = None) -> date:
    """The next trading day strictly after `reference` (defaults to
    today, IST)."""
    d = (reference or datetime.now(_IST).date()) + timedelta(days=1)
    while not is_weekday_trading_day(d):
        d += timedelta(days=1)
    return d


def resolve_weekend_session(reference: date | None = None) -> tuple[str, str]:
    """
    (last_trading_date, target_trading_date) as YYYY-MM-DD strings — the
    trading day Weekend Intelligence is BASED ON and the trading day it
    is FOR. `reference` defaults to today (IST) when omitted; tests pass
    an explicit date to stay deterministic.
    """
    today = reference or datetime.now(_IST).date()
    return last_trading_date(today).isoformat(), next_trading_date(today).isoformat()

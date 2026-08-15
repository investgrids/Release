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


# Phase 1C fix — byte-for-byte mirror of engine.py::_market_session()'s
# own weekday/9:15/15:30 thresholds. Needed only because that function
# takes no `now` parameter (other existing callers depend on its
# real-time-only behavior, so it is not touched here — see module
# docstring's "no new session implementation" rule, applied by NOT
# duplicating engine.py's real-time codepath, only its classification
# logic for an explicitly-supplied instant). resolve_opening_prediction_session
# below always calls the REAL _market_session() on the production (no-arg)
# path — this mirror only classifies a caller-supplied `now_ist`, e.g.
# from a test.
_PRE_MARKET_CUTOFF_MIN = 9 * 60 + 15
_MARKET_CLOSE_MIN = 15 * 60 + 30


def _classify_session(now_ist: datetime) -> str:
    if now_ist.weekday() >= 5:
        return "weekend"
    mins = now_ist.hour * 60 + now_ist.minute
    if mins < _PRE_MARKET_CUTOFF_MIN:
        return "pre_market"
    if mins <= _MARKET_CLOSE_MIN:
        return "live"
    return "post_market"


def resolve_opening_prediction_session(now_ist: datetime | None = None) -> str:
    """
    The canonical "which trading session is Opening Intelligence
    currently predicting" resolver (Phase 1C fix — replaces the ad hoc
    reuse of opening_prediction_service._ist_tomorrow(), which always
    means literal calendar-tomorrow and therefore resolves to Tuesday
    on an actual Monday morning, never matching Weekend Intelligence's
    real Monday target — the bug this function exists to fix).

    V1 semantics (holiday-unaware — same documented gap as
    resolve_weekend_session above, not solved here):
      Saturday / Sunday                    -> next Monday
      weekday, before or during market hours (pre_market / live)
                                            -> that same day
      weekday, after market close (post_market)
                                            -> the next weekday session

    Returns a YYYY-MM-DD string. `now_ist` is None on the real
    production path (the only path that matters for correctness) and is
    classified via the REAL engine.py::_market_session() — true reuse,
    not a parallel implementation. Tests pass an explicit `now_ist` to
    get a deterministic instant; that path uses _classify_session's
    mirror of the same thresholds (see its docstring for why a mirror
    was necessary here rather than a shared parameterized function).
    """
    if now_ist is None:
        from app.services.intelligence.engine import _market_session
        now_ist = datetime.now(_IST)
        session = _market_session()
    else:
        session = _classify_session(now_ist)

    if session in ("weekend", "post_market"):
        return next_trading_date(now_ist.date()).isoformat()
    return now_ist.date().isoformat()

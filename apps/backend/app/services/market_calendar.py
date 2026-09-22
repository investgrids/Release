"""
NSE/BSE trading-holiday calendar (2026-09-14).

Fills the gap every session-resolution module in this codebase already
documents as a known limitation (see session_resolution.py's module
docstring, price_monitor.py's compute_freshness docstring,
engine.py::_market_session's own callers): "weekday" was always treated
as synonymous with "trading day", so a real market holiday on a weekday
(e.g. Ganesh Chaturthi, 2026-09-14 -- the real case that surfaced this
gap: /api/mie/status reported market_session="live" on an actual NSE
holiday) was silently miscaptured as a normal trading day.

Dates verified against two independent public sources (Zerodha's and
Groww's published 2026 NSE/BSE equity holiday calendars, both
2026-09-13) and cross-checked for agreement before being hardcoded --
this is real-world calendar data, not something to guess at or
approximate, and getting it wrong is worse than not having it. Covers
2026 only; extend `_NSE_TRADING_HOLIDAYS` with the next year's verified
list before relying on this for 2027 -- deliberately fails to the old
"no holiday awareness" behavior (returns False) for any year not yet
populated here, rather than guessing.

Muhurat trading (a special Sunday session, e.g. 2026-11-08) is NOT a
holiday and is out of scope -- this module only answers "is this
otherwise-tradeable weekday actually closed", not "which weekends
exceptionally open".

Extended (2026-09-22, price-bar ingestion guard): that "out of scope"
carve-out was real for market-status DISPLAY, but became a genuine gap
once a trading-CALENDAR check started gating whether a price bar gets
stored at all -- `is_valid_nse_trading_session()` needs one real answer
for "was this specific date open", including the weekend-exception
case, not two separate partial checks a caller could get out of sync.
`_NSE_EXCEPTIONAL_TRADING_DATES` is the home for a verified weekend/
Muhurat session, same two-independent-source discipline as
`_NSE_TRADING_HOLIDAYS` above -- starts EMPTY, not guessed: no such
date has been independently verified for this codebase's covered years
yet, and asserting one without that verification would be exactly the
"getting it wrong is worse than not having it" mistake this module's
own holiday list already refuses to make. Add a real, sourced date here
when one is verified; until then, every date defaults through the
ordinary weekend/holiday rule below, which is the same fail-closed
behavior the holiday list itself uses for unpopulated years.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

_NSE_TRADING_HOLIDAYS: frozenset[date] = frozenset({
    date(2026, 1, 15),   # Municipal Corporation Elections (Maharashtra)
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 3),    # Holi
    date(2026, 3, 26),   # Shri Ram Navami
    date(2026, 3, 31),   # Shri Mahavir Jayanti
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 28),   # Bakri Eid
    date(2026, 6, 26),   # Moharram
    date(2026, 9, 14),   # Ganesh Chaturthi
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 10),  # Diwali-Balipratipada
    date(2026, 11, 24),  # Prakash Gurpurb Sri Guru Nanak Dev
    date(2026, 12, 25),  # Christmas
})


def is_nse_trading_holiday(d: date) -> bool:
    """True only for a verified weekday NSE/BSE equity-segment holiday.
    Returns False (never a guess) for any date outside a populated year,
    weekends included -- callers already have their own weekend check;
    this function answers holiday-or-not, nothing else."""
    return d in _NSE_TRADING_HOLIDAYS


# Real, sourced weekend/Muhurat sessions the market was open despite the
# calendar day -- see this module's own 2026-09-22 docstring addendum
# for why this starts empty rather than an unverified guess.
_NSE_EXCEPTIONAL_TRADING_DATES: frozenset[date] = frozenset()


def is_valid_nse_trading_session(when: date | datetime) -> bool:
    """The one authoritative "was the NSE equity segment actually open
    on this date" answer -- weekends, verified holidays, AND verified
    weekend exceptions (Muhurat-style special sessions), combined,
    instead of scattered ad hoc weekend/holiday checks a caller could
    apply inconsistently or forget one of.

    Accepts either a plain `date` (the normal case -- a daily OHLCV
    bar's own `bar_date`, which yfinance already indexes by the
    exchange's own local trading date) or a timezone-aware `datetime`,
    converted to its IST calendar date first -- a defensive path for
    any future caller that only has a UTC timestamp in hand, so the
    classification is never done against the wrong day for a bar
    fetched or processed close to the IST midnight boundary.

    Precedence: a verified exceptional date is open regardless of what
    weekday it falls on; otherwise a real Sat/Sun is always closed;
    otherwise a verified weekday holiday is closed; every other weekday
    is open. Never guesses beyond what's actually verified in the two
    frozensets above -- an unpopulated year behaves exactly like
    is_nse_trading_holiday's own fail-closed default (holiday-wise
    "no", weekend rule still applies)."""
    if isinstance(when, datetime):
        aware = when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)
        d = aware.astimezone(_IST).date()
    else:
        d = when

    if d in _NSE_EXCEPTIONAL_TRADING_DATES:
        return True
    if d.weekday() >= 5:
        return False
    if d in _NSE_TRADING_HOLIDAYS:
        return False
    return True

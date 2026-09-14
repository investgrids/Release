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
"""
from __future__ import annotations

from datetime import date

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

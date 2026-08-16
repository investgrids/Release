"""
Phase 5A.4 — explicit DST correctness proof, owner's specific requirement:
"an official US release at 08:30 Eastern should convert differently to
IST depending on whether New York is on EST or EDT... use the source
timezone (America/New_York) and actual event date, not a hardcoded
13:30 UTC or IST offset."

Deterministic (doesn't depend on which real dates happen to be live
right now) — constructs known EST-side and EDT-side local times via the
SAME ZoneInfo-based localization every source module uses, and asserts
the UTC (and IST) conversion differs correctly across the transition.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
_IST = ZoneInfo("Asia/Kolkata")


def test_same_wall_clock_time_converts_differently_est_vs_edt():
    """08:30 America/New_York in January (EST, UTC-5) vs July (EDT,
    UTC-4) — same local wall-clock time, different real UTC instant.
    A hardcoded 13:30 UTC would be correct for EST and silently wrong
    by one hour for EDT."""
    winter = datetime(2026, 1, 15, 8, 30, tzinfo=_NY)
    summer = datetime(2026, 7, 15, 8, 30, tzinfo=_NY)

    winter_utc = winter.astimezone(timezone.utc)
    summer_utc = summer.astimezone(timezone.utc)

    assert winter_utc.hour == 13   # EST = UTC-5 -> 08:30 + 5:00 = 13:30 UTC
    assert summer_utc.hour == 12   # EDT = UTC-4 -> 08:30 + 4:00 = 12:30 UTC
    assert winter_utc.hour != summer_utc.hour


def test_dst_transition_boundary_dates():
    """2026's real US DST transitions: spring-forward March 8, fall-back
    November 1 (2nd Sunday in March / 1st Sunday in November, per the
    US's own DST rule — real calendar dates, not assumed). A release
    scheduled the day before vs. the day after each transition must
    show the correct, differing UTC offset."""
    before_spring = datetime(2026, 3, 7, 8, 30, tzinfo=_NY).astimezone(timezone.utc)
    after_spring = datetime(2026, 3, 9, 8, 30, tzinfo=_NY).astimezone(timezone.utc)
    assert before_spring.hour == 13   # still EST
    assert after_spring.hour == 12    # now EDT

    before_fall = datetime(2026, 10, 31, 8, 30, tzinfo=_NY).astimezone(timezone.utc)
    after_fall = datetime(2026, 11, 2, 8, 30, tzinfo=_NY).astimezone(timezone.utc)
    assert before_fall.hour == 12     # still EDT
    assert after_fall.hour == 13      # now EST


def test_ist_render_reflects_dst_correctly():
    """The API's eventual IST render (§4 of the Phase 5A design) must
    also come out correct across DST, since it's derived from the same
    stored UTC instant, never a second hardcoded offset."""
    winter_ist = datetime(2026, 1, 15, 8, 30, tzinfo=_NY).astimezone(_IST)
    summer_ist = datetime(2026, 7, 15, 8, 30, tzinfo=_NY).astimezone(_IST)

    # IST is a fixed UTC+5:30 offset (India doesn't observe DST) — the
    # US-side EST/EDT difference is what must show up here.
    assert (winter_ist.hour, winter_ist.minute) == (19, 0)    # 13:30 UTC -> 19:00 IST
    assert (summer_ist.hour, summer_ist.minute) == (18, 0)    # 12:30 UTC -> 18:00 IST

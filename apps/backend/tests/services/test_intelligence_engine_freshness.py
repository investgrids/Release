"""
Freshness contract (2026-08 homepage redesign) —
app/services/intelligence/engine.py::compute_freshness().

Root-caused live: StoryEngineWorker itself is correct (477 real historical
rows, properly market-hours-gated); the "Monday's Market Wrap" shown on a
Tuesday evening was the backend process not running during Tuesday's
market hours, not a worker bug. This function is the single place that
decides fresh vs stale vs unavailable so every consumer reads the same
verdict instead of re-deriving its own staleness heuristic — these tests
pin the exact session-expectation rule (not a generic "older than X
hours") the user asked for: a prior-day story is fresh-enough right up
until the CURRENT day's own market-hours window has started, and stale
after that if nothing newer landed. Weekends never expect a fresher story
at all.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

import app.services.intelligence.engine as engine_module
from app.services.intelligence.engine import compute_freshness

_IST = timezone(timedelta(hours=5, minutes=30))


def _freeze(monkeypatch, ist_dt: datetime):
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return ist_dt.astimezone(tz)
            return ist_dt
    monkeypatch.setattr(engine_module, "datetime", _FrozenDatetime)


def _iso(ist_dt: datetime) -> str:
    return ist_dt.astimezone(timezone.utc).isoformat()


def test_unavailable_when_no_story():
    result = compute_freshness(None)
    assert result["state"] == "unavailable"
    assert result["is_stale"] is False
    assert result["freshness_label"] is None


def test_unavailable_when_malformed_timestamp():
    result = compute_freshness("not-a-real-timestamp")
    assert result["state"] == "unavailable"


def test_fresh_when_generated_today(monkeypatch):
    # Tuesday 2026-08-18, story generated earlier the same day during market hours.
    now = datetime(2026, 8, 18, 14, 0, tzinfo=_IST)
    story_time = datetime(2026, 8, 18, 9, 47, tzinfo=_IST)
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "fresh"
    assert result["is_stale"] is False
    assert result["story_date"] == "2026-08-18"
    assert "Today" in result["freshness_label"]


def test_stale_monday_story_on_tuesday_after_market_open(monkeypatch):
    # The exact live-observed bug: Monday's last story, read Tuesday evening
    # (well after Tuesday's 9:15 AM market open) — today's window has
    # already passed with nothing fresher landing.
    now = datetime(2026, 8, 18, 19, 22, tzinfo=_IST)  # Tuesday evening
    story_time = datetime(2026, 8, 17, 9, 47, tzinfo=_IST)  # Monday
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "stale"
    assert result["is_stale"] is True
    assert result["story_date"] == "2026-08-17"
    assert result["freshness_label"] == "Monday close · Update delayed"


def test_fresh_monday_story_on_tuesday_before_market_open(monkeypatch):
    # Tuesday 7:00 AM — before today's 9:15 AM open. Nothing newer could
    # exist yet, so Monday's close is still the legitimately-latest read,
    # not a degraded state.
    now = datetime(2026, 8, 18, 7, 0, tzinfo=_IST)
    story_time = datetime(2026, 8, 17, 9, 47, tzinfo=_IST)
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "fresh"
    assert result["is_stale"] is False
    assert result["freshness_label"] == "Monday close"


def test_fresh_friday_story_on_saturday(monkeypatch):
    # 2026-08-15 is a Saturday. No session ever expects a fresher story
    # over a weekend.
    now = datetime(2026, 8, 15, 12, 0, tzinfo=_IST)
    story_time = datetime(2026, 8, 14, 15, 0, tzinfo=_IST)  # Friday close
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "fresh"
    assert result["is_stale"] is False
    assert result["freshness_label"] == "Friday close"


def test_fresh_friday_story_on_sunday(monkeypatch):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=_IST)  # Sunday
    story_time = datetime(2026, 8, 14, 15, 0, tzinfo=_IST)  # Friday close
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "fresh"
    assert result["is_stale"] is False


def test_stale_friday_story_on_monday_evening(monkeypatch):
    now = datetime(2026, 8, 17, 18, 0, tzinfo=_IST)  # Monday evening
    story_time = datetime(2026, 8, 14, 15, 0, tzinfo=_IST)  # Friday close
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "stale"
    assert result["is_stale"] is True
    assert result["freshness_label"] == "Friday close · Update delayed"


def test_age_minutes_is_real_elapsed_time(monkeypatch):
    now = datetime(2026, 8, 18, 10, 30, tzinfo=_IST)
    story_time = datetime(2026, 8, 18, 9, 47, tzinfo=_IST)
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["age_minutes"] == 43


def test_story_session_reflects_when_the_story_itself_was_generated(monkeypatch):
    now = datetime(2026, 8, 18, 19, 0, tzinfo=_IST)
    story_time = datetime(2026, 8, 18, 9, 47, tzinfo=_IST)  # generated during live market hours
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["story_session"] == "live"


def test_stale_tuesday_story_on_thursday_pre_market(monkeypatch):
    """The exact live bug (2026-08-20): the pre-market carve-out had no
    bound on story age at all -- a story from two days ago read as "fresh"
    purely because right now happens to be pre-market, with a full skipped
    Wednesday session never flagged. Confirmed live: StoryEngineWorker
    stalled on Tuesday's story and /api/mie/state reported is_stale=false,
    freshness_label="Tuesday close" on Thursday morning."""
    now = datetime(2026, 8, 20, 8, 0, tzinfo=_IST)  # Thursday, before 9:15 AM open
    story_time = datetime(2026, 8, 18, 15, 0, tzinfo=_IST)  # Tuesday close
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "stale"
    assert result["is_stale"] is True
    assert result["story_date"] == "2026-08-18"
    assert result["freshness_label"] == "Tuesday close · Update delayed"


def test_fresh_wednesday_story_on_thursday_pre_market(monkeypatch):
    """Must not regress: yesterday's close, read before today's own market
    open, is still the legitimately-latest read -- the carve-out's actual
    intended case."""
    now = datetime(2026, 8, 20, 8, 0, tzinfo=_IST)  # Thursday, before open
    story_time = datetime(2026, 8, 19, 15, 0, tzinfo=_IST)  # Wednesday close
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "fresh"
    assert result["is_stale"] is False
    assert result["story_date"] == "2026-08-19"
    assert result["freshness_label"] == "Wednesday close"


def test_fresh_friday_story_on_monday_pre_market(monkeypatch):
    """Weekend-adjacent boundary: Friday's close is still the correct prior
    trading day on Monday morning before open, not stale."""
    now = datetime(2026, 8, 17, 8, 0, tzinfo=_IST)  # Monday, before open
    story_time = datetime(2026, 8, 14, 15, 0, tzinfo=_IST)  # Friday close
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "fresh"
    assert result["is_stale"] is False
    assert result["freshness_label"] == "Friday close"


def test_stale_thursday_story_on_next_monday_pre_market(monkeypatch):
    """A story from the Thursday before last is well past even the
    weekend-adjusted prior trading day (Friday) by the following Monday
    pre-market -- must be stale, not silently carried forward indefinitely."""
    now = datetime(2026, 8, 17, 8, 0, tzinfo=_IST)  # Monday, before open
    story_time = datetime(2026, 8, 13, 15, 0, tzinfo=_IST)  # prior Thursday
    _freeze(monkeypatch, now)
    result = compute_freshness(_iso(story_time))
    assert result["state"] == "stale"
    assert result["is_stale"] is True
    assert result["freshness_label"] == "Thursday close · Update delayed"

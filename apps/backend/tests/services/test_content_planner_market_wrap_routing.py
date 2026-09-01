"""
P0-A Market Wrap Integrity Fix (2026-09-01) — regression suite.

Real production incident: `select_article_type()` used to relabel
WHATEVER single EventTriage item it was called with as "market_wrap"
whenever the wall clock was past 15:30 IST, regardless of the event's
actual subject. A real, live example: Signet Industries' routine
machine-readable-filing notice became a whole-market "wrap" article with
a fabricated sector breakdown, an invented Nifty/Bank Nifty ripple, and
named trade recommendations traceable to nothing in the source filing —
published in production with confidence_score 0.85-0.95 (see the
production article-generator audit, 2026-09-01).

This suite locks in the fix: a single triage event must retain its real,
content-appropriate classification no matter what time of day it's
processed, while the legitimate, independently-built scheduled
market-wrap path (`_build_scheduled_event` in publisher.py, which never
calls `select_article_type()` at all) must keep working exactly as
before.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete

from app.db.models_legacy import NewsArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe.content_planner import select_article_type, _IST
from app.services.aipe.publisher import _build_scheduled_event

# The real, live Signet-shaped event from the audit's own trigger_data --
# a single-company routine filing notice, not market-wide content.
_SIGNET_FILING_EVENT = {
    "event_id": "nse-5cf7277329",
    "headline": (
        "Signet Industries Limited has informed the Exchange regarding "
        "'Financial results for the quarter ended 30.06.2026 in Machine "
        "readable format'."
    ),
    "urgency": 6,
    "importance": 5,
    "sectors": [],
    "tickers": [{"symbol": "SIGNET", "name": "Signet Industries Limited"}],
    "companies": [{"symbol": "SIGNET", "name": "Signet Industries Limited"}],
    "is_structural": False,
}


def _ist(hour: int, minute: int = 0) -> datetime:
    today = datetime.now(_IST).date()
    return datetime(today.year, today.month, today.day, hour, minute, tzinfo=_IST)


@pytest.mark.parametrize("hour,minute", [(11, 0), (14, 59)])
def test_company_filing_before_1530_ist_not_market_wrap(hour, minute):
    with patch("app.services.aipe.content_planner._ist_now", return_value=_ist(hour, minute)):
        article_type, story_id, _ = select_article_type(_SIGNET_FILING_EVENT)
    assert article_type != "market_wrap"
    assert article_type == "company_intelligence"


@pytest.mark.parametrize("hour,minute", [(15, 30), (16, 1), (18, 0), (23, 45)])
def test_same_filing_after_1530_ist_still_not_market_wrap(hour, minute):
    """The core regression: this exact input used to become market_wrap
    once the clock crossed 15:30. It must not anymore, at any later hour."""
    with patch("app.services.aipe.content_planner._ist_now", return_value=_ist(hour, minute)):
        article_type, story_id, _ = select_article_type(_SIGNET_FILING_EVENT)
    assert article_type != "market_wrap"
    assert article_type == "company_intelligence"
    assert not story_id.startswith("wrap-")


def test_company_event_classification_is_time_invariant():
    """The same real event must classify identically at every hour outside
    the pre-market window -- proving time-of-day cannot change a single
    company event into market-wide sector/ripple/recommendation behavior
    merely by clock position, per the explicit requirement this test name
    matches. Hours before 9:15 IST are deliberately excluded: the
    pre_market->morning_intelligence override (content_planner.py:112-113)
    has the identical shape but is explicitly OUT OF SCOPE for this fix
    (the owner authorized only the market_wrap branch) -- it still applies
    to any event during that window by design, unchanged."""
    seen_types = set()
    for hour, minute in ((9, 20), (11, 0), (14, 0), (15, 0), (16, 0), (18, 0), (21, 0), (23, 0)):
        with patch("app.services.aipe.content_planner._ist_now", return_value=_ist(hour, minute)):
            article_type, _, _ = select_article_type(_SIGNET_FILING_EVENT)
        seen_types.add(article_type)
    assert seen_types == {"company_intelligence"}
    assert "market_wrap" not in seen_types


@pytest.mark.asyncio
async def test_legitimate_scheduled_market_wrap_still_generates_after_1530():
    """The REAL wrap path -- _build_scheduled_event, which never calls
    select_article_type() at all -- must be completely unaffected by the
    fix above. Seeds a real NewsArticle row (its own real data source)
    and confirms the post-market/closed sessions still resolve to
    market_wrap."""
    tag = uuid.uuid4().hex[:8]
    row_id = f"test-news-{tag}"
    async with AsyncSessionLocal() as db:
        db.add(NewsArticle(
            id=row_id, headline=f"Real market update headline {tag}",
            summary="A real synthetic summary for this regression test.",
            source="Test Wire", published_at=datetime.now(timezone.utc).isoformat(),
            companies=[], impact_score=5.0,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            for session in ("post_market", "closed"):
                sched_event = await _build_scheduled_event(db, session)
                assert sched_event is not None
                assert sched_event["_article_type"] == "market_wrap"
                assert sched_event["_scheduled"] is True

            for session in ("pre_open", "pre_market", "live"):
                sched_event = await _build_scheduled_event(db, session)
                assert sched_event is not None
                assert sched_event["_article_type"] == "morning_intelligence"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(NewsArticle).where(NewsArticle.id == row_id))
            await db.commit()


def test_other_real_event_types_still_classify_correctly_after_1530():
    """Guard against an over-broad fix: policy/ripple/sector classification
    for OTHER real event shapes must still work normally post-15:30 -- the
    removed branch should have zero effect on any branch below it."""
    policy_event = {
        "event_id": "nse-policy-1", "headline": "RBI cuts repo rate by 25 bps",
        "urgency": 7, "sectors": [], "tickers": [],
    }
    ripple_event = {
        "event_id": "nse-ripple-1", "headline": "Crude oil prices surge on Middle East tensions",
        "urgency": 8, "sectors": ["Energy", "Aviation", "Chemicals"], "tickers": [],
    }
    with patch("app.services.aipe.content_planner._ist_now", return_value=_ist(17, 0)):
        p_type, _, _ = select_article_type(policy_event)
        r_type, _, _ = select_article_type(ripple_event)
    assert p_type == "policy_intelligence"
    assert r_type == "ripple_intelligence"

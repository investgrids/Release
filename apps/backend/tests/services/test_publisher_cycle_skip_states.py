"""
run_aipe_cycle() -- regression tests for the two real silent-return
branches closed in the 2026-08-31 AIPE candidate lifecycle audit
(follow-up to test_publisher_cycle_fanout.py's crash fix).

Before this: a non-critical event blocked by the daily article cap, or a
morning_intelligence/market_wrap slot already filled for today, left the
EventCoverage row at DETECTED forever -- indistinguishable from "never
attempted." Neither is a failure (generation was never attempted), so
these get their own terminal states (SKIPPED_DAILY_CAP,
SKIPPED_ALREADY_GENERATED_TODAY) rather than reusing FAILED.

should_generate_today() gained a third return value, reason_code, so the
caller never has to guess WHY it returned False from the free-text
`reason` string -- see content_planner.py's own docstring.
"""
from __future__ import annotations

import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.models.event_coverage import EventCoverage
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services import coverage_engine
from app.services.aipe import content_planner, publisher


def _fake_published_article(article_id: str, headline: str) -> IntelligenceArticle:
    return IntelligenceArticle(
        id=article_id, slug=article_id, article_type="company_intelligence",
        story_id=article_id, story_version=1, lifecycle_status="published",
        status="published", update_count=0, update_history=[],
        angle="primary", angle_entity=None,
        headline=headline, executive_summary="", key_takeaway="",
        why_it_matters="", what_happened="",
        companies_affected=[], sectors_affected=[],
    )


async def _cleanup(event_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(event_ids)))
        await db.commit()


def _triage_event(event_id: str, headline: str, urgency: int = 6, importance: int = 5) -> dict:
    return {
        "event_id": event_id, "headline": headline, "urgency": urgency,
        "importance": importance, "sectors": [], "themes": [], "tickers": [],
    }


async def _register_real_coverage_rows(events: list[dict]) -> None:
    async with AsyncSessionLocal() as db:
        for ev in events:
            await coverage_engine.register_event(
                db, event_id=ev["event_id"], source="test", headline=ev["headline"],
                urgency=ev["urgency"], importance=ev["importance"], sectors=[], companies=[],
            )


async def _get_coverage_status(event_id: str) -> str:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == event_id))).scalar_one()
        return row.coverage_status


def _run_with_mocks(triage_events, publish_side_effect, daily_count=0, today_story_ids=None,
                     find_duplicate_return=None, article_type="company_intelligence"):
    stack = ExitStack()
    stack.enter_context(patch("app.services.aipe.publisher.get_mie_context", new_callable=AsyncMock, return_value={"session": "closed", "themes": [], "mood": "neutral", "story": "", "story_hash": "x"}))
    stack.enter_context(patch("app.services.aipe.publisher.get_high_urgency_triage", new_callable=AsyncMock, return_value=triage_events))
    stack.enter_context(patch("app.services.aipe.publisher.filter_triage_batch", side_effect=lambda events, max_per_cycle: [(e, "approved") for e in events]))
    stack.enter_context(patch("app.services.aipe.publisher.count_today_articles", new_callable=AsyncMock, return_value=daily_count))
    stack.enter_context(patch("app.services.aipe.publisher.get_today_story_ids", new_callable=AsyncMock, return_value=today_story_ids or set()))
    stack.enter_context(patch("app.services.aipe.publisher.select_article_type", side_effect=lambda ev, mie: (article_type, f"story-{ev['event_id']}", "normal")))
    stack.enter_context(patch("app.services.aipe.publisher.find_duplicate", new_callable=AsyncMock, return_value=find_duplicate_return))
    publish_mock = stack.enter_context(patch("app.services.aipe.publisher._publish_new_article", new_callable=AsyncMock, side_effect=publish_side_effect))
    stack.enter_context(patch("app.services.aipe.publisher.plan_extra_angles", return_value=[]))
    stack.enter_context(patch("app.services.aipe.publisher.run_continuous_update_cycle", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher._scheduled_article_due", new_callable=AsyncMock, return_value=False))
    stack.enter_context(patch("app.services.aipe.publisher.get_latest_market_snapshot", new_callable=AsyncMock, return_value={}))
    return stack, publish_mock


# ── content_planner unit-level: reason_code is deterministic, not guessed ──

def test_reason_code_daily_cap():
    should_gen, reason, code = content_planner.should_generate_today(
        "company_intelligence", "story-x", set(), daily_count=8, max_per_day=8, critical=False,
    )
    assert should_gen is False
    assert code == "daily_cap"


def test_reason_code_already_generated_today():
    should_gen, reason, code = content_planner.should_generate_today(
        "market_wrap", "wrap-2026-08-31", {"wrap-2026-08-31"}, daily_count=0, max_per_day=8, critical=False,
    )
    assert should_gen is False
    assert code == "already_generated_today"


def test_reason_code_critical_bypass():
    should_gen, reason, code = content_planner.should_generate_today(
        "company_intelligence", "story-x", set(), daily_count=8, max_per_day=8, critical=True,
    )
    assert should_gen is True
    assert code == "critical_bypass"


# ── run_aipe_cycle integration: real EventCoverage terminal states ─────────

@pytest.mark.asyncio
async def test_noncritical_event_blocked_by_cap_marks_skipped_daily_cap():
    """Case 1: non-critical + daily cap reached -> SKIPPED_DAILY_CAP, and
    _publish_new_article is never even called (blocked before generation
    is attempted, at publisher.py's own pre-select_article_type gate)."""
    event_id = f"pytest-skip-cap-{uuid.uuid4().hex[:8]}"
    # urgency=6/importance=5 -> below the Critical/High threshold (see
    # coverage_engine._MUST_COVER_TIERS / compute_priority) -> non-critical.
    events = [_triage_event(event_id, "Non-critical event at cap", urgency=6, importance=5)]
    await _register_real_coverage_rows(events)
    try:
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[], daily_count=publisher._MAX_PER_DAY)
        with stack:
            await publisher.run_aipe_cycle()

        publish_mock.assert_not_called()
        assert await _get_coverage_status(event_id) == "SKIPPED_DAILY_CAP"
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_critical_event_bypasses_cap_and_generates():
    """Case 2: critical/high + cap reached -> bypass remains intact,
    generation proceeds (real regression guard: this must NOT start
    getting marked SKIPPED_DAILY_CAP by an over-broad fix)."""
    event_id = f"pytest-skip-critical-bypass-{uuid.uuid4().hex[:8]}"
    # urgency=9/importance=9 -> Critical tier (compute_priority) -> is_critical=True.
    events = [_triage_event(event_id, "Critical event past cap", urgency=9, importance=9)]
    await _register_real_coverage_rows(events)
    try:
        article = _fake_published_article(f"art-{event_id}", "Critical event past cap")
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[article], daily_count=publisher._MAX_PER_DAY)
        with stack:
            await publisher.run_aipe_cycle()

        publish_mock.assert_called_once()
        assert await _get_coverage_status(event_id) == "PUBLISHED"
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_already_generated_morning_wrap_marks_skipped_already_generated():
    """Case 3: already-generated morning/wrap slot -> SKIPPED_ALREADY_
    GENERATED_TODAY, no generation attempt."""
    event_id = f"pytest-skip-already-gen-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(event_id, "Second market wrap trigger today", urgency=6, importance=5)]
    await _register_real_coverage_rows(events)
    try:
        story_id = f"story-{event_id}"
        stack, publish_mock = _run_with_mocks(
            events, publish_side_effect=[], daily_count=0, today_story_ids={story_id},
            article_type="market_wrap",
        )
        with stack:
            await publisher.run_aipe_cycle()

        publish_mock.assert_not_called()
        assert await _get_coverage_status(event_id) == "SKIPPED_ALREADY_GENERATED_TODAY"
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_duplicate_marks_covered_by_existing_unchanged():
    """Case 4: a real duplicate match still correctly marks
    COVERED_BY_EXISTING_ARTICLE -- unchanged by this audit's fix, but
    covered here for a complete regression set."""
    event_id = f"pytest-skip-duplicate-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(event_id, "Duplicate of an existing story")]
    await _register_real_coverage_rows(events)
    try:
        existing = _fake_published_article(f"existing-{event_id}", "Existing story")
        stack, publish_mock = _run_with_mocks(
            events, publish_side_effect=[], daily_count=0, find_duplicate_return=existing,
        )
        # update_article is imported locally inside run_aipe_cycle's
        # duplicate branch (from app.services.aipe.continuous_updater
        # import update_article) -- patch it at its source, not on
        # publisher, since a fresh from-import re-resolves it at call time.
        with stack, patch("app.services.aipe.continuous_updater.update_article", new_callable=AsyncMock, return_value=existing):
            await publisher.run_aipe_cycle()

        publish_mock.assert_not_called()
        assert await _get_coverage_status(event_id) == "COVERED_BY_EXISTING_ARTICLE"
    finally:
        await _cleanup([event_id])

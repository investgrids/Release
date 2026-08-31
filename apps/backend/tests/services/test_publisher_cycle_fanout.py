"""
run_aipe_cycle() -- regression tests for a real bug found and fixed in the
2026-08-31 AIPE candidate lifecycle audit.

The "fan out extra angle articles" block used to live inside the FAILURE
branch of `if article and article.status == "published": ... else: ...`,
reading `article.headline`/`article.companies_affected`/etc. even when
`article` was None (a real generation failure, see _publish_new_article's
own None-return branch). That raised an uncaught AttributeError, caught
only by run_aipe_cycle's own outer try/except, which silently aborted the
REST of that cycle's approved batch (up to 2 other candidates) with zero
record that any of it happened.

The fix moves fan-out into the SUCCESS branch and leaves the failure
branch to only record the failure and move on. These tests exercise the
real run_aipe_cycle() orchestration against a real DB (this codebase's
established convention -- see test_coverage_engine.py/
test_candidate_lifecycle.py), with all external/generation calls mocked
so no LLM/network calls happen.
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
from app.services.aipe import publisher


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


def _fake_failed_article(article_id: str) -> IntelligenceArticle:
    return IntelligenceArticle(
        id=article_id, slug=article_id, article_type="company_intelligence",
        story_id=article_id, story_version=1, lifecycle_status="failed",
        status="failed", update_count=0, update_history=[],
        angle="primary", angle_entity=None,
        headline="unpublished", executive_summary="", key_takeaway="",
        why_it_matters="", what_happened="",
        companies_affected=[], sectors_affected=[],
    )


async def _cleanup(event_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(event_ids)))
        await db.commit()


def _triage_event(event_id: str, headline: str) -> dict:
    return {
        "event_id": event_id, "headline": headline, "urgency": 6, "importance": 5,
        "sectors": [], "themes": [], "tickers": [],
    }


async def _register_real_coverage_rows(events: list[dict]) -> None:
    async with AsyncSessionLocal() as db:
        for ev in events:
            await coverage_engine.register_event(
                db, event_id=ev["event_id"], source="test", headline=ev["headline"],
                urgency=ev["urgency"], importance=ev["importance"], sectors=[], companies=[],
            )


async def _get_coverage_status(event_id: str) -> tuple[str, str | None]:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == event_id))).scalar_one()
        return row.coverage_status, row.failure_reason


def _run_with_mocks(triage_events, publish_side_effect, fanout_return=None):
    """Enters every patch run_aipe_cycle needs (except coverage_engine,
    left real so EventCoverage rows are the assertion target), returns the
    ExitStack plus the plan_extra_angles and _publish_new_article mocks."""
    stack = ExitStack()
    stack.enter_context(patch("app.services.aipe.publisher.get_mie_context", new_callable=AsyncMock, return_value={"session": "closed", "themes": [], "mood": "neutral", "story": "", "story_hash": "x"}))
    stack.enter_context(patch("app.services.aipe.publisher.get_high_urgency_triage", new_callable=AsyncMock, return_value=triage_events))
    stack.enter_context(patch("app.services.aipe.publisher.filter_triage_batch", side_effect=lambda events, max_per_cycle: [(e, "approved") for e in events]))
    stack.enter_context(patch("app.services.aipe.publisher.count_today_articles", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher.get_today_story_ids", new_callable=AsyncMock, return_value=set()))
    stack.enter_context(patch("app.services.aipe.publisher.select_article_type", side_effect=lambda ev, mie: ("company_intelligence", f"story-{ev['event_id']}", "normal")))
    stack.enter_context(patch("app.services.aipe.publisher.should_generate_today", return_value=(True, "ok")))
    stack.enter_context(patch("app.services.aipe.publisher.find_duplicate", new_callable=AsyncMock, return_value=None))
    publish_mock = stack.enter_context(patch("app.services.aipe.publisher._publish_new_article", new_callable=AsyncMock, side_effect=publish_side_effect))
    fanout_mock = stack.enter_context(patch("app.services.aipe.publisher.plan_extra_angles", return_value=fanout_return or []))
    stack.enter_context(patch("app.services.aipe.publisher.run_continuous_update_cycle", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher._scheduled_article_due", new_callable=AsyncMock, return_value=False))
    stack.enter_context(patch("app.services.aipe.publisher.get_latest_market_snapshot", new_callable=AsyncMock, return_value={}))
    return stack, publish_mock, fanout_mock


@pytest.mark.asyncio
async def test_generation_failure_does_not_crash_cycle():
    """The exact crash this closes: _publish_new_article returns None
    (real generation failure) -- must not raise, must mark FAILED with
    reason=generation_failed, and must NOT attempt fan-out (plan_extra_
    angles must not be called)."""
    event_id = f"pytest-fanout-genfail-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(event_id, "Test generation failure headline")]
    await _register_real_coverage_rows(events)
    try:
        stack, publish_mock, fanout_mock = _run_with_mocks(events, publish_side_effect=[None])
        with stack:
            await publisher.run_aipe_cycle()  # must not raise

        fanout_mock.assert_not_called()
        status, reason = await _get_coverage_status(event_id)
        assert status == "FAILED"
        assert reason == "generation_failed"
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_validation_failure_does_not_crash_or_fanout():
    """_publish_new_article returns a real (non-None) article whose
    status != published -- must mark FAILED with reason=validation_failed
    and must NOT attempt fan-out either."""
    event_id = f"pytest-fanout-valfail-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(event_id, "Test validation failure headline")]
    await _register_real_coverage_rows(events)
    try:
        article = _fake_failed_article(f"art-{event_id}")
        stack, publish_mock, fanout_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack:
            await publisher.run_aipe_cycle()

        fanout_mock.assert_not_called()
        status, reason = await _get_coverage_status(event_id)
        assert status == "FAILED"
        assert reason == "validation_failed"
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_success_triggers_fanout():
    """A genuinely published article DOES reach the fan-out call (the
    real behavioral fix -- fan-out now runs on success, not failure)."""
    event_id = f"pytest-fanout-success-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(event_id, "Test success headline")]
    await _register_real_coverage_rows(events)
    try:
        article = _fake_published_article(f"art-{event_id}", "Test success headline")
        stack, publish_mock, fanout_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack:
            await publisher.run_aipe_cycle()

        fanout_mock.assert_called_once()
        called_headline = fanout_mock.call_args[0][2]
        assert called_headline == "Test success headline"
        status, reason = await _get_coverage_status(event_id)
        assert status == "PUBLISHED"
        assert reason is None
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_batch_continues_after_earlier_candidate_fails():
    """The real regression this whole fix is about: candidate 1 fails
    generation (article=None), candidates 2 and 3 must still be attempted
    and published in the SAME cycle -- before the fix, the AttributeError
    from candidate 1's fan-out attempt would have aborted the loop,
    silently dropping candidates 2 and 3 for that cycle."""
    ids = [f"pytest-fanout-batch-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    events = [_triage_event(ids[0], "fails"), _triage_event(ids[1], "succeeds 2"), _triage_event(ids[2], "succeeds 3")]
    await _register_real_coverage_rows(events)
    try:
        publish_results = [
            None,
            _fake_published_article(f"art-{ids[1]}", "succeeds 2"),
            _fake_published_article(f"art-{ids[2]}", "succeeds 3"),
        ]
        stack, publish_mock, fanout_mock = _run_with_mocks(events, publish_side_effect=publish_results)
        with stack:
            await publisher.run_aipe_cycle()  # must not raise partway through

        # All 3 candidates must have been attempted -- the real proof the
        # loop did not abort partway through.
        assert publish_mock.call_count == 3

        status0, reason0 = await _get_coverage_status(ids[0])
        status1, _ = await _get_coverage_status(ids[1])
        status2, _ = await _get_coverage_status(ids[2])
        assert status0 == "FAILED" and reason0 == "generation_failed"
        assert status1 == "PUBLISHED"
        assert status2 == "PUBLISHED"
    finally:
        await _cleanup(ids)

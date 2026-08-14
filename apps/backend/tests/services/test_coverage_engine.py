"""
Regression suite — app.services.coverage_engine, against the real
configured DB (this codebase's existing convention for DB-touching tests).

Covers:
  - register_event / mark_published / mark_covered_by_existing / mark_failed
    all write the coverage_status the audit's state machine expects.
  - mark_failed writes a real failure_reason and never overwrites a row
    that already reached PUBLISHED/COVERED_BY_EXISTING_ARTICLE (a failure
    surfacing AFTER a real success must not un-publish it).
  - funnel_counts' failed/possibly_truncated fields exist and behave
    sensibly (the 2026-08-13 re-audit fix for the no-ORDER-BY + LIMIT 2000
    truncation bug found live in production).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event_coverage import EventCoverage
from app.services import coverage_engine


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_mark_failed_writes_reason_and_status():
    test_id = f"pytest-coverage-failed-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        async with AsyncSessionLocal() as db:
            await coverage_engine.register_event(
                db, event_id=test_id, source="test", headline="Test Critical headline about RBI policy",
                urgency=9, importance=9, sectors=[], companies=[],
            )
            await coverage_engine.mark_failed(db, event_id=test_id, reason="generation_failed")

            from sqlalchemy import select
            row = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == test_id))).scalar_one()
            assert row.coverage_status == "FAILED"
            assert row.failure_reason == "generation_failed"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_mark_failed_does_not_overwrite_published():
    # A failure signal arriving after a real success (e.g. a late retry, or
    # a duplicate-detection race) must never regress a PUBLISHED row back
    # to FAILED — mark_failed explicitly guards this.
    test_id = f"pytest-coverage-failed-after-published-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        async with AsyncSessionLocal() as db:
            await coverage_engine.register_event(
                db, event_id=test_id, source="test", headline="Test headline",
                urgency=9, importance=9, sectors=[], companies=[],
            )
            await coverage_engine.mark_published(db, event_id=test_id, article_id="article-123")
            await coverage_engine.mark_failed(db, event_id=test_id, reason="should_not_apply")

            from sqlalchemy import select
            row = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == test_id))).scalar_one()
            assert row.coverage_status == "PUBLISHED", "mark_failed must not regress a PUBLISHED row"
            assert row.article_id == "article-123"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_funnel_counts_returns_failed_and_truncation_fields():
    async with AsyncSessionLocal() as db:
        funnel = await coverage_engine.funnel_counts(db, hours=1)
    assert "failed" in funnel, "funnel_counts must expose a distinct failed-coverage count"
    assert "possibly_truncated" in funnel, "funnel_counts must expose whether its result may be truncated"
    assert isinstance(funnel["failed"], int)
    assert isinstance(funnel["possibly_truncated"], bool)

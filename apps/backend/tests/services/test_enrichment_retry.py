"""
Regression suite — event enrichment retry/backoff (Phase 2, 2026-08-13
audit), against the real configured DB (this codebase's existing
convention for DB-touching tests).

Covers: first failure, backoff scheduling, repeated failure, max-retry
graduation to a terminal status, successful recovery, and that
get_pending_enrichment doesn't let a steady stream of new pending events
starve an older retry-eligible failure.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.repositories.event_repository import EventRepository
from app.pipeline.event_pipeline import (
    _compute_backoff,
    _classify_failure_reason,
    _AIUnavailable,
    _MAX_ENRICHMENT_RETRIES,
)


async def _make_event(event_id: str, **overrides) -> None:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=event_id, title="Test event", summary="x", source="test",
        event_type="news", published_at=now, created_at=now, updated_at=now,
        enrichment_status="pending",
    )
    defaults.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(Event(**defaults))
        await db.commit()


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(ids)))
        await db.commit()


def test_backoff_is_exponential_and_capped():
    now = datetime.now(timezone.utc)
    delays = [(_compute_backoff(n) - now).total_seconds() / 60 for n in range(1, 8)]
    # Strictly increasing until it hits the cap.
    for i in range(len(delays) - 1):
        assert delays[i] <= delays[i + 1]
    assert max(delays) <= 240 + 1  # capped at 4h, +1min tolerance for test execution time


def test_failure_classification():
    assert _classify_failure_reason(_AIUnavailable("x")) == "provider_unavailable"
    assert _classify_failure_reason(ValueError("boom")) == "pipeline_exception"


@pytest.mark.asyncio
async def test_first_failure_schedules_retry_not_permanent():
    test_id = f"pytest-retry-first-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            await repo.mark_enrichment_failed(
                test_id, retry_count=1, reason="rate_limited",
                next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, test_id)
            assert ev.enrichment_status == "failed"
            assert ev.retry_count == 1
            assert ev.last_failure_reason == "rate_limited"
            assert ev.next_retry_at is not None
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_retry_not_eligible_before_backoff_expires():
    test_id = f"pytest-retry-notyet-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id, enrichment_status="failed", retry_count=1)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            await repo.mark_enrichment_failed(
                test_id, retry_count=1, reason="rate_limited",
                next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),  # far future
            )
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=1000)
            assert test_id not in [e.id for e in pending], "should not be eligible before next_retry_at"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_retry_eligible_after_backoff_expires():
    test_id = f"pytest-retry-nowdue-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id, enrichment_status="failed", retry_count=1)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            await repo.mark_enrichment_failed(
                test_id, retry_count=1, reason="rate_limited",
                next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # already due
            )
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=1000)
            assert test_id in [e.id for e in pending], "should be eligible once next_retry_at has passed"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_max_retries_graduates_to_permanent_and_stops_retrying():
    test_id = f"pytest-retry-maxed-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id, enrichment_status="failed", retry_count=_MAX_ENRICHMENT_RETRIES - 1)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            # Simulate one more failure pushing it over the cap — mirrors
            # what run_event_pipeline's except-block does when
            # new_retry_count >= _MAX_ENRICHMENT_RETRIES.
            await repo.mark_enrichment_failed(
                test_id, retry_count=_MAX_ENRICHMENT_RETRIES, reason="pipeline_exception",
                next_retry_at=None,
            )
        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, test_id)
            assert ev.enrichment_status == "failed_permanent"
            assert ev.retry_count == _MAX_ENRICHMENT_RETRIES

            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=1000)
            assert test_id not in [e.id for e in pending], "permanently-failed events must not be retried"

            permanent = await repo.get_permanently_failed_enrichment(limit=1000)
            assert test_id in [e.id for e in permanent], "must remain visible in operational monitoring"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_successful_recovery_after_prior_failure():
    test_id = f"pytest-retry-recovers-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id, enrichment_status="failed", retry_count=2)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            await repo.mark_enrichment_failed(
                test_id, retry_count=2, reason="rate_limited",
                next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
            # A subsequent successful run calls mark_status(eid, "done") —
            # same as any other event, no special-casing needed.
            await repo.mark_status(test_id, "done")
        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, test_id)
            assert ev.enrichment_status == "done"
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=1000)
            assert test_id not in [e.id for e in pending], "done events must not be re-picked"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_new_pending_events_do_not_starve_older_retry_eligible_failure():
    old_failed_id = f"pytest-retry-old-{uuid.uuid4().hex[:8]}"
    new_pending_id = f"pytest-retry-new-{uuid.uuid4().hex[:8]}"
    await _cleanup(old_failed_id, new_pending_id)
    try:
        # Old failure, backoff already expired well in the past.
        await _make_event(old_failed_id, enrichment_status="failed", retry_count=1)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            await repo.mark_enrichment_failed(
                old_failed_id, retry_count=1, reason="rate_limited",
                next_retry_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        # Brand new pending event, created just now (would sort first under
        # the old `created_at DESC` ordering).
        await _make_event(new_pending_id)

        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=1000)
            ids = [e.id for e in pending]
            assert old_failed_id in ids and new_pending_id in ids
            # The older, already-overdue retry must not sort behind the
            # brand-new pending event.
            assert ids.index(old_failed_id) < ids.index(new_pending_id), (
                "new pending event starved an older retry-eligible failure"
            )
    finally:
        await _cleanup(old_failed_id, new_pending_id)

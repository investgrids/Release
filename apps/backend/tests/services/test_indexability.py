"""
Regression suite — coverage_engine.compute_indexable_batch/compute_indexable
(Phase 15, 2026-08 audit: sitemap/search eligibility must default to NOT
indexable absent real evidence of importance, to avoid indexing routine
low-value events — e.g. the ~94%-unscored NSE/BSE compliance-filing volume
already documented elsewhere in this codebase).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event_coverage import EventCoverage
from app.db.models.macro_release import MacroRelease
from app.services import coverage_engine


async def _cleanup(event_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(event_ids)))
        await db.execute(delete(MacroRelease).where(MacroRelease.id.in_(event_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_no_evidence_defaults_to_not_indexable():
    event_id = f"pytest-idx-none-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        result = await coverage_engine.compute_indexable(db, event_id)
    assert result is False


@pytest.mark.asyncio
async def test_critical_or_high_coverage_priority_is_indexable():
    critical_id = f"pytest-idx-critical-{uuid.uuid4().hex[:8]}"
    high_id = f"pytest-idx-high-{uuid.uuid4().hex[:8]}"
    medium_id = f"pytest-idx-medium-{uuid.uuid4().hex[:8]}"
    low_id = f"pytest-idx-low-{uuid.uuid4().hex[:8]}"
    ids = [critical_id, high_id, medium_id, low_id]
    await _cleanup(ids)
    try:
        async with AsyncSessionLocal() as db:
            for eid, tier in ((critical_id, "Critical"), (high_id, "High"), (medium_id, "Medium"), (low_id, "Low")):
                db.add(EventCoverage(event_id=eid, priority=tier, event_title="Test", detected_at=datetime.now(timezone.utc)))
            await db.commit()

            flags = await coverage_engine.compute_indexable_batch(db, ids)
        assert flags[critical_id] is True
        assert flags[high_id] is True
        assert flags[medium_id] is False
        assert flags[low_id] is False
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_real_macro_release_is_indexable_regardless_of_coverage_priority():
    # A genuine economic data print is always worth indexing — even a
    # Medium-tier triage priority shouldn't suppress it once a real value
    # was extracted.
    event_id = f"pytest-idx-macro-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(event_id=event_id, priority="Medium", event_title="Test", detected_at=datetime.now(timezone.utc)))
            db.add(MacroRelease(
                id=event_id, event_id=event_id, metric="CPI", release_value=4.2,
                affected_sectors=[], affected_companies=[], headline="Test macro headline",
            ))
            await db.commit()

            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is True
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_macro_release_row_without_a_real_value_does_not_force_indexable():
    # A MacroRelease row could theoretically exist with release_value=None
    # (defensive case) — must not be treated as real evidence.
    event_id = f"pytest-idx-macro-null-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(MacroRelease(
                id=event_id, event_id=event_id, metric="CPI", release_value=None,
                affected_sectors=[], affected_companies=[], headline="Test macro headline",
            ))
            await db.commit()

            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_batch_handles_empty_list():
    async with AsyncSessionLocal() as db:
        result = await coverage_engine.compute_indexable_batch(db, [])
    assert result == {}

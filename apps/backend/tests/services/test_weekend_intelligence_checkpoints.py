"""
Checkpoint runner tests — brief §32/§33's non-scheduler behaviors
(material-change gating, versioning through the real runner, safe
duplicate invocation). Scheduler registration itself is covered in
test_weekend_intelligence_scheduler.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.event import Event
from app.db.models.intelligence import MarketSnapshot
from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot
from app.db.session import AsyncSessionLocal
from app.services.weekend_intelligence.checkpoints import CREATED, SKIPPED_NO_MATERIAL_CHANGE, run_checkpoint

TARGET = "2099-05-04"  # a Monday; matches session_resolution's own arithmetic, no need to hardcode last_trading
CHECKPOINT_1 = datetime(2099, 5, 2, 4, 0, tzinfo=timezone.utc)   # Saturday morning
CHECKPOINT_2 = datetime(2099, 5, 2, 13, 0, tzinfo=timezone.utc)  # Saturday evening
CHECKPOINT_3 = datetime(2099, 5, 3, 4, 0, tzinfo=timezone.utc)   # Sunday morning


async def _cleanup(event_ids=(), snapshot_ids=()):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(WeekendIntelligenceSnapshot).where(WeekendIntelligenceSnapshot.target_trading_date == TARGET))
        if event_ids:
            await db.execute(delete(Event).where(Event.id.in_(event_ids)))
        if snapshot_ids:
            await db.execute(delete(MarketSnapshot).where(MarketSnapshot.id.in_(snapshot_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_first_checkpoint_always_creates_version_1_even_with_low_evidence():
    """brief §22's explicit exception: the first snapshot for a
    target_trading_date is created even with thin/no evidence, so the
    system has an explicit state."""
    await _cleanup()
    try:
        async with AsyncSessionLocal() as db:
            result = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_1, checkpoint_label="Saturday AM")
        assert result.outcome == CREATED
        assert result.snapshot_version == 1
        assert result.status == "insufficient_evidence"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_second_checkpoint_with_no_new_evidence_is_skipped():
    await _cleanup()
    try:
        async with AsyncSessionLocal() as db:
            first = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_1, checkpoint_label="Saturday AM")
        assert first.outcome == CREATED

        async with AsyncSessionLocal() as db:
            second = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_2, checkpoint_label="Saturday PM")
        assert second.outcome == SKIPPED_NO_MATERIAL_CHANGE

        async with AsyncSessionLocal() as db:
            from app.services.weekend_intelligence.versioning import get_version_history
            history = await get_version_history(db, TARGET)
            assert len(history) == 1  # no new version created by the skip
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_material_new_evidence_creates_version_2_and_supersedes_version_1():
    await _cleanup()
    event_id = f"pytest-cp-evt-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            first = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_1, checkpoint_label="Saturday AM")
        assert first.snapshot_version == 1

        # New Critical-tier-worthy evidence lands between checkpoint 1 and 2.
        async with AsyncSessionLocal() as db:
            from app.db.models.intelligence import EventTriage
            triage_id = f"pytest-cp-triage-{uuid.uuid4().hex[:8]}"
            db.add(Event(id=event_id, title="RBI announces emergency repo rate cut",
                         published_at=datetime(2099, 5, 2, 8, 0, tzinfo=timezone.utc),
                         companies=["HDFCBANK"], sectors=["Banking"], confidence=90.0))
            db.add(EventTriage(id=triage_id, event_id=event_id, source="policy",
                                headline="RBI announces emergency repo rate cut", urgency=10, importance=10))
            await db.commit()

            second = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_2, checkpoint_label="Saturday PM")
        assert second.outcome == CREATED
        assert second.snapshot_version == 2

        async with AsyncSessionLocal() as db:
            from app.services.weekend_intelligence.versioning import get_current_snapshot, get_version_history
            history = await get_version_history(db, TARGET)
            assert [h.version for h in history] == [1, 2]
            current = await get_current_snapshot(db, TARGET)
            assert current.version == 2
            v1 = next(h for h in history if h.version == 1)
            assert v1.is_current is False
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_duplicate_invocation_at_same_checkpoint_time_is_safe():
    """Simulates a scheduler restart re-firing the same checkpoint —
    must not create a second identical version."""
    await _cleanup()
    try:
        async with AsyncSessionLocal() as db:
            first = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_1, checkpoint_label="Saturday AM")
        async with AsyncSessionLocal() as db:
            second = await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_1, checkpoint_label="Saturday AM (retry)")

        assert first.outcome == CREATED
        assert second.outcome == SKIPPED_NO_MATERIAL_CHANGE

        async with AsyncSessionLocal() as db:
            from app.services.weekend_intelligence.versioning import get_version_history
            history = await get_version_history(db, TARGET)
            assert len(history) == 1
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_exactly_one_current_row_across_three_checkpoints():
    await _cleanup()
    event_id = f"pytest-cp-evt-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_1, checkpoint_label="Saturday AM")

        async with AsyncSessionLocal() as db:
            from app.db.models.intelligence import EventTriage
            triage_id = f"pytest-cp-triage-{uuid.uuid4().hex[:8]}"
            db.add(Event(id=event_id, title="Major policy shift affecting NBFC sector",
                         published_at=datetime(2099, 5, 3, 2, 0, tzinfo=timezone.utc),
                         companies=["BAJFINANCE"], sectors=["Finance"], confidence=88.0))
            db.add(EventTriage(id=triage_id, event_id=event_id, source="policy",
                                headline="Major policy shift affecting NBFC sector", urgency=9, importance=9))
            await db.commit()
            await run_checkpoint(db, TARGET, checkpoint_time=CHECKPOINT_3, checkpoint_label="Sunday AM")

        async with AsyncSessionLocal() as db:
            from app.services.weekend_intelligence.versioning import get_version_history
            history = await get_version_history(db, TARGET)
            current_rows = [h for h in history if h.is_current]
            assert len(current_rows) == 1
    finally:
        await _cleanup(event_ids=[event_id])

"""
Evidence window tests — real DB (this codebase's convention for
DB-touching tests, see test_dashboard_metrics.py), unique test-scoped
ids, explicit cleanup. Covers the core correctness requirement design
doc §17 calls out: a real lower bound, not "latest N rows."
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.event import Event
from app.db.session import AsyncSessionLocal
from app.services.weekend_intelligence.evidence_window import collect_evidence_since


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_evidence_before_window_is_excluded():
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=2)
    before_id = f"pytest-wi-before-{uuid.uuid4().hex[:8]}"
    inside_id = f"pytest-wi-inside-{uuid.uuid4().hex[:8]}"
    ids = [before_id, inside_id]
    await _cleanup(*ids)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=before_id, title="Before window", published_at=since - timedelta(hours=1)))
            db.add(Event(id=inside_id, title="Inside window", published_at=since + timedelta(minutes=30)))
            await db.commit()

            items = await collect_evidence_since(db, since, now)
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert before_id not in found_ids
            assert inside_id in found_ids
    finally:
        await _cleanup(*ids)


@pytest.mark.asyncio
async def test_evidence_at_exact_since_boundary_is_excluded():
    """since is exclusive (`>`), until is inclusive (`<=`) — a row stamped
    exactly at `since` belongs to the PRIOR window, not this one."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    boundary_id = f"pytest-wi-boundary-{uuid.uuid4().hex[:8]}"
    await _cleanup(boundary_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=boundary_id, title="Exactly at since", published_at=since))
            await db.commit()

            items = await collect_evidence_since(db, since, now)
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert boundary_id not in found_ids
    finally:
        await _cleanup(boundary_id)


@pytest.mark.asyncio
async def test_evidence_after_until_is_excluded():
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=2)
    until = now - timedelta(hours=1)
    after_id = f"pytest-wi-after-{uuid.uuid4().hex[:8]}"
    await _cleanup(after_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=after_id, title="After until", published_at=now))
            await db.commit()

            items = await collect_evidence_since(db, since, until)
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert after_id not in found_ids
    finally:
        await _cleanup(after_id)


@pytest.mark.asyncio
async def test_event_priority_tier_joined_from_event_triage():
    from app.db.models.intelligence import EventTriage

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    event_id = f"pytest-wi-triaged-{uuid.uuid4().hex[:8]}"
    triage_id = f"pytest-wi-triage-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=event_id, title="RBI monetary policy decision", published_at=now))
            db.add(EventTriage(
                id=triage_id, event_id=event_id, source="policy",
                headline="RBI monetary policy decision", urgency=10, importance=10,
            ))
            await db.commit()

            items = await collect_evidence_since(db, since, now + timedelta(minutes=1))
            match = next(i for i in items if i.source_type == "event" and i.source_id == event_id)
            assert match.impact_strength in ("Critical", "High")
    finally:
        await _cleanup(event_id)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventTriage).where(EventTriage.id == triage_id))
            await db.commit()

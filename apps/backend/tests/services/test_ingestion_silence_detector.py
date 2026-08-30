"""
job_check_ingestion_silence — real, since a real ~4-day EventTriage gap
(2026-08-26, artifacts/aipe_scheduler_publication_failure_audit.md) went
undetected until a retrospective 30-day audit found it. Real DB-backed
tests, no mocking of the DB query itself (only the log calls, to assert
on them).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.tasks.daily_tasks import job_check_ingestion_silence


async def _seed_triage(triaged_at: datetime) -> str:
    event_id = f"test-{uuid.uuid4().hex[:12]}"
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=str(uuid.uuid4()), event_id=event_id, source="news", headline="Test headline",
            urgency=1, importance=1, triaged_at=triaged_at,
        ))
        await db.commit()
    return event_id


async def _cleanup(event_id: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id == event_id))
        await db.commit()


@pytest.mark.asyncio
async def test_recent_triage_does_not_trigger_silence_alert(monkeypatch):
    calls = []
    monkeypatch.setattr("app.tasks.daily_tasks.log.error", lambda *a, **kw: calls.append((a, kw)))
    event_id = await _seed_triage(datetime.now(timezone.utc) - timedelta(minutes=5))
    try:
        await job_check_ingestion_silence()
        assert calls == []
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_stale_triage_beyond_threshold_triggers_silence_alert(monkeypatch):
    calls = []
    monkeypatch.setattr("app.tasks.daily_tasks.log.error", lambda *a, **kw: calls.append((a, kw)))
    stale_at = datetime.now(timezone.utc) - timedelta(hours=6)
    event_id = await _seed_triage(stale_at)
    try:
        await job_check_ingestion_silence()
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert args[0] == "ingestion.silence_detected"
        assert kwargs["gap_minutes"] > 90
    finally:
        await _cleanup(event_id)

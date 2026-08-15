"""
WeekendContext loader tests — brief §36. DB-backed: creates real
WeekendIntelligenceSnapshot rows via versioning.create_next_version,
cleans up in finally.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import AsyncSessionLocal
from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot
from app.services.weekend_intelligence.context import get_weekend_context_for_session
from app.services.weekend_intelligence.versioning import create_next_version
from sqlalchemy import delete


def _target() -> str:
    return f"2099-06-{uuid.uuid4().hex[:2] or '01'}"  # placeholder, overridden per test


@pytest.mark.asyncio
async def test_correct_target_date_returns_context():
    target = f"2099-06-0{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-06-01",
                status="ok", overall_bias="positive", production_confidence=70.0,
                top_sector_refs=[{"sector": "IT", "direction": "positive", "score": 0.7, "evidence_count": 3}],
                top_company_refs=[{"symbol": "INFY", "state": "positive_watch", "confidence": 0.6, "evidence_count": 2}],
                new_since_close_refs=[{"source_type": "event", "source_id": "e1", "title": "t", "direction": "positive"}],
                market_snapshot_id="ms1",
            )
            await db.commit()

            context = await get_weekend_context_for_session(db, target)
            assert context is not None
            assert context.target_trading_date == target
            assert context.overall_bias == "positive"
            assert context.production_confidence == 70.0
            assert context.top_sector_signals[0].id == "IT"
            assert context.top_sector_signals[0].direction == "positive"
            assert context.top_company_signals[0].id == "INFY"
            assert context.top_company_signals[0].direction == "positive_watch"  # state, not "direction" key
            assert context.baseline_available is True
            assert context.meaningful_development_count == 1
            assert "e1" in context.meaningful_development_event_ids
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()


@pytest.mark.asyncio
async def test_wrong_target_date_returns_none():
    target = f"2099-06-1{(uuid.uuid4().int % 8) + 1}"
    other = f"2099-06-2{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-06-10",
                status="ok", overall_bias="positive", production_confidence=70.0,
            )
            await db.commit()
            context = await get_weekend_context_for_session(db, other)
            assert context is None
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()


@pytest.mark.asyncio
async def test_no_snapshot_returns_none():
    target = f"2099-07-0{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        context = await get_weekend_context_for_session(db, target)
        assert context is None


@pytest.mark.asyncio
async def test_stale_snapshot_returns_none():
    target = f"2099-07-1{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            snap = await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-07-10",
                status="ok", overall_bias="positive", production_confidence=70.0,
            )
            snap.generated_at = datetime.now(timezone.utc) - timedelta(hours=48)
            await db.commit()

            context = await get_weekend_context_for_session(db, target)
            assert context is None
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()


@pytest.mark.asyncio
async def test_non_current_snapshot_ignored():
    """A superseded version must never be returned even if queried
    directly — get_current_snapshot already filters is_current=True, and
    the loader defensively re-checks it."""
    target = f"2099-07-2{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            v1 = await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-07-20",
                status="ok", overall_bias="positive", production_confidence=70.0,
            )
            await db.commit()
            v1.is_current = False
            await db.commit()

            context = await get_weekend_context_for_session(db, target)
            assert context is None
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()


@pytest.mark.asyncio
async def test_degraded_snapshot_returns_valid_reduced_quality_context():
    target = f"2099-08-0{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-08-01",
                status="degraded", overall_bias="mixed", production_confidence=35.0,
                market_snapshot_id=None,
            )
            await db.commit()
            context = await get_weekend_context_for_session(db, target)
            assert context is not None
            assert context.status == "degraded"
            assert context.baseline_available is False
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()


@pytest.mark.asyncio
async def test_insufficient_evidence_context_has_no_directional_signal():
    target = f"2099-08-1{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-08-10",
                status="insufficient_evidence", overall_bias="neutral", production_confidence=0.0,
            )
            await db.commit()
            context = await get_weekend_context_for_session(db, target)
            assert context is not None
            assert context.has_directional_signal is False
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()


@pytest.mark.asyncio
async def test_malformed_status_rejected():
    target = f"2099-08-2{(uuid.uuid4().int % 8) + 1}"
    async with AsyncSessionLocal() as db:
        try:
            snap = await create_next_version(
                db, target_trading_date=target, last_trading_date="2099-08-20",
                status="ok", overall_bias="positive", production_confidence=70.0,
            )
            await db.commit()
            snap.status = "totally_bogus_status"
            await db.commit()

            context = await get_weekend_context_for_session(db, target)
            assert context is None
        finally:
            await db.execute(delete(WeekendIntelligenceSnapshot).where(
                WeekendIntelligenceSnapshot.target_trading_date == target))
            await db.commit()

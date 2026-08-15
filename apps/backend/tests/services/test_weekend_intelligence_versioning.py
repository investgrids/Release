"""
WeekendIntelligenceSnapshot versioning tests — real DB, unique
test-scoped target_trading_date per test (so tests can run concurrently/
repeatedly without colliding on the is_current partial-unique index),
explicit cleanup.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot
from app.db.session import AsyncSessionLocal
from app.services.weekend_intelligence.versioning import (
    create_next_version,
    get_current_snapshot,
    get_version_history,
)


def _target_date() -> str:
    # A fake, obviously-test-scoped date string, unique per test run —
    # target_trading_date isn't a real FK to anything, just an indexed
    # string key, so this is safe and avoids colliding with any other
    # test/real data.
    return f"2099-01-{uuid.uuid4().hex[:2]}"


async def _cleanup(target_trading_date: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(WeekendIntelligenceSnapshot).where(
            WeekendIntelligenceSnapshot.target_trading_date == target_trading_date
        ))
        await db.commit()


@pytest.mark.asyncio
async def test_first_snapshot_version_is_one_and_current():
    target = _target_date()
    await _cleanup(target)
    try:
        async with AsyncSessionLocal() as db:
            snap = await create_next_version(db, target_trading_date=target, last_trading_date="2098-12-31")
            await db.commit()
            assert snap.version == 1
            assert snap.is_current is True
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_second_version_increments_and_supersedes_first():
    target = _target_date()
    await _cleanup(target)
    try:
        async with AsyncSessionLocal() as db:
            first = await create_next_version(db, target_trading_date=target, last_trading_date="2098-12-31")
            await db.commit()
            first_id = first.id

        async with AsyncSessionLocal() as db:
            second = await create_next_version(db, target_trading_date=target, last_trading_date="2098-12-31")
            await db.commit()
            assert second.version == 2
            assert second.is_current is True

        async with AsyncSessionLocal() as db:
            current = await get_current_snapshot(db, target)
            assert current.id == second.id
            assert current.version == 2

            history = await get_version_history(db, target)
            assert [h.version for h in history] == [1, 2]
            first_row = next(h for h in history if h.id == first_id)
            assert first_row.is_current is False
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_exactly_one_current_row_after_multiple_versions():
    target = _target_date()
    await _cleanup(target)
    try:
        for _ in range(4):
            async with AsyncSessionLocal() as db:
                await create_next_version(db, target_trading_date=target, last_trading_date="2098-12-31")
                await db.commit()

        async with AsyncSessionLocal() as db:
            history = await get_version_history(db, target)
            current_rows = [h for h in history if h.is_current]
            assert len(history) == 4
            assert len(current_rows) == 1
            assert current_rows[0].version == 4
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_no_current_snapshot_for_unknown_target_returns_none():
    target = _target_date()
    async with AsyncSessionLocal() as db:
        result = await get_current_snapshot(db, target)
        assert result is None


@pytest.mark.asyncio
async def test_prior_version_content_not_overwritten():
    """Immutability: creating v2 must not change v1's own stored fields —
    only its is_current flag."""
    target = _target_date()
    await _cleanup(target)
    try:
        async with AsyncSessionLocal() as db:
            first = await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-12-31",
                checkpoint_label="Saturday AM", overall_bias="neutral",
            )
            await db.commit()
            first_id = first.id

        async with AsyncSessionLocal() as db:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-12-31",
                checkpoint_label="Sunday PM", overall_bias="bullish",
            )
            await db.commit()

        async with AsyncSessionLocal() as db:
            history = await get_version_history(db, target)
            first_row = next(h for h in history if h.id == first_id)
            assert first_row.checkpoint_label == "Saturday AM"
            assert first_row.overall_bias == "neutral"
            assert first_row.is_current is False
    finally:
        await _cleanup(target)

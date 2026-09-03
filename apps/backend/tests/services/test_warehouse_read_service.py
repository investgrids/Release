"""
Warehouse Read Service — Phase 2 Consumption (owner instruction, 2026-08-25,
following the read-only Warehouse Consumption Audit).

Real DB-backed, no mocks. Uses a synthetic metric name (never colliding with
a real production metric) so assertions are exact regardless of whatever
real rows already exist in this DB, matching this session's established
test-isolation discipline.

`source_id` originally reused a real seeded source row from the shared dev
DB (`yfinance_india_vix`) -- fixed after this test suite was run against a
fully test-isolated DB (tests/conftest.py's session-scoped scratch DB,
never the real dev DB) and every insert-based test failed on a real FK
violation: the scratch DB has the real schema but none of
source_registry_seed.py's real rows. That's not a bug in the isolation
guardrail -- it's the guardrail correctly catching that these tests
implicitly depended on real local seed data rather than being genuinely
self-contained. Fixed properly: each test seeds its own synthetic Source
row instead.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.market_observation import MarketObservation
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.warehouse.read_service import (
    get_latest_market_observations,
    get_market_context_at,
)


def _tag() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def source_id():
    """A synthetic Source row, self-contained -- never assumes any real
    seed data exists in whatever DB the test suite happens to run
    against."""
    sid = f"test_source_{_tag()}"
    async with AsyncSessionLocal() as db:
        db.add(Source(id=sid, name="Test Source", source_type="api", collection_method="test"))
        await db.commit()
    yield sid
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Source).where(Source.id == sid))
        await db.commit()


async def _insert(rows: list[MarketObservation]) -> None:
    async with AsyncSessionLocal() as db:
        db.add_all(rows)
        await db.commit()


async def _cleanup(metric: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketObservation).where(MarketObservation.metric == metric))
        await db.commit()


def _row(metric: str, value: float | None, quality: str, obs_time: datetime, source_id: str, extra: dict | None = None) -> MarketObservation:
    return MarketObservation(
        id=str(uuid.uuid4()), metric=metric, value=value, unit="index_points",
        observation_time=obs_time, market_date=obs_time.date(), session="live",
        source_id=source_id, captured_at=obs_time, quality=quality, extra=extra,
    )


@pytest.mark.asyncio
async def test_get_latest_returns_the_newest_row_per_metric(source_id):
    metric = f"TEST_METRIC_{_tag()}"
    now = datetime.now(timezone.utc)
    older = now - timedelta(minutes=30)
    try:
        await _insert([
            _row(metric, 100.0, "fresh", older, source_id),
            _row(metric, 105.5, "fresh", now, source_id),
        ])
        async with AsyncSessionLocal() as db:
            result = await get_latest_market_observations(db, metrics=[metric])
        assert metric in result
        snap = result[metric]
        assert snap.value == 105.5, "must return the NEWEST row, not the first/oldest"
        assert snap.quality == "fresh"
        assert snap.is_current is True
    finally:
        await _cleanup(metric)


@pytest.mark.asyncio
async def test_get_latest_reports_stale_data_honestly_not_as_current(source_id):
    """A real row that's genuinely old (capture stopped) must be flagged
    is_current=False, never silently presented as if it were fresh."""
    metric = f"TEST_METRIC_{_tag()}"
    ancient = datetime.now(timezone.utc) - timedelta(hours=6)
    try:
        await _insert([_row(metric, 42.0, "fresh", ancient, source_id)])
        async with AsyncSessionLocal() as db:
            result = await get_latest_market_observations(db, metrics=[metric])
        assert result[metric].is_current is False
        assert result[metric].value == 42.0, "the real stale value is still returned -- caller decides what to do with it, never silently dropped"
    finally:
        await _cleanup(metric)


@pytest.mark.asyncio
async def test_get_latest_never_fabricates_a_missing_metric():
    """A metric with zero real rows must be absent from the result --
    never filled in as a fake zero or a silently-assumed-normal value."""
    metric = f"TEST_METRIC_NEVER_CAPTURED_{_tag()}"
    async with AsyncSessionLocal() as db:
        result = await get_latest_market_observations(db, metrics=[metric])
    assert metric not in result


@pytest.mark.asyncio
async def test_get_latest_preserves_a_real_source_failure_row_honestly(source_id):
    """A real source_failure row (value=NULL) must still come back --
    proves this layer doesn't silently filter out real capture failures,
    matching Warehouse's own 'never fabricate, never drop' discipline."""
    metric = f"TEST_METRIC_{_tag()}"
    now = datetime.now(timezone.utc)
    try:
        await _insert([_row(metric, None, "source_failure", now, source_id)])
        async with AsyncSessionLocal() as db:
            result = await get_latest_market_observations(db, metrics=[metric])
        assert metric in result
        assert result[metric].value is None
        assert result[metric].quality == "source_failure"
        assert result[metric].has_real_value is False
    finally:
        await _cleanup(metric)


@pytest.mark.asyncio
async def test_get_market_context_at_finds_the_nearest_real_observation(source_id):
    metric = f"TEST_METRIC_{_tag()}"
    anchor = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        await _insert([
            _row(metric, 10.0, "fresh", anchor - timedelta(minutes=20), source_id),
            _row(metric, 20.0, "fresh", anchor - timedelta(minutes=3), source_id),   # nearest
            _row(metric, 30.0, "fresh", anchor + timedelta(minutes=25), source_id),
        ])
        async with AsyncSessionLocal() as db:
            result = await get_market_context_at(db, anchor, metrics=[metric], window_minutes=30)
        assert result[metric].value == 20.0, "must pick the row closest in time to the anchor, not the newest or oldest"
    finally:
        await _cleanup(metric)


@pytest.mark.asyncio
async def test_get_market_context_at_respects_the_window_boundary(source_id):
    """A real row that exists but falls outside the requested window must
    not be returned -- no silent widening, no nearest-available fallback
    across an explicit boundary the caller set."""
    metric = f"TEST_METRIC_{_tag()}"
    anchor = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        await _insert([_row(metric, 99.0, "fresh", anchor - timedelta(minutes=90), source_id)])
        async with AsyncSessionLocal() as db:
            result = await get_market_context_at(db, anchor, metrics=[metric], window_minutes=30)
        assert metric not in result
    finally:
        await _cleanup(metric)


@pytest.mark.asyncio
async def test_get_market_context_at_never_interpolates_between_real_rows(source_id):
    """Two real rows straddling the anchor must never be averaged/
    interpolated into a fabricated value -- only the nearer real row is
    ever returned."""
    metric = f"TEST_METRIC_{_tag()}"
    anchor = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        await _insert([
            _row(metric, 50.0, "fresh", anchor - timedelta(minutes=10), source_id),
            _row(metric, 60.0, "fresh", anchor + timedelta(minutes=15), source_id),
        ])
        async with AsyncSessionLocal() as db:
            result = await get_market_context_at(db, anchor, metrics=[metric], window_minutes=30)
        assert result[metric].value in (50.0, 60.0), "must be one of the two real rows, never an average like 55.0"
        assert result[metric].value == 50.0, "the row 10 minutes away is nearer than the one 15 minutes away"
    finally:
        await _cleanup(metric)

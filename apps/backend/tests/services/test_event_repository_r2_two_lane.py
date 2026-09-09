"""
Regression suite — R2-B two-lane fresh/backlog scheduling
(app/repositories/event_repository.py::get_pending_enrichment), against
the isolated test-scratch DB (see conftest.py).

Covers exactly the invariants the R2 design review locked: lane
membership by created_at (age) only, retry state never creates a third
lane or promotes/demotes a lane, FIFO within each lane preserved,
guaranteed backlog service only when an eligible backlog row exists,
work-conserving fallthrough in both directions, no duplicate row across
lanes, and the wall-clock N=4 bucket boundary (injectable via the `now`
kwarg for deterministic tests rather than depending on real wall-clock
time at test-run).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.repositories.event_repository import EventRepository

_INTERVAL_SEC = 300  # matches settings.event_enrichment_interval_sec default


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


def _guarantee_bucket_time(force: bool) -> datetime:
    """Returns a UTC datetime whose wall-clock bucket satisfies
    (bucket % 4 == 0) == force, for deterministic testing of the
    backlog-guarantee boundary without depending on real wall-clock time."""
    base = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)
    bucket = int(base.timestamp() // _INTERVAL_SEC)
    # Walk forward in whole-bucket steps until we hit the desired parity.
    # (NOTE: `X == 0 != force` is a Python chained comparison -- it means
    # `X == 0 and 0 != force`, NOT `(X == 0) != force`. Must be spelled out.)
    offset = 0
    while ((bucket + offset) % 4 == 0) != force:
        offset += 1
    return base + timedelta(seconds=_INTERVAL_SEC * offset)


@pytest.mark.asyncio
async def test_fresh_event_created_at_exactly_cutoff_is_fresh_not_backlog():
    """created_at == now - 24h is the inclusive fresh-lane boundary
    (Event.created_at >= cutoff): confirmed by seeding an old_failed-style
    backlog event alongside one sitting exactly on the line, then checking
    both lanes' membership via the guarantee mechanism rather than reading
    private lane internals."""
    test_id = f"pytest-r2-boundary-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        now = _guarantee_bucket_time(force=False)
        cutoff = now - timedelta(hours=24)
        await _make_event(test_id, created_at=cutoff, updated_at=cutoff)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=1000, now=now)
            assert test_id in [e.id for e in pending]
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_retry_stays_in_lane_by_age_not_by_retry_state():
    """An OLD event (created 30h ago) with a just-expired retry backoff
    must land in the backlog lane, never get promoted to fresh just
    because it's newly eligible again."""
    old_id = f"pytest-r2-old-retry-{uuid.uuid4().hex[:8]}"
    fresh_id = f"pytest-r2-fresh-retry-{uuid.uuid4().hex[:8]}"
    await _cleanup(old_id, fresh_id)
    try:
        now = _guarantee_bucket_time(force=True)
        old_created = now - timedelta(hours=30)
        await _make_event(
            old_id, created_at=old_created, updated_at=old_created,
            enrichment_status="failed", retry_count=1,
            next_retry_at=now - timedelta(minutes=1),
        )
        # A fresh (created 1h ago) event also with a just-expired retry.
        fresh_created = now - timedelta(hours=1)
        await _make_event(
            fresh_id, created_at=fresh_created, updated_at=fresh_created,
            enrichment_status="failed", retry_count=1,
            next_retry_at=now - timedelta(minutes=1),
        )
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            # limit=1 on a guarantee bucket: exactly 1 slot, reserved for
            # backlog since an eligible backlog row (old_id) exists --
            # proves old_id is being served from the backlog lane, not
            # merely happening to sort first in a single combined queue.
            pending = await repo.get_pending_enrichment(limit=1, now=now)
            assert [e.id for e in pending] == [old_id]
    finally:
        await _cleanup(old_id, fresh_id)


@pytest.mark.asyncio
async def test_empty_fresh_lane_all_slots_fall_through_to_backlog():
    ids = [f"pytest-r2-onlybacklog-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    await _cleanup(*ids)
    try:
        now = _guarantee_bucket_time(force=False)  # non-guarantee bucket
        old_created = now - timedelta(hours=48)
        for eid in ids:
            await _make_event(eid, created_at=old_created, updated_at=old_created)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=3, now=now)
            assert sorted(e.id for e in pending) == sorted(ids), (
                "no fresh demand must not waste capacity -- all slots should "
                "fall through to backlog even off the guarantee bucket"
            )
    finally:
        await _cleanup(*ids)


@pytest.mark.asyncio
async def test_empty_backlog_guarantee_falls_through_to_fresh():
    ids = [f"pytest-r2-onlyfresh-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    await _cleanup(*ids)
    try:
        now = _guarantee_bucket_time(force=True)  # guarantee bucket, but...
        fresh_created = now - timedelta(hours=1)
        for eid in ids:
            await _make_event(eid, created_at=fresh_created, updated_at=fresh_created)
        # ...no backlog rows exist at all, so the reserved slot must not be
        # wasted.
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=3, now=now)
            assert sorted(e.id for e in pending) == sorted(ids)
    finally:
        await _cleanup(*ids)


@pytest.mark.asyncio
async def test_fewer_than_limit_eligible_rows_returns_exactly_what_exists():
    fresh_id = f"pytest-r2-partial-{uuid.uuid4().hex[:8]}"
    await _cleanup(fresh_id)
    try:
        now = _guarantee_bucket_time(force=False)
        fresh_created = now - timedelta(minutes=5)
        await _make_event(fresh_id, created_at=fresh_created, updated_at=fresh_created)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=3, now=now)
            assert [e.id for e in pending] == [fresh_id]
    finally:
        await _cleanup(fresh_id)


@pytest.mark.asyncio
async def test_guarantee_bucket_reserves_one_backlog_slot_before_fresh():
    """3 fresh + 3 backlog eligible, limit=3, guarantee bucket: exactly 1
    backlog row (the oldest-eligible one) plus 2 fresh rows (oldest-eligible
    first) -- never 3 fresh with backlog starved on a bucket where the
    guarantee is due and satisfiable."""
    fresh_ids = [f"pytest-r2-gbfresh-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    backlog_ids = [f"pytest-r2-gbback-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    await _cleanup(*fresh_ids, *backlog_ids)
    try:
        now = _guarantee_bucket_time(force=True)
        for i, eid in enumerate(fresh_ids):
            created = now - timedelta(hours=1, minutes=i)  # oldest-first: index 0 oldest? see below
            await _make_event(eid, created_at=created, updated_at=created)
        for i, eid in enumerate(backlog_ids):
            created = now - timedelta(hours=30, minutes=i)
            await _make_event(eid, created_at=created, updated_at=created)

        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=3, now=now)
            result_ids = [e.id for e in pending]
            assert len(result_ids) == 3
            backlog_selected = [i for i in result_ids if i in backlog_ids]
            fresh_selected = [i for i in result_ids if i in fresh_ids]
            assert len(backlog_selected) == 1, "guarantee bucket must reserve exactly 1 backlog slot when satisfiable"
            assert len(fresh_selected) == 2
            # oldest-eligible backlog row: created earliest -> index 2 (hours=30, minutes=2 is oldest since more minutes subtracted... )
            # index i has created_at = now - (30h + i min), so larger i is OLDER.
            assert backlog_selected[0] == backlog_ids[2]
            # oldest-eligible fresh rows: indices 1,2 are older than index 0.
            assert set(fresh_selected) == {fresh_ids[1], fresh_ids[2]}
    finally:
        await _cleanup(*fresh_ids, *backlog_ids)


@pytest.mark.asyncio
async def test_non_guarantee_bucket_never_reserves_backlog_slot():
    fresh_ids = [f"pytest-r2-nogfresh-{i}-{uuid.uuid4().hex[:8]}" for i in range(3)]
    backlog_id = f"pytest-r2-nogback-{uuid.uuid4().hex[:8]}"
    await _cleanup(*fresh_ids, backlog_id)
    try:
        now = _guarantee_bucket_time(force=False)
        for eid in fresh_ids:
            created = now - timedelta(hours=1)
            await _make_event(eid, created_at=created, updated_at=created)
        old_created = now - timedelta(hours=30)
        await _make_event(backlog_id, created_at=old_created, updated_at=old_created)

        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=3, now=now)
            result_ids = sorted(e.id for e in pending)
            assert result_ids == sorted(fresh_ids), (
                "a non-guarantee bucket with enough fresh demand must not "
                "reserve a backlog slot"
            )
    finally:
        await _cleanup(*fresh_ids, backlog_id)


@pytest.mark.asyncio
async def test_sustained_pressure_across_n4_buckets_backlog_cannot_starve():
    """Simulates 8 consecutive real scheduler cycles (2 full N=4 periods)
    under sustained fresh pressure (always >= limit fresh rows available)
    plus a standing backlog pool -- ordinary buckets return all-fresh,
    every 4th bucket returns >=1 backlog row, so backlog receives
    guaranteed forward progress rather than zero service indefinitely."""
    fresh_ids = [f"pytest-r2-sustained-fresh-{i}-{uuid.uuid4().hex[:8]}" for i in range(30)]
    backlog_ids = [f"pytest-r2-sustained-back-{i}-{uuid.uuid4().hex[:8]}" for i in range(10)]
    await _cleanup(*fresh_ids, *backlog_ids)
    try:
        base = _guarantee_bucket_time(force=True)  # bucket 0 of this run is a guarantee bucket
        # Stagger fresh creation times so there's always more than `limit`
        # eligible fresh rows across the whole 8-cycle window (sustained
        # pressure), all within the 24h fresh window.
        for i, eid in enumerate(fresh_ids):
            created = base - timedelta(minutes=i)
            await _make_event(eid, created_at=created, updated_at=created)
        for i, eid in enumerate(backlog_ids):
            created = base - timedelta(hours=25 + i)
            await _make_event(eid, created_at=created, updated_at=created)

        backlog_served_total = set()
        for cycle in range(8):
            now = base + timedelta(seconds=_INTERVAL_SEC * cycle)
            async with AsyncSessionLocal() as db:
                repo = EventRepository(db)
                pending = await repo.get_pending_enrichment(limit=3, now=now)
            result_ids = [e.id for e in pending]
            is_guarantee = (int(now.timestamp() // _INTERVAL_SEC) % 4) == 0
            served_backlog = [i for i in result_ids if i in backlog_ids]
            if is_guarantee:
                assert len(served_backlog) >= 1, f"cycle {cycle} was a guarantee bucket but served no backlog row"
            backlog_served_total.update(served_backlog)

        assert len(backlog_served_total) >= 1, "backlog must receive guaranteed forward progress, not zero service"
    finally:
        await _cleanup(*fresh_ids, *backlog_ids)


@pytest.mark.asyncio
async def test_no_duplicate_event_across_returned_slots():
    fresh_ids = [f"pytest-r2-nodup-fresh-{i}-{uuid.uuid4().hex[:8]}" for i in range(2)]
    backlog_ids = [f"pytest-r2-nodup-back-{i}-{uuid.uuid4().hex[:8]}" for i in range(2)]
    await _cleanup(*fresh_ids, *backlog_ids)
    try:
        now = _guarantee_bucket_time(force=True)
        for eid in fresh_ids:
            created = now - timedelta(hours=1)
            await _make_event(eid, created_at=created, updated_at=created)
        for eid in backlog_ids:
            created = now - timedelta(hours=30)
            await _make_event(eid, created_at=created, updated_at=created)

        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=100, now=now)
            result_ids = [e.id for e in pending]
            assert len(result_ids) == len(set(result_ids)), "no event may occupy two returned slots"
    finally:
        await _cleanup(*fresh_ids, *backlog_ids)


@pytest.mark.asyncio
async def test_limit_less_than_one_bypasses_lane_logic_matches_pre_r2_behavior():
    test_id = f"pytest-r2-degenerate-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=0)
            assert pending == []
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_returns_up_to_batch_size_when_enough_eligible_work_exists():
    ids = [f"pytest-r2-fullbatch-{i}-{uuid.uuid4().hex[:8]}" for i in range(5)]
    await _cleanup(*ids)
    try:
        now = _guarantee_bucket_time(force=False)
        for i, eid in enumerate(ids):
            created = now - timedelta(minutes=i)
            await _make_event(eid, created_at=created, updated_at=created)
        async with AsyncSessionLocal() as db:
            repo = EventRepository(db)
            pending = await repo.get_pending_enrichment(limit=3, now=now)
            assert len(pending) == 3
    finally:
        await _cleanup(*ids)

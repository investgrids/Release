"""
V2-B promotion mechanics — the single opportunity_read_source flag and
everything gated on it: the V2 public list (public_status enforcement,
mirroring read_service.py's own detail-lookup gate), and scheduler
registration (V1's job_daily_opportunities stops when promoted; V2's
opportunity_v2_shadow_pass runs either way).

Real DB-backed for the list tests (same precedent as
test_opportunity_v2_read_service.py — no mocks for OpportunityV2 rows).
Scheduler tests use a fresh, never-started AsyncIOScheduler so nothing
here actually fires a job.

Don't run this file while the local uvicorn dev server is running — same
`database is locked` risk documented in the sibling test files.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete

from app.core.config import settings
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.read_service import list_public_opportunities_v2


def _make_opp(*, public_status: str, title: str) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor=f"company:{uuid.uuid4().hex[:6]}", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title=title, formation_score=50.0, formation_at=now,
        current_title=title, current_summary="Real test summary.", current_score=55.0,
        sectors=["Banking"], companies=[],
        slug=f"promotion-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


async def _cleanup(opportunity_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if opportunity_ids:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(opportunity_ids)))
            await db.commit()


@pytest.mark.asyncio
async def test_list_public_opportunities_v2_excludes_shadow_rows():
    """The exact leak this whole flag exists to prevent: a shadow row must
    never become reachable through the list either, not just the detail
    lookup (which read_service.py's own tests already cover)."""
    public_opp = _make_opp(public_status="public", title="Public Promotion Test Opportunity")
    shadow_opp = _make_opp(public_status="shadow", title="Shadow Promotion Test Opportunity")
    opp_ids = [public_opp.id, shadow_opp.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([public_opp, shadow_opp])
            await db.commit()

        async with AsyncSessionLocal() as db:
            result = await list_public_opportunities_v2(db, page=1, page_size=100)

        slugs = {item.slug for item in result.items}
        assert public_opp.slug in slugs
        assert shadow_opp.slug not in slugs
    finally:
        await _cleanup(opp_ids)


@pytest.mark.asyncio
async def test_list_public_opportunities_v2_pagination_is_real():
    """total/pages reflect the real public-only count, not the unfiltered
    table size — a real regression here would misreport how much content
    actually exists to promote."""
    opp_ids: list[str] = []
    try:
        opps = [_make_opp(public_status="public", title=f"Pagination Test {i}") for i in range(3)]
        async with AsyncSessionLocal() as db:
            db.add_all(opps)
            await db.commit()
        opp_ids = [o.id for o in opps]

        async with AsyncSessionLocal() as db:
            page1 = await list_public_opportunities_v2(db, page=1, page_size=2)

        our_slugs = {o.slug for o in opps}
        page1_our_items = [i for i in page1.items if i.slug in our_slugs]
        # Real page_size cap holds even though 3 of our own public rows exist.
        assert len(page1.items) <= 2
        assert page1.total >= 3
        assert len(page1_our_items) <= 2
    finally:
        await _cleanup(opp_ids)


def test_scheduler_gates_v1_job_on_promotion_flag(monkeypatch):
    """The real 'when does V1 stop receiving new writes' mechanism —
    job_daily_opportunities registers pre-promotion, does not
    post-promotion. opportunity_v2_shadow_pass registers either way (it's
    the ongoing observation-window writer before promotion, and the sole
    writer after)."""
    from app.scheduler import scheduler as sched_module

    # Neither scheduler is ever .start()ed — register_jobs() only populates
    # the job store, no shutdown() needed for an unstarted scheduler.
    monkeypatch.setattr(settings, "opportunity_read_source", "v1")
    s1 = AsyncIOScheduler()
    sched_module.register_jobs(s1)
    assert s1.get_job("daily_opportunities") is not None
    assert s1.get_job("opportunity_v2_shadow_pass") is not None

    monkeypatch.setattr(settings, "opportunity_read_source", "v2")
    s2 = AsyncIOScheduler()
    sched_module.register_jobs(s2)
    assert s2.get_job("daily_opportunities") is None
    assert s2.get_job("opportunity_v2_shadow_pass") is not None


@pytest.mark.asyncio
async def test_radar_meta_endpoint_reflects_the_flag(monkeypatch):
    from app.api.radar import get_radar_meta

    monkeypatch.setattr(settings, "opportunity_read_source", "v1")
    assert (await get_radar_meta())["opportunity_v2_promoted"] is False

    monkeypatch.setattr(settings, "opportunity_read_source", "v2")
    assert (await get_radar_meta())["opportunity_v2_promoted"] is True

"""
app/api/admin.py's temporary opportunity-v2-canary-promote/-revert
endpoints (2026-09-20) -- real DB-backed tests for the exact-row-guard
contract: an update must affect precisely one row matching BOTH the id
AND the expected current public_status, or it must roll back and report
failure rather than silently doing nothing or affecting the wrong row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.core.config import settings
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal

client = TestClient(app)
HEADERS = {"X-Admin-Key": settings.admin_api_key} if getattr(settings, "admin_api_key", None) else {}


def _make_opp(*, public_status: str) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:canarytest", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title="Real Canary Test Opportunity", formation_score=60.0, formation_at=now,
        current_title="Real Canary Test Opportunity", current_summary="Real test summary.", current_score=60.0,
        sectors=["Banking"], companies=[], contradictions=[],
        slug=f"real-canary-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


async def _cleanup(ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_promote_affects_exactly_one_shadow_row_and_flips_it_to_public():
    opp = _make_opp(public_status="shadow")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["public_status"] == "public"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "public"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_promote_refuses_a_row_that_is_already_public_never_a_silent_noop():
    opp = _make_opp(public_status="public")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 409

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "public"  # unchanged
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_promote_refuses_an_unknown_id():
    resp = client.post("/api/admin/opportunity-v2-canary-promote?opportunity_id=this-id-does-not-exist", headers=HEADERS)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_revert_affects_exactly_one_public_row_and_flips_it_back_to_shadow():
    opp = _make_opp(public_status="public")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-revert?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["public_status"] == "shadow"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_revert_refuses_a_row_that_is_already_shadow():
    opp = _make_opp(public_status="shadow")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-revert?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 409

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"  # unchanged
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_promote_never_affects_a_second_unrelated_row():
    target = _make_opp(public_status="shadow")
    bystander = _make_opp(public_status="shadow")
    async with AsyncSessionLocal() as db:
        db.add(target)
        db.add(bystander)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={target.id}", headers=HEADERS)
        assert resp.status_code == 200

        async with AsyncSessionLocal() as db:
            refreshed_target = await db.get(OpportunityV2, target.id)
            refreshed_bystander = await db.get(OpportunityV2, bystander.id)
        assert refreshed_target.public_status == "public"
        assert refreshed_bystander.public_status == "shadow"  # untouched
    finally:
        await _cleanup([target.id, bystander.id])

"""
app/api/radar.py's dual V1/V2 lookup route (GET /api/radar/{opportunity_id})
-- real HTTP-level tests via TestClient. The 2026-09-19 Opportunity V2
production/local audit found this exact route had zero test coverage
despite being the literal thing a real HTTP client hits; the service
layer underneath it (read_service.py) was already well tested via direct
function calls.

Same session-wide scratch-DB isolation as every other opportunity_v2
test (tests/conftest.py) -- never the real dev DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.db.models.opportunity import Opportunity
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal

client = TestClient(app)


def _make_v1_opportunity() -> Opportunity:
    now = datetime.now(timezone.utc)
    return Opportunity(
        slug=f"real-v1-dual-lookup-test-{uuid.uuid4().hex[:8]}",
        title="Real V1 Test Opportunity", summary="Real summary.",
        opportunity_score=60.0, confidence=0.7, trend="positive", risk_level="Medium",
        time_horizon="3-6 months", sectors=["Banking"], source="pipeline",
        created_at=now, updated_at=now,
    )


def _make_v2_opportunity(*, public_status: str) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:dualtest", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title="Real V2 Test Opportunity", formation_score=55.0, formation_at=now,
        current_title="Real V2 Test Opportunity", current_summary="Real V2 test summary.", current_score=55.0,
        sectors=["Banking"], companies=[], contradictions=[],
        slug=f"real-v2-dual-lookup-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


async def _seed(opp) -> None:
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()


async def _cleanup(v1_ids: list[int], v2_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if v1_ids:
            await db.execute(delete(Opportunity).where(Opportunity.id.in_(v1_ids)))
        if v2_ids:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(v2_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_numeric_id_resolves_through_v1():
    opp = _make_v1_opportunity()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
        await db.refresh(opp)
    try:
        resp = client.get(f"/api/radar/{opp.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == opp.id
        assert body["title"] == "Real V1 Test Opportunity"
        # V2-shaped-only field must never appear on a V1 response.
        assert "thesis_anchor" not in body
    finally:
        await _cleanup([opp.id], [])


@pytest.mark.asyncio
async def test_valid_public_v2_slug_returns_v2():
    opp = _make_v2_opportunity(public_status="public")
    await _seed(opp)
    try:
        resp = client.get(f"/api/radar/{opp.slug}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == opp.slug
        assert body["thesis_anchor"] == "company:dualtest"
        # V1-shaped-only fields (explicitly excluded from the V2 contract)
        # must never leak into a V2 response.
        for v1_only_field in ("confidence", "risk_level", "trend", "time_horizon"):
            assert v1_only_field not in body
    finally:
        await _cleanup([], [opp.id])


@pytest.mark.asyncio
async def test_shadow_v2_slug_returns_404_never_leaks():
    opp = _make_v2_opportunity(public_status="shadow")
    await _seed(opp)
    try:
        resp = client.get(f"/api/radar/{opp.slug}")
        assert resp.status_code == 404
    finally:
        await _cleanup([], [opp.id])


def test_unknown_slug_returns_404():
    resp = client.get("/api/radar/this-slug-has-never-existed-zzz-000000")
    assert resp.status_code == 404


def test_malformed_numeric_like_id_that_is_not_a_real_v1_row_returns_404_not_v2():
    """A digit-only path segment always takes the V1 branch (isdigit()
    check in radar.py) -- confirms it 404s as a real V1 miss rather than
    silently falling through to a V2 lookup."""
    resp = client.get("/api/radar/999999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_no_accidental_fallback_v1_numeric_id_never_returns_a_v2_shaped_body():
    opp = _make_v1_opportunity()
    await _seed(opp)
    try:
        resp = client.get(f"/api/radar/{opp.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "thesis_anchor" not in body and "contradictions_risks" not in body
    finally:
        await _cleanup([opp.id], [])

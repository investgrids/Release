"""
P0 remediation -- real, DB-backed tests for POST /api/publishing/articles/
retire, the thin admin-protected transport wrapper around
app.services.aipe.article_retirement (already independently tested).
These prove the HTTP layer (auth gate, request/response shape, dry_run
default) works correctly end to end through the real app, not just the
underlying service function in isolation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.main import app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle

client = TestClient(app)
_HEADERS = {"X-Admin-Key": settings.admin_api_key}


async def _seed(**overrides) -> str:
    now = datetime.now(timezone.utc)
    base = dict(
        id=str(uuid.uuid4()), slug=f"test-retire-ep-{uuid.uuid4().hex[:8]}", article_type="market_wrap",
        angle="primary", is_evergreen=False, lifecycle_status="published", status="published",
        headline="Real Endpoint Test Contaminated Wrap", executive_summary="s", key_takeaway="k",
        companies_affected=[], sectors_affected=[], sources=["NSE"],
        trigger_event_id="nse-endpointtest1", trigger_type="high_urgency_triage",
        market_context={"session": "post_market"}, published_at=now, last_updated=now,
    )
    base.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(**base))
        await db.commit()
    return base["id"]


async def _cleanup(article_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()


def test_missing_admin_key_is_rejected():
    resp = client.post("/api/publishing/articles/retire", json={"article_ids": ["x"], "reason": "r", "retired_by": "t"})
    assert resp.status_code == 401


def test_wrong_admin_key_is_rejected():
    resp = client.post(
        "/api/publishing/articles/retire",
        json={"article_ids": ["x"], "reason": "r", "retired_by": "t"},
        headers={"X-Admin-Key": "definitely-wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dry_run_is_the_default_and_does_not_write():
    aid = await _seed()
    try:
        resp = client.post(
            "/api/publishing/articles/retire",
            json={"article_ids": [aid], "reason": "test", "retired_by": "test"},  # dry_run omitted -> defaults True
            headers=_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["requested"] == 1
        assert body["would_retire"] == 1
        assert body["retired"] == 0

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == aid))).scalar_one()
            assert row.status == "published"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_real_execution_via_endpoint_retires_and_response_matches_db():
    aid = await _seed()
    try:
        resp = client.post(
            "/api/publishing/articles/retire",
            json={"article_ids": [aid], "reason": "market_wrap_clock_reclassification_contamination_2026_09", "retired_by": "owner_authorized_p0_remediation", "dry_run": False},
            headers=_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "requested": 1, "retired": 1, "would_retire": 0, "skipped": 0,
            "results": [{
                "article_id": aid, "outcome": "RETIRED",
                "reason": body["results"][0]["reason"],  # message text isn't the contract, outcome/counts are
                "prior_status": "published", "prior_trigger_event_id": "nse-endpointtest1",
            }],
        }

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == aid))).scalar_one()
            assert row.status == "retired"
            assert row.archived_at is not None
            assert row.market_context["retirement"]["retired_by"] == "owner_authorized_p0_remediation"

        # Idempotent through the endpoint too -- calling again is a clean skip.
        resp2 = client.post(
            "/api/publishing/articles/retire",
            json={"article_ids": [aid], "reason": "r", "retired_by": "t", "dry_run": False},
            headers=_HEADERS,
        )
        body2 = resp2.json()
        assert body2["retired"] == 0
        assert body2["skipped"] == 1
        assert body2["results"][0]["outcome"] == "SKIPPED_ALREADY_RETIRED"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_legitimate_scheduled_wrap_refused_via_endpoint():
    aid = await _seed(trigger_event_id="scheduled-market_wrap-2026-08-10")
    try:
        resp = client.post(
            "/api/publishing/articles/retire",
            json={"article_ids": [aid], "reason": "r", "retired_by": "t", "dry_run": False},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["retired"] == 0
        assert body["skipped"] == 1
        assert body["results"][0]["outcome"] == "SKIPPED_PROVENANCE_MISMATCH"

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == aid))).scalar_one()
            assert row.status == "published"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_batch_never_discovers_only_uses_explicit_ids():
    aid = await _seed()
    unrelated_id = await _seed(headline="Unrelated article, should never be touched")
    try:
        resp = client.post(
            "/api/publishing/articles/retire",
            json={"article_ids": [aid], "reason": "r", "retired_by": "t", "dry_run": False},
            headers=_HEADERS,
        )
        assert resp.json()["retired"] == 1

        async with AsyncSessionLocal() as db:
            unrelated = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == unrelated_id))).scalar_one()
            assert unrelated.status == "published"
    finally:
        await _cleanup(aid)
        await _cleanup(unrelated_id)

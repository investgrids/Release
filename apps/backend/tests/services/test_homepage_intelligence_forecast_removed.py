"""
CD3-D (D5) — homepage_intelligence.py used to derive a one-line "AI
Prediction" ("Today's market will likely be led by {sector}.") from the
article's own sectors_affected and surface it verbatim in
GET /api/homepage/intelligence's ai_prediction field, which page.tsx then
injected directly into the "Conclusion" summary sentence. This was a
genuine, unhedged FORECAST claim with zero legitimate producer anywhere
in the pipeline (see app.services.claim_authorization.FORECAST_UNAVAILABLE)
-- audit finding #2, the second most severe in the whole CD3-D report.

Per the ecac930 lesson, this goes through the REAL route via TestClient,
not just a check that the removed function is gone from the module.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services import homepage_intelligence as hi

client = TestClient(app)


async def _cleanup(article_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()


def test_get_ai_prediction_no_longer_exists_on_the_module():
    """A direct guard against reintroduction -- the forecast producer
    itself must not exist, not just be unused."""
    assert not hasattr(hi, "get_ai_prediction")


@pytest.mark.asyncio
async def test_real_api_response_never_contains_a_forecast_field_or_sentence():
    now = datetime.now(timezone.utc)
    article_id = str(uuid.uuid4())
    await _cleanup(article_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(IntelligenceArticle(
                id=article_id, slug=f"pytest-forecast-removed-{uuid.uuid4().hex[:8]}",
                article_type="morning_intelligence", angle="primary", is_evergreen=False,
                lifecycle_status="published", status="published",
                headline="Test Morning Brief", executive_summary="Test.",
                key_takeaway="Test.", companies_affected=[],
                # A real strong positive sector -- exactly the shape that
                # used to trigger "Today's market will likely be led by
                # Information Technology."
                sectors_affected=[{"name": "Information Technology", "impact": "positive", "magnitude": "high"}],
                sources=["Test"], published_at=now, last_updated=now, update_count=0,
            ))
            await db.commit()

        with patch("app.services.event_lifecycle.get_homepage_event_intelligence", new=AsyncMock(return_value={"available": False})):
            resp = client.get("/api/homepage/intelligence")

        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert "ai_prediction" not in body
        # Defense in depth: even if some other field ever carried it, the
        # literal forecast phrase must never appear anywhere in the
        # response body.
        assert "will likely be led by" not in str(body)
    finally:
        await _cleanup(article_id)

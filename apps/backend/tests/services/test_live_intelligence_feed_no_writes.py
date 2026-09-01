"""
P0-B (2026-09-01) — regression suite for the GET-request write-side-effect
fix.

Real production issue: GET /api/live-intelligence/feed used to call
signal_publisher.publish_signal() (a real DB create/update) directly
inside the request handler on every cache-cold hit — a public,
unauthenticated GET request creating/updating durable IntelligenceArticle
rows as a side effect of generating its own response. Any crawler,
uptime monitor, or prefetch could trigger production publication.

The invariant this suite locks in: a GET request must never create,
update, publish, or otherwise mutate an IntelligenceArticle. Durable
publication now happens only from run_signal_publish_cycle's own
scheduled job (signal_publisher.py / scheduler.py's "signal_publish_cycle"
job, id matches scheduler.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle

client = TestClient(app)

_LIVE_SIGNAL_TYPE = "live_signal"


async def _live_signal_row_count() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count()).select_from(IntelligenceArticle)
            .where(IntelligenceArticle.article_type == _LIVE_SIGNAL_TYPE)
        )
        return result.scalar_one()


@pytest.mark.asyncio
async def test_get_feed_creates_zero_intelligence_article_rows():
    before = await _live_signal_row_count()
    resp = client.get("/api/live-intelligence/feed")
    assert resp.status_code == 200
    after = await _live_signal_row_count()
    assert after == before, "GET /feed must never write a live_signal IntelligenceArticle row"


@pytest.mark.asyncio
async def test_repeated_get_feed_still_zero_writes():
    before = await _live_signal_row_count()
    for _ in range(3):
        resp = client.get("/api/live-intelligence/feed")
        assert resp.status_code == 200
    after = await _live_signal_row_count()
    assert after == before


@pytest.mark.asyncio
async def test_crawler_like_repeated_gets_zero_duplicate_or_publication_rows():
    """Simulates the exact real-world exposure the incident described: many
    rapid, independent requests (a crawler/monitor/prefetch pattern) --
    none of them may create or duplicate a row."""
    before = await _live_signal_row_count()
    for _ in range(10):
        resp = client.get("/api/live-intelligence/feed")
        assert resp.status_code == 200
    after = await _live_signal_row_count()
    assert after == before


@pytest.mark.asyncio
async def test_existing_published_signal_is_untouched_by_get():
    """A pre-existing, already-published live_signal row must remain
    completely unmodified by hitting the feed -- proving the fix removed
    the write, not just made it less frequent."""
    slug = f"test-signal-{uuid.uuid4().hex[:8]}"
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(
            id=row_id, slug=slug, article_type=_LIVE_SIGNAL_TYPE,
            angle="primary", is_evergreen=True,
            lifecycle_status="published", status="published",
            headline="Real Test Signal Headline", executive_summary="Real test summary.",
            key_takeaway="Real test summary.", companies_affected=[], sectors_affected=[],
            sources=["MarketRipple Live Intelligence Engine"],
            published_at=now, last_updated=now, update_count=0,
        ))
        await db.commit()

    try:
        # Confirm it's genuinely readable first (existing published signal
        # can still be read -- via the same real API path the frontend uses).
        read_resp = client.get(f"/api/insights/{slug}")
        assert read_resp.status_code == 200
        assert read_resp.json()["slug"] == slug

        client.get("/api/live-intelligence/feed")
        client.get("/api/live-intelligence/feed")

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(IntelligenceArticle).where(IntelligenceArticle.id == row_id)
            )).scalar_one()
            assert row.update_count == 0
            # SQLite returns a naive datetime for this tz-aware column even
            # though it was written as real UTC (the same footgun worked
            # around elsewhere in this codebase) -- compare the real value,
            # not the tzinfo SQLite drops on read-back.
            stored = row.last_updated.replace(tzinfo=timezone.utc) if row.last_updated.tzinfo is None else row.last_updated
            assert stored == now
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == row_id))
            await db.commit()


@pytest.mark.asyncio
async def test_get_feed_response_still_includes_a_slug_per_item():
    """Response contract check: slug_for_item() is a pure function that
    returns the exact same value publish_signal() used to derive and
    return -- so a real detected item must still carry a real slug field,
    proving no behavior difference for the feed's actual consumers."""
    from app.services.aipe.signal_publisher import slug_for_item

    fake_item = {"type": "policy_ripple", "headline": "Real Fake Policy Ripple For This Test"}
    expected_slug = slug_for_item(dict(fake_item))
    with patch("app.services.live_intelligence.get_live_intelligence", new=AsyncMock(return_value=[dict(fake_item)])):
        with patch("app.core.redis.cache_get", new=AsyncMock(return_value=None)):
            with patch("app.core.redis.cache_set", new=AsyncMock(return_value=None)):
                resp = client.get("/api/live-intelligence/feed")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["slug"] == expected_slug


@pytest.mark.asyncio
async def test_legitimate_scheduled_producer_still_creates_the_signal_article():
    """The controlled producer path (run_signal_publish_cycle, the new
    scheduled job) must still be able to do exactly what the old
    request-time write did -- proving this isn't a silent removal of the
    feature, just a relocation of WHERE the write happens."""
    from app.services.aipe.signal_publisher import run_signal_publish_cycle

    fake_item = {"type": "policy_ripple", "headline": f"Real Fake Scheduled Signal {uuid.uuid4().hex[:8]}"}
    with patch("app.services.live_intelligence.get_live_intelligence", new=AsyncMock(return_value=[dict(fake_item)])):
        published_count = await run_signal_publish_cycle()

    assert published_count == 1
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.headline == fake_item["headline"])
        )).scalar_one_or_none()
        assert row is not None
        assert row.article_type == _LIVE_SIGNAL_TYPE
        row_id = row.id

    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == row_id))
        await db.commit()

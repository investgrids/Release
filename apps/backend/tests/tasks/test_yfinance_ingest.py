"""
Workstream C — Gate C non-production verification for Option A forward durability
(2026-10-24): the scheduled ingest now also persists the yfinance live-only
source via the SAME `_persist_articles` path, reusing the `rss-md5(source+title)`
id scheme. yfinance network is mocked for determinism (no external calls).

Asserts: new source persisted; idempotent re-ingest (no dup rows); deterministic
stable `rss-` ids (no `live-` ids); source-failure isolation; ISO published_at;
and job_ingest_news end-to-end includes yfinance without creating Events for it.
No production access; disposable test DB only.
"""
from __future__ import annotations

import hashlib
import uuid
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import delete, func, select

from app.db.session import AsyncSessionLocal
from app.db.models_legacy import NewsArticle
from app.tasks.ingest_tasks import _fetch_yfinance_items, _persist_articles, job_ingest_news

NF = "app.services.news_fetcher._sync_fetch_yfinance"


def _yf_dict(headline, source="Reuters", ts=1_750_000_000.0, summary="s", url="http://x"):
    # mirrors news_fetcher._normalize's output keys used by _fetch_yfinance_items
    return {"id": "live-ignored", "headline": headline, "summary": summary, "source": source,
            "published_at": "1d ago", "url": url, "_ts": ts, "companies": [], "impact_score": 5.0}


async def _count(ids):
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(func.count()).select_from(NewsArticle).where(NewsArticle.id.in_(ids)))).scalar()


async def _cleanup(ids):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_yfinance_items_become_rss_ids_with_iso_published_at():
    h = "Pytest yfinance headline " + uuid.uuid4().hex[:8]
    with patch(NF, return_value=[_yf_dict(h, source="Bloomberg")]):
        items = await _fetch_yfinance_items()
    assert len(items) == 1
    it = items[0]
    expected = "rss-" + hashlib.md5(("Bloomberg" + h).encode()).hexdigest()[:12]
    assert it.id == expected and it.id.startswith("rss-") and "live-" not in it.id
    # ISO published_at (not the relative "1d ago" display label)
    datetime.fromisoformat(it.published_at)  # raises if not ISO
    assert it.published_at.startswith("2025-")  # from the fixed epoch


@pytest.mark.asyncio
async def test_yfinance_fetch_failure_is_isolated():
    with patch(NF, side_effect=RuntimeError("yahoo down")):
        items = await _fetch_yfinance_items()
    assert items == []  # returns empty, does not raise


@pytest.mark.asyncio
async def test_yfinance_persist_is_idempotent_and_stable():
    h = "Pytest yf idempotent " + uuid.uuid4().hex[:8]
    with patch(NF, return_value=[_yf_dict(h, source="Mint")]):
        items = await _fetch_yfinance_items()
    ids = [i.id for i in items]
    try:
        async with AsyncSessionLocal() as db:
            first = await _persist_articles(db, items)
        async with AsyncSessionLocal() as db:               # fresh session = restart
            second = await _persist_articles(db, items)
        assert first == ids and second == []                 # 0 re-inserts
        assert await _count(ids) == 1
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_job_ingest_news_persists_yfinance_without_events():
    h = "Pytest job yf " + uuid.uuid4().hex[:8]
    yid = "rss-" + hashlib.md5(("Reuters" + h).encode()).hexdigest()[:12]
    stack = ExitStack()
    nse = MagicMock(); nse.return_value.fetch_and_normalize = AsyncMock(return_value=[])
    nse.filter_announcements_only = MagicMock(return_value=[])
    rss = MagicMock(); rss.return_value.fetch_and_normalize = AsyncMock(return_value=[])
    stack.enter_context(patch("app.tasks.ingest_tasks.NSEProvider", nse))
    stack.enter_context(patch("app.tasks.ingest_tasks.RSSProvider", rss))
    stack.enter_context(patch(NF, return_value=[_yf_dict(h, source="Reuters")]))
    stack.enter_context(patch("app.tasks.ingest_tasks._push_to_triage_bus", new_callable=AsyncMock))
    stack.enter_context(patch("app.services.company_announcements_service.ingest_announcements", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.cache.delete_pattern", new_callable=AsyncMock))
    try:
        with stack:
            await job_ingest_news()
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(NewsArticle).where(NewsArticle.id == yid))).scalar_one_or_none()
            # yfinance item persisted as a news_article under its rss- id
            assert row is not None and row.source == "Reuters"
            # and it did NOT become an Event (only nse_items feed _create_events)
            from app.db.models.event import Event
            ev = (await db.execute(select(func.count()).select_from(Event).where(Event.id == yid))).scalar()
            assert ev == 0
    finally:
        await _cleanup([yid])

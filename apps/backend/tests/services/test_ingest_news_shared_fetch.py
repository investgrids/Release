"""
CR-2A (2026-09-13) — regression tests for job_ingest_news's consolidated
NSE fetch: one network acquisition (NSEProvider.fetch_and_normalize)
feeding two independent downstream consumers (Event/NewsArticle here,
CompanyAnnouncement via ingest_announcements), plus BSE's removal from
this hot path and failure isolation between the two consumers.

Real DB, mocked network layer (NSEProvider/RSSProvider/BSEProvider),
matching this codebase's established convention (see
test_ingest_news_article_impact_score.py).
"""
from __future__ import annotations

import inspect
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

import app.services.company_announcements_service as cas
from app.db.models.company_announcements import CompanyAnnouncement
from app.db.models.event import Event
from app.db.models_legacy import NewsArticle
from app.db.session import AsyncSessionLocal
from app.providers.base import RawItem
from app.tasks import ingest_tasks


def _reset_announcements_module_state():
    """These tests call the REAL ingest_announcements() (through
    job_ingest_news, not mocked) -- its module-level _last_run/_seen
    guards are shared process state that would otherwise leak between
    test files/runs and make this test spuriously return 0 (see
    _MIN_INTERVAL in company_announcements_service.py)."""
    cas._last_run = 0.0
    cas._seen.clear()


def _announcement_item(test_id: str, symbol: str) -> RawItem:
    return RawItem(
        id=test_id, headline=f"Test announcement for {symbol}", summary="Test summary.",
        source="NSE", published_at="2026-09-13", companies=[symbol],
        impact_score=None, event_type="corporate",
        extra={"company_name": f"{symbol} Ltd", "nse_feed_kind": "announcement"},
    )


async def _cleanup(test_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id == test_id))
        await db.execute(delete(NewsArticle).where(NewsArticle.id == test_id))
        await db.execute(delete(CompanyAnnouncement).where(CompanyAnnouncement.id == f"ann_{test_id}"))
        await db.commit()


@pytest.mark.asyncio
async def test_one_nse_fetch_feeds_both_event_and_company_announcement_consumers():
    test_id = f"nse-cr2a-{uuid.uuid4().hex[:10]}"
    symbol = f"CR2A{uuid.uuid4().hex[:4].upper()}"
    item = _announcement_item(test_id, symbol)
    await _cleanup(test_id)
    _reset_announcements_module_state()
    try:
        with patch.object(ingest_tasks.NSEProvider, "fetch_and_normalize", AsyncMock(return_value=[item])) as nse_mock, \
             patch.object(ingest_tasks.RSSProvider, "fetch_and_normalize", AsyncMock(return_value=[])):
            await ingest_tasks.job_ingest_news()

        nse_mock.assert_awaited_once()  # exactly one NSE network acquisition

        async with AsyncSessionLocal() as db:
            event_row = await db.get(Event, test_id)
            news_row = await db.get(NewsArticle, test_id)
            ann_row = await db.get(CompanyAnnouncement, f"ann_{test_id}")

        assert event_row is not None
        assert news_row is not None
        assert ann_row is not None, "CompanyAnnouncement must be created from the SAME fetch, no second NSE call"
        assert ann_row.symbol == symbol
        assert ann_row.company_name == f"{symbol} Ltd"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_event_persistence_failure_does_not_suppress_company_announcement():
    """Failure isolation, direction 1: NSE fetch succeeds, but the
    events/news_articles side blows up -- job_ingest_news must catch it
    (not propagate) and still attempt company_announcements from the
    same already-fetched data, since the two write paths are independent
    DB transactions, not a shared one."""
    test_id = f"nse-cr2a-{uuid.uuid4().hex[:10]}"
    symbol = f"CR2B{uuid.uuid4().hex[:4].upper()}"
    item = _announcement_item(test_id, symbol)
    await _cleanup(test_id)
    _reset_announcements_module_state()
    try:
        with patch.object(ingest_tasks.NSEProvider, "fetch_and_normalize", AsyncMock(return_value=[item])), \
             patch.object(ingest_tasks.RSSProvider, "fetch_and_normalize", AsyncMock(return_value=[])), \
             patch.object(ingest_tasks, "_create_events", AsyncMock(side_effect=RuntimeError("simulated Event write failure"))):
            await ingest_tasks.job_ingest_news()  # must NOT raise

        async with AsyncSessionLocal() as db:
            event_row = await db.get(Event, test_id)
            ann_row = await db.get(CompanyAnnouncement, f"ann_{test_id}")
        assert event_row is None, "Event write genuinely failed, as simulated"
        assert ann_row is not None, "CompanyAnnouncement must still succeed despite the Event-side failure"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_company_announcement_persistence_failure_does_not_suppress_events():
    """Failure isolation, direction 2: NSE fetch succeeds, Event/
    NewsArticle persistence succeeds, but ingest_announcements() fails --
    job_ingest_news must catch it (not propagate) and complete normally
    with the Event/NewsArticle rows intact, already committed in their
    own independent transaction before ingest_announcements() is even
    called."""
    test_id = f"nse-cr2a-{uuid.uuid4().hex[:10]}"
    symbol = f"CR2C{uuid.uuid4().hex[:4].upper()}"
    item = _announcement_item(test_id, symbol)
    await _cleanup(test_id)
    _reset_announcements_module_state()
    try:
        with patch.object(ingest_tasks.NSEProvider, "fetch_and_normalize", AsyncMock(return_value=[item])), \
             patch.object(ingest_tasks.RSSProvider, "fetch_and_normalize", AsyncMock(return_value=[])), \
             patch("app.services.company_announcements_service.ingest_announcements",
                   AsyncMock(side_effect=RuntimeError("simulated CompanyAnnouncement write failure"))):
            await ingest_tasks.job_ingest_news()  # must NOT raise

        async with AsyncSessionLocal() as db:
            event_row = await db.get(Event, test_id)
            news_row = await db.get(NewsArticle, test_id)
        assert event_row is not None
        assert news_row is not None
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_bse_provider_is_never_called_from_job_ingest_news():
    test_id = f"nse-cr2a-{uuid.uuid4().hex[:10]}"
    symbol = f"CR2D{uuid.uuid4().hex[:4].upper()}"
    item = _announcement_item(test_id, symbol)
    await _cleanup(test_id)
    _reset_announcements_module_state()
    try:
        from app.providers.bse_provider import BSEProvider
        with patch.object(ingest_tasks.NSEProvider, "fetch_and_normalize", AsyncMock(return_value=[item])), \
             patch.object(ingest_tasks.RSSProvider, "fetch_and_normalize", AsyncMock(return_value=[])), \
             patch.object(BSEProvider, "fetch_and_normalize", AsyncMock()) as bse_mock:
            await ingest_tasks.job_ingest_news()
        bse_mock.assert_not_called()
    finally:
        await _cleanup(test_id)


def test_bse_provider_is_not_even_imported_by_ingest_tasks():
    """Structural proof, not just behavioral: BSEProvider must not appear
    in ingest_tasks.py's module source at all -- 144 guaranteed-fail
    calls/day eliminated by removing the call site, not just by mocking
    it out of a test's path."""
    source = inspect.getsource(ingest_tasks)
    assert "BSEProvider" not in source

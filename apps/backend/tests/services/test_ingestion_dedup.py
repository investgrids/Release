"""Cross-source near-duplicate filter: true duplicates from different publishers are caught; different stories, same-source repeats and exchange filings are never dropped."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from sqlalchemy import delete

import app.services.ingestion_dedup as D
from app.db.models_legacy import NewsArticle
from app.db.session import AsyncSessionLocal
from app.providers.base import RawItem
from app.tasks.ingest_tasks import _persist_articles

DUPLICATES = [
    ("Vishal Nirmiti shares list at 2% discount over IPO price on NSE, BSE", "Vishal Nirmiti shares list at 2% discount over IPO price on NSE, BSE - The Economic Times"),
    ("RBI To Conduct Rs 25,000 Crore OMO Sale Auction Of Government Securities On October 13", "RBI to conduct Rs 25,000 cr OMO sale auction of government securities on Oct 13"),
    ("India IT Set For Fourth Year Of Weak Growth On Geopolitics, AI Risks", "India IT set for fourth year of weak growth on geopolitics, AI risks"),
    ("Airtel Money Makes London Stock Exchange Debut; Biggest Listing In 5 Years", "Airtel Money makes London Stock Exchange debut"),
]
DIFFERENT = [
    ("TCS Q2 profit rises 12% to Rs 12,400 crore", "TCS Q2 profit rises 15% to Rs 12,900 crore"),                  # same template, different numbers
    ("Sensex jumps 500 points, Nifty reclaims 22,500", "Sensex falls 300 points, Nifty slips below 22,300"),
    ("RBI hikes repo rate by 25 bps to 6.75%", "Kotak Mahindra Bank shares rise after RBI repo rate hike"),         # related but a different story
    ("HDFC Bank board approves dividend", "ICICI Bank board approves dividend"),
]


@pytest.mark.parametrize("a,b", DUPLICATES)
def test_same_story_from_two_publishers_is_a_duplicate(a, b):
    assert D.is_duplicate(D.fingerprint(a), D.fingerprint(b))


@pytest.mark.parametrize("a,b", DIFFERENT)
def test_different_stories_are_never_duplicates(a, b):
    assert not D.is_duplicate(D.fingerprint(a), D.fingerprint(b))


def test_same_source_repeats_are_not_this_filters_job_and_first_item_wins():
    items = [NS(headline=DUPLICATES[2][0], source="NDTV Profit"), NS(headline=DUPLICATES[2][1], source="Economic Times"), NS(headline=DUPLICATES[2][0], source="NDTV Profit")]
    kept, dropped = D.drop_cross_source_duplicates(items, [])
    assert [i.source for i in kept] == ["NDTV Profit", "NDTV Profit"] and len(dropped) == 1 and dropped[0][0].source == "Economic Times"


@pytest.mark.asyncio
async def test_persist_skips_a_second_publishers_copy_but_keeps_exchange_filings():
    ids = ["pytest-dd-1", "pytest-dd-2", "pytest-dd-3", "pytest-dd-4"]
    async with AsyncSessionLocal() as db:
        await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(ids)))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            first = await _persist_articles(db, [RawItem(id=ids[0], headline=DUPLICATES[1][0], summary="x", source="NDTV Profit", impact_score=None)])
            second = await _persist_articles(db, [
                RawItem(id=ids[1], headline=DUPLICATES[1][1], summary="x", source="Economic Times", impact_score=None),      # same story, other publisher: skipped
                RawItem(id=ids[2], headline=DUPLICATES[1][1], summary="x", source="NSE", impact_score=None),                  # exchange item: never compared
                RawItem(id=ids[3], headline="Completely different headline about monsoon rains and crop output", summary="x", source="Economic Times", impact_score=None),
            ])
        assert first == [ids[0]] and sorted(second) == sorted([ids[2], ids[3]])
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(ids)))
            await db.commit()

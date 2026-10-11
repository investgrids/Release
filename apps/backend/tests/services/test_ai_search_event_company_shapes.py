"""Event.companies holds company tags in more than one JSON shape; company-scoped retrieval must find events in every one of them (real temp SQLite, no network)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy  # noqa: F401  (registers models on the shared Base)
from app.db.base import Base
from app.db.models.event import Event
from app.services.ai_search import retrieval as RT

NOW = datetime.now(timezone.utc)


async def seed(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'shapes.db'}", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    rows = [
        ("plain", ["KOTAKBANK"]),
        ("plain_multi", ["HDFCBANK", "KOTAKBANK"]),
        ("dict", [{"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank", "impact": "Positive"}]),
        ("other", ["KOTAKBANKX"]),            # a different symbol that merely starts with the same letters must NOT match
        ("untagged", []),
    ]
    async with factory() as s:
        for i, (name, companies) in enumerate(rows):
            s.add(Event(id=f"ev_{name}", title=f"headline {name}", summary="x", source="NSE", event_date=NOW - timedelta(days=i), published_at=NOW - timedelta(days=i),
                        impact_score=5.0, companies=companies, sectors=[]))
        await s.commit()
    return engine, factory


@pytest.mark.asyncio
async def test_company_events_are_found_in_plain_list_and_dict_shapes(tmp_path):
    engine, factory = await seed(tmp_path)
    async with factory() as db:
        rows = await RT._search_events(db, "What is happening with Kotak Mahindra Bank?", limit=10, entities={"companies": ["KOTAKBANK"]}, tagged_only=True)
    await engine.dispose()
    assert sorted(r["id"] for r in rows) == ["ev_dict", "ev_plain", "ev_plain_multi"]


@pytest.mark.asyncio
async def test_no_tagged_events_still_returns_nothing_when_tagged_only(tmp_path):
    engine, factory = await seed(tmp_path)
    async with factory() as db:
        rows = await RT._search_events(db, "tell me about Reliance", limit=10, entities={"companies": ["RELIANCE"]}, tagged_only=True)
    await engine.dispose()
    assert rows == []


@pytest.mark.asyncio
async def test_plain_symbols_are_expanded_so_the_relevance_filter_keeps_them(tmp_path):
    from app.services.ai_search import evidence_filter as EF
    engine, factory = await seed(tmp_path)
    async with factory() as db:
        rows = await RT._search_events(db, "What is happening with Kotak Mahindra Bank?", limit=10, entities={"companies": ["KOTAKBANK"]}, tagged_only=True)
    await engine.dispose()
    assert rows and all(isinstance(c, dict) and c["symbol"] for r in rows for c in r["companies"])
    assert all(EF._tagged_to(r, ["KOTAKBANK"]) for r in rows)
    assert not EF._tagged_to({"companies": [{"symbol": "KOTAKBANKX", "name": ""}]}, ["KOTAKBANK"])

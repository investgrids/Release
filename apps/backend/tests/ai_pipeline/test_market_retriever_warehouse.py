"""
Warehouse Consumption Phase 2, Batch 2 (2026-08-25) — market_retriever.py's
new Warehouse integration. Calls `_fetch()` directly (not the full
`run_pipeline()`) so these stay fast and don't depend on live AI-provider
calls; the only things monkeypatched are the pre-existing LIVE fetchers
(`get_extended_indices`/`get_sector_changes`/`get_top_movers` — real
network/yfinance calls, inherently external) — everything Warehouse-related
runs against a real, in-memory DB with real inserted rows, no mocks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai_pipeline.retrieval import market_retriever as mr
from app.ai_pipeline.retrieval.base import RetrievalContext
from app.db.base import Base
from app.db.models.market_observation import MarketObservation
from app.db.models.source_registry import Source


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(Source(id="test_source", name="Test Source", source_type="api", collection_method="test"))
        await session.commit()
        yield session
    await engine.dispose()


def _row(metric: str, value: float, obs_time: datetime, extra: dict | None = None, quality: str = "fresh") -> MarketObservation:
    return MarketObservation(
        id=str(uuid.uuid4()), metric=metric, value=value, unit="pct_change",
        observation_time=obs_time, market_date=obs_time.date(), session="live",
        source_id="test_source", captured_at=obs_time, quality=quality, extra=extra,
    )


async def _no_live_indices():
    return []


async def _no_live_movers():
    return {}


@pytest.mark.asyncio
async def test_current_warehouse_sector_data_used_with_real_timestamp(db, monkeypatch):
    """A sector with a real, current Warehouse row must produce Evidence
    sourced from Warehouse (real observation_time, not None) and must NOT
    trigger the live fallback for that sector."""
    now = datetime.now(timezone.utc)
    db.add(_row("SECTOR_BANKING", 1.25, now))
    await db.commit()

    live_fallback_called_for: list[str] = []
    async def _tracking_sector_changes():
        live_fallback_called_for.append("called")
        return [{"name": "Banking", "value": "+9.99%", "positive": True}]   # would be obviously wrong if ever used

    monkeypatch.setattr(mr, "get_extended_indices", _no_live_indices)
    monkeypatch.setattr(mr, "get_sector_changes", _tracking_sector_changes)
    monkeypatch.setattr(mr, "get_top_movers", _no_live_movers)

    ctx = RetrievalContext(query="test", db=db, intent="market_outlook")
    evidence = await mr._fetch(ctx)

    banking = [e for e in evidence if e.entity == "Banking" and e.source == "market"]
    assert len(banking) == 1
    assert banking[0].timestamp is not None, "Warehouse-sourced evidence must carry a real timestamp (the old always-None behavior this replaces)"
    assert "1.25" in banking[0].claim
    assert "9.99" not in banking[0].claim, "must use the real Warehouse value, not the live-fallback stub -- proves Banking's own evidence came from Warehouse even though get_sector_changes is still called for the other 11 sectors that have no Warehouse row in this minimal fixture"


@pytest.mark.asyncio
async def test_stale_and_missing_sectors_fall_back_to_live(db, monkeypatch):
    """Covers both real gaps in one pass: a sector with a real Warehouse
    row that's too old to trust (IT), and a sector with no row at all
    (Pharma) -- both must fall back to the live fetch, so coverage never
    regresses versus pre-Warehouse behavior."""
    ancient = datetime.now(timezone.utc) - timedelta(hours=5)
    db.add(_row("SECTOR_IT", 2.0, ancient))   # real row, but too old -- must NOT be trusted as current
    # SECTOR_PHARMA: no row at all
    await db.commit()

    async def _sector_changes():
        return [
            {"name": "IT", "value": "-0.50%", "positive": False},
            {"name": "Pharma", "value": "+0.75%", "positive": True},
        ]

    monkeypatch.setattr(mr, "get_extended_indices", _no_live_indices)
    monkeypatch.setattr(mr, "get_sector_changes", _sector_changes)
    monkeypatch.setattr(mr, "get_top_movers", _no_live_movers)

    ctx = RetrievalContext(query="test", db=db, intent="market_outlook")
    evidence = await mr._fetch(ctx)

    it = [e for e in evidence if e.entity == "IT" and e.source == "market"]
    pharma = [e for e in evidence if e.entity == "Pharma" and e.source == "market"]
    assert len(it) == 1 and "-0.50%" in it[0].claim, "stale Warehouse row must not be trusted -- live fallback must fire"
    assert it[0].timestamp is None, "the live-fallback path never has a real Warehouse timestamp"
    assert len(pharma) == 1 and "+0.75%" in pharma[0].claim


@pytest.mark.asyncio
async def test_global_index_evidence_is_additive_and_absent_when_no_warehouse_row(db, monkeypatch):
    now = datetime.now(timezone.utc)
    db.add(_row("GLOBAL_DOW_JONES", 42500.75, now, extra={"pct": 0.42}))
    # GLOBAL_SP500: intentionally no row -- must simply be absent, never fabricated
    await db.commit()

    monkeypatch.setattr(mr, "get_extended_indices", _no_live_indices)
    monkeypatch.setattr(mr, "get_sector_changes", _no_live_indices)
    monkeypatch.setattr(mr, "get_top_movers", _no_live_movers)

    ctx = RetrievalContext(query="test", db=db, intent="market_outlook")
    evidence = await mr._fetch(ctx)

    dow = [e for e in evidence if e.entity == "Dow Jones"]
    sp500 = [e for e in evidence if e.entity == "S&P 500"]
    assert len(dow) == 1
    assert dow[0].timestamp == now
    assert "42,500.75" in dow[0].claim and "+0.42%" in dow[0].claim
    assert sp500 == [], "no real row exists for GLOBAL_SP500 -- must never be fabricated"


@pytest.mark.asyncio
async def test_commodity_and_macro_evidence_real_and_timestamped(db, monkeypatch):
    now = datetime.now(timezone.utc)
    db.add(_row("COMMODITY_GOLD", 2650.30, now))
    db.add(_row("USDINR", 87.1234, now))
    await db.commit()

    monkeypatch.setattr(mr, "get_extended_indices", _no_live_indices)
    monkeypatch.setattr(mr, "get_sector_changes", _no_live_indices)
    monkeypatch.setattr(mr, "get_top_movers", _no_live_movers)

    ctx = RetrievalContext(query="test", db=db, intent="market_outlook")
    evidence = await mr._fetch(ctx)

    gold = [e for e in evidence if e.entity == "Gold"]
    inr = [e for e in evidence if e.entity == "USD/INR"]
    assert len(gold) == 1 and gold[0].timestamp == now and "2,650.30" in gold[0].claim
    assert len(inr) == 1 and inr[0].timestamp == now and "87.1234" in inr[0].claim


@pytest.mark.asyncio
async def test_source_failure_row_never_surfaces_as_evidence(db, monkeypatch):
    """A real, honest source_failure row (value=None) must not produce
    fabricated Evidence -- exactly the Warehouse "never fabricate" contract."""
    now = datetime.now(timezone.utc)
    db.add(_row("GLOBAL_NIKKEI225", None, now, quality="source_failure"))
    await db.commit()

    monkeypatch.setattr(mr, "get_extended_indices", _no_live_indices)
    monkeypatch.setattr(mr, "get_sector_changes", _no_live_indices)
    monkeypatch.setattr(mr, "get_top_movers", _no_live_movers)

    ctx = RetrievalContext(query="test", db=db, intent="market_outlook")
    evidence = await mr._fetch(ctx)

    assert [e for e in evidence if e.entity == "Nikkei 225"] == []

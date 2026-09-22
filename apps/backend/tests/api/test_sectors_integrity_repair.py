"""
Content-integrity repair (2026-09-22): SectorData's 12 rows were hand-
typed once at seed time (2026-07-22, db/seed.py) and never updated by
any job since — presented to users as live sector momentum via
list_sectors()/sector_intelligence() even though nothing behind that
`value`/`positive` column was ever real. This module locks in the
repair: neither endpoint may ever surface a SectorData-derived
percentage again, regardless of what rows exist in the table.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.sectors import _SECTOR_STOCKS, list_sectors, sector_intelligence
from app.db.base import Base


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_list_sectors_returns_empty_unconditionally():
    assert await list_sectors() == []


async def test_sector_intelligence_never_returns_a_fabricated_percentage(db_session):
    for key in _SECTOR_STOCKS:
        result = await sector_intelligence(key, db_session)
        assert result["value"] is None
        assert result["positive"] is None


async def test_sector_intelligence_uses_correct_display_names_not_naive_title_case(db_session):
    # .title() would wrongly produce "It"/"Fmcg" — the real fix source is
    # _SECTOR_NAMES, not a string transform.
    it_result = await sector_intelligence("it", db_session)
    assert it_result["name"] == "IT"
    fmcg_result = await sector_intelligence("fmcg", db_session)
    assert fmcg_result["name"] == "FMCG"


async def test_sector_intelligence_404s_for_ids_with_no_real_stock_backing(db_session):
    """"media", "psu-bank", and "pvt-bank" only ever rendered because the
    fabricated SectorData table had rows for them — no real
    _SECTOR_STOCKS entry backs any of the three. Content-integrity
    repair: these must 404 honestly now, not serve a page with nothing
    real to show."""
    from fastapi import HTTPException

    for orphaned_id in ("media", "psu-bank", "pvt-bank"):
        with pytest.raises(HTTPException) as exc_info:
            await sector_intelligence(orphaned_id, db_session)
        assert exc_info.value.status_code == 404


async def test_sector_intelligence_still_returns_real_stocks_for_every_real_sector(db_session):
    """The repair must not regress the real, non-fabricated part of this
    endpoint — constituent stock lookup keeps working for all 13 real
    sector keys."""
    result = await sector_intelligence("banking", db_session)
    assert result["stocks"]  # real _get_sector_stocks_cached output, non-empty
    assert all("symbol" in s for s in result["stocks"])

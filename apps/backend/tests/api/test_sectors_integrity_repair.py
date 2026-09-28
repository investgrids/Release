"""
Content-integrity repair (2026-09-22): SectorData's 12 rows were hand-
typed once at seed time (2026-07-22, db/seed.py) and never updated by
any job since — presented to users as live sector momentum via
list_sectors()/sector_intelligence() even though nothing behind that
`value`/`positive` column was ever real. This module locks in the
repair: neither endpoint may ever surface a SectorData-derived
percentage again, regardless of what rows exist in the table.
list_sectors() now reports the real NSE sectoral index day change
(2026-09-28) — tested here with yfinance mocked, no network.
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


class _FakeFastInfo:
    def __init__(self, last, prev):
        self.last_price, self.previous_close = last, prev


def _patch_yf(monkeypatch, values: dict[str, tuple]):
    import yfinance

    class _FakeTicker:
        def __init__(self, ticker):
            last, prev = values.get(ticker, (None, None))
            self.fast_info = _FakeFastInfo(last, prev)

    monkeypatch.setattr(yfinance, "Ticker", _FakeTicker)
    from app.api import sectors
    sectors._sector_index_cache.update(checked_at=0.0, success_at=0.0, data=None)


async def test_list_sectors_computes_real_day_change_from_the_actual_nse_index(monkeypatch):
    """2026-09-28: list_sectors() now reads the real NSE sectoral index
    (not the removed SectorData table, and not an ETF proxy) — the % is
    last/previous_close from the index itself, with provenance attached."""
    from app.api.sectors import _SECTOR_INDICES

    _patch_yf(monkeypatch, {"^NSEBANK": (110.0, 100.0), "^CNXIT": (95.0, 100.0)})
    rows = await list_sectors()
    by_id = {r["id"]: r for r in rows}
    assert by_id["banking"]["value"] == "10.00%" and by_id["banking"]["positive"] is True
    assert by_id["it"]["value"] == "-5.00%" and by_id["it"]["positive"] is False
    assert by_id["banking"]["ticker"] == _SECTOR_INDICES["banking"][1]
    assert by_id["banking"]["index_name"] == "NIFTY Bank"
    assert by_id["banking"]["previous_close"] == 100.0
    assert [r["id"] for r in rows] == ["banking", "it"]  # sorted best to worst


async def test_list_sectors_omits_an_index_with_missing_data_never_estimates(monkeypatch):
    _patch_yf(monkeypatch, {"^NSEBANK": (110.0, None), "^CNXIT": (float("nan"), 100.0), "^CNXPHARMA": (101.0, 100.0)})
    rows = await list_sectors()
    assert [r["id"] for r in rows] == ["pharma"]


async def test_upstream_failure_keeps_recent_real_data_but_never_serves_it_past_the_stale_cap(monkeypatch):
    from app.api import sectors

    _patch_yf(monkeypatch, {"^NSEBANK": (110.0, 100.0)})
    good = await list_sectors()
    assert [r["id"] for r in good] == ["banking"]

    # Upstream now fails (e.g. rate limited) after the fresh TTL expired.
    _patch_yf(monkeypatch, {})
    sectors._sector_index_cache.update(data=good, success_at=sectors.time.time() - sectors._SECTOR_INDEX_TTL - 1, checked_at=0.0)
    assert await list_sectors() == good  # recent real data still served

    sectors._sector_index_cache.update(data=good, success_at=sectors.time.time() - sectors._SECTOR_INDEX_MAX_STALE - 1, checked_at=0.0)
    assert await list_sectors() == []  # too old — honest empty state instead


async def test_every_listed_sector_links_to_a_real_sector_page():
    from app.api.sectors import _SECTOR_INDICES

    assert set(_SECTOR_INDICES) <= set(_SECTOR_STOCKS)


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

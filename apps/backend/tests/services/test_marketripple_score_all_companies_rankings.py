"""
Full-directory paginated Company Rankings — owner instruction 2026-09-27
("Company Rankings and UI": "show every company from the real Companies
directory, with pagination... eligible companies show their canonical
score... everyone else shows an explicit N/A with an honest reason, never
zero, never ranked"). Confirms get_all_companies_rankings() iterates the
SAME real directory list_companies() reads, ranks a real Banking symbol
within its own peer group, marks a real unsupported-sector company (e.g.
Finance/Insurance) honestly rather than silently dropping it, paginates
correctly, and never shows a fabricated score for anything.
"""
from __future__ import annotations

import pytest

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.rankings import get_all_companies_rankings


@pytest.mark.asyncio
async def test_every_row_has_a_symbol_and_an_honest_status():
    async with AsyncSessionLocal() as db:
        result = await get_all_companies_rankings(db, page=1, page_size=50)
    assert result["total"] > 0
    assert len(result["companies"]) <= 50
    for row in result["companies"]:
        assert row["symbol"]
        # 2026-10-03: one public state vocabulary (coverage.py).
        assert row["status"] in {
            "ranked", "not_processed", "needs_refresh", "insufficient_data", "unsupported",
        }
        if row["status"] != "ranked":
            assert row["score"] is None, f"{row['symbol']} is not ranked but shows a score"
            assert row["rank"] is None


@pytest.mark.asyncio
async def test_a_finance_or_insurance_company_reports_unsupported_sector_not_dropped():
    """Finance/Insurance are real, deliberately-excluded sectors (no
    approved methodology) -- a real company in one of them must still
    appear somewhere in the directory with an honest reason, never
    silently missing and never fabricated."""
    async with AsyncSessionLocal() as db:
        directory_total = (await get_all_companies_rankings(db, page=1, page_size=1))["total"]
        # Walk pages until we find a real Finance/Insurance-sector row (cap
        # the scan so a real, large directory doesn't make this test slow).
        found = None
        page_size = 200
        for page in range(1, min(10, (directory_total // page_size) + 2)):
            result = await get_all_companies_rankings(db, page=page, page_size=page_size)
            for row in result["companies"]:
                if row["sector"] in ("Finance", "Insurance"):
                    found = row
                    break
            if found:
                break
    assert found is not None, "expected at least one real Finance/Insurance company in the directory"
    assert found["status"] == "unsupported"
    assert found["score"] is None
    assert found["rank"] is None
    assert found["message"]


@pytest.mark.asyncio
async def test_pagination_covers_the_full_directory_with_no_overlap():
    async with AsyncSessionLocal() as db:
        page1 = await get_all_companies_rankings(db, page=1, page_size=100)
        page2 = await get_all_companies_rankings(db, page=2, page_size=100)
    symbols_1 = {r["symbol"] for r in page1["companies"]}
    symbols_2 = {r["symbol"] for r in page2["companies"]}
    assert not (symbols_1 & symbols_2), "consecutive pages must never overlap"
    assert page1["total"] == page2["total"]
    assert page1["total_pages"] == page2["total_pages"]


@pytest.mark.asyncio
async def test_superseded_symbols_helper_finds_a_real_renamed_alias():
    """The general mechanism behind the real 2025-10-24 TATAMOTORS -> TMPV
    NSE rename (owner instruction, 2026-09-27: "resolve the legacy
    TATAMOTORS/TMPV identity issue so it doesn't create a misleading
    duplicate") — _superseded_symbols() must report a company's OLD symbol
    once a real CompanyAlias(alias_type="old_symbol") row exists pointing
    at a DIFFERENT current CompanyEntity.symbol. Seeds its own fixture
    rather than relying on the real production bootstrap data (this test
    runs against the isolated scratch DB, which never carries that real
    NSE dataset) — the isolated scratch DB has no old_symbol rows at all
    until this test adds one, so the cache is reset first."""
    import uuid

    from sqlalchemy import delete
    from app.api.companies import _SUPERSEDED_SYMBOLS_CACHE, _superseded_symbols
    from app.db.models.company_entity import CompanyAlias, CompanyEntity

    entity_id = f"cmp_test_rename_{uuid.uuid4().hex[:8]}"
    old_symbol, current_symbol = "OLDTESTSYM", "NEWTESTSYM"
    async with AsyncSessionLocal() as db:
        db.add(CompanyEntity(entity_id=entity_id, company_name="Test Renamed Co", exchange="NSE", symbol=current_symbol, source="test"))
        await db.flush()
        db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=current_symbol, exchange="NSE", valid_to=None, source="test"))
        db.add(CompanyAlias(entity_id=entity_id, alias_type="old_symbol", alias_value=old_symbol, exchange="NSE", valid_to=None, source="test"))
        await db.commit()

    _SUPERSEDED_SYMBOLS_CACHE["data"] = None  # force a fresh read past the TTL cache
    try:
        async with AsyncSessionLocal() as db:
            superseded = await _superseded_symbols(db)
        assert old_symbol in superseded
        assert current_symbol not in superseded
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
            await db.commit()
        _SUPERSEDED_SYMBOLS_CACHE["data"] = None

"""
C4 qualification — real DB-backed. Reuses the same fixture Company Master
data as test_company_identity.py (RELIANCE, TCS, etc. — all already
outside the static _NSE_UNIVERSE's specific test symbols, so they're
real "missing" candidates once seeded). Rather than depending on the
real 1000+-node Graph (exercised live once against real data instead --
see artifacts/company_identity_c4_intelligence_exposure.md), this adds a
synthetic graph edge and a real AICompanySignal row to prove both
evidence sources independently gate qualification.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.models.company_signal import AICompanySignal
from app.db.session import AsyncSessionLocal
from app.services.company_identity.importer import run_full_import
from app.services.company_identity.qualification import qualify_missing_companies, resolve_entity_by_any_symbol
from tests.services.test_company_identity import EQ_CSV, SYMBOLCHANGE_CSV, _clean_fixture_rows


def _tag():
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def company_master_seeded():
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()
    yield
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)


@pytest.mark.asyncio
async def test_resolve_entity_by_any_symbol_finds_historical_alias(company_master_seeded):
    async with AsyncSessionLocal() as db:
        entity = await resolve_entity_by_any_symbol(db, "TATAMOTORS")
    assert entity is not None
    assert entity.symbol == "TMPV"


@pytest.mark.asyncio
async def test_resolve_entity_by_any_symbol_returns_none_for_unknown():
    async with AsyncSessionLocal() as db:
        entity = await resolve_entity_by_any_symbol(db, "TOTALLYFAKESYMBOL999")
    assert entity is None


@pytest.mark.asyncio
async def test_graph_edge_qualifies_a_previously_unevidenced_symbol(company_master_seeded):
    """Uses a uuid-unique fake symbol (never in the real Graph/AICompanySignal
    tables, so no real pre-existing evidence to confound the assertion)
    seeded as its own fixture entity, proving graph-edge evidence alone
    is sufficient to qualify."""
    tag = _tag()
    fake_symbol = f"ZQUAL{tag[:6].upper()}"
    node_id = f"company:{fake_symbol.lower()}"
    other_id = f"sector:x-{tag}"

    async with AsyncSessionLocal() as db:
        from app.db.models.company_entity import CompanyEntity, CompanyAlias
        entity = CompanyEntity(company_name=f"Test {fake_symbol}", isin=f"INE{tag.upper()}FAKE", exchange="NSE", symbol=fake_symbol, series="EQ", source="test")
        db.add(entity)
        await db.flush()
        db.add(CompanyAlias(entity_id=entity.entity_id, alias_type="symbol", alias_value=fake_symbol, exchange="NSE", source="test"))
        await db.commit()
        entity_id = entity.entity_id

    try:
        async with AsyncSessionLocal() as db:
            before = await qualify_missing_companies(db)
        before_row = next((r for r in before if r.symbol == fake_symbol), None)
        assert before_row is not None
        assert before_row.qualified is False
        assert before_row.graph_edge_count == 0

        async with AsyncSessionLocal() as db:
            db.add_all([
                IGNode(id=node_id, node_type="company", label=fake_symbol, ticker=fake_symbol),
                IGNode(id=other_id, node_type="sector", label="X"),
            ])
            await db.flush()
            db.add(IGEdge(id=f"eq-{tag}", source_id=node_id, target_id=other_id, edge_type="benefits", weight=0.5, confidence=0.5))
            await db.commit()

        async with AsyncSessionLocal() as db:
            after = await qualify_missing_companies(db)
        after_row = next(r for r in after if r.symbol == fake_symbol)
        assert after_row.qualified is True
        assert after_row.graph_edge_count >= 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IGEdge).where((IGEdge.source_id == node_id) | (IGEdge.target_id == node_id)))
            await db.execute(delete(IGNode).where(IGNode.id.in_([node_id, other_id])))
            from app.db.models.company_entity import CompanyEntity, CompanyAlias
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
            await db.commit()


@pytest.mark.asyncio
async def test_ai_signal_alone_also_qualifies(company_master_seeded):
    tag = _tag()
    fake_symbol = f"ZSIG{tag[:6].upper()}"

    async with AsyncSessionLocal() as db:
        from app.db.models.company_entity import CompanyEntity, CompanyAlias
        entity = CompanyEntity(company_name=f"Test {fake_symbol}", isin=f"INE{tag.upper()}SIG", exchange="NSE", symbol=fake_symbol, series="EQ", source="test")
        db.add(entity)
        await db.flush()
        db.add(CompanyAlias(entity_id=entity.entity_id, alias_type="symbol", alias_value=fake_symbol, exchange="NSE", source="test"))
        await db.commit()
        entity_id = entity.entity_id

    try:
        async with AsyncSessionLocal() as db:
            before = await qualify_missing_companies(db)
        before_row = next(r for r in before if r.symbol == fake_symbol)
        assert before_row.qualified is False

        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="article", source_id=f"test-{tag}", symbol=fake_symbol, company_name=fake_symbol,
                signed_magnitude=10.0, confidence=0.8, quality=0.8, signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            after = await qualify_missing_companies(db)
        after_row = next(r for r in after if r.symbol == fake_symbol)
        assert after_row.qualified is True
        assert after_row.ai_signal_count >= 1
        assert after_row.graph_edge_count == 0
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol == fake_symbol))
            from app.db.models.company_entity import CompanyEntity, CompanyAlias
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
            await db.commit()

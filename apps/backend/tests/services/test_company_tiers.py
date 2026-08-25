"""
C5 tiers — real DB-backed, against the isolated scratch DB (conftest.py).
Live-price checks (`check_live_data=True`) are network-dependent by
design (the same real yfinance mechanism companies.py's directory uses),
so tier-boundary tests here run with `check_live_data=False` to stay
deterministic; the one live-path test monkeypatches the batch-price
function rather than depending on real network access in CI.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_entity import CompanyEntity, CompanyAlias
from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.models.company_signal import AICompanySignal
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal
from app.services.company_identity.tiers import (
    classify_all_entities, summarize, alias_redirect_summary, classify_one, CoverageTier,
)


def _tag():
    return uuid.uuid4().hex[:8]


async def _make_entity(db, tag: str, suffix: str) -> CompanyEntity:
    symbol = f"ZT{suffix}{tag[:5].upper()}"
    entity = CompanyEntity(company_name=f"Test {symbol}", isin=f"INE{tag.upper()}{suffix}", exchange="NSE", symbol=symbol, series="EQ", source="test")
    db.add(entity)
    await db.flush()
    db.add(CompanyAlias(entity_id=entity.entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", source="test"))
    await db.commit()
    return entity


@pytest.mark.asyncio
async def test_two_graph_edges_qualify_tier_a_but_one_does_not():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        weak = await _make_entity(db, tag, "WEAK")
        strong = await _make_entity(db, tag, "STRONG")

    node_weak, node_strong, other1, other2 = f"company:{weak.symbol.lower()}", f"company:{strong.symbol.lower()}", f"sector:a-{tag}", f"sector:b-{tag}"
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([
                IGNode(id=node_weak, node_type="company", label=weak.symbol, ticker=weak.symbol),
                IGNode(id=node_strong, node_type="company", label=strong.symbol, ticker=strong.symbol),
                IGNode(id=other1, node_type="sector", label="A"),
                IGNode(id=other2, node_type="sector", label="B"),
            ])
            await db.flush()
            db.add_all([
                IGEdge(id=f"e1-{tag}", source_id=node_weak, target_id=other1, edge_type="benefits", weight=0.5, confidence=0.5),
                IGEdge(id=f"e2-{tag}", source_id=node_strong, target_id=other1, edge_type="benefits", weight=0.5, confidence=0.5),
                IGEdge(id=f"e3-{tag}", source_id=node_strong, target_id=other2, edge_type="hurts", weight=0.5, confidence=0.5),
            ])
            await db.commit()

        async with AsyncSessionLocal() as db:
            results = await classify_all_entities(db, check_live_data=False)
        by_symbol = {r.symbol: r for r in results}

        assert by_symbol[weak.symbol].tier == CoverageTier.C_IDENTITY_ONLY  # 1 edge -- not meaningful alone
        assert by_symbol[strong.symbol].tier == CoverageTier.A_INTELLIGENCE_RICH  # 2 edges
        assert by_symbol[strong.symbol].indexable is True
        assert by_symbol[weak.symbol].indexable is False
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IGEdge).where(IGEdge.id.in_([f"e1-{tag}", f"e2-{tag}", f"e3-{tag}"])))
            await db.execute(delete(IGNode).where(IGNode.id.in_([node_weak, node_strong, other1, other2])))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_([weak.entity_id, strong.entity_id])))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_([weak.entity_id, strong.entity_id])))
            await db.commit()


@pytest.mark.asyncio
async def test_single_ai_signal_alone_qualifies_tier_a():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        entity = await _make_entity(db, tag, "SIG")
    try:
        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="article", source_id=f"test-{tag}", symbol=entity.symbol, company_name=entity.symbol,
                signed_magnitude=5.0, confidence=0.7, quality=0.7, signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            results = await classify_all_entities(db, check_live_data=False)
        r = next(x for x in results if x.symbol == entity.symbol)
        assert r.tier == CoverageTier.A_INTELLIGENCE_RICH
        assert r.ai_signal_count == 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol == entity.symbol))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity.entity_id))
            await db.commit()


@pytest.mark.asyncio
async def test_v2_opportunity_linkage_alone_qualifies_tier_a():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        entity = await _make_entity(db, tag, "OPP")
    opp_id = f"opp-{tag}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(OpportunityV2(
                id=opp_id, formation_title="Test", current_title="Test",
                thesis_anchor="raw_dev:test", thesis_direction="positive",
                sectors=[], companies=[entity.symbol],
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            results = await classify_all_entities(db, check_live_data=False)
        r = next(x for x in results if x.symbol == entity.symbol)
        assert r.tier == CoverageTier.A_INTELLIGENCE_RICH
        assert r.v2_opportunity_count == 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id == opp_id))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity.entity_id))
            await db.commit()


@pytest.mark.asyncio
async def test_no_evidence_at_all_is_tier_c_not_indexed():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        entity = await _make_entity(db, tag, "NONE")
    try:
        async with AsyncSessionLocal() as db:
            results = await classify_all_entities(db, check_live_data=False)
        r = next(x for x in results if x.symbol == entity.symbol)
        assert r.tier == CoverageTier.C_IDENTITY_ONLY
        assert r.indexable is False
        assert r.sitemap is False
        assert r.public_page is False  # C: "Optional/resolvable", not automatically public
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity.entity_id))
            await db.commit()


@pytest.mark.asyncio
async def test_live_price_data_promotes_to_tier_b(monkeypatch):
    tag = _tag()
    async with AsyncSessionLocal() as db:
        entity = await _make_entity(db, tag, "MKT")
    try:
        def _fake_prices(symbols):
            return {s: {"price": "100.00", "pct": 0.5, "positive": True} for s in symbols if s == entity.symbol}

        monkeypatch.setattr("app.api.companies._fetch_prices_sync", _fake_prices)

        async with AsyncSessionLocal() as db:
            results = await classify_all_entities(db, check_live_data=True)
        r = next(x for x in results if x.symbol == entity.symbol)
        assert r.tier == CoverageTier.B_DATA_RICH
        assert r.has_live_market_data is True
        assert r.indexable is True
        assert r.public_page is True
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity.entity_id))
            await db.commit()


def test_summarize_matches_real_counts():
    from app.services.company_identity.tiers import TierResult
    results = [
        TierResult(entity_id="1", symbol="A", company_name="A", tier=CoverageTier.A_INTELLIGENCE_RICH, graph_edge_count=2, ai_signal_count=0, v2_opportunity_count=0, has_live_market_data=None, public_page=True, indexable=True, sitemap=True),
        TierResult(entity_id="2", symbol="B", company_name="B", tier=CoverageTier.B_DATA_RICH, graph_edge_count=0, ai_signal_count=0, v2_opportunity_count=0, has_live_market_data=True, public_page=True, indexable=True, sitemap=True),
        TierResult(entity_id="3", symbol="C", company_name="C", tier=CoverageTier.C_IDENTITY_ONLY, graph_edge_count=0, ai_signal_count=0, v2_opportunity_count=0, has_live_market_data=False, public_page=False, indexable=False, sitemap=False),
    ]
    summary = summarize(results)
    assert summary["total_entities"] == 3
    assert summary["tier_A"] == 1
    assert summary["tier_B"] == 1
    assert summary["tier_C"] == 1
    assert summary["indexable_count"] == 2
    assert summary["internal_only_count"] == 1


@pytest.mark.asyncio
async def test_alias_redirect_summary_counts_and_conflicts():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        e1 = await _make_entity(db, tag, "AL1")
        e2 = await _make_entity(db, tag, "AL2")
    old_symbol = f"OLDSYM{tag[:4].upper()}"
    try:
        async with AsyncSessionLocal() as db:
            # Real, sourced old_symbol alias -- counts toward canonical_redirects.
            db.add(CompanyAlias(entity_id=e1.entity_id, alias_type="old_symbol", alias_value=old_symbol, source="test"))
            await db.commit()

        async with AsyncSessionLocal() as db:
            summary = await alias_redirect_summary(db)
        assert summary["total_aliases"] >= 3  # 2 symbol aliases from _make_entity + 1 old_symbol
        assert summary["by_type"].get("old_symbol", 0) >= 1
        assert summary["canonical_redirects"] >= 1

        # Now create a real conflict: the SAME alias value on a DIFFERENT
        # entity, both with no valid_to (both "currently valid").
        async with AsyncSessionLocal() as db:
            db.add(CompanyAlias(entity_id=e2.entity_id, alias_type="old_symbol", alias_value=old_symbol, source="test"))
            await db.commit()

        async with AsyncSessionLocal() as db:
            summary_after = await alias_redirect_summary(db)
        assert summary_after["unresolved_conflicts"] >= 1
        assert old_symbol in summary_after["conflict_sample"]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_([e1.entity_id, e2.entity_id])))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_([e1.entity_id, e2.entity_id])))
            await db.commit()


# ── classify_one: the real, single-symbol path generateMetadata calls ──────

@pytest.mark.asyncio
async def test_classify_one_returns_none_for_unresolved_symbol():
    async with AsyncSessionLocal() as db:
        result = await classify_one(db, "TOTALLYFAKESYMBOL999")
    assert result is None


@pytest.mark.asyncio
async def test_classify_one_finds_tier_a_via_graph_edges():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        entity = await _make_entity(db, tag, "ONE")
    node, other1, other2 = f"company:{entity.symbol.lower()}", f"sector:a-{tag}", f"sector:b-{tag}"
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([
                IGNode(id=node, node_type="company", label=entity.symbol, ticker=entity.symbol),
                IGNode(id=other1, node_type="sector", label="A"),
                IGNode(id=other2, node_type="sector", label="B"),
            ])
            await db.flush()
            db.add_all([
                IGEdge(id=f"e1-{tag}", source_id=node, target_id=other1, edge_type="benefits", weight=0.5, confidence=0.5),
                IGEdge(id=f"e2-{tag}", source_id=node, target_id=other2, edge_type="hurts", weight=0.5, confidence=0.5),
            ])
            await db.commit()

        async with AsyncSessionLocal() as db:
            result = await classify_one(db, entity.symbol)
        assert result is not None
        assert result.tier == CoverageTier.A_INTELLIGENCE_RICH
        assert result.graph_edge_count == 2
        assert result.indexable is True
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IGEdge).where(IGEdge.id.in_([f"e1-{tag}", f"e2-{tag}"])))
            await db.execute(delete(IGNode).where(IGNode.id.in_([node, other1, other2])))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity.entity_id))
            await db.commit()


@pytest.mark.asyncio
async def test_classify_one_resolves_historical_symbol_to_the_current_entity():
    """Real, sourced C2 rename chain (TELCO->TATAMOTORS->TMPV) already
    exercised in test_company_identity.py -- confirms classify_one honors
    the same Company Master resolution the /companies/[symbol] redirect
    and generateMetadata both depend on."""
    from tests.services.test_company_identity import EQ_CSV, SYMBOLCHANGE_CSV, _clean_fixture_rows
    from app.services.company_identity.importer import run_full_import

    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            old = await classify_one(db, "TATAMOTORS")
            current = await classify_one(db, "TMPV")
        assert old is not None and current is not None
        assert old.symbol == current.symbol == "TMPV"
        assert old.entity_id == current.entity_id
    finally:
        async with AsyncSessionLocal() as db:
            await _clean_fixture_rows(db)


@pytest.mark.asyncio
async def test_classify_one_tier_c_when_no_evidence_and_no_live_data(monkeypatch):
    tag = _tag()
    async with AsyncSessionLocal() as db:
        entity = await _make_entity(db, tag, "DRK")
    try:
        monkeypatch.setattr("app.api.companies._fetch_prices_sync", lambda symbols: {})
        async with AsyncSessionLocal() as db:
            result = await classify_one(db, entity.symbol)
        assert result is not None
        assert result.tier == CoverageTier.C_IDENTITY_ONLY
        assert result.indexable is False
        assert result.public_page is False
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity.entity_id))
            await db.commit()

"""
S5-A — real DB-backed tests for the snapshot read/derivation path. The
full compute_and_persist_snapshot() itself is network-dependent (it calls
the real, frozen compute_marketripple_score()) — verified via a real
manual backfill run instead (artifacts/marketripple_score_s5_snapshot_backfill.md),
matching this whole initiative's established pattern of proving live-network
paths with a real run rather than a slow/flaky live pytest. These tests
cover the two pieces that are pure DB logic: which fiscal period counts as
"financial_data_as_of" (must respect the same S4.5/S4.5-B exclusions
scoring itself uses) and which snapshot counts as "latest" for a symbol.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.financial_fact import FinancialFact
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.snapshot import _real_financial_data_as_of, get_latest_snapshot


def _tag():
    return uuid.uuid4().hex[:8]


def _fact_row(symbol, metric_code, value, quality_status, fy, fq, doc_id):
    return FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_code, value=value, unit="pct",
        fiscal_year=fy, fiscal_quarter=fq, period_type="Quarterly", consolidation_scope="Non-Consolidated",
        source_provider="NSE", source_document_id=doc_id, source_document_url=f"https://example/{doc_id}",
        extraction_status="POPULATED", quality_status=quality_status, quality_reason=None,
        observed_at=datetime.now(timezone.utc),
    )


async def _cleanup_facts(symbol: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol == symbol))
        await db.commit()


async def _cleanup_snapshots(symbol: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol == symbol))
        await db.commit()


@pytest.mark.asyncio
async def test_financial_data_as_of_picks_newest_eligible_period():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        db.add_all([
            _fact_row(symbol, "gross_npa_pct", 0.02, "OK", 2024, 4, "doc-a"),
            _fact_row(symbol, "cet1_ratio", 0.15, "OK", 2025, 2, "doc-b"),
            # Newest real period, but ALL its facts are quarantined -- must
            # be skipped, the same way scoring itself would skip it.
            _fact_row(symbol, "roa", 0.02, "SOURCE_DOCUMENT_QUARANTINED", 2025, 3, "doc-c"),
        ])
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await _real_financial_data_as_of(db, symbol)
        assert result == "FY2025Q2"  # newest ELIGIBLE period, not the newest period overall
    finally:
        await _cleanup_facts(symbol)


@pytest.mark.asyncio
async def test_financial_data_as_of_none_when_nothing_eligible():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        db.add(_fact_row(symbol, "roa", 0.0001, "IMPLAUSIBLE_SCALE", 2025, 3, "doc-x"))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await _real_financial_data_as_of(db, symbol)
        assert result is None
    finally:
        await _cleanup_facts(symbol)


@pytest.mark.asyncio
async def test_get_latest_snapshot_picks_most_recent_by_calculated_at():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=50.0, coverage_pct=80.0, methodology_version="BANKING_V1",
            peer_universe=[], peer_universe_count=0, calculated_at=now - timedelta(days=1),
            publishable=False,
        ))
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=55.5, coverage_pct=83.3, methodology_version="BANKING_V1",
            peer_universe=[], peer_universe_count=0, calculated_at=now,
            publishable=False,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            latest = await get_latest_snapshot(db, symbol)
        assert latest is not None
        assert latest.score == 55.5  # the newer row, not the older one
    finally:
        await _cleanup_snapshots(symbol)


@pytest.mark.asyncio
async def test_get_latest_snapshot_none_when_no_snapshot_exists():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        result = await get_latest_snapshot(db, symbol)
    assert result is None

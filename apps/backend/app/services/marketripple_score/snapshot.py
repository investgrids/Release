"""
S5-A — compute-and-persist + read for MarketRippleScoreSnapshot. The real
27-bank sequential compute (measured 37-40 min for the full universe, S4)
must never run inside a Company-page request; this is the boundary
between that real computation and a fast, cached read.

compute_and_persist_snapshot() is the ONLY writer — it calls the existing,
frozen compute_marketripple_score() verbatim (no new scoring logic here)
and persists its real output. get_latest_snapshot() is the ONLY reader a
Company page should ever call for this data going forward — it does no
live computation, no yfinance/NSE calls, just a DB read.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.services.marketripple_score.engine import compute_marketripple_score


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _real_financial_data_as_of(db: AsyncSession, symbol: str) -> str | None:
    """The newest real fiscal period actually eligible for scoring (POPULATED
    and not ANOMALY/IMPLAUSIBLE_SCALE/SOURCE_DOCUMENT_QUARANTINED) among the
    4 FinancialFact-sourced metrics — mirrors _latest_valid_fact_value's own
    exclusion rules exactly, since this reports what scoring actually used,
    not just what exists in the table."""
    from app.db.models.financial_fact import (
        EXTRACTION_POPULATED, FinancialFact, QUALITY_ANOMALY,
        QUALITY_IMPLAUSIBLE_SCALE, QUALITY_SOURCE_DOCUMENT_QUARANTINED,
    )
    from app.services.marketripple_score.financial_strength import _FACT_METRICS

    _excluded = (QUALITY_ANOMALY, QUALITY_IMPLAUSIBLE_SCALE, QUALITY_SOURCE_DOCUMENT_QUARANTINED)
    rows = (await db.execute(
        select(FinancialFact.fiscal_year, FinancialFact.fiscal_quarter, FinancialFact.quality_status)
        .where(
            FinancialFact.symbol == symbol,
            FinancialFact.metric_code.in_([code for code, _ in _FACT_METRICS]),
            FinancialFact.consolidation_scope == "Non-Consolidated",
            FinancialFact.extraction_status == EXTRACTION_POPULATED,
        )
    )).all()
    periods = sorted({(fy, fq or 0) for fy, fq, qs in rows if qs not in _excluded}, reverse=True)
    if not periods:
        return None
    fy, fq = periods[0]
    return f"FY{fy}Q{fq}"


async def compute_and_persist_snapshot(db: AsyncSession, symbol: str, peer_group: list[str] | None = None) -> MarketRippleScoreSnapshot:
    """Runs the real, frozen scoring engine and persists its output as a
    new snapshot row (never updates an existing row — history is kept,
    the read path always takes the latest by calculated_at). Real network
    calls happen here (yfinance/NSE), same as any direct
    compute_marketripple_score() call — callers should run this from a
    scheduled job or a manual script, never from a live request handler."""
    from app.services.company_identity.qualification import resolve_entity_by_any_symbol

    symbol = symbol.upper()
    result = await compute_marketripple_score(db, symbol, peer_group=peer_group)
    entity = await resolve_entity_by_any_symbol(db, symbol)
    financial_data_as_of = await _real_financial_data_as_of(db, symbol)
    now = _now()

    fs = result.pillars.get("financial_strength")
    val = result.pillars.get("valuation")
    mkt = result.pillars.get("market_behaviour")
    ci = result.pillars.get("current_intelligence")

    snapshot = MarketRippleScoreSnapshot(
        entity_id=entity.entity_id if entity else None,
        symbol=symbol,
        score=result.score,
        rating=result.label,
        financial_strength=fs.score if fs else None,
        valuation=val.score if val else None,
        market_behaviour=mkt.score if mkt else None,
        current_intelligence=ci.score if ci else None,
        coverage_pct=result.overall_coverage_pct,
        financial_coverage_pct=fs.coverage_pct if fs else None,
        valuation_coverage_pct=val.coverage_pct if val else None,
        market_behaviour_coverage_pct=mkt.coverage_pct if mkt else None,
        current_intelligence_coverage_pct=ci.coverage_pct if ci else None,
        methodology_version=result.methodology_version,
        peer_universe=result.peer_universe,
        peer_universe_count=result.peer_universe_count,
        peer_universe_as_of=result.peer_universe_as_of,
        calculated_at=now,
        financial_data_as_of=financial_data_as_of,
        market_data_as_of=now,
        intelligence_as_of=now,
        publishable=result.publishable,
        publication_block_reason=result.publish_reason,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def get_latest_snapshot(db: AsyncSession, symbol: str) -> MarketRippleScoreSnapshot | None:
    """The one real read path a Company page should use — no live
    computation, no external network calls."""
    symbol = symbol.upper()
    return (await db.execute(
        select(MarketRippleScoreSnapshot)
        .where(MarketRippleScoreSnapshot.symbol == symbol)
        .order_by(MarketRippleScoreSnapshot.calculated_at.desc())
        .limit(1)
    )).scalar_one_or_none()

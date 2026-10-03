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


def _industrial_financial_data_as_of(fs) -> str | None:
    """The newest real statement date actually used across the Non-Banking
    Industrial Financial Strength pillar's own metrics — mirrors
    _real_financial_data_as_of's "what scoring actually used" intent, but
    reads it from the pillar's own metric_provenance (financial_strength_
    industrial.py) rather than a FinancialFact table, which doesn't exist
    for non-bank sectors."""
    if fs is None:
        return None
    provenance = (fs.detail or {}).get("metrics", {})
    dates = [m.get("observation_as_of") for m in provenance.values() if m.get("observation_as_of")]
    return max(dates) if dates else None


async def compute_and_persist_snapshot(
    db: AsyncSession, symbol: str, peer_group: list[str] | None = None,
    industrial_cache: dict | None = None,
) -> MarketRippleScoreSnapshot:
    """build_snapshot() + commit, one company at a time. The production refresh
    uses build_snapshot() directly and commits a whole sector in ONE
    transaction instead (see refresh.py)."""
    snapshot = await build_snapshot(db, symbol, peer_group=peer_group, industrial_cache=industrial_cache)
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def build_snapshot(
    db: AsyncSession, symbol: str, peer_group: list[str] | None = None,
    industrial_cache: dict | None = None,
) -> MarketRippleScoreSnapshot:
    """Runs the real, frozen scoring engine and persists its output as a
    new snapshot row (never updates an existing row — history is kept,
    the read path always takes the latest by calculated_at). Real network
    calls happen here (yfinance/NSE), same as any direct
    compute_marketripple_score() call — callers should run this from a
    scheduled job or a manual script, never from a live request handler.

    industrial_cache: forwarded verbatim to compute_marketripple_score's
    own identical parameter (NS1 round 2, 2026-09-27) — lets a batch
    backfill share one sector's prefetched peer/benchmark data across many
    persisted snapshots instead of each one re-fetching independently."""
    from app.services.company_identity.qualification import resolve_entity_by_any_symbol
    from app.services.marketripple_score.eligibility import (
        BANKING_V1_P1, NONBANK_INDUSTRIAL_V2_P1, evaluate_eligibility,
    )
    from app.services.marketripple_score.financial_strength import REAL_BANKING_METRICS_TOTAL
    from app.services.marketripple_score.financial_strength_industrial import REAL_INDUSTRIAL_METRICS_TOTAL
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    symbol = symbol.upper()
    result = await compute_marketripple_score(db, symbol, peer_group=peer_group, industrial_cache=industrial_cache)
    entity = await resolve_entity_by_any_symbol(db, symbol)
    now = _now()

    fs = result.pillars.get("financial_strength")
    val = result.pillars.get("valuation")
    mkt = result.pillars.get("market_behaviour")
    ci = result.pillars.get("current_intelligence")

    # S5-B — direct, real metric count (never reverse-derived from a
    # coverage percentage), and the real per-methodology eligibility
    # verdict. The headline SCORE now shares one function/tag across
    # sectors (engine.py's MARKETRIPPLE_SCORE_METHODOLOGY_VERSION), but
    # ELIGIBILITY still keys off which real metric registry (7 Banking
    # metrics vs. 6 Industrial metrics) actually produced this company's
    # Financial Strength pillar — a genuinely different denominator per
    # sector, not a leftover from the old two-methodology split. Peer
    # universe membership is the real, authoritative way to tell them
    # apart (methodology_version is now identical for both).
    from app.services.marketripple_score.coverage import score_sector_for
    sector = score_sector_for(symbol)
    is_banking = sector == "Banking"
    is_industrial = sector in NONBANK_INDUSTRIAL_SECTORS

    if is_banking:
        financial_data_as_of = await _real_financial_data_as_of(db, symbol)
    elif is_industrial:
        financial_data_as_of = _industrial_financial_data_as_of(fs)
    else:
        financial_data_as_of = None

    financial_metrics_used_count = len(fs.metrics_used) if fs else None
    financial_metrics_total_count = (
        REAL_BANKING_METRICS_TOTAL if is_banking
        else REAL_INDUSTRIAL_METRICS_TOTAL if is_industrial
        else None
    )
    publication_policy_version = None
    publication_block_reasons = None
    if is_banking:
        eligibility = evaluate_eligibility(
            financial_strength_score=fs.score if fs else None,
            financial_metrics_used=financial_metrics_used_count or 0,
            financial_metrics_total=REAL_BANKING_METRICS_TOTAL,
            overall_coverage_pct=result.overall_coverage_pct,
            financial_data_as_of=financial_data_as_of,
            policy=BANKING_V1_P1,
        )
        publication_policy_version = BANKING_V1_P1.name
        publication_block_reasons = eligibility.reasons
    elif is_industrial:
        eligibility = evaluate_eligibility(
            financial_strength_score=fs.score if fs else None,
            financial_metrics_used=financial_metrics_used_count or 0,
            financial_metrics_total=REAL_INDUSTRIAL_METRICS_TOTAL,
            overall_coverage_pct=result.overall_coverage_pct,
            financial_data_as_of=financial_data_as_of,
            policy=NONBANK_INDUSTRIAL_V2_P1,
        )
        publication_policy_version = NONBANK_INDUSTRIAL_V2_P1.name
        publication_block_reasons = eligibility.reasons

    # Market-behaviour publication floor (see market_behaviour.py): applies to
    # every supported sector, on top of the sector's own eligibility policy.
    if publication_policy_version is not None:
        from app.services.marketripple_score.eligibility import REASON_INSUFFICIENT_MARKET_HISTORY
        from app.services.marketripple_score.market_behaviour import pillar_has_sufficient_market_history

        if not pillar_has_sufficient_market_history(mkt):
            publication_block_reasons = [*(publication_block_reasons or []), REASON_INSUFFICIENT_MARKET_HISTORY]

    from types import SimpleNamespace

    from app.services.marketripple_score.corporate_action_holds import REASON_CORPORATE_ACTION_HOLD, score_hold_for
    from app.services.marketripple_score.data_quality import snapshot_data_quality_reasons

    # Data-quality gate (see data_quality.py): stale financials / unverifiable inputs are never publishable.
    if publication_policy_version is not None:
        quality = snapshot_data_quality_reasons(SimpleNamespace(
            symbol=symbol, financial_data_as_of=financial_data_as_of,
            market_behaviour_inputs=(mkt.detail or {}).get("input_provenance") if mkt else None,
        ))
        publication_block_reasons = [*(publication_block_reasons or []), *[r for r in quality if r not in (publication_block_reasons or [])]]

    if score_hold_for(symbol) is not None:
        publication_block_reasons = [*(publication_block_reasons or []), REASON_CORPORATE_ACTION_HOLD]

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
        financial_metrics_used_count=financial_metrics_used_count,
        financial_metrics_total_count=financial_metrics_total_count,
        publication_policy_version=publication_policy_version,
        publication_block_reasons=publication_block_reasons,
        methodology_version=result.methodology_version,
        peer_universe=result.peer_universe,
        peer_universe_count=result.peer_universe_count,
        peer_universe_as_of=result.peer_universe_as_of,
        calculated_at=now,
        financial_data_as_of=financial_data_as_of,
        market_data_as_of=now,
        intelligence_as_of=now,
        # Public only when the engine produced a headline AND an eligibility
        # policy actually ran AND every one of its checks passed (fail-closed:
        # a sector with no policy is never public).
        publishable=bool(result.publishable and publication_policy_version is not None and not publication_block_reasons),
        publication_block_reason=(
            result.publish_reason if not result.publishable
            else ("Not eligible: " + ", ".join(publication_block_reasons)) if publication_block_reasons
            else None
        ),
        pillar_coverage_status=result.pillar_coverage_status,
        pillar_coverage_message=result.pillar_coverage_message,
        market_behaviour_inputs=(mkt.detail or {}).get("input_provenance") if mkt else None,
    )
    return snapshot  # unsaved; the caller adds and commits


async def get_latest_snapshot(db: AsyncSession, symbol: str) -> MarketRippleScoreSnapshot | None:
    """The one real read path a Company page (and Compare, and Rankings —
    all three read through this same function) should use — no live
    computation, no external network calls.

    Filtered to MARKETRIPPLE_SCORE_METHODOLOGY_VERSION only (owner
    instruction, 2026-09-27, "one score calculation" unification — the
    prior filter accepted either of two separate tags, BANKING_V1 and
    NONBANK_INDUSTRIAL_V2; both are now retired and superseded by the one
    shared tag). "Latest by calculated_at" alone is not a safe proxy for
    "current methodology" — a stale-tagged row could otherwise still be
    selected if it ever happened to carry a newer timestamp than expected
    (a delayed batch, clock skew, a partially-completed recompute). Real
    superseded history (BANKING_V1/NONBANK_INDUSTRIAL_V1/V2 rows) is never
    deleted and stays queryable directly, it simply can never be chosen as
    "the" current result again — old and new methodology calculations
    can't be mistaken for each other by construction, not by convention."""
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION

    symbol = symbol.upper()
    return (await db.execute(
        select(MarketRippleScoreSnapshot)
        .where(
            MarketRippleScoreSnapshot.symbol == symbol,
            MarketRippleScoreSnapshot.methodology_version == MARKETRIPPLE_SCORE_METHODOLOGY_VERSION,
        )
        .order_by(MarketRippleScoreSnapshot.calculated_at.desc())
        .limit(1)
    )).scalar_one_or_none()

"""
Warehouse-health measurement — Phase 1B (owner instruction, 2026-08-23:
"Warehouse health now reports Raw Evidence totals and daily growth").

Admin/report use only — no public UI, per the original Phase 1 design.
Reused as-is for the eventual BEFORE-vs-CURRENT scorecard rather than
building a second, separate measurement path for that later.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.market_observation import MarketObservation
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source


async def _category_stats(db: AsyncSession, model, ts_col) -> dict:
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    week_start = now - timedelta(days=7)

    total = (await db.execute(select(func.count()).select_from(model))).scalar()
    added_today = (await db.execute(select(func.count()).select_from(model).where(ts_col >= today_start))).scalar()
    added_7d = (await db.execute(select(func.count()).select_from(model).where(ts_col >= week_start))).scalar()
    oldest = (await db.execute(select(func.min(ts_col)))).scalar()
    newest = (await db.execute(select(func.max(ts_col)))).scalar()

    return {
        "total": total, "added_today": added_today, "added_last_7d": added_7d,
        "oldest": str(oldest) if oldest else None, "newest": str(newest) if newest else None,
    }


async def raw_evidence_health(db: AsyncSession) -> dict:
    base = await _category_stats(db, RawEvidence, RawEvidence.observed_at)

    by_source = (await db.execute(
        select(RawEvidence.source_type, func.count()).group_by(RawEvidence.source_type)
    )).all()
    by_quality = (await db.execute(
        select(RawEvidence.quality, func.count()).group_by(RawEvidence.quality)
    )).all()
    distinct_sources = (await db.execute(select(func.count(func.distinct(RawEvidence.source_id))))).scalar()

    base.update({
        "by_source_type": {s: c for s, c in by_source},
        "by_quality": {q: c for q, c in by_quality},
        "distinct_active_sources": distinct_sources,
    })
    return base


async def market_observations_health(db: AsyncSession) -> dict:
    base = await _category_stats(db, MarketObservation, MarketObservation.captured_at)

    by_metric = (await db.execute(
        select(MarketObservation.metric, func.count()).group_by(MarketObservation.metric)
    )).all()
    by_quality = (await db.execute(
        select(MarketObservation.quality, func.count()).group_by(MarketObservation.quality)
    )).all()
    distinct_metrics = (await db.execute(select(func.count(func.distinct(MarketObservation.metric))))).scalar()

    base.update({
        "by_metric": {m: c for m, c in by_metric},
        "by_quality": {q: c for q, c in by_quality},
        "distinct_persisted_metrics": distinct_metrics,
    })
    return base


async def source_registry_health(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count()).select_from(Source))).scalar()
    by_rights_basis = (await db.execute(
        select(Source.rights_basis, func.count()).group_by(Source.rights_basis)
    )).all()
    return {"total_sources": total, "by_rights_basis": {r: c for r, c in by_rights_basis}}


async def warehouse_health_report(db: AsyncSession) -> dict:
    """The single reusable measurement — same shape used for the daily
    observability requirement and the eventual BEFORE-vs-CURRENT
    scorecard, so neither redefines its own metrics independently."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_evidence": await raw_evidence_health(db),
        "market_observations": await market_observations_health(db),
        "source_registry": await source_registry_health(db),
    }

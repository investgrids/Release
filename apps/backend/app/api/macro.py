"""
Macro Release API — read-only access to structured macro-economic data
releases (see app/services/macro_extraction.py, app/db/models/macro_release.py).

GET /api/macro/releases       -> list, optionally filtered by metric
GET /api/macro/releases/{id}  -> single release
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.macro_release import MacroRelease

router = APIRouter()


def _to_dict(row: MacroRelease) -> dict:
    return {
        "id": row.id,
        "event_id": row.event_id,
        "metric": row.metric,
        "release_value": row.release_value,
        "previous_value": row.previous_value,
        "expected_value": row.expected_value,
        "surprise": (
            round(row.release_value - row.expected_value, 4)
            if row.release_value is not None and row.expected_value is not None
            else None
        ),
        "unit": row.unit,
        "period": row.period,
        "geography": row.geography,
        "importance": row.importance,
        "affected_sectors": row.affected_sectors,
        "affected_companies": row.affected_companies,
        "source": row.source,
        "source_url": row.source_url,
        "headline": row.headline,
        "release_date": row.release_date.isoformat() if row.release_date else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/releases")
async def list_releases(
    metric: str | None = Query(None),
    hours: int = Query(720, le=8760),  # default 30 days, cap 1 year
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = select(MacroRelease).where(MacroRelease.created_at >= cutoff)
    if metric:
        stmt = stmt.where(MacroRelease.metric == metric.upper())
    stmt = stmt.order_by(MacroRelease.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {"count": len(rows), "releases": [_to_dict(r) for r in rows]}


@router.get("/releases/{release_id}")
async def get_release(release_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        select(MacroRelease).where(MacroRelease.id == release_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Macro release not found")
    return _to_dict(row)

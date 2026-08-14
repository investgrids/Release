"""
Critical Event Coverage API — read-only observability over the
EventCoverage registry (see app/services/coverage_engine.py). Answers the
two questions the audit found the pipeline couldn't answer before: what
important events did we detect, and which of them did we fail to cover.

GET /api/coverage/funnel             -> publishing funnel counts (Part 25)
GET /api/coverage/critical-gaps      -> Critical/High events still uncovered
GET /api/coverage/publishing-summary -> articles-vs-events-covered split (Phase 12)
GET /api/coverage/enrichment-health  -> pending/retrying/failed enrichment counts
GET /api/coverage/publishing-latency -> real event-to-publish elapsed time
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.session import get_db
from app.services import coverage_engine

router = APIRouter()


@router.get("/funnel")
async def get_funnel(hours: int = Query(24, le=168), db: AsyncSession = Depends(get_db)):
    return await coverage_engine.funnel_counts(db, hours=hours)


@router.get("/publishing-summary")
async def get_publishing_summary(hours: int = Query(24, le=168), db: AsyncSession = Depends(get_db)):
    return await coverage_engine.coverage_vs_publishing_summary(db, hours=hours)


@router.get("/enrichment-health")
async def get_enrichment_health(hours: int = Query(24, le=168), db: AsyncSession = Depends(get_db)):
    return await coverage_engine.enrichment_health(db, hours=hours)


@router.get("/publishing-latency")
async def get_publishing_latency(hours: int = Query(24, le=168), db: AsyncSession = Depends(get_db)):
    return await coverage_engine.publishing_latency(db, hours=hours)


@router.get("/critical-gaps")
async def get_critical_gaps(hours: int = Query(24, le=168), db: AsyncSession = Depends(get_db)):
    rows = await coverage_engine.find_uncovered_critical(db, hours=hours)
    return {
        "window_hours": hours,
        "count": len(rows),
        "items": [
            {
                "event_id": r.event_id,
                "priority": r.priority,
                "priority_score": r.priority_score,
                "detected_at": r.detected_at.replace(tzinfo=None).isoformat() + "Z" if r.detected_at else None,
                "source": r.source,
                "event_title": r.event_title,
                "sectors": r.sectors,
                "companies": r.companies,
                "coverage_status": r.coverage_status,
            }
            for r in rows
        ],
    }

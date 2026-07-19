"""
Events API — list + detail + market-data + market-chart endpoints.
"""
from __future__ import annotations

import structlog
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import get_events
from app.db.session import get_db
from app.schemas.event import CompanyImpact, EventSummary
from app.schemas.event_detail import EventDetailResponse
from app.services.event_service import EventService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _normalize_score(score: float) -> float:
    """Normalize to 0-100 scale. Seed events use 0-10; pipeline events use 0-100."""
    if score <= 10.0:
        return round(score * 10.0, 1)
    return round(score, 1)


def _build_summary(e, companies: list) -> EventSummary:
    return EventSummary(
        id=e.id,
        title=e.title,
        summary=e.summary or "",
        impact_score=_normalize_score(float(e.impact_score or 0)),
        confidence=float(e.confidence or 0),
        sectors=e.sectors or [],
        companies=companies,
        date=e.published_at,
        category=e.category or e.event_type or "Macro",
        event_type=e.event_type or "",
        source=e.source or "",
    )


@router.get("/", response_model=List[EventSummary])
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    page_size: int = Query(None, ge=1, le=100),
    sort_by: str = Query("published_at"),
    db: AsyncSession = Depends(get_db),
):
    effective_limit = page_size if page_size is not None else limit

    if sort_by == "impact_score":
        # Fetch a wider pool so mixed-scale scores can be normalized and re-sorted in Python.
        # Pipeline events use 0-100 (score=60), seed events use 0-10 (score=8.7 → norm 87).
        # DB ordering on raw values would put 60 before 8.7, hiding high-quality seeds.
        pool_rows = await get_events(db, limit=200, sort_by="published_at")
        result = []
        for e in pool_rows:
            companies = [
                CompanyImpact(symbol=c.get("symbol", ""), name=c.get("name", ""), impact=c.get("impact", "Neutral"))
                if isinstance(c, dict) else
                CompanyImpact(symbol=c.strip(), name=c.strip(), impact="Neutral")
                for c in (e.companies or []) if isinstance(c, dict) or (isinstance(c, str) and c.strip())
            ]
            result.append(_build_summary(e, companies))
        result.sort(key=lambda x: x.impact_score, reverse=True)
        return result[:effective_limit]
    else:
        rows = await get_events(db, limit=effective_limit, sort_by=sort_by)
        result = []
        for e in rows:
            companies = [
                CompanyImpact(symbol=c.get("symbol", ""), name=c.get("name", ""), impact=c.get("impact", "Neutral"))
                if isinstance(c, dict) else
                CompanyImpact(symbol=c.strip(), name=c.strip(), impact="Neutral")
                for c in (e.companies or []) if isinstance(c, dict) or (isinstance(c, str) and c.strip())
            ]
            result.append(_build_summary(e, companies))
        return result


@router.get("/{event_id}/market-data")
async def get_event_market_data(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Real-time market status + sector-relevant index quotes (never cached)."""
    from app.repositories.event_repository import EventRepository
    from app.services.market_data import get_market_status, get_event_market_indices

    repo = EventRepository(db)
    sectors_obj = await repo.get_sectors(event_id)
    sector_names = [s.sector for s in sectors_obj]

    market_status = get_market_status()
    indices = await get_event_market_indices(sector_names)
    return {"marketStatus": market_status, "marketIndices": indices}


@router.get("/{event_id}/market-chart")
async def get_event_market_chart(
    event_id: str,
    period: str = Query("1D"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns chart data for the primary sector index of this event.
    Falls back to Nifty 50 when no sectors are mapped.
    """
    from app.repositories.event_repository import EventRepository
    from app.services.market_data import (
        get_ticker_chart, _SECTOR_INDEX_MAP,
    )

    repo = EventRepository(db)
    sectors_obj = await repo.get_sectors(event_id)
    sector_names = [s.sector for s in sectors_obj]

    primary_ticker = "^NSEI"
    primary_name   = "Nifty 50"
    for sector in sector_names:
        key = sector.lower().strip()
        for keyword, (name, ticker) in _SECTOR_INDEX_MAP.items():
            if keyword in key:
                primary_ticker = ticker
                primary_name   = name
                break
        else:
            continue
        break

    data = await get_ticker_chart(primary_ticker, period)
    return {"period": period, "ticker": primary_ticker, "name": primary_name, "data": data}


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    logger.info("GET /api/events/%s", event_id)
    service = EventService(db)
    detail = await service.get_event_detail(event_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return detail


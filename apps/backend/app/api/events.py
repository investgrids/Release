"""
Events API â€” list + detail + market-data + market-chart endpoints.
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


@router.get("/", response_model=List[EventSummary])
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = await get_events(db, limit=limit)
    result = []
    for e in rows:
        companies = []
        for c in (e.companies or []):
            if isinstance(c, dict):
                companies.append(CompanyImpact(
                    symbol=c.get("symbol", ""),
                    name=c.get("name", ""),
                    impact=c.get("impact", "Neutral"),
                ))
            elif isinstance(c, str) and c.strip():
                companies.append(CompanyImpact(symbol=c.strip(), name=c.strip(), impact="Neutral"))
        result.append(
            EventSummary(
                id=e.id,
                title=e.title,
                summary=e.summary or "",
                impact_score=float(e.impact_score or 0),
                confidence=float(e.confidence or 0),
                sectors=e.sectors or [],
                companies=companies,
                date=e.published_at,
                category=e.category or e.event_type or "Macro",
                event_type=e.event_type or "",
                source=e.source or "",
            )
        )
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


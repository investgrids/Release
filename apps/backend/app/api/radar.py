"""
Radar API
  GET /api/radar/           â€” paginated opportunity list (from DB)
  GET /api/radar/{id}       â€” full opportunity detail (from DB, cached via Redis)

No AI inference happens here. All data is pre-computed by background workers.
"""
from __future__ import annotations

import structlog

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.opportunity_detail import OpportunityDetailResponse, PaginatedOpportunities
from app.services.opportunity_service import OpportunityService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> OpportunityService:
    return OpportunityService(db)


# â”€â”€ Detail â€” must be declared BEFORE list so /{id} doesn't swallow GET / â”€â”€â”€â”€â”€

@router.get("/{opportunity_id}", response_model=OpportunityDetailResponse)
async def get_opportunity_detail(
    opportunity_id: int,
    service: OpportunityService = Depends(_get_service),
) -> OpportunityDetailResponse:
    detail = await service.get_opportunity_details(opportunity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id} not found")
    return detail


@router.get("/", response_model=PaginatedOpportunities)
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: OpportunityService = Depends(_get_service),
) -> PaginatedOpportunities:
    return await service.list_opportunities(page=page, page_size=page_size)


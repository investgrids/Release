"""
Radar API
  GET /api/radar/           — paginated opportunity list (from DB)
  GET /api/radar/{id}       — full opportunity detail (from DB, cached via Redis)

No AI inference happens here. All data is pre-computed by background workers.
"""
from __future__ import annotations

import structlog

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.opportunity_detail import OpportunityDetailResponse, PaginatedOpportunities
from app.services.opportunity_service import OpportunityService
from app.services.opportunity_v2.read_service import get_opportunity_v2_detail

logger = structlog.get_logger(__name__)

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> OpportunityService:
    return OpportunityService(db)


# ── Detail — must be declared BEFORE list so /{id} doesn't swallow GET / ─────
#
# Dual lookup (V2 Promotion Blocker Remediation, Batch A): a plain integer
# path segment is a legacy V1 numeric id (existing lookup, byte-for-byte
# unchanged, never redirected — V1 URLs stay 200 permanently). Anything
# else is treated as a V2 slug. This is additive only; nothing about the
# V1 branch below changed.

@router.get("/{opportunity_id}")
async def get_opportunity_detail(
    opportunity_id: str,
    service: OpportunityService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    if not opportunity_id.isdigit():
        detail_v2 = await get_opportunity_v2_detail(db, opportunity_id)
        if detail_v2 is None:
            raise HTTPException(status_code=404, detail=f"Opportunity '{opportunity_id}' not found")
        return detail_v2

    detail = await service.get_opportunity_details(int(opportunity_id))
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id} not found")

    # Opportunity Radar 2.0 — see opportunity_intelligence.py's module
    # docstring. Best-effort: any single piece failing must never break the
    # page (each already degrades gracefully to None/[] on its own).
    from app.services import opportunity_intelligence as oi

    try:
        detail.investment_verdict = oi.compute_investment_verdict(
            detail.opportunity_score, detail.confidence, detail.risk_level, detail.trend,
        )
    except Exception as exc:
        logger.warning("radar.verdict_fail", exc=str(exc)[:160])

    try:
        detail.primary_event = max(detail.events, key=lambda e: e.importance) if detail.events else None
    except Exception as exc:
        logger.warning("radar.primary_event_fail", exc=str(exc)[:160])

    try:
        detail.historical_similarity = await oi.get_historical_similarity(detail.sectors, detail.title)
    except Exception as exc:
        logger.warning("radar.historical_fail", exc=str(exc)[:160])

    try:
        detail.catalysts = await oi.get_catalysts(detail.sectors)
    except Exception as exc:
        logger.warning("radar.catalysts_fail", exc=str(exc)[:160])

    return detail


@router.get("/", response_model=PaginatedOpportunities)
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: OpportunityService = Depends(_get_service),
) -> PaginatedOpportunities:
    return await service.list_opportunities(page=page, page_size=page_size)


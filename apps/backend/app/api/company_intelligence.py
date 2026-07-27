"""Company Intelligence — GET /api/company-intelligence/{symbol}.

Own router, same reasoning as every other dedicated router this session.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import company_intelligence as ci

router = APIRouter()
log = structlog.get_logger(__name__)


@router.get("/{symbol}")
async def company_intelligence(
    symbol: str,
    gov_score: float | None = Query(None),
    price_positive: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """{"available": False} for an unrecognized symbol — never a 404, the
    frontend just hides the section."""
    try:
        return await ci.get_company_intelligence(db, symbol, gov_score, price_positive)
    except Exception as exc:
        log.warning("company_intelligence.fail", symbol=symbol, exc=str(exc)[:200])
        return {"available": False}

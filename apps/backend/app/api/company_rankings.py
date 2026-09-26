"""
Company Rankings API — the one real backend ranking endpoint over approved
MarketRippleScoreSnapshot data (2026-09-26 migration). Banking-only today
(BANKING_V1 is the only approved methodology). No frontend score
calculation — every field here is read straight from
services.marketripple_score.rankings, which itself never recomputes a
score, only reads get_marketripple_score_projection() per symbol.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.marketripple_score.rankings import get_banking_rankings, get_unsupported_sector_response

router = APIRouter()


@router.get("/{sector}")
async def get_company_rankings(sector: str, db: AsyncSession = Depends(get_db)):
    if sector.lower() == "banking":
        return await get_banking_rankings(db)
    return get_unsupported_sector_response(sector)

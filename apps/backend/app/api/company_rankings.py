"""
Company Rankings API — the one real backend ranking endpoint over approved
MarketRippleScoreSnapshot data (2026-09-26 migration; NS1 non-Banking
cohort added 2026-09-27). Two approved methodologies today: BANKING_V1 and
NONBANK_INDUSTRIAL_V1 (sector_universe.py's NONBANK_INDUSTRIAL_SECTORS) —
each ranked in its own separate list, never blended, since scores from
different methodologies are never directly comparable. No frontend score
calculation — every field here is read straight from
services.marketripple_score.rankings, which itself never recomputes a
score, only reads get_marketripple_score_projection() per symbol.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.marketripple_score.rankings import (
    get_banking_rankings, get_industrial_sector_rankings, get_unsupported_sector_response,
)
from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

router = APIRouter()

_INDUSTRIAL_SECTORS_LOWER = {s.lower(): s for s in NONBANK_INDUSTRIAL_SECTORS}


@router.get("/{sector}")
async def get_company_rankings(sector: str, db: AsyncSession = Depends(get_db)):
    if sector.lower() == "banking":
        return await get_banking_rankings(db)
    real_sector = _INDUSTRIAL_SECTORS_LOWER.get(sector.lower())
    if real_sector:
        return await get_industrial_sector_rankings(db, real_sector)
    return get_unsupported_sector_response(sector)

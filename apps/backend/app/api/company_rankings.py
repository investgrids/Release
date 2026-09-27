"""
Company Rankings API — the one real backend ranking endpoint over approved
MarketRippleScoreSnapshot data (2026-09-26 migration; NS1 non-Banking
cohort added 2026-09-27; full-directory pagination added the same day,
"Company Rankings and UI"). One shared methodology
(MARKETRIPPLE_SCORE_METHODOLOGY_VERSION) computes every supported
company's headline number, but ranking POSITION stays scoped to a real,
comparable peer group — Banking and each NONBANK_INDUSTRIAL_SECTORS
sector are still ranked in their own separate list, never blended, since
a company is only ever comparable to its real sector peers. No frontend
score calculation — every field here is read straight from
services.marketripple_score.rankings, which itself never recomputes a
score, only reads get_marketripple_score_projection() per symbol.

GET / (no sector) — the full, paginated real Companies directory: every
company, sorted by name, each row showing its real rank within its own
sector if ranked, or an honest reason if not (see
get_all_companies_rankings's own docstring). GET /{sector} keeps the
older single-sector view for any caller that still wants just Banking or
just one industrial sector.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.marketripple_score.rankings import (
    get_all_companies_rankings, get_banking_rankings, get_industrial_sector_rankings,
    get_unsupported_sector_response,
)
from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

router = APIRouter()

_INDUSTRIAL_SECTORS_LOWER = {s.lower(): s for s in NONBANK_INDUSTRIAL_SECTORS}


@router.get("/")
async def get_all_company_rankings(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await get_all_companies_rankings(db, page=page, page_size=page_size)


@router.get("/{sector}")
async def get_company_rankings(sector: str, db: AsyncSession = Depends(get_db)):
    if sector.lower() == "banking":
        return await get_banking_rankings(db)
    real_sector = _INDUSTRIAL_SECTORS_LOWER.get(sector.lower())
    if real_sector:
        return await get_industrial_sector_rankings(db, real_sector)
    return get_unsupported_sector_response(sector)

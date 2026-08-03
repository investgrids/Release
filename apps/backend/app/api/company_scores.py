"""
AI Company Intelligence Score API — thin HTTP layer over
company_score_engine.py. See that module's docstring for the formula and
data sources; this file only exposes it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.aipe.company_score_engine import compute_company_score, compute_sector_rankings, get_sector_signal_counts

router = APIRouter()


@router.get("/sector-counts")
async def get_sector_counts(db: AsyncSession = Depends(get_db)):
    return await get_sector_signal_counts(db)


@router.get("/{symbol}")
async def get_company_score(symbol: str, db: AsyncSession = Depends(get_db)):
    return await compute_company_score(db, symbol)


@router.get("/sector/{sector}")
async def get_sector_rankings(sector: str, limit: int = Query(20, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    ranked = await compute_sector_rankings(db, sector=sector, limit=limit)
    return {"sector": sector, "companies": ranked}


@router.get("/")
async def get_top_rankings(
    sector: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    ranked = await compute_sector_rankings(db, sector=sector, limit=limit)
    return {"sector": sector, "companies": ranked}

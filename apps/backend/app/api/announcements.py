"""
Company Announcements API
GET /api/announcements/              — recent announcements (all companies)
GET /api/announcements/{symbol}      — announcements for a specific stock
POST /api/announcements/refresh      — trigger manual ingestion
"""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/")
async def list_announcements(
    limit: int = Query(default=20, le=100),
    high_impact: bool = Query(default=False),
):
    from app.services.company_announcements_service import get_recent_announcements
    items = await get_recent_announcements(limit=limit, high_impact_only=high_impact)
    return {"announcements": items, "count": len(items)}


@router.get("/{symbol}")
async def symbol_announcements(
    symbol: str,
    limit: int = Query(default=10, le=50),
):
    from app.services.company_announcements_service import get_recent_announcements
    items = await get_recent_announcements(symbol=symbol.upper(), limit=limit)
    return {"symbol": symbol.upper(), "announcements": items, "count": len(items)}


@router.post("/refresh")
async def refresh_announcements():
    from app.services.company_announcements_service import ingest_announcements
    saved = await ingest_announcements()
    return {"status": "ok", "saved": saved}

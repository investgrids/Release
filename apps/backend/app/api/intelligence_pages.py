"""
Page Intelligence API — /api/intelligence/{context}

Universal intelligence endpoints — one per page context.
Every endpoint returns the same standardized shape; pages only render.

Routes (all GET):
  /home                  — macro market intelligence for the home page
  /company/{symbol}      — company-specific intelligence (NSE ticker)
  /event/{event_id}      — event-specific intelligence
  /theme/{theme_id:path} — theme-specific intelligence (slug, e.g. "rate-cuts")
  /news/{news_id}        — news article intelligence
  /search?q=...          — search intelligence (wraps AI search pipeline)

Standard response shape:
  market_story, key_takeaway, opportunities, risks, companies, sectors,
  themes, historical_context, related_intelligence, confidence, monitoring_points,
  generated_at, context_type, context_id
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

log = structlog.get_logger(__name__)
router = APIRouter()


def _err(detail: str = "Intelligence temporarily unavailable") -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": detail})


@router.get("/home")
async def home_intelligence():
    """Market intelligence for the home page — macro overview."""
    try:
        from app.services.page_intelligence_service import get_home_intelligence
        return await get_home_intelligence()
    except Exception as exc:
        log.error("api.intelligence.home", error=str(exc))
        return _err()


@router.get("/company/{symbol}")
async def company_intelligence(symbol: str):
    """Intelligence for a specific NSE-listed company."""
    try:
        from app.services.page_intelligence_service import get_company_intelligence
        return await get_company_intelligence(symbol)
    except Exception as exc:
        log.error("api.intelligence.company", symbol=symbol, error=str(exc))
        return _err()


@router.get("/event/{event_id}")
async def event_intelligence(event_id: str):
    """Intelligence for a specific market event."""
    try:
        from app.services.page_intelligence_service import get_event_intelligence
        return await get_event_intelligence(event_id)
    except Exception as exc:
        log.error("api.intelligence.event", event_id=event_id, error=str(exc))
        return _err()


@router.get("/theme/{theme_id:path}")
async def theme_intelligence(theme_id: str):
    """Intelligence for a market theme (slug, e.g. 'rate-cuts' or 'banking-stress')."""
    try:
        from app.services.page_intelligence_service import get_theme_intelligence
        return await get_theme_intelligence(theme_id)
    except Exception as exc:
        log.error("api.intelligence.theme", theme_id=theme_id, error=str(exc))
        return _err()


@router.get("/news/{news_id}")
async def news_intelligence(news_id: str):
    """Intelligence for a specific news article."""
    try:
        from app.services.page_intelligence_service import get_news_intelligence
        return await get_news_intelligence(news_id)
    except Exception as exc:
        log.error("api.intelligence.news", news_id=news_id, error=str(exc))
        return _err()


@router.get("/search")
async def search_intelligence(
    q: str = Query(..., min_length=1, max_length=300, description="Search query"),
):
    """Intelligence for a free-text search query."""
    try:
        from app.services.page_intelligence_service import get_search_intelligence
        return await get_search_intelligence(q)
    except Exception as exc:
        log.error("api.intelligence.search", error=str(exc))
        return _err()

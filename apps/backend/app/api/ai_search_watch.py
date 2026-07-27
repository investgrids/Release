"""Investment Watch (Phase 2B) — GET /api/ai/search/investment-watch.

Own router (not appended to ai_search.py's), same reasoning as every other
ai_search_*.py file this session: routes added directly to the large
ai_search.py router have proven unreachable under this FastAPI version.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from fastapi import Request
from app.db.session import get_db
from app.services.ai_search import investment_watch as investment_watch_mod

router = APIRouter()
log = structlog.get_logger(__name__)


@router.get("/investment-watch")
@limiter.limit("60/minute")
async def investment_watch(
    request: Request,
    key: str | None = Query(None, max_length=96, description='e.g. "company:HAL" or "sector:defence" — see response["watch_subject"]'),
    symbol: str | None = Query(None, max_length=32),
    sector: str | None = Query(None, max_length=64),
    db: AsyncSession = Depends(get_db),
):
    """Returns None-shaped {"available": False} when there's no verdict
    history yet for this subject (e.g. first-ever search for it, or a
    multi-company comparison the panel deliberately doesn't track — see
    investment_watch.subject_for). Never a 404 — the frontend just hides
    the panel.

    `key` is the preferred param — it's the exact subject_key the search
    response already handed back as response["watch_subject"]["subject_key"],
    so the frontend never has to re-derive it. `symbol`/`sector` stay as a
    convenience fallback for direct/manual calls."""
    subject_key = key
    if not subject_key and symbol:
        subject_key = f"company:{symbol.upper()}"
    elif not subject_key and sector:
        subject_key = f"sector:{sector.lower()}"
    if not subject_key:
        return {"available": False}

    watch = await investment_watch_mod.get_watch(db, subject_key, sector or symbol)
    if not watch:
        return {"available": False}
    return {"available": True, **watch}

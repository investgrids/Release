"""
Monitoring Checklist API — AI-generated checklists for any entity.

GET /api/checklist/{entity_type}/{entity_id}
  entity_type : event | company | story | opportunity | ripple | search
  Query params: title, description, sector
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from app.core.limiter import limiter
from app.services.ai_service import generate_monitoring_checklist

router = APIRouter()

_VALID_TYPES = {"event", "company", "story", "opportunity", "ripple", "search"}


@router.get("/{entity_type}/{entity_id}")
@limiter.limit("20/minute")
async def get_checklist(
    request: Request,
    entity_type: str,
    entity_id: str,
    title: str       = Query(default="", max_length=200),
    description: str = Query(default="", max_length=800),
    sector: str      = Query(default="", max_length=100),
):
    safe_type = entity_type if entity_type in _VALID_TYPES else "event"
    return await generate_monitoring_checklist(
        entity_type=safe_type,
        entity_id=entity_id,
        title=title,
        description=description,
        sector=sector,
    )

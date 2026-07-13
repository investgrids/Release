"""
Pattern Intelligence API — AI historical pattern matching for any entity.

GET /api/pattern/{entity_type}/{entity_id}
  entity_type : event | company | story | opportunity | ripple | search
  Query params: title, description, sector
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from app.services.ai_service import generate_pattern_intelligence

router = APIRouter()

_VALID_TYPES = {"event", "company", "story", "opportunity", "ripple", "search"}


@router.get("/{entity_type}/{entity_id}")
async def get_pattern(
    entity_type: str,
    entity_id: str,
    title: str       = Query(default="", max_length=200),
    description: str = Query(default="", max_length=800),
    sector: str      = Query(default="", max_length=100),
):
    safe_type = entity_type if entity_type in _VALID_TYPES else "event"
    return await generate_pattern_intelligence(
        entity_type=safe_type,
        entity_id=entity_id,
        title=title,
        description=description,
        sector=sector,
    )

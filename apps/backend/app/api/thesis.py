"""
Investment Thesis API — standardised thesis generation for any entity.

GET /api/thesis/{entity_type}/{entity_id}
  entity_type : event | company | story | opportunity | ripple | search
  entity_id   : the entity's primary ID or symbol
  Query params: title, description, sector  (provide as much context as possible)

Results are cached 60 minutes so the AI is not called on every page view.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from app.core.limiter import limiter
from app.services.ai_service import generate_investment_thesis

router = APIRouter()

_VALID_TYPES = {"event", "company", "story", "opportunity", "ripple", "search"}


@router.get("/{entity_type}/{entity_id}")
@limiter.limit("20/minute")
async def get_thesis(
    request: Request,
    entity_type: str,
    entity_id: str,
    title: str       = Query(default="", max_length=200),
    description: str = Query(default="", max_length=800),
    sector: str      = Query(default="", max_length=100),
):
    """
    Return a structured InvestmentThesis for any MarketRipple entity.
    The caller provides light context (title, description, sector) as query
    params; the AI generates the full thesis and we cache it 60 minutes.
    """
    safe_type = entity_type if entity_type in _VALID_TYPES else "event"
    return await generate_investment_thesis(
        entity_type=safe_type,
        entity_id=entity_id,
        title=title,
        description=description,
        sector=sector,
    )

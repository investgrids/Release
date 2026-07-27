"""AI Search Follow-up Intelligence click tracking — POST /api/ai/search/followup-click.

Own router (not appended to ai_search.py's), same reasoning as
ai_search_feedback.py / ai_search_refine.py's module docstrings.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.models.ai_search_followup_click import AISearchFollowupClick
from app.db.session import get_db

router = APIRouter()
log = structlog.get_logger(__name__)


class FollowupClickRequest(BaseModel):
    response_id: str = Field(..., min_length=1, max_length=64)
    category: str = Field(..., min_length=1, max_length=32)
    item_text: str = Field(..., min_length=1, max_length=500)
    item_query: str = Field(..., min_length=1, max_length=500)
    position: int | None = None


@router.post("/followup-click")
@limiter.limit("60/minute")
async def track_followup_click(
    request: Request,
    body: FollowupClickRequest,
    db: AsyncSession = Depends(get_db),
):
    """Fire-and-forget click capture — the data half of the Follow-up
    Intelligence spec's "Learning System (Future-ready)" (see
    AISearchFollowupClick's docstring). Never blocks or affects the actual
    navigation the frontend does on click."""
    db.add(AISearchFollowupClick(
        response_id=body.response_id, category=body.category,
        item_text=body.item_text, item_query=body.item_query, position=body.position,
    ))
    await db.commit()
    return {"status": "ok"}

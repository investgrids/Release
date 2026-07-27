"""AI Search V3 feedback — POST /api/ai/search/feedback, GET .../stats.

Split into its own router/module (rather than living in ai_search.py
alongside /search, /search/v3, /search/stream) purely for a practical
reason found live in this dev environment: appending these two routes to
the end of the already-large ai_search router left them unreachable
(404) at request-dispatch time despite being demonstrably present on the
router object at import time — reproducible, isolated via a debug route
dump, and unresolved after eliminating every other suspect (Literal[*...]
typing, decorator order, stale process). A brand-new router sidesteps it
cleanly. Kept as a standing note in case this recurs elsewhere.
"""
from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.models.ai_search_feedback import REASONS, AISearchFeedback
from app.db.session import get_db

router = APIRouter()
log = structlog.get_logger(__name__)


class FeedbackRequest(BaseModel):
    response_id: str = Field(..., min_length=1, max_length=64)
    query:       str = Field(..., min_length=1, max_length=500)
    rating:      Literal["helpful", "not_helpful"]
    reason:      Literal[*REASONS] | None = None
    reason_text: str | None = Field(None, max_length=1000)
    # Delivery context — echoed straight back from what SearchResponseV3 /
    # the SSE "answer" event handed the frontend for this response_id.
    specialist:     str | None = None
    provider:       str | None = None
    cache_hit:      bool | None = None
    latency_ms:     float | None = None
    schema_version: str | None = None


@router.post("/feedback")
@limiter.limit("20/minute")
async def submit_ai_search_feedback(
    request: Request,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """👍/👎 on an AI Search V3 answer — the raw dataset behind Phase 1.5's
    continuous-improvement loop (see AISearchFeedback's docstring)."""
    if body.rating == "not_helpful" and not body.reason:
        raise HTTPException(status_code=400, detail="reason is required when rating is 'not_helpful'.")

    row = AISearchFeedback(
        response_id=body.response_id,
        query=body.query.strip(),
        rating=body.rating,
        reason=body.reason if body.rating == "not_helpful" else None,
        reason_text=(body.reason_text or "").strip()[:1000] or None,
        specialist=body.specialist,
        provider=body.provider,
        cache_hit=body.cache_hit,
        latency_ms=body.latency_ms,
        schema_version=body.schema_version,
    )
    db.add(row)
    await db.commit()
    log.info(
        "ai_search_v3.feedback", rating=body.rating, reason=body.reason,
        response_id=body.response_id, query=body.query[:50],
    )
    return {"status": "ok"}


@router.get("/feedback/stats")
async def ai_search_feedback_stats(db: AsyncSession = Depends(get_db)):
    """Internal aggregate view over the feedback dataset — same "ops
    dashboard" spirit as ai_search.get_search_stats(), so weaknesses can
    be prioritized from real usage instead of guesswork."""
    total_row = (await db.execute(select(func.count()).select_from(AISearchFeedback))).scalar_one()
    if not total_row:
        return {"total": 0, "helpful": 0, "not_helpful": 0, "helpful_rate": None, "by_reason": {}, "by_specialist": {}}

    helpful = (
        await db.execute(select(func.count()).select_from(AISearchFeedback).where(AISearchFeedback.rating == "helpful"))
    ).scalar_one()
    not_helpful = total_row - helpful

    reason_rows = await db.execute(
        select(AISearchFeedback.reason, func.count())
        .where(AISearchFeedback.rating == "not_helpful")
        .group_by(AISearchFeedback.reason)
    )
    by_reason = {r or "unspecified": c for r, c in reason_rows.all()}

    specialist_rows = await db.execute(
        select(AISearchFeedback.specialist, AISearchFeedback.rating, func.count())
        .group_by(AISearchFeedback.specialist, AISearchFeedback.rating)
    )
    by_specialist: dict[str, dict[str, int]] = {}
    for specialist, rating, count in specialist_rows.all():
        by_specialist.setdefault(specialist or "unknown", {"helpful": 0, "not_helpful": 0})[rating] = count

    return {
        "total": total_row,
        "helpful": helpful,
        "not_helpful": not_helpful,
        "helpful_rate": round(helpful / total_row * 100, 1),
        "by_reason": by_reason,
        "by_specialist": by_specialist,
    }

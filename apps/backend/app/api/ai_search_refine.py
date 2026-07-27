"""AI Search V3 Refine Analysis — POST /api/ai/search/refine.

Own router (not appended to ai_search.py's), same reasoning as
ai_search_feedback.py's module docstring: routes appended late to that
particular router became unreachable at request-dispatch time for a
still-unexplained reason in this FastAPI version, and a fresh router
sidesteps it cleanly every time it's recurred.
"""
from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.limiter import limiter
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
log = structlog.get_logger(__name__)


class RefineRequest(BaseModel):
    response_id: str = Field(..., min_length=1, max_length=64)
    horizon: str | None = Field(None, max_length=64)
    risk_tolerance: str | None = Field(None, max_length=64)
    investment_goal: str | None = Field(None, max_length=64)
    portfolio_size: str | None = Field(None, max_length=64)
    style: str | None = Field(None, max_length=64)
    entry_mode: str | None = Field(None, max_length=64)
    holder_status: str | None = Field(None, max_length=64)


class RefineResponse(BaseModel):
    response_id: str
    latency_ms: float
    provider: str | None = None
    investment_verdict: dict
    decision_engine_v2: dict
    ai_conclusion: dict
    synthesis_incomplete: bool


@router.post("/refine", response_model=RefineResponse)
@limiter.limit("15/minute")
async def refine_ai_search(
    request: Request,
    body: RefineRequest,
    db: AsyncSession = Depends(get_db),
):
    """Regenerates ONLY the decision layer for an existing answer against
    its already-gathered real evidence — see specialists/refine.py's
    module docstring. 404s (with a clear reason) rather than silently
    falling back to a generic answer when the snapshot has expired or
    was never cached (a degraded original, or the TTL window passed) —
    the frontend's job in that case is to re-run the full search, not to
    have this endpoint quietly paper over missing evidence."""
    from app.services.ai_search import cache as cache_mod
    from app.services.ai_search.specialists import refine as refine_specialist
    from app.services.ai_search import validation as validation_mod

    snapshot = cache_mod.get_snapshot(body.response_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="This answer's evidence is no longer available to refine (expired or was a degraded response). Please run the search again.",
        )

    params = {
        "horizon": body.horizon, "risk_tolerance": body.risk_tolerance,
        "investment_goal": body.investment_goal, "portfolio_size": body.portfolio_size,
        "style": body.style, "entry_mode": body.entry_mode, "holder_status": body.holder_status,
    }
    log.info("ai_search_v3.refine.request", response_id=body.response_id, params={k: v for k, v in params.items() if v})

    _t0 = time.monotonic()
    parsed, was_degraded = await refine_specialist.run(
        snapshot["query"], snapshot["evidence_context"], snapshot["companies"], snapshot["is_comparison"], params,
    )
    if not was_degraded:
        parsed, _report = validation_mod.validate_and_repair(parsed)
    latency_ms = round((time.monotonic() - _t0) * 1000, 1)

    from app.services.ai_service import _AI_USAGE
    provider = None if was_degraded else _AI_USAGE.get("last_provider")

    import uuid
    new_response_id = str(uuid.uuid4())
    # Same evidence, new decision — the refined answer is a distinct
    # generated analysis (own response_id for feedback purposes) but
    # grounded in identical evidence, so a second refine on top of this
    # one can keep reusing it without re-fetching anything.
    if not was_degraded:
        cache_mod.set_snapshot(new_response_id, snapshot)

    log.info(
        "ai_search_v3.refine.done", latency_ms=latency_ms, degraded=was_degraded,
        response_id=body.response_id, new_response_id=new_response_id,
    )

    return RefineResponse(
        response_id=new_response_id,
        latency_ms=latency_ms,
        provider=provider,
        investment_verdict=parsed.get("investment_verdict", {}),
        decision_engine_v2=parsed.get("decision_engine_v2", {}),
        ai_conclusion=parsed.get("ai_conclusion", {}),
        synthesis_incomplete=was_degraded,
    )

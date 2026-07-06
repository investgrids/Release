"""
Multi-Horizon Investment Outlook API
  POST /api/intelligence/horizon   — generate or retrieve cached analysis
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.multi_horizon_service import generate_multi_horizon, ContextType

log = structlog.get_logger(__name__)
router = APIRouter()


class HorizonRequest(BaseModel):
    type:       ContextType = "query"
    title:      str         = Field(..., min_length=1, max_length=500)
    symbol:     str | None  = None
    context:    str         = ""
    sectors:    list[str]   = []
    context_id: str | None  = None   # stable cache key (e.g. "stock:RELIANCE")


class HorizonResponse(BaseModel):
    type:     str
    title:    str
    symbol:   str | None
    horizons: list[dict]


@router.post("/horizon", response_model=HorizonResponse)
async def get_multi_horizon(body: HorizonRequest) -> HorizonResponse:
    horizons = await generate_multi_horizon(
        context_type=body.type,
        title=body.title,
        symbol=body.symbol,
        context=body.context,
        sectors=body.sectors,
        context_id=body.context_id,
    )
    return HorizonResponse(
        type=body.type,
        title=body.title,
        symbol=body.symbol,
        horizons=horizons,
    )

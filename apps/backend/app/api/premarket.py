"""
Pre-market data endpoint.
Returns Asian, US, and commodity quotes cached for 15 minutes.
Shown on the dashboard before NSE opens (before 9:15 AM IST).
"""
from __future__ import annotations

import asyncio
import structlog
from fastapi import APIRouter

from app.services.market_data import get_premarket_data

router = APIRouter()
log = structlog.get_logger(__name__)


@router.get("/", response_model=dict)
async def get_premarket():
    try:
        data = await asyncio.wait_for(get_premarket_data(), timeout=30.0)
        return data
    except asyncio.TimeoutError:
        log.warning("premarket.timeout")
        return {"asian": [], "us": [], "commodities": []}
    except Exception as exc:
        log.error("premarket.error", exc=str(exc))
        return {"asian": [], "us": [], "commodities": []}

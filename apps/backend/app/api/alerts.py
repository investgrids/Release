"""
Breaking Market Alerts API
- GET  /api/alerts/breaking  — latest high-impact alerts (from Redis or in-memory fallback)
- POST /api/alerts/test      — manually trigger an alert for any headline (for testing)
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.redis import get_redis
from app.services.ai_service import _call_with_fallback

log = structlog.get_logger(__name__)
router = APIRouter()

# ── In-memory fallback when Redis is unavailable ──────────────────────────────
_MEM_ALERTS: list[dict] = []
_REDIS_KEY = "breaking_alerts"

# ── AI prompt ────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a senior Indian equity market analyst. "
    "Respond with valid JSON only. No markdown. No commentary."
)

def _build_prompt(headline: str) -> str:
    return f"""Breaking market news headline: "{headline}"

Analyse the impact on Indian (NSE/BSE) listed stocks and return ONLY this JSON:
{{
  "summary": "2 sentences. What happened and why it matters for Indian markets.",
  "urgency": "critical",
  "sentiment": "bearish",
  "stocks": [
    {{"symbol": "ONGC", "name": "Oil and Natural Gas Corp", "direction": "up", "reason": "Oil price spike benefits upstream", "magnitude": "high"}},
    {{"symbol": "INDIGO", "name": "IndiGo", "direction": "down", "reason": "Jet fuel cost surge", "magnitude": "high"}}
  ],
  "sectors": ["Energy", "Aviation", "Defence"]
}}

Rules:
- stocks: 4 to 6 most affected NSE/BSE listed companies
- direction: "up" or "down" only
- magnitude: "high", "medium", or "low"
- urgency: "critical" if geopolitical/war/major macro, else "high"
- sentiment: "bearish", "bullish", or "mixed"
- Use real NSE ticker symbols (e.g. HDFCBANK, RELIANCE, TATAMOTORS)"""


# ── Core generator ────────────────────────────────────────────────────────────

async def generate_alert(headline: str) -> dict[str, Any]:
    """Call AI and return a structured alert dict."""
    raw = await _call_with_fallback(_build_prompt(headline), _SYSTEM, max_tokens=400)

    # Parse AI JSON
    impact: dict = {}
    if raw:
        try:
            impact = json.loads(raw.strip())
        except Exception:
            # Try extracting JSON from response if wrapped in text
            import re
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    impact = json.loads(m.group())
                except Exception:
                    pass

    return {
        "id": str(uuid4()),
        "headline": headline,
        "summary": impact.get("summary", f"Breaking: {headline}. Monitor market impact closely."),
        "urgency": impact.get("urgency", "high"),
        "sentiment": impact.get("sentiment", "mixed"),
        "stocks": impact.get("stocks", []),
        "sectors": impact.get("sectors", []),
        "source": "AI Analysis",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "query": headline,
    }


async def store_alert(alert: dict) -> None:
    """Push alert to Redis list (or in-memory fallback)."""
    global _MEM_ALERTS
    redis = await get_redis()
    if redis:
        try:
            await redis.lpush(_REDIS_KEY, json.dumps(alert))
            await redis.ltrim(_REDIS_KEY, 0, 19)   # keep latest 20
            await redis.expire(_REDIS_KEY, 7200)    # 2-hour TTL
            return
        except Exception:
            pass
    # In-memory fallback
    _MEM_ALERTS.insert(0, alert)
    _MEM_ALERTS = _MEM_ALERTS[:20]


async def fetch_alerts() -> list[dict]:
    """Return all current alerts from Redis or in-memory."""
    redis = await get_redis()
    if redis:
        try:
            items = await redis.lrange(_REDIS_KEY, 0, 19)
            return [json.loads(i) for i in items]
        except Exception:
            pass
    return list(_MEM_ALERTS)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/breaking")
async def get_breaking_alerts():
    alerts = await fetch_alerts()
    return {"alerts": alerts, "generated_at": datetime.now(timezone.utc).isoformat()}


class TestAlertRequest(BaseModel):
    headline: str


@router.post("/test")
async def trigger_test_alert(body: TestAlertRequest):
    """Manually generate and store a breaking alert — for testing only."""
    if not body.headline or len(body.headline.strip()) < 5:
        raise HTTPException(status_code=422, detail="headline must be at least 5 characters")

    log.info("alerts.test_trigger", headline=body.headline[:80])
    alert = await generate_alert(body.headline)
    await store_alert(alert)
    log.info("alerts.test_stored", alert_id=alert["id"])
    return {"ok": True, "alert": alert}


@router.delete("/clear")
async def clear_alerts():
    """Clear all alerts — for testing."""
    global _MEM_ALERTS
    _MEM_ALERTS = []
    redis = await get_redis()
    if redis:
        try:
            await redis.delete(_REDIS_KEY)
        except Exception:
            pass
    return {"ok": True}

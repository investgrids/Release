"""
Scenario Analysis API — Bull / Base / Bear AI scenarios for any entity.

GET /api/scenario/{entity_type}/{entity_id}
  entity_type : event | company | story | opportunity | ripple | search
  Query params: title, description, sector

P0-CD3-C follow-up (2026-09-03) — narrow containment patch, not the
broader confidence-semantics work. generate_scenario_analysis()'s own
`degraded: True` fallback (identical templated boilerplate for every
entity -- e.g. "Strong performance for {title} driven by favourable
macro conditions... 25-40% returns") is correctly filtered by the
consolidated Deep Research path (event_deep_research_service.py checks
`degraded` before using the result) but this standalone route used to
return the raw dict unfiltered -- full fallback bull/base/bear content
included -- to ScenarioAnalysis.tsx, which only checked whether those
keys existed (true for both real and fallback content). Confirmed real,
non-hypothetical firing conditions: the exact provider-exhaustion
condition that triggers this fallback was observed live the day before
this fix.

Public contract: never send fallback/templated scenario content and
expect the frontend to remember not to display it. bull/base/bear are
null whenever content isn't genuinely generated for this entity -- there
is nothing left for a consumer to accidentally render.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from app.core.limiter import limiter
from app.services.ai_service import generate_scenario_analysis

router = APIRouter()

_VALID_TYPES = {"event", "company", "story", "opportunity", "ripple", "search"}


def _to_public_contract(raw: dict) -> dict:
    """Available only when the content is genuinely generated for this
    entity: not degraded, and bull/base/bear all present. Any other
    shape (degraded, a partial/empty dict from total provider failure,
    a missing key) reports unavailable with bull/base/bear explicitly
    nulled -- not just labeled, so a consumer that ignores the status
    fields still gets nothing to render."""
    degraded = bool(raw.get("degraded"))
    has_all = bool(raw.get("bull") and raw.get("base") and raw.get("bear"))
    available = has_all and not degraded

    if available:
        return {
            "status": "available",
            "provenance": "generated",
            "degraded": False,
            "bull": raw["bull"],
            "base": raw["base"],
            "bear": raw["bear"],
            "last_updated": raw.get("last_updated"),
        }
    return {
        "status": "unavailable",
        "provenance": "fallback" if degraded else "unavailable",
        "degraded": degraded,
        "bull": None,
        "base": None,
        "bear": None,
        "last_updated": raw.get("last_updated"),
    }


@router.get("/{entity_type}/{entity_id}")
@limiter.limit("20/minute")
async def get_scenario(
    request: Request,
    entity_type: str,
    entity_id: str,
    title: str       = Query(default="", max_length=200),
    description: str = Query(default="", max_length=800),
    sector: str      = Query(default="", max_length=100),
):
    safe_type = entity_type if entity_type in _VALID_TYPES else "event"
    raw = await generate_scenario_analysis(
        entity_type=safe_type,
        entity_id=entity_id,
        title=title,
        description=description,
        sector=sector,
        priority="interactive",
    )
    return _to_public_contract(raw)

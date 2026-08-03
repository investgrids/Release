"""
Related Content API
GET /api/related/{entity_type}/{entity_id}

Returns related entities of different types for any given entity.
Used by the RelatedContent frontend component to power "Related Intelligence" sections.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db import models_legacy as models

router = APIRouter()

_VALID_TYPES = {"event", "company", "story", "opportunity", "ripple", "search", "comparison"}


def _sector_match(sectors_a: list[str], sector_b: str | None) -> bool:
    """True if sector_b appears in sectors_a (case-insensitive)."""
    if not sector_b or not sectors_a:
        return False
    b_lower = sector_b.lower()
    return any(b_lower in s.lower() or s.lower() in b_lower for s in sectors_a)


def _extract_sectors(row_sectors) -> list[str]:
    """Safely extract sector names from the JSON field."""
    if not row_sectors:
        return []
    result = []
    for s in row_sectors:
        if isinstance(s, str):
            result.append(s)
        elif isinstance(s, dict):
            result.append(s.get("sector") or s.get("name") or "")
    return [x for x in result if x]


async def _recent_events(db: AsyncSession, limit: int, exclude_id: str = "", sector: str = "") -> list[dict[str, Any]]:
    rows = await db.execute(
        select(models.Event)
        .order_by(models.Event.impact_score.desc())
        .limit(limit * 3)  # over-fetch for sector filtering
    )
    items = []
    for r in rows.scalars().all():
        if r.id == exclude_id:
            continue
        if sector and not _sector_match(_extract_sectors(r.sectors), sector):
            continue
        items.append({
            "id":    r.id,
            "title": r.title,
            "href":  f"/events/{r.id}",
            "score": round(float(r.impact_score or 0)),
        })
        if len(items) >= limit:
            break
    return items


async def _recent_opportunities(db: AsyncSession, limit: int, sector: str = "") -> list[dict[str, Any]]:
    """Real Opportunity rows (app.db.models.opportunity.Opportunity — 40
    live rows), not the legacy RadarOpportunity model this used to read
    from (5 stale seed rows, linking to /radar/{id} which itself
    301-redirects to /opportunity-radar/{id}) — found live while fixing
    RelatedContent's SSR conversion. This endpoint also used to surface a
    "stories" group from the confirmed-dead Story model (see the SEO/Growth
    audit's Critical Finding #3), linking to /stories/{id} — another
    redirecting dead end — removed entirely rather than relabeled."""
    from app.db.models.opportunity import Opportunity

    rows = await db.execute(
        select(Opportunity).order_by(Opportunity.opportunity_score.desc()).limit(limit * 3)
    )
    items = []
    for r in rows.scalars().all():
        if sector and not _sector_match(r.sectors or [], sector):
            continue
        items.append({"id": str(r.id), "title": r.title, "href": f"/opportunity-radar/{r.id}", "score": round(r.opportunity_score or 0)})
        if len(items) >= limit:
            break
    return items


@router.get("/{entity_type}/{entity_id}")
async def get_related(
    entity_type: str,
    entity_id:   str,
    title:       str = Query(""),
    sector:      str = Query(""),
    db:          AsyncSession = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    """
    Returns related content grouped by type.
    All groups are best-effort; missing data returns empty lists, never 404.
    """
    if entity_type not in _VALID_TYPES:
        entity_type = "event"

    result: dict[str, list[dict[str, Any]]] = {}

    if entity_type == "event":
        result["events"]        = await _recent_events(db, 5, exclude_id=entity_id, sector=sector)
        result["opportunities"] = await _recent_opportunities(db, 4)

    elif entity_type == "company":
        # Events mentioning this company symbol
        rows = await db.execute(
            select(models.Event).order_by(models.Event.impact_score.desc()).limit(30)
        )
        company_events = []
        sym_lower = entity_id.lower()
        for r in rows.scalars().all():
            companies = r.companies or []
            mentions = any(
                (c.get("symbol", "").lower() == sym_lower if isinstance(c, dict) else c.lower() == sym_lower)
                for c in companies
            )
            if mentions:
                company_events.append({"id": r.id, "title": r.title, "href": f"/events/{r.id}", "score": round(float(r.impact_score or 0))})
            if len(company_events) >= 5:
                break
        if not company_events:
            company_events = await _recent_events(db, 4, sector=sector)
        result["events"]        = company_events
        result["opportunities"] = await _recent_opportunities(db, 4)

    elif entity_type == "opportunity":
        result["events"]        = await _recent_events(db, 5, sector=sector)

    elif entity_type == "ripple":
        result["events"]        = await _recent_events(db, 5, exclude_id=entity_id, sector=sector)
        result["opportunities"] = await _recent_opportunities(db, 4)

    elif entity_type == "search":
        result["events"]        = await _recent_events(db, 5)
        result["opportunities"] = await _recent_opportunities(db, 5)

    elif entity_type == "comparison":
        # Comparison research pages (/research/{slug}) had NO related-
        # content section at all before this — a confirmed orphan-risk
        # page type (SEO audit's Part 8/Stage 4 "no orphan pages" finding).
        # Reuses the same real event/opportunity lookups every other
        # entity type already uses; no new data source.
        result["events"]        = await _recent_events(db, 5, sector=sector)
        result["opportunities"] = await _recent_opportunities(db, 4, sector=sector)

    return result

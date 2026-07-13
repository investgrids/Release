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

_VALID_TYPES = {"event", "company", "story", "opportunity", "ripple", "search"}


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


async def _recent_stories(db: AsyncSession, limit: int) -> list[dict[str, Any]]:
    rows = await db.execute(select(models.Story).limit(limit))
    return [
        {"id": r.id, "title": r.title, "href": f"/stories/{r.id}"}
        for r in rows.scalars().all()
    ]


async def _recent_opportunities(db: AsyncSession, limit: int, sector: str = "") -> list[dict[str, Any]]:
    rows = await db.execute(
        select(models.RadarOpportunity).order_by(models.RadarOpportunity.score.desc()).limit(limit)
    )
    return [
        {"id": str(r.id), "title": r.theme, "href": f"/radar/{r.id}", "score": r.score}
        for r in rows.scalars().all()
    ]


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
        result["stories"]       = await _recent_stories(db, 4)
        result["opportunities"] = await _recent_opportunities(db, 3)

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
        result["stories"]       = await _recent_stories(db, 4)
        result["opportunities"] = await _recent_opportunities(db, 3)

    elif entity_type == "story":
        result["events"]        = await _recent_events(db, 5, sector=sector)
        result["opportunities"] = await _recent_opportunities(db, 4)

    elif entity_type == "opportunity":
        result["events"]        = await _recent_events(db, 5, sector=sector)
        result["stories"]       = await _recent_stories(db, 4)

    elif entity_type == "ripple":
        result["events"]        = await _recent_events(db, 5, exclude_id=entity_id, sector=sector)
        result["opportunities"] = await _recent_opportunities(db, 3)
        result["stories"]       = await _recent_stories(db, 3)

    elif entity_type == "search":
        result["events"]        = await _recent_events(db, 5)
        result["opportunities"] = await _recent_opportunities(db, 4)
        result["stories"]       = await _recent_stories(db, 3)

    return result

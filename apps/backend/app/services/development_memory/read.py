"""
Development Memory — generic structured read-path (2026-08 Pre-Market
rebuild, Part A2).

ai_search_context.py's build_development_context() is symbol-scoped and
returns pre-formatted prose for LLM prompt injection — nothing until now
returned structured, filterable, ranked Development rows a UI could render
directly. This module is that missing read path, kept consumer-agnostic
(Pre-Market is the first caller, not the only intended one).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.services.development_memory.graph_link import is_graph_worthy

_TIER_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _tier_rank(tier: str | None) -> int:
    return _TIER_RANK.get((tier or "").strip().lower(), 0)


async def list_active_developments(
    db: AsyncSession,
    sectors: list[str] | None = None,
    since: datetime | None = None,
    limit: int = 8,
    order: str = "importance",
) -> list[dict[str, Any]]:
    """Open Developments, filtered/ranked for direct UI consumption.

    order="importance" (default) ranks by current_impact_tier ->
    current_confidence -> evidence_count -> last_observed_at, all
    descending — plain recency would let a low-importance filing outrank
    a major RBI/policy development just for being newer. order="recency"
    (plain last_observed_at desc) is kept for other future callers that
    genuinely want "newest first"; this function is intentionally generic,
    not Pre-Market-specific.

    Only returns Developments passing is_graph_worthy() (corroboration OR
    materiality) — the same bar ai_search_context.py already applies
    before surfacing a Development in a user-facing answer. A single
    stray low-value evidence row should not appear as a prominent
    "development that matters" here either.
    """
    stmt = select(Development).where(Development.status == "open")
    if since is not None:
        stmt = stmt.where(Development.last_observed_at >= since)

    wanted = {s.strip().lower() for s in sectors if s and s.strip()} if sectors else None

    # Over-fetch before the sector/is_graph_worthy filters (both applied in
    # Python — `sectors` is a JSON column, not overlap-indexable in SQLite;
    # is_graph_worthy needs a DB round-trip per row) so `limit` still gets
    # filled after filtering, not before.
    candidates = (await db.execute(
        stmt.order_by(Development.last_observed_at.desc()).limit(max(limit * 4, 40))
    )).scalars().all()

    rows: list[dict[str, Any]] = []
    for dev in candidates:
        if wanted is not None:
            dev_sectors = {str(s).strip().lower() for s in (dev.sectors or [])}
            if not (dev_sectors & wanted):
                continue
        if not await is_graph_worthy(db, dev):
            continue
        rows.append({
            "id":               dev.id,
            "title":            dev.canonical_title,
            "sectors":          dev.sectors or [],
            "companies":        dev.companies or [],
            "direction":        dev.current_direction or dev.formation_direction,
            "confidence":       dev.current_confidence,
            "impact_tier":      dev.current_impact_tier or dev.formation_impact_tier,
            "evidence_count":   dev.evidence_count,
            "last_observed_at": dev.last_observed_at.isoformat() if dev.last_observed_at else None,
        })

    if order == "recency":
        rows.sort(key=lambda r: r["last_observed_at"] or "", reverse=True)
    else:
        rows.sort(
            key=lambda r: (
                _tier_rank(r["impact_tier"]),
                r["confidence"] or 0.0,
                r["evidence_count"] or 0,
                r["last_observed_at"] or "",
            ),
            reverse=True,
        )
    return rows[:limit]

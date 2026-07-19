"""
OpportunityService — aggregates all repository data into a single DTO.
No AI inference happens here. Reads only pre-computed PostgreSQL data.
"""
from __future__ import annotations

import asyncio
import json
import structlog
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.core.config import settings
from app.repositories.opportunity_repository import OpportunityRepository
from app.schemas.opportunity_detail import (
    AISummarySchema,
    CompanySchema,
    EventSchema,
    GraphEdgeSchema,
    GraphNodeSchema,
    MetricSchema,
    NewsSchema,
    OpportunityDetailResponse,
    OpportunityListItem,
    PaginatedOpportunities,
    SectorDistSchema,
    TimelineStepSchema,
)

logger = structlog.get_logger(__name__)

_CACHE_KEY = "opportunity:detail:{id}"
_LIST_CACHE_KEY = "opportunity:list:p{page}:s{size}"


class OpportunityService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = OpportunityRepository(db)

    # ── Public API ────────────────────────────────────────────────────────────

    async def list_by_sector_or_theme(self, terms: list[str], limit: int = 10) -> list[dict]:
        """Lightweight summaries for sector/theme-scoped queries — no nested-join DTO needed here."""
        opps = await self._repo.list_by_sector_or_theme(terms, limit)
        return [
            {
                "id": o.id, "slug": o.slug, "title": o.title, "summary": o.summary,
                "opportunity_score": o.opportunity_score, "confidence": o.confidence,
                "trend": o.trend, "risk_level": o.risk_level, "sectors": o.sectors or [],
            }
            for o in opps
        ]

    async def get_opportunity_details(
        self, opportunity_id: int
    ) -> Optional[OpportunityDetailResponse]:
        cache_key = _CACHE_KEY.format(id=opportunity_id)

        cached = await cache_get(cache_key)
        if cached:
            logger.debug("Cache hit: %s", cache_key)
            return OpportunityDetailResponse(**cached)

        opp = await self._repo.get_by_id(opportunity_id)
        if opp is None:
            return None

        # Fetch all related data concurrently
        (
            metrics,
            events,
            companies,
            news,
            timeline,
            sector_dist,
            (nodes, edges),
        ) = await asyncio.gather(
            self._repo.get_metrics(opportunity_id),
            self._repo.get_events(opportunity_id),
            self._repo.get_companies(opportunity_id),
            self._repo.get_news(opportunity_id),
            self._repo.get_timeline(opportunity_id),
            self._repo.get_sector_distribution(opportunity_id),
            self._repo.get_graph(opportunity_id),
        )

        ai_raw = opp.ai_summary or {}
        if isinstance(ai_raw, str):
            try:
                ai_raw = json.loads(ai_raw)
            except Exception:
                ai_raw = {}

        response = OpportunityDetailResponse(
            id=opp.id,
            slug=opp.slug,
            title=opp.title,
            summary=opp.summary,
            opportunity_score=opp.opportunity_score,
            confidence=opp.confidence,
            trend=opp.trend,
            risk_level=opp.risk_level,
            time_horizon=opp.time_horizon,
            sectors=opp.sectors or [],
            ai_summary=AISummarySchema(
                matters=ai_raw.get("matters", ""),
                benefits=ai_raw.get("benefits", ""),
                risks=ai_raw.get("risks", []),
                invalidate=ai_raw.get("invalidate", ""),
                why_bullets=ai_raw.get("why_bullets", []),
            ) if ai_raw else None,
            metrics=MetricSchema(
                revenue_potential=metrics.revenue_potential,
                expected_cagr=metrics.expected_cagr,
                eps_growth=metrics.eps_growth,
                investment_cycle=metrics.investment_cycle,
                market_size=metrics.market_size,
            ) if metrics else None,
            timeline=[
                TimelineStepSchema(
                    order=t.order,
                    phase=t.phase,
                    date_label=t.date_label,
                    title=t.title,
                    description=t.description,
                    status=t.status,
                )
                for t in timeline
            ],
            events=[
                EventSchema(
                    event_id=e.event_id,
                    title=e.title,
                    event_date=e.event_date,
                    tag=e.tag,
                    description=e.description,
                    importance=e.importance,
                )
                for e in events
            ],
            companies=[
                CompanySchema(
                    symbol=c.company_id,
                    company_name=c.company_name,
                    impact_score=c.impact_score,
                    impact_label=c.impact_label,
                    trend=c.trend,
                    confidence=c.confidence,
                    reason=c.reason,
                )
                for c in companies
            ],
            news=[
                NewsSchema(
                    news_id=n.news_id,
                    headline=n.headline,
                    source=n.source,
                    published_at=n.published_at,
                    url=n.url,
                )
                for n in news
            ],
            sector_distribution=[
                SectorDistSchema(
                    sector=s.sector,
                    percentage=s.percentage,
                    color=s.color,
                )
                for s in sector_dist
            ],
            graph_nodes=[
                GraphNodeSchema(
                    node_id=n.node_id,
                    label=n.label,
                    node_type=n.node_type,
                    metadata=n.node_metadata or {},
                )
                for n in nodes
            ],
            graph_edges=[
                GraphEdgeSchema(
                    source=e.source,
                    target=e.target,
                    relationship=e.edge_relationship,
                )
                for e in edges
            ],
        )

        await cache_set(
            cache_key,
            response.model_dump(),
            ttl=settings.redis_ttl_opportunity,
        )
        return response

    async def list_opportunities(
        self, page: int = 1, page_size: int = 20
    ) -> PaginatedOpportunities:
        cache_key = _LIST_CACHE_KEY.format(page=page, size=page_size)
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedOpportunities(**cached)

        items, total = await self._repo.list_opportunities(page, page_size)

        # Deduplicate by normalized title
        import re
        seen: set[str] = set()
        deduped: list = []
        for o in items:
            key = re.sub(r'\s+', ' ', o.title.lower().strip())[:60]
            if key not in seen:
                seen.add(key)
                deduped.append(o)
        items = deduped
        total = len(deduped)

        # Fetch company + event counts
        ids = [o.id for o in items]
        company_counts, event_counts = await asyncio.gather(
            self._repo.get_company_counts(ids),
            self._repo.get_event_counts(ids),
        )

        pages = max(1, (total + page_size - 1) // page_size)

        result = PaginatedOpportunities(
            items=[
                OpportunityListItem(
                    id=o.id,
                    slug=o.slug,
                    title=o.title,
                    summary=o.summary,
                    opportunity_score=o.opportunity_score,
                    confidence=o.confidence,
                    trend=o.trend,
                    risk_level=o.risk_level,
                    time_horizon=o.time_horizon,
                    sectors=o.sectors or [],
                    company_count=company_counts.get(o.id, 0),
                    event_count=event_counts.get(o.id, 0),
                )
                for o in items
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
        await cache_set(cache_key, result.model_dump(), ttl=300)  # 5-min cache
        return result


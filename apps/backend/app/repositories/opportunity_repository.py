"""
OpportunityRepository — all DB reads for the Opportunity Details page.
Single responsibility: query, never transform business logic.
"""
from __future__ import annotations

import structlog
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.opportunity import (
    Opportunity,
    OpportunityCompany,
    OpportunityEvent,
    OpportunityGraphEdge,
    OpportunityGraphNode,
    OpportunityMetric,
    OpportunityNews,
    OpportunitySectorDistribution,
    OpportunityTimeline,
)

logger = structlog.get_logger(__name__)


class OpportunityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Core ─────────────────────────────────────────────────────────────────

    async def get_by_id(self, opportunity_id: int) -> Optional[Opportunity]:
        result = await self._db.execute(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Opportunity]:
        result = await self._db.execute(
            select(Opportunity).where(Opportunity.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_opportunities(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Opportunity], int]:
        offset = (page - 1) * page_size
        count_q = await self._db.execute(select(func.count()).select_from(Opportunity))
        total = count_q.scalar_one()
        rows_q = await self._db.execute(
            select(Opportunity)
            .order_by(Opportunity.opportunity_score.desc())
            .offset(offset)
            .limit(page_size)
        )
        return rows_q.scalars().all(), total

    async def list_by_sector_or_theme(
        self, terms: list[str], limit: int = 10
    ) -> list[Opportunity]:
        """
        Opportunities whose `sectors` JSON list contains any of `terms`
        (case-insensitive) or whose title mentions one. `sectors` is stored
        as a plain JSON list of strings on SQLite, which doesn't offer a
        portable JSON-containment operator the way Postgres JSONB does — so
        this filters in Python over a bounded, score-ordered candidate pool
        rather than relying on a DB-side JSON query.
        """
        if not terms:
            return []
        terms_lower = [t.lower() for t in terms]
        # Title matching is a plain substring test, so short/common terms
        # produce false positives regardless of what the caller passed in —
        # found live: an unfiltered "me" (from "give ME top 5...") matched
        # inside every "X Invest-ME-nt Opportunity" title. The sector match
        # above is list-membership (exact equality against a known short
        # list of real sector names), not substring, so it's unaffected and
        # stays open to short terms like "IT". Only gate the title branch,
        # and gate it here so every caller is protected, not just the one
        # that already learned to pre-filter its terms.
        title_terms = [t for t in terms_lower if len(t) >= 4]
        candidates_q = await self._db.execute(
            select(Opportunity).order_by(Opportunity.opportunity_score.desc()).limit(200)
        )
        candidates = candidates_q.scalars().all()

        def _matches(opp: Opportunity) -> bool:
            opp_sectors = [str(s).lower() for s in (opp.sectors or [])]
            if any(t in opp_sectors for t in terms_lower):
                return True
            title_lower = (opp.title or "").lower()
            return any(t in title_lower for t in title_terms)

        return [o for o in candidates if _matches(o)][:limit]

    async def get_company_counts(self, ids: list[int]) -> dict[int, int]:
        from sqlalchemy import func
        if not ids:
            return {}
        result = await self._db.execute(
            select(OpportunityCompany.opportunity_id, func.count(OpportunityCompany.id).label("cnt"))
            .where(OpportunityCompany.opportunity_id.in_(ids))
            .group_by(OpportunityCompany.opportunity_id)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_event_counts(self, ids: list[int]) -> dict[int, int]:
        from sqlalchemy import func
        if not ids:
            return {}
        result = await self._db.execute(
            select(OpportunityEvent.opportunity_id, func.count(OpportunityEvent.id).label("cnt"))
            .where(OpportunityEvent.opportunity_id.in_(ids))
            .group_by(OpportunityEvent.opportunity_id)
        )
        return {row[0]: row[1] for row in result.all()}


    # ── Related data ─────────────────────────────────────────────────────────

    async def get_metrics(self, opportunity_id: int) -> Optional[OpportunityMetric]:
        result = await self._db.execute(
            select(OpportunityMetric).where(
                OpportunityMetric.opportunity_id == opportunity_id
            )
        )
        return result.scalar_one_or_none()

    async def get_events(
        self, opportunity_id: int, limit: int = 10
    ) -> list[OpportunityEvent]:
        result = await self._db.execute(
            select(OpportunityEvent)
            .where(OpportunityEvent.opportunity_id == opportunity_id)
            .order_by(OpportunityEvent.importance.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_companies(
        self, opportunity_id: int, limit: int = 10
    ) -> list[OpportunityCompany]:
        result = await self._db.execute(
            select(OpportunityCompany)
            .where(OpportunityCompany.opportunity_id == opportunity_id)
            .order_by(OpportunityCompany.impact_score.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_news(
        self, opportunity_id: int, limit: int = 5
    ) -> list[OpportunityNews]:
        result = await self._db.execute(
            select(OpportunityNews)
            .where(OpportunityNews.opportunity_id == opportunity_id)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_timeline(
        self, opportunity_id: int
    ) -> list[OpportunityTimeline]:
        result = await self._db.execute(
            select(OpportunityTimeline)
            .where(OpportunityTimeline.opportunity_id == opportunity_id)
            .order_by(OpportunityTimeline.order)
        )
        return result.scalars().all()

    async def get_sector_distribution(
        self, opportunity_id: int
    ) -> list[OpportunitySectorDistribution]:
        result = await self._db.execute(
            select(OpportunitySectorDistribution)
            .where(OpportunitySectorDistribution.opportunity_id == opportunity_id)
            .order_by(OpportunitySectorDistribution.percentage.desc())
        )
        return result.scalars().all()

    async def get_graph(
        self, opportunity_id: int
    ) -> tuple[list[OpportunityGraphNode], list[OpportunityGraphEdge]]:
        nodes_q = await self._db.execute(
            select(OpportunityGraphNode).where(
                OpportunityGraphNode.opportunity_id == opportunity_id
            )
        )
        edges_q = await self._db.execute(
            select(OpportunityGraphEdge).where(
                OpportunityGraphEdge.opportunity_id == opportunity_id
            )
        )
        return nodes_q.scalars().all(), edges_q.scalars().all()

    # ── Writes (used by workers) ──────────────────────────────────────────────

    async def upsert_opportunity(self, data: dict) -> Opportunity:
        slug = data["slug"]
        existing = await self.get_by_slug(slug)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            opp = existing
        else:
            opp = Opportunity(**data)
            self._db.add(opp)
        await self._db.flush()
        return opp

    async def replace_metrics(self, opportunity_id: int, data: dict) -> None:
        existing = await self.get_metrics(opportunity_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            self._db.add(OpportunityMetric(opportunity_id=opportunity_id, **data))

    async def replace_timeline(
        self, opportunity_id: int, steps: list[dict]
    ) -> None:
        await self._db.execute(
            OpportunityTimeline.__table__.delete().where(
                OpportunityTimeline.opportunity_id == opportunity_id
            )
        )
        for step in steps:
            self._db.add(OpportunityTimeline(opportunity_id=opportunity_id, **step))

    async def replace_companies(
        self, opportunity_id: int, companies: list[dict]
    ) -> None:
        await self._db.execute(
            OpportunityCompany.__table__.delete().where(
                OpportunityCompany.opportunity_id == opportunity_id
            )
        )
        for c in companies:
            self._db.add(OpportunityCompany(opportunity_id=opportunity_id, **c))

    async def replace_sector_distribution(
        self, opportunity_id: int, sectors: list[dict]
    ) -> None:
        await self._db.execute(
            OpportunitySectorDistribution.__table__.delete().where(
                OpportunitySectorDistribution.opportunity_id == opportunity_id
            )
        )
        for s in sectors:
            self._db.add(
                OpportunitySectorDistribution(opportunity_id=opportunity_id, **s)
            )

    async def replace_graph(
        self, opportunity_id: int, nodes: list[dict], edges: list[dict]
    ) -> None:
        await self._db.execute(
            OpportunityGraphNode.__table__.delete().where(
                OpportunityGraphNode.opportunity_id == opportunity_id
            )
        )
        await self._db.execute(
            OpportunityGraphEdge.__table__.delete().where(
                OpportunityGraphEdge.opportunity_id == opportunity_id
            )
        )
        for n in nodes:
            self._db.add(OpportunityGraphNode(opportunity_id=opportunity_id, **n))
        for e in edges:
            self._db.add(OpportunityGraphEdge(opportunity_id=opportunity_id, **e))

    async def add_news_links(
        self, opportunity_id: int, news_items: list[dict]
    ) -> None:
        for item in news_items:
            self._db.add(OpportunityNews(opportunity_id=opportunity_id, **item))

    async def add_event_links(
        self, opportunity_id: int, events: list[dict]
    ) -> None:
        from sqlalchemy import select as _select
        for item in events:
            existing = await self._db.execute(
                _select(OpportunityEvent.id).where(
                    OpportunityEvent.opportunity_id == opportunity_id,
                    OpportunityEvent.event_id == item.get("event_id", ""),
                )
            )
            if existing.scalar_one_or_none() is None:
                self._db.add(OpportunityEvent(opportunity_id=opportunity_id, **item))


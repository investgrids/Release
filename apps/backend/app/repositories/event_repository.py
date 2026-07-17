"""
EventRepository â€” single responsibility: all database I/O for event detail data.
No business logic, no AI calls, no transformations beyond raw ORM queries.
"""
from __future__ import annotations

import structlog
from typing import Optional

from sqlalchemy import select, update, or_, String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import (
    Event,
    EventCompany,
    EventGraphEdge,
    EventGraphNode,
    EventNews,
    EventPolicy,
    EventSector,
    EventSimilar,
    EventTimeline,
)

logger = structlog.get_logger(__name__)


class EventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # â”€â”€ Core reads â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def get_by_id(self, event_id: str) -> Optional[Event]:
        result = await self._db.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Event]:
        result = await self._db.execute(
            select(Event).where(Event.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_pending_enrichment(self, limit: int = 10) -> list[Event]:
        result = await self._db.execute(
            select(Event)
            .where(Event.enrichment_status == "pending")
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed_enrichment(self, limit: int = 5) -> list[Event]:
        result = await self._db.execute(
            select(Event)
            .where(Event.enrichment_status == "failed")
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_similar_by_sectors(
        self, sectors: list[str], exclude_id: str, limit: int = 10
    ) -> list[Event]:
        """Keyword-based candidate lookup; AI will rank afterward."""
        if not sectors:
            return []
        conditions = [cast(Event.sectors, String).ilike(f"%{s}%") for s in sectors]
        result = await self._db.execute(
            select(Event)
            .where(Event.id != exclude_id)
            .where(Event.enrichment_status == "done")
            .where(or_(*conditions))
            .order_by(Event.impact_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # â”€â”€ Related data reads â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def get_companies(self, event_id: str) -> list[EventCompany]:
        result = await self._db.execute(
            select(EventCompany)
            .where(EventCompany.event_id == event_id)
            .order_by(EventCompany.impact_score.desc())
        )
        return list(result.scalars().all())

    async def get_sectors(self, event_id: str) -> list[EventSector]:
        result = await self._db.execute(
            select(EventSector).where(EventSector.event_id == event_id)
        )
        return list(result.scalars().all())

    async def get_timeline(self, event_id: str) -> list[EventTimeline]:
        result = await self._db.execute(
            select(EventTimeline)
            .where(EventTimeline.event_id == event_id)
            .order_by(EventTimeline.order)
        )
        return list(result.scalars().all())

    async def get_news_links(self, event_id: str, limit: int = 10) -> list[EventNews]:
        result = await self._db.execute(
            select(EventNews)
            .where(EventNews.event_id == event_id)
            .order_by(EventNews.relevance_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_graph(
        self, event_id: str
    ) -> tuple[list[EventGraphNode], list[EventGraphEdge]]:
        nodes = await self._db.execute(
            select(EventGraphNode).where(EventGraphNode.event_id == event_id)
        )
        edges = await self._db.execute(
            select(EventGraphEdge).where(EventGraphEdge.event_id == event_id)
        )
        return list(nodes.scalars().all()), list(edges.scalars().all())

    async def get_similar_events(self, event_id: str) -> list[EventSimilar]:
        result = await self._db.execute(
            select(EventSimilar)
            .where(EventSimilar.event_id == event_id)
            .order_by(EventSimilar.similarity_score.desc())
        )
        return list(result.scalars().all())

    async def get_policy_links(self, event_id: str) -> list[EventPolicy]:
        result = await self._db.execute(
            select(EventPolicy).where(EventPolicy.event_id == event_id)
        )
        return list(result.scalars().all())

    async def get_events_by_ids(self, ids: list[str]) -> list[Event]:
        if not ids:
            return []
        result = await self._db.execute(
            select(Event).where(Event.id.in_(ids))
        )
        return list(result.scalars().all())

    # â”€â”€ Status updates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def mark_status(self, event_id: str, status: str) -> None:
        await self._db.execute(
            update(Event).where(Event.id == event_id).values(enrichment_status=status)
        )
        await self._db.commit()

    async def update_core_fields(self, event_id: str, data: dict) -> None:
        await self._db.execute(
            update(Event).where(Event.id == event_id).values(**data)
        )

    async def update_company_score(self, event_id: str, symbol: str, impact_score: Optional[float]) -> None:
        """
        Patch a single event-company row's impact_score in place — unlike
        replace_companies(), this doesn't touch the other companies on the
        same event, so the enrichment worker can update just the top-impact
        symbols it actually fetched live data for.
        """
        await self._db.execute(
            update(EventCompany)
            .where(EventCompany.event_id == event_id, EventCompany.symbol == symbol)
            .values(impact_score=impact_score)
        )

    # â”€â”€ Writes (pipeline) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def replace_companies(self, event_id: str, items: list[dict]) -> None:
        await self._db.execute(
            EventCompany.__table__.delete().where(EventCompany.event_id == event_id)
        )
        for item in items:
            self._db.add(EventCompany(event_id=event_id, **item))

    async def replace_sectors(self, event_id: str, items: list[dict]) -> None:
        await self._db.execute(
            EventSector.__table__.delete().where(EventSector.event_id == event_id)
        )
        for item in items:
            self._db.add(EventSector(event_id=event_id, **item))

    async def replace_timeline(self, event_id: str, steps: list[dict]) -> None:
        await self._db.execute(
            EventTimeline.__table__.delete().where(EventTimeline.event_id == event_id)
        )
        for step in steps:
            self._db.add(EventTimeline(event_id=event_id, **step))

    async def replace_graph(
        self, event_id: str, nodes: list[dict], edges: list[dict]
    ) -> None:
        await self._db.execute(
            EventGraphNode.__table__.delete().where(EventGraphNode.event_id == event_id)
        )
        await self._db.execute(
            EventGraphEdge.__table__.delete().where(EventGraphEdge.event_id == event_id)
        )
        for n in nodes:
            self._db.add(EventGraphNode(event_id=event_id, **n))
        for e in edges:
            self._db.add(EventGraphEdge(event_id=event_id, **e))

    async def add_news_links(self, event_id: str, items: list[dict]) -> None:
        for item in items:
            existing = await self._db.execute(
                select(EventNews.id).where(
                    EventNews.event_id == event_id,
                    EventNews.news_id == item["news_id"],
                )
            )
            if existing.scalar_one_or_none() is None:
                self._db.add(EventNews(event_id=event_id, **item))

    async def replace_similar(self, event_id: str, items: list[dict]) -> None:
        await self._db.execute(
            EventSimilar.__table__.delete().where(EventSimilar.event_id == event_id)
        )
        for item in items:
            self._db.add(EventSimilar(event_id=event_id, **item))

    async def replace_policies(
        self, event_id: str, policy_ids: list[int], relevances: list[str]
    ) -> None:
        await self._db.execute(
            EventPolicy.__table__.delete().where(EventPolicy.event_id == event_id)
        )
        for pid, rel in zip(policy_ids, relevances):
            self._db.add(EventPolicy(event_id=event_id, policy_id=pid, relevance=rel))


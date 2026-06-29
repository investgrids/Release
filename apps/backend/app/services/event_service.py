"""
EventService â€” aggregates all event-related repository calls into a single
fully-populated API response. Handles Redis caching at the service boundary.
"""
from __future__ import annotations

import asyncio
import structlog
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_get, cache_set
from app.db.models.event import Event
from app.db.models_legacy import NewsArticle
from app.repositories.event_repository import EventRepository
from app.repositories.government_policy_repository import GovernmentPolicyRepository

logger = structlog.get_logger(__name__)

_CACHE_TTL = 900  # 15 minutes â€” matches the user's spec


class EventService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._events = EventRepository(db)
        self._policies = GovernmentPolicyRepository(db)

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def get_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"event:{event_id}"

        cached = await cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit: event %s", event_id)
            return cached

        event = await self._events.get_by_id(event_id)
        if event is None:
            return None

        # Fan out all DB reads concurrently
        (
            companies,
            sectors,
            timeline,
            news_links,
            similar_links,
            policy_links,
            graph_pair,
        ) = await asyncio.gather(
            self._events.get_companies(event_id),
            self._events.get_sectors(event_id),
            self._events.get_timeline(event_id),
            self._events.get_news_links(event_id),
            self._events.get_similar_events(event_id),
            self._events.get_policy_links(event_id),
            self._events.get_graph(event_id),
        )
        nodes, edges = graph_pair

        # Resolve FK references concurrently
        news_ids = [n.news_id for n in news_links]
        similar_ids = [s.similar_event_id for s in similar_links]
        policy_ids = [p.policy_id for p in policy_links]

        news_articles, similar_events, gov_policies = await asyncio.gather(
            self._fetch_news_articles(news_ids),
            self._events.get_events_by_ids(similar_ids),
            self._policies.get_by_ids(policy_ids),
        )

        # â”€â”€ Fallbacks when junction tables are empty (seeded events) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        # Companies: fall back to Event.companies JSON field
        if not companies and event.companies:
            _IMPACT_MAP = {"positive": "beneficiary", "negative": "loser", "neutral": "neutral"}

            class _FakeCompany:
                def __init__(self, d: dict):
                    self.symbol       = d.get("symbol", "")
                    self.name         = d.get("name", d.get("symbol", ""))
                    self.impact_type  = _IMPACT_MAP.get(str(d.get("impact", "Neutral")).lower(), "neutral")
                    self.impact_score = float(d.get("impact_score", 5.0))
                    self.reason       = d.get("reason", "")

            companies = [
                _FakeCompany(c) if isinstance(c, dict) else _FakeCompany({"symbol": str(c)})
                for c in event.companies
                if c
            ]

        # Sectors: fall back to Event.sectors JSON or derive from category
        _CAT_SECTORS: dict[str, list[str]] = {
            "monetary_policy": ["Banking", "NBFCs", "Financials"],
            "defence":         ["Defence", "Capital Goods", "Aerospace"],
            "energy":          ["Energy", "Oil & Gas", "Power"],
            "infrastructure":  ["Infrastructure", "Capital Goods", "Cement"],
            "technology":      ["IT", "Technology", "Software"],
            "pharmaceuticals": ["Pharmaceuticals", "Healthcare", "Chemicals"],
            "automotive":      ["Automobiles", "Auto Ancillaries"],
            "trade":           ["Trade", "Exports", "FMCG"],
            "agriculture":     ["Agriculture", "FMCG", "Chemicals"],
            "macro":           ["Economy", "Macro", "Financials"],
        }
        if not sectors:
            raw_sectors = event.sectors or []
            if not raw_sectors:
                raw_sectors = _CAT_SECTORS.get((event.category or "macro").lower(), ["Economy"])

            class _FakeSector:
                def __init__(self, name: str):
                    self.sector       = name
                    self.impact       = "positive"
                    self.impact_score = 50.0

            sectors = [_FakeSector(s) for s in raw_sectors]

        # Timeline: derive from AI summary bullets when EventTimeline is empty
        if not timeline:
            ai_s_tmp = event.ai_summary or {}
            _bullets = [b for b in ai_s_tmp.get("key_bullets", []) if b and len(b) > 10]

            class _FakeTimeline:
                def __init__(self, order: int, title: str, description: str = "", date: str = ""):
                    self.order       = order
                    self.title       = title
                    self.description = description
                    self.date        = date

            _summary_text = ai_s_tmp.get("summary", event.summary or "")
            _risk_factors = ai_s_tmp.get("risk_factors", [])
            _opps         = ai_s_tmp.get("opportunities", [])

            tl_items: list[_FakeTimeline] = []
            # Step 1 â€” always show event trigger
            tl_items.append(_FakeTimeline(0, "Event Announced", _summary_text[:120]))

            # Middle steps from bullets
            for i, b in enumerate(_bullets[:3]):
                tl_items.append(_FakeTimeline(i + 1, b, ""))

            # Risk & opportunity context
            if _risk_factors:
                tl_items.append(_FakeTimeline(len(tl_items), "Risk Factors", "; ".join(_risk_factors[:2])))
            if _opps:
                tl_items.append(_FakeTimeline(len(tl_items), "Opportunities", "; ".join(_opps[:2])))

            # Always end with an outlook step
            tl_items.append(_FakeTimeline(len(tl_items), "Market Outlook", "Monitor for developments over the coming weeks."))

            timeline = tl_items

        # Similar events: sector-based fallback
        if not similar_events:
            event_sector_names = [s.sector for s in sectors]
            if event_sector_names:
                similar_events = await self._events.get_similar_by_sectors(
                    event_sector_names[:3], event_id, limit=4
                )

        # Build denormalized similarity map for O(1) lookup
        similar_meta: dict[str, Any] = {
            s.similar_event_id: {"score": s.similarity_score, "reason": s.reason}
            for s in similar_links
        }

        ai_s = event.ai_summary or {}

        result = {
            "event": {
                "id": event.id,
                "slug": event.slug,
                "title": event.title,
                "description": event.description or event.summary or "",
                "source": event.source or "",
                "event_type": event.event_type or event.category or "macro",
                "event_date": _dt(event.event_date or event.published_at),
                "created_at": _dt(event.created_at),
                "updated_at": _dt(event.updated_at),
                "enrichment_status": event.enrichment_status,
            },
            "summary": {
                "text": ai_s.get("summary", event.summary or ""),
                "why_it_matters": ai_s.get("why_it_matters", ""),
                "key_bullets": ai_s.get("key_bullets", []),
                "immediate_impact": ai_s.get("immediate_impact", "neutral"),
                "long_term_impact": ai_s.get("long_term_impact", "neutral"),
                "risk_factors": ai_s.get("risk_factors", []),
                "opportunities": ai_s.get("opportunities", []),
            },
            "impactScore": float(event.impact_score or 0),
            "confidence": float(event.confidence or 0),
            "companies": [
                {
                    "symbol": c.symbol,
                    "name": c.name or c.symbol,
                    "impact_type": c.impact_type,
                    "impact_score": float(c.impact_score or 0),
                    "reason": c.reason or "",
                }
                for c in companies
            ],
            "beneficiaries": [
                {
                    "symbol": c.symbol,
                    "name": c.name or c.symbol,
                    "impact_score": float(c.impact_score or 0),
                    "reason": c.reason or "",
                }
                for c in companies
                if c.impact_type == "beneficiary"
            ],
            "losers": [
                {
                    "symbol": c.symbol,
                    "name": c.name or c.symbol,
                    "impact_score": float(c.impact_score or 0),
                    "reason": c.reason or "",
                }
                for c in companies
                if c.impact_type == "loser"
            ],
            "affectedSectors": [
                {
                    "sector": s.sector,
                    "impact": s.impact,
                    "impact_score": float(s.impact_score or 0),
                }
                for s in sectors
            ],
            "timeline": [
                {
                    "date": t.date or "",
                    "title": t.title,
                    "description": t.description or "",
                    "order": t.order,
                }
                for t in timeline
            ],
            "governmentPolicies": [
                {
                    "id": p.id,
                    "title": p.title,
                    "ministry": p.ministry or "",
                    "announcement_date": _dt(p.announcement_date),
                    "summary": p.summary or "",
                    "url": p.url or "",
                }
                for p in gov_policies
            ],
            "historicalEvents": [
                {
                    "id": e.id,
                    "title": e.title,
                    "event_date": _dt(e.event_date or e.published_at),
                    "impact_score": float(e.impact_score or 0),
                    "similarity_score": similar_meta.get(e.id, {}).get("score", 0.0),
                    "reason": similar_meta.get(e.id, {}).get("reason", ""),
                }
                for e in similar_events
            ],
            "relatedNews": [
                {
                    "id": a["id"],
                    "headline": a["headline"],
                    "source": a["source"],
                    "published_at": a["published_at"],
                    "summary": a["summary"],
                    "url": a.get("url", ""),
                }
                for a in news_articles
            ],
            "graph": {
                "nodes": [
                    {
                        "id": n.node_id,
                        "label": n.label,
                        "type": n.node_type,
                        "metadata": n.node_metadata or {},
                    }
                    for n in nodes
                ],
                "edges": [
                    {
                        "source": e.source,
                        "target": e.target,
                        "relationship": e.edge_relationship,
                    }
                    for e in edges
                ],
            },
            "marketReaction": ai_s.get("market_reaction", {}),
            "aiAnalysis": {
                **(ai_s.get("analysis", {})),
                "classification": ai_s.get("classification", {}),
            },
        }

        await cache_set(cache_key, result, ttl=_CACHE_TTL)
        return result

    # â”€â”€ Private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _fetch_news_articles(self, news_ids: list[str]) -> list[Dict]:
        if not news_ids:
            return []
        try:
            result = await self._db.execute(
                select(NewsArticle).where(NewsArticle.id.in_(news_ids))
            )
            return [
                {
                    "id": a.id,
                    "headline": a.headline,
                    "source": a.source,
                    "published_at": str(a.published_at),
                    "summary": a.summary,
                }
                for a in result.scalars().all()
            ]
        except Exception as exc:
            logger.warning("Failed to fetch news articles: %s", exc)
            return []


def _dt(val: Any) -> str:
    """Safely convert datetime or None to ISO string."""
    return str(val) if val is not None else ""


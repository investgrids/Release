"""
EventService — aggregates all event-related repository calls into a single
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
from app.db.models.macro_release import MacroRelease
from app.db.models_legacy import NewsArticle
from app.services import coverage_engine
from app.repositories.event_repository import EventRepository
from app.repositories.government_policy_repository import GovernmentPolicyRepository
from app.services.claim_provenance import ClaimProvenance, RippleEvidenceState
from app.services.event_scale import normalize_impact_score, normalize_confidence

logger = structlog.get_logger(__name__)

_CACHE_TTL = 900  # 15 minutes — matches the user's spec


class EventService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._events = EventRepository(db)
        self._policies = GovernmentPolicyRepository(db)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"event:{event_id}"

        cached = await cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit: event %s", event_id)
            return cached

        # Accept either the real id or the real, human-readable slug (SEO
        # fix — event pages were only ever linked by id, e.g.
        # "/events/nse-4cc93acbc1", even though every event already has a
        # real title-based slug in the DB, just never used). id lookup
        # first since it's the more common/cheaper path (existing links,
        # internal calls); slug is the fallback, not the other way round.
        event = await self._events.get_by_id(event_id)
        if event is None:
            event = await self._events.get_by_slug(event_id)
        if event is None:
            return None
        # Every downstream repository call below is keyed by the REAL id,
        # not whatever the caller passed in — reassign so a slug-based
        # lookup doesn't silently break every one of them.
        event_id = event.id

        # Fan out all DB reads concurrently
        (
            companies,
            sectors,
            timeline,
            news_links,
            similar_links,
            policy_links,
            graph_pair,
            macro_release,
            indexable,
        ) = await asyncio.gather(
            self._events.get_companies(event_id),
            self._events.get_sectors(event_id),
            self._events.get_timeline(event_id),
            self._events.get_news_links(event_id),
            self._events.get_similar_events(event_id),
            self._events.get_policy_links(event_id),
            self._events.get_graph(event_id),
            self._get_macro_release(event_id),
            coverage_engine.compute_indexable(self._db, event_id),
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

        # ── Fallbacks when junction tables are empty (seeded events) ──────────

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
                # CD3-B: zero evidence backs this row at all (no EventSector
                # rows, no Event.sectors JSON) — "positive" was a fabricated
                # directional claim, indistinguishable from a real one at the
                # API surface. "unavailable" is not a second guess ("neutral"
                # would still be a claim); it authorizes no directional claim
                # whatsoever. See app.services.claim_provenance.
                def __init__(self, name: str):
                    self.sector       = name
                    self.impact       = "unavailable"
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
            # Step 1 — always show event trigger
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
                # CD3-D (D6) — summarize_event's own integrity_status tag
                # (deepseek_provider.py's _safe_json_call), preserved
                # through event_pipeline.py's merged_summary spread.
                "integrity_status": ai_s.get("integrity_status", "unknown"),
            },
            "impactScore": normalize_impact_score(event.id, event.impact_score),
            "confidence": normalize_confidence(event.id, event.confidence),
            "companies": [
                {
                    "symbol": c.symbol,
                    "name": c.name or c.symbol,
                    "impact_type": c.impact_type,
                    "impact_score": float(c.impact_score or 0),
                    "reason": c.reason or "",
                    # CD3-B: a one-shot LLM extraction at Stage 4, made before
                    # the real Scoring Engine runs at Stage 5b and never
                    # reconciled with it afterward — an analytical hypothesis,
                    # never a verified beneficiary/loser. Same on both the
                    # real EventCompany path and the event.companies JSON
                    # fallback (_FakeCompany) — both come from the same
                    # extraction, just persisted differently.
                    "impact_provenance": ClaimProvenance.ANALYTICAL_HYPOTHESIS.value,
                }
                for c in companies
            ],
            "beneficiaries": [
                {
                    "symbol": c.symbol,
                    "name": c.name or c.symbol,
                    "impact_score": float(c.impact_score or 0),
                    "reason": c.reason or "",
                    "impact_provenance": ClaimProvenance.ANALYTICAL_HYPOTHESIS.value,
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
                    "impact_provenance": ClaimProvenance.ANALYTICAL_HYPOTHESIS.value,
                }
                for c in companies
                if c.impact_type == "loser"
            ],
            "affectedSectors": [
                {
                    "sector": s.sector,
                    "impact": s.impact,
                    "impact_score": float(s.impact_score or 0),
                    # CD3-B: real EventSector rows are the same one-shot Stage-4
                    # LLM extraction as companies above (analytical hypothesis).
                    # "unavailable" only ever comes from the _FakeSector
                    # zero-evidence fallback above, which already sets
                    # impact="unavailable" itself — detected here from that
                    # value rather than an isinstance check so this works
                    # regardless of which branch populated `sectors`.
                    "impact_provenance": (
                        ClaimProvenance.UNAVAILABLE.value if s.impact == "unavailable"
                        else ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
                    ),
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
                    "slug": e.slug or "",
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
                        # CD3-B: LLM-chosen relationship type (generate_graph),
                        # no evidence check for this specific event — same
                        # unverified-mechanism shape as ripple_effect[] and
                        # Deep Research's second-order effects.
                        "evidence_state": RippleEvidenceState.HYPOTHESIZED.value,
                    }
                    for e in edges
                ],
            },
            # CD3-D (D6) — both market_reaction and analysis come from the
            # SAME generate_impact_analysis call, so they share one
            # integrity_status tag (event_pipeline.py's
            # "narrative_integrity_status", since neither sub-dict alone
            # carries the top-level tag generate_impact_analysis actually
            # sets). classification carries its own, independent tag
            # nested inside itself (a separate AI call, classify_event).
            "marketReaction": {
                **(ai_s.get("market_reaction", {})),
                "integrity_status": ai_s.get("narrative_integrity_status", "unknown"),
            },
            "aiAnalysis": {
                **(ai_s.get("analysis", {})),
                "classification": ai_s.get("classification", {}),
                "integrity_status": ai_s.get("narrative_integrity_status", "unknown"),
            },
            "macroRelease": (
                {
                    "metric": macro_release.metric,
                    "release_value": macro_release.release_value,
                    "previous_value": macro_release.previous_value,
                    "expected_value": macro_release.expected_value,
                    "surprise": (
                        round(macro_release.release_value - macro_release.expected_value, 4)
                        if macro_release.release_value is not None and macro_release.expected_value is not None
                        else None
                    ),
                    "unit": macro_release.unit,
                    "period": macro_release.period,
                    "geography": macro_release.geography,
                    "importance": macro_release.importance,
                    "affected_sectors": macro_release.affected_sectors,
                    "affected_companies": macro_release.affected_companies,
                    "source": macro_release.source,
                    "source_url": macro_release.source_url,
                }
                if macro_release is not None
                else None
            ),
            "indexable": indexable,
        }

        await cache_set(cache_key, result, ttl=_CACHE_TTL)
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_macro_release(self, event_id: str) -> Optional[MacroRelease]:
        try:
            result = await self._db.execute(
                select(MacroRelease).where(MacroRelease.event_id == event_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.warning("Failed to fetch macro release: %s", exc)
            return None

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


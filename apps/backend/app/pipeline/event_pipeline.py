"""
Event AI Pipeline — 10 sequential stages for enriching a single event.

Flow:
  classify → summarize → extract_companies → extract_sectors
  → impact_analysis → timeline → similar_events → graph
  → government_policies → persist

Called exclusively by the event enrichment worker.
Never called from API routes.
"""
from __future__ import annotations

import asyncio
import structlog
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import Event
from app.repositories.event_repository import EventRepository
from app.repositories.government_policy_repository import GovernmentPolicyRepository
from app.services.provider_factory import get_ai_provider
from app.services import feature_extraction, scoring_engine, intelligence_orchestrator
from app.services.historical_memory_service import find_similar_events

logger = structlog.get_logger(__name__)


def _make_slug(title: str, suffix: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:160]
    return f"{base}-{suffix}"[:180] if suffix else base


async def run_event_pipeline(event: Event, db: AsyncSession) -> bool:
    """
    Enrich a single event through the full AI pipeline.
    Returns True on success, False on any unrecoverable failure.
    All writes are committed atomically at the end.
    """
    eid = event.id
    title = event.title or ""
    body = (event.description or event.summary or "")
    full_text = f"{title}. {body}".strip()
    source = event.source or "Unknown"

    repo = EventRepository(db)
    policy_repo = GovernmentPolicyRepository(db)
    ai = get_ai_provider()

    logger.info("[Pipeline] Starting event %s | %s", eid, title[:80])

    try:
        # Stage 1 — Mark as processing so the worker doesn't re-pick it
        await repo.mark_status(eid, "processing")

        # Stage 2 — Classify
        logger.debug("[Pipeline:%s] classify", eid)
        classification = await ai.classify_event(full_text)
        event_type = str(classification.get("category", "macro"))

        # Stage 3 — Summarize
        logger.debug("[Pipeline:%s] summarize", eid)
        ai_summary = await ai.summarize_event(title, full_text, source)

        # Stage 4 — Extract companies (run concurrently with stage 5)
        logger.debug("[Pipeline:%s] extract companies + sectors", eid)
        companies_raw, sectors_raw = await asyncio.gather(
            ai.extract_companies(title, full_text),
            ai.extract_sectors(title, full_text),
        )

        # Stage 5 — Impact analysis (AI's structured read: market_reaction, analysis,
        # and per-entity impact_type/reason text — used for narrative, NOT for the
        # published impact_score/confidence numbers anymore; those come from the
        # Scoring Engine at stage 5b so they're never an LLM's self-rated guess).
        logger.debug("[Pipeline:%s] impact analysis", eid)
        impact = await ai.generate_impact_analysis(title, full_text, companies_raw, sectors_raw)

        # Stage 5b — Feature extraction + centralized scoring (real signals only)
        logger.debug("[Pipeline:%s] feature extraction + scoring", eid)
        sector_names = [s.get("sector", "") for s in sectors_raw if s.get("sector")]
        published_at = event.event_date or event.published_at
        similar_for_scoring = await find_similar_events(
            {"category": event_type, "sectors": sector_names}, limit=8, min_similarity=20.0,
        )
        event_features = feature_extraction.extract_event_features(
            event_type=event_type,
            source=source,
            published_at=published_at,
            companies_affected=[{"symbol": c["symbol"]} for c in companies_raw if c.get("symbol")],
            sectors_affected=sector_names,
            similar_historical_events=similar_for_scoring,
        )
        event_score = scoring_engine.score_event_impact(event_features)
        logger.info(
            "[Pipeline:%s] Event Impact Score: %s (status=%s, confidence=%s, %s)",
            eid, event_score.score, event_score.status, event_score.confidence, event_score.version,
        )

        # Stage 6 — Timeline
        logger.debug("[Pipeline:%s] timeline", eid)
        timeline_raw = await ai.generate_timeline(title, full_text, event_type)

        # Stage 7 — Similar events (DB lookup → AI ranking)
        logger.debug("[Pipeline:%s] similar events", eid)
        candidates = await repo.get_similar_by_sectors(sector_names, exclude_id=eid)
        candidate_dicts = [
            {"id": e.id, "title": e.title, "sectors": e.sectors or []}
            for e in candidates
        ]
        similar_raw = await ai.find_similar_events(title, sector_names, candidate_dicts)

        # Stage 8 — Network graph
        logger.debug("[Pipeline:%s] graph", eid)
        graph_raw = await ai.generate_graph(title, companies_raw, sectors_raw)

        # Stage 9 — Government policies (keyword search in DB)
        logger.debug("[Pipeline:%s] policies", eid)
        keywords = sector_names[:3] + title.split()[:4]
        policies = await policy_repo.search_by_keywords(keywords[:6], limit=5)

        # ── Stage 10: Persist everything atomically ──────────────────────────
        logger.debug("[Pipeline:%s] persist", eid)

        slug = _make_slug(title, suffix=eid[:8])

        merged_summary = {
            **ai_summary,
            "classification": classification,
            "market_reaction": impact.get("market_reaction", {}),
            "analysis": impact.get("analysis", {}),
            # Real, evidence-backed score — breakdown/top_contributors/reasoning/
            # version travel with the event so the "why" UI (Phase 4/5) can read
            # them straight from ai_summary without recomputing anything.
            "score_engine": event_score.to_dict(),
        }

        await repo.update_core_fields(eid, {
            "slug": slug,
            "event_type": event_type,
            "ai_summary": merged_summary,
            # None when the engine didn't have enough real signal — never a
            # fabricated placeholder number. The old code defaulted a missing
            # AI-guessed score to 60/65; that fallback is gone entirely.
            "impact_score": event_score.score,
            "confidence": event_score.confidence,
            "sectors": sector_names,
        })

        # Companies
        company_rows = [
            {
                "symbol": c["symbol"],
                "name": c.get("name", c["symbol"]),
                "impact_type": c.get("impact_type", "neutral"),
                "impact_score": float(c.get("impact_score", 5.0)),
                "reason": c.get("reason", ""),
            }
            for c in companies_raw
            if c.get("symbol")
        ]
        await repo.replace_companies(eid, company_rows)

        # Sectors
        sector_rows = [
            {
                "sector": s["sector"],
                "impact": s.get("impact", "neutral"),
                "impact_score": float(s.get("impact_score", 5.0)),
            }
            for s in sectors_raw
            if s.get("sector")
        ]
        await repo.replace_sectors(eid, sector_rows)

        # Timeline
        timeline_rows = [
            {
                "date": str(t.get("date", "")),
                "title": t.get("title", ""),
                "description": t.get("description", ""),
                "order": int(t.get("order", i)),
            }
            for i, t in enumerate(timeline_raw)
            if t.get("title")
        ]
        await repo.replace_timeline(eid, timeline_rows)

        # Graph
        node_rows = [
            {
                "node_id": n.get("node_id", f"n{i}"),
                "label": n.get("label", ""),
                "node_type": n.get("node_type", "entity"),
                "node_metadata": n.get("node_metadata", {}),
            }
            for i, n in enumerate(graph_raw.get("nodes", []))
            if n.get("label")
        ]
        edge_rows = [
            {
                "source": e.get("source", ""),
                "target": e.get("target", ""),
                "edge_relationship": e.get("edge_relationship", e.get("relationship", "impacts")),
            }
            for e in graph_raw.get("edges", [])
            if e.get("source") and e.get("target")
        ]
        await repo.replace_graph(eid, node_rows, edge_rows)

        # Similar events
        similar_rows = [
            {
                "similar_event_id": str(s["event_id"]),
                "similarity_score": float(s.get("similarity_score", 0.5)),
                "reason": s.get("reason", ""),
            }
            for s in similar_raw
            if s.get("event_id") and str(s["event_id"]) != eid
        ]
        await repo.replace_similar(eid, similar_rows)

        # Policy links
        if policies:
            await repo.replace_policies(
                eid,
                [p.id for p in policies],
                ["relevant"] * len(policies),
            )

        # Commit everything
        await db.commit()

        # Final status (separate commit so it's not rolled back with data)
        await repo.mark_status(eid, "done")

        logger.info(
            "[Pipeline] Enrichment complete: event %s | score=%s", eid, event_score.score,
        )

        # Ripple propagation + cache invalidation + live broadcast. Best-effort:
        # the event is already successfully enriched and committed above, so an
        # orchestrator failure (graph lookup, cache, SSE fan-out) must never
        # turn a successful enrichment into a failed one.
        try:
            await intelligence_orchestrator.on_event_scored(
                event=event,
                event_features=event_features,
                event_score=event_score,
                sector_names=sector_names,
                companies=company_rows,
                db=db,
                similar_historical_events=similar_for_scoring,
            )
        except Exception as orch_exc:
            logger.error("[Pipeline] Orchestrator step failed for %s: %s", eid, orch_exc, exc_info=True)

        return True

    except Exception as exc:
        logger.error("[Pipeline] Failed for event %s: %s", eid, exc, exc_info=True)
        try:
            await db.rollback()
            await repo.mark_status(eid, "failed")
        except Exception as inner:
            logger.error("[Pipeline] Could not mark failure for %s: %s", eid, inner)
        return False


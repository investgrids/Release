"""
Intelligence Orchestrator — the single place every scoring trigger flows
through once the Scoring Engine has produced a first-pass score.

    Raw data -> Feature Extraction -> Score Engine  (run by the caller)
                                            |
                                            v
                          Intelligence Orchestrator          <- this file
                                            |
              +-----------------------------+-----------------------------+
              |                             |                             |
        Ripple Engine                Cache invalidation               Broadcast
  (resolve a graph node,           (this entity + every            (ScoreUpdate,
   re-score the source              dashboard variant that       data_status=
   with real ripple                 might list it)                "preliminary")
   depth/width, persist
   if it changed)
              |
              v
   Bounded Enrichment Queue  (non-blocking push — never awaited here)
              |
              v   [app/services/enrichment_worker.py, runs independently]
   Live market-data fetch (bounded concurrency + per-symbol timeout)
              |
              v
   Company Impact Score (data_status="live") + Event rescore
   (data_status="verified") -> cache invalidation -> broadcast

This module exists so cache-invalidation and broadcast logic live in
exactly one place instead of being copy-pasted into every job/worker that
produces a score. Every future trigger (earnings, market close, a policy
change, a company added) should call an entry point here rather than
duplicating this fan-out itself.

Today only `on_event_scored` exists, wired from the end of
app/pipeline/event_pipeline.py (the one real, already-wired trigger:
scheduled event enrichment). Sibling entry points (on_earnings_released,
on_market_close, ...) should follow the same shape once those triggers
have a real upstream data source — this file intentionally doesn't stub
them out in advance, to avoid an orchestrator that pretends to cover
triggers nothing feeds yet.
"""
from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import Event
from app.cache import delete, delete_pattern
from app.services import feature_extraction, scoring_engine
from app.services.enrichment_queue import CompanyCandidate, EnrichmentJob, get_enrichment_queue
from app.services.intelligence.event_bus import ScoreUpdate
from app.services.intelligence_graph_service import make_node_id, ripple_from_node
from app.services.score_history_service import publish_score_update

log = structlog.get_logger(__name__)

_MAX_RIPPLE_BROADCASTS = 10  # cap fan-out per event so one hub node doesn't flood subscribers
_MAX_COMPANIES_TO_ENRICH = 5  # bound how many companies per event get a live market-data fetch


async def _resolve_ripple_source(sector_names: list, company_symbols: list) -> tuple:
    """
    Try candidate graph nodes — sectors first (more likely to be seeded
    with real outgoing edges), then companies — until one actually
    produces impacts. A node that exists but has no outgoing edges
    returns a valid, empty result; trying candidates in order and taking
    the first *real* one beats trusting only the first/best text match
    (same lesson learned wiring the AI Search ripple chain earlier).
    """
    candidates = [make_node_id("sector", s) for s in sector_names if s] + \
                 [make_node_id("company", c) for c in company_symbols if c]
    for node_id in candidates:
        result = await ripple_from_node(node_id, change="rise")
        if result.get("impacts"):
            return node_id, result
    return None, None


async def on_event_scored(
    event: Event,
    event_features,           # feature_extraction.EventFeatures
    event_score,                # scoring_engine.ScoreResult — the first-pass (preliminary) score
    sector_names: list,
    companies: list,             # list[dict] with at least "symbol", ideally "name"/"impact_score" (AI's own 0-10ish estimate, used only to rank)
    db: AsyncSession,
    similar_historical_events: Optional[list] = None,
) -> None:
    """
    Run once an event has its first-pass Event Impact Score (event_pipeline.py
    stage 5b). Resolves the event to a graph node if one exists, re-scores it
    with real ripple depth/width when found (still "preliminary" — the graph
    is local, no external market-data call), persists the change, invalidates
    the caches that could be showing the stale number, broadcasts a
    ScoreUpdate, and — without awaiting it — enqueues the bounded live
    market-data enrichment for the event's highest-impact companies. That
    enrichment runs independently in app/services/enrichment_worker.py and
    broadcasts its own "verified"/"live" ScoreUpdates when it completes;
    this function never blocks on it.
    """
    previous_score = event_score.score
    final_score = event_score

    company_symbols = [c["symbol"] for c in companies if c.get("symbol")]
    node_id, ripple_result = await _resolve_ripple_source(sector_names, company_symbols)

    if ripple_result:
        ripple_features = feature_extraction.extract_ripple_features(ripple_result)
        if ripple_features.get("ripple_depth") is not None or ripple_features.get("ripple_width") is not None:
            event_features.ripple_depth = ripple_features.get("ripple_depth")
            event_features.ripple_width = ripple_features.get("ripple_width")
            rescored = scoring_engine.score_event_impact(event_features)

            if rescored.status == "ok":
                final_score = rescored
                if final_score.score != previous_score:
                    from app.repositories.event_repository import EventRepository
                    repo = EventRepository(db)
                    await repo.update_core_fields(event.id, {
                        "impact_score": final_score.score,
                        "confidence": final_score.confidence,
                    })
                    await db.commit()
                    log.info(
                        "orchestrator.ripple_rescore",
                        event_id=event.id, previous=previous_score, updated=final_score.score,
                        ripple_source=node_id,
                    )

    # Cache invalidation — this event's own cache entry plus every
    # dashboard variant that could be listing its old score.
    await delete(f"event:{event.id}")
    await delete_pattern("dashboard:*")

    # Broadcast — the event's own score first, then a lightweight signal
    # for each entity the ripple actually touched. Ripple-touched entities
    # get a "ripple_signal" status, not a real re-scored number: computing
    # a full Company/Sector score for each one needs live market data this
    # orchestrator doesn't fetch (see event_pipeline.py's known-gap note on
    # company-level scoring) — broadcasting a fabricated score for them
    # would violate the same "never invent a number" rule the rest of the
    # engine enforces, so this only ever states the real ripple weight.
    await publish_score_update(ScoreUpdate(
        entity_type="event",
        entity_id=event.id,
        model="event_impact",
        score=final_score.score,
        previous_score=previous_score,
        confidence=final_score.confidence,
        status=final_score.status,
        version=final_score.version,
        breakdown=final_score.breakdown,
        top_contributors=final_score.top_contributors,
        reasoning=final_score.reasoning,
        trigger="new_event",
        data_status="preliminary",
    ))

    if ripple_result:
        for impact in ripple_result.get("impacts", [])[:_MAX_RIPPLE_BROADCASTS]:
            node = impact.get("node") or {}
            if not node.get("id"):
                continue
            await publish_score_update(ScoreUpdate(
                entity_type=node.get("node_type", "entity"),
                entity_id=node["id"],
                model="ripple_propagation",
                score=None,
                previous_score=None,
                confidence=round((impact.get("accumulated_weight") or 0) * 100, 1),
                status="ripple_signal",
                version=f"Ripple Strength {scoring_engine.CURRENT_VERSION['ripple_strength']}",
                top_contributors=[],
                reasoning=[f"In the ripple path of \"{event.title}\" (via {node_id}, depth {impact.get('depth')})"],
                trigger="ripple_propagation",
            ))

    # Bounded async enrichment — rank companies by the AI's own rough
    # impact estimate, take the top N, and hand them off to the enrichment
    # queue. `.push()` is a synchronous, non-blocking queue put; the actual
    # live market-data fetch happens later in a completely separate task
    # (app/services/enrichment_worker.py), so this event pipeline run is
    # never held up waiting on an external market-data request.
    ranked = sorted(
        (c for c in companies if c.get("symbol")),
        key=lambda c: c.get("impact_score", 0) or 0,
        reverse=True,
    )[:_MAX_COMPANIES_TO_ENRICH]

    if ranked:
        get_enrichment_queue().push(EnrichmentJob(
            event_id=event.id,
            event_title=event.title,
            sector_names=sector_names,
            companies=[
                CompanyCandidate(symbol=c["symbol"], name=c.get("name", c["symbol"]), ai_impact_score=c.get("impact_score", 0) or 0)
                for c in ranked
            ],
            event_features=event_features,
            preliminary_score=final_score.score,
            similar_historical_events=similar_historical_events or [],
        ))
        log.info("orchestrator.enrichment_enqueued", event_id=event.id, companies=[c["symbol"] for c in ranked])

"""
Score History service — the single funnel every ScoreUpdate passes through
on its way to becoming both a live SSE push and a durable row. Mirrors the
persist-then-broadcast pattern already used for TriagedEvent
(app/services/intelligence/triage_worker.py::_store_triage), just factored
into one function so intelligence_orchestrator.py and enrichment_worker.py
both call exactly one thing instead of two.
"""
from __future__ import annotations

import structlog

from app.services.intelligence.event_bus import ScoreUpdate, get_broadcaster

log = structlog.get_logger(__name__)


async def publish_score_update(update: ScoreUpdate) -> None:
    """Persist a ScoreUpdate to score_history, then broadcast it live. Never raises — a history-write failure must not stop the score from reaching live subscribers."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.score_history import ScoreHistory

        async with AsyncSessionLocal() as db:
            db.add(ScoreHistory(
                entity_type=update.entity_type,
                entity_id=update.entity_id,
                model=update.model,
                score=update.score,
                previous_score=update.previous_score,
                confidence=update.confidence,
                status=update.status,
                data_status=update.data_status,
                version=update.version,
                breakdown=update.breakdown,
                top_contributors=update.top_contributors,
                reasoning=update.reasoning,
                trigger=update.trigger,
                created_at=update.timestamp,
            ))
            await db.commit()
    except Exception as exc:
        log.warning("score_history.write_failed", entity_id=update.entity_id, error=str(exc))

    await get_broadcaster().broadcast(update)


async def get_score_history(entity_type: str, entity_id: str, model: str | None = None, limit: int = 50) -> list[dict]:
    """Chronological (oldest -> newest) score history for one entity — powers Score History / Evidence Timeline / Confidence Evolution."""
    from app.db.session import AsyncSessionLocal
    from app.db.models.score_history import ScoreHistory
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        query = (
            select(ScoreHistory)
            .where(ScoreHistory.entity_type == entity_type, ScoreHistory.entity_id == entity_id)
        )
        if model:
            query = query.where(ScoreHistory.model == model)
        query = query.order_by(ScoreHistory.created_at.desc()).limit(limit)

        rows = (await db.execute(query)).scalars().all()

    return [r.to_dict() for r in reversed(rows)]  # oldest -> newest for a timeline UI

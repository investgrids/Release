"""
Event Enrichment Worker — pulls pending events from the DB and runs the AI pipeline.

Schedule: every 5 minutes.
Batch:    up to 5 events per run (rate-limits AI calls).
Retry:    failed events are retried on the next cycle (max 3 attempts via status tracking).

The worker is stateless — all coordination is through the `enrichment_status` column.
"""
from __future__ import annotations

import asyncio
import structlog

from app.db.session import AsyncSessionLocal
from app.pipeline.event_pipeline import run_event_pipeline
from app.repositories.event_repository import EventRepository

logger = structlog.get_logger(__name__)

_INTERVAL_SEC = 300   # 5 minutes between sweeps
_BATCH_SIZE = 5       # max events per sweep (controls AI API rate)
_AI_CALL_DELAY = 2    # seconds between events in the same batch


async def run_event_enrichment_worker() -> None:
    """Long-running async task: periodically enriches pending events."""
    logger.info("Event enrichment worker started (interval=%ds, batch=%d)", _INTERVAL_SEC, _BATCH_SIZE)

    while True:
        try:
            await _process_batch()
        except Exception as exc:
            logger.error("Event enrichment worker top-level error: %s", exc, exc_info=True)

        await asyncio.sleep(_INTERVAL_SEC)


async def _process_batch() -> None:
    async with AsyncSessionLocal() as db:
        repo = EventRepository(db)

        pending = await repo.get_pending_enrichment(limit=_BATCH_SIZE)

        if not pending:
            logger.debug("No pending events — enrichment worker idle")
            return

        logger.info("Enrichment worker: processing %d event(s)", len(pending))

        for event in pending:
            try:
                success = await run_event_pipeline(event, db)
                if success:
                    logger.info("Enriched event %s: %s", event.id, event.title[:60])
                else:
                    logger.warning("Pipeline returned False for event %s", event.id)
            except Exception as exc:
                logger.error("Unhandled error for event %s: %s", event.id, exc, exc_info=True)

            # Brief pause between events to avoid hammering the AI API
            await asyncio.sleep(_AI_CALL_DELAY)

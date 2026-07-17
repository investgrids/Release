"""
Enrichment Worker — consumes EnrichmentJob items and performs the bounded,
asynchronous live market-data enrichment the event pipeline deliberately
defers. This is what lets the pipeline produce an immediate, explainable
"preliminary" score without ever blocking on an external market-data
request: it just enqueues a job here and moves on (see
app/services/intelligence_orchestrator.py).

For each job:
  1. Fetch live market data (market cap, institutional holding, volume,
     sector) for the job's bounded, pre-ranked company candidates —
     concurrently, capped, with a per-symbol timeout. A symbol that times
     out or errors is skipped, never given a fabricated result.
  2. Score each company that got real data via score_company_impact()
     (data_status="live" — this model only ever exists once live data
     backs it) and persist to its event_company row.
  3. Fold the aggregated real market-cap/institutional data back into the
     event's EventFeatures and rescore the event via score_event_impact()
     (data_status="verified").
  4. Invalidate caches and broadcast a ScoreUpdate for everything that
     changed, over the same SSE channel the preliminary score already
     used — the frontend tells preliminary from verified/live by the
     `data_status` field, not by a different event type.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from app.cache import delete, delete_pattern
from app.services import feature_extraction, scoring_engine
from app.services.enrichment_queue import EnrichmentJob, get_enrichment_queue
from app.services.intelligence.event_bus import ScoreUpdate
from app.services.market_data import get_stock_scoring_raw
from app.services.score_history_service import publish_score_update

log = structlog.get_logger(__name__)

_FETCH_TIMEOUT = 8.0            # seconds per symbol — a hanging yfinance call must not stall the worker
_MAX_CONCURRENT_FETCHES = 3     # bounded concurrency — never hammer the market-data provider


def _historical_sensitivity(symbol: str, similar_events: list) -> Optional[float]:
    """
    0-100 signal from how this symbol actually moved in similar past events
    (historical_winners/historical_losers, similarity-weighted). None if the
    symbol never appears in the matched history — a real "no data", not a
    fabricated neutral midpoint.
    """
    hits = []
    for ev in similar_events or []:
        sim = ev.get("similarity")
        if sim is None:
            continue
        for bucket in ("historical_winners", "historical_losers"):
            for entry in ev.get(bucket) or []:
                if entry.get("symbol") != symbol:
                    continue
                ret = entry.get("return_1m", entry.get("return_1w", entry.get("return_1d")))
                if ret is not None:
                    hits.append((sim, abs(float(ret))))

    if not hits:
        return None
    total_w = sum(s for s, _ in hits)
    if total_w <= 0:
        return None
    weighted_avg_abs_return = sum(s * r for s, r in hits) / total_w
    return round(min(weighted_avg_abs_return * 3, 100), 1)  # ~30% historical move saturates the scale


async def _fetch_one(symbol: str, sem: asyncio.Semaphore) -> Optional[dict]:
    async with sem:
        try:
            return await asyncio.wait_for(get_stock_scoring_raw(symbol), timeout=_FETCH_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning("enrichment.fetch_timeout", symbol=symbol)
            return None
        except Exception as exc:
            log.warning("enrichment.fetch_error", symbol=symbol, error=str(exc))
            return None


async def process_enrichment_job(job: EnrichmentJob) -> None:
    sem = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)

    raw_results = await asyncio.gather(*[_fetch_one(c.symbol, sem) for c in job.companies])

    enriched = [(c, raw) for c, raw in zip(job.companies, raw_results) if raw is not None]

    if not enriched:
        log.info("enrichment.no_live_data", event_id=job.event_id, attempted=len(job.companies))
        return

    from app.db.session import AsyncSessionLocal
    from app.repositories.event_repository import EventRepository

    company_scores = []
    event_score = None

    async with AsyncSessionLocal() as db:
        repo = EventRepository(db)

        for candidate, raw in enriched:
            sector_exposure = None
            if raw.get("sector") and job.sector_names:
                event_sectors_lower = {s.strip().lower() for s in job.sector_names if s}
                sector_exposure = 100.0 if raw["sector"].strip().lower() in event_sectors_lower else 0.0

            company_features = feature_extraction.extract_company_features(
                sector_exposure=sector_exposure,
                market_cap=raw.get("market_cap"),
                institutional_holding_pct=raw.get("held_institutions_pct"),
                volume=raw.get("volume"),
                avg_volume=raw.get("avg_volume"),
                historical_sensitivity=_historical_sensitivity(candidate.symbol, job.similar_historical_events),
            )
            company_score = scoring_engine.score_company_impact(company_features)

            await repo.update_company_score(job.event_id, candidate.symbol, company_score.score)
            company_scores.append((candidate, company_score))

        # Fold real market data into the event's own features and rescore —
        # only the two features live data can actually inform; everything
        # else (news volume, historical similarity, ripple...) is unchanged.
        total_market_cap = sum(r["market_cap"] for _, r in enriched if r.get("market_cap")) or None
        inst_pcts = [r["held_institutions_pct"] for _, r in enriched if r.get("held_institutions_pct") is not None]

        if total_market_cap is not None:
            job.event_features.market_cap_affected = feature_extraction.extract_market_cap_score(total_market_cap)
        if inst_pcts:
            job.event_features.institutional_mentions = round(sum(inst_pcts) / len(inst_pcts), 1)

        if total_market_cap is not None or inst_pcts:
            event_score = scoring_engine.score_event_impact(job.event_features, data_status="verified")
            if event_score.status == "ok":
                await repo.update_core_fields(job.event_id, {
                    "impact_score": event_score.score,
                    "confidence": event_score.confidence,
                })

        await db.commit()

    # Cache: this event + every dashboard variant, now backed by verified data
    await delete(f"event:{job.event_id}")
    await delete_pattern("dashboard:*")

    if event_score is not None and event_score.status == "ok":
        await publish_score_update(ScoreUpdate(
            entity_type="event", entity_id=job.event_id, model="event_impact",
            score=event_score.score, previous_score=job.preliminary_score,
            confidence=event_score.confidence, status=event_score.status,
            version=event_score.version, breakdown=event_score.breakdown,
            top_contributors=event_score.top_contributors,
            reasoning=event_score.reasoning, trigger="enrichment_complete",
            data_status="verified",
        ))

    for candidate, company_score in company_scores:
        await publish_score_update(ScoreUpdate(
            entity_type="company", entity_id=candidate.symbol, model="company_impact",
            score=company_score.score, previous_score=None,
            confidence=company_score.confidence, status=company_score.status,
            version=company_score.version, breakdown=company_score.breakdown,
            top_contributors=company_score.top_contributors,
            reasoning=company_score.reasoning, trigger="enrichment_complete",
            data_status="live",
        ))

    log.info(
        "enrichment.job_complete", event_id=job.event_id,
        companies_enriched=len(enriched), companies_attempted=len(job.companies),
        event_rescored=event_score is not None and event_score.status == "ok",
    )


class EnrichmentWorker:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run(), name="enrichment-worker")
        log.info("enrichment_worker.started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("enrichment_worker.stopped")

    async def _run(self) -> None:
        queue = get_enrichment_queue()
        while self._running:
            try:
                job = await asyncio.wait_for(queue.consume(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                log.error("enrichment_worker.consume_error", error=str(exc))
                await asyncio.sleep(1)
                continue

            try:
                await process_enrichment_job(job)
            except Exception as exc:
                log.error("enrichment_worker.job_failed", event_id=job.event_id, error=str(exc), exc_info=True)
            finally:
                queue.task_done()


_worker: Optional[EnrichmentWorker] = None


def get_enrichment_worker() -> EnrichmentWorker:
    global _worker
    if _worker is None:
        _worker = EnrichmentWorker()
    return _worker

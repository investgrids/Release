"""
Ingest tasks — run every 15 minutes (news) or every hour (policy).
Each job:
  1. Calls the relevant providers
  2. Persists new articles to news_articles
  3. Creates Event rows (status=pending) for exchange and policy items
  4. Invalidates affected cache keys
"""
from __future__ import annotations

import time

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models_legacy import NewsArticle
from app.db.models.event import Event
from app.providers import NSEProvider, BSEProvider, RSSProvider, RBIProvider, PIBProvider, SEBIProvider, RawItem
from app.repositories.government_policy_repository import GovernmentPolicyRepository

log = structlog.get_logger(__name__)


# ── Intelligence bus helper ───────────────────────────────────────────────────

async def _push_to_triage_bus(items: list[RawItem], new_ids: set[str], source: str) -> None:
    """Push newly-ingested items onto the EventIngestionBus for AI triage."""
    try:
        from app.services.intelligence.event_bus import get_event_bus, RawEvent
        bus = get_event_bus()
        for item in items:
            if item.id not in new_ids:
                continue
            await bus.push(RawEvent(
                id=item.id,
                headline=item.headline,
                summary=item.summary,
                source=source,
                source_url=item.url or "",
                sectors=[],
                companies=item.companies or [],
                raw_impact=float(item.impact_score or 5.0),
            ))
    except Exception as exc:
        log.warning("ingest.bus_push_failed", source=source, error=str(exc))


# ── Shared DB helpers ─────────────────────────────────────────────────────────

async def _existing_ids(db, model, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    result = await db.execute(select(model.id).where(model.id.in_(ids)))
    return {r for (r,) in result}


async def _persist_articles(db, items: list[RawItem]) -> list[str]:
    """Write new NewsArticle rows; return list of newly-inserted IDs."""
    if not items:
        return []
    all_ids = [i.id for i in items]
    existing = await _existing_ids(db, NewsArticle, all_ids)
    new_ids = []
    for item in items:
        if item.id in existing:
            continue
        db.add(NewsArticle(
            id=item.id,
            headline=item.headline,
            summary=item.summary,
            source=item.source,
            published_at=item.published_at or "—",
            companies=item.companies,
            impact_score=item.impact_score,
        ))
        new_ids.append(item.id)
    if new_ids:
        await db.commit()
    return new_ids


async def _create_events(db, items: list[RawItem], new_ids: set[str],
                          event_type: str) -> int:
    """Create Event rows for newly-saved items."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    existing = await _existing_ids(db, Event, list(new_ids))
    saved = 0
    for item in items:
        if item.id not in new_ids or item.id in existing:
            continue
        db.add(Event(
            id=item.id,
            title=item.headline,
            summary=item.summary,
            description=item.summary,
            source=item.source,
            event_type=event_type,
            companies=item.companies,
            impact_score=item.impact_score,
            confidence=0.0,
            published_at=now,
            created_at=now,
            updated_at=now,
            enrichment_status="pending",
        ))
        saved += 1
    if saved:
        await db.commit()
    return saved


async def _persist_policies(db, items: list[RawItem]) -> int:
    """Upsert government policies for RBI/PIB/SEBI items."""
    repo = GovernmentPolicyRepository(db)
    saved = 0
    for item in items:
        if not item.headline:
            continue
        await repo.upsert({
            "external_id":       item.id,
            "title":             item.headline,
            "ministry":          item.ministry,
            "announcement_date": None,
            "summary":           item.summary,
            "url":               item.url,
        })
        saved += 1
    if saved:
        await db.commit()
    return saved


# ── Job: news ingest (NSE + BSE + RSS) — every 15 min ─────────────────────────

async def job_ingest_news() -> None:
    t0 = time.perf_counter()
    log.info("job.ingest_news.start")

    nse_items = await NSEProvider().fetch_and_normalize()
    bse_items = await BSEProvider().fetch_and_normalize()
    rss_items = await RSSProvider().fetch_and_normalize()

    all_items = nse_items + bse_items + rss_items

    async with AsyncSessionLocal() as db:
        new_ids = await _persist_articles(db, all_items)
        new_id_set = set(new_ids)

        nse_events = await _create_events(db, nse_items, new_id_set, "corporate")
        bse_events = await _create_events(db, bse_items, new_id_set, "corporate")
        # RSS items do NOT become Events (too generic)

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info(
        "job.ingest_news.done",
        nse=len(nse_items), bse=len(bse_items), rss=len(rss_items),
        new_articles=len(new_ids),
        new_events=nse_events + bse_events,
        elapsed_ms=elapsed,
    )

    # Push new articles to the intelligence bus for AI triage
    if new_ids:
        await _push_to_triage_bus(all_items, set(new_ids), "news")

    # Invalidate news cache so next request gets fresh data
    from app.cache import delete_pattern
    await delete_pattern("dashboard:*")


# ── Job: policy ingest (RBI + PIB + SEBI) — every hour ───────────────────────

async def job_ingest_policy() -> None:
    t0 = time.perf_counter()
    log.info("job.ingest_policy.start")

    rbi_items  = await RBIProvider().fetch_and_normalize()
    pib_items  = await PIBProvider().fetch_and_normalize()
    sebi_items = await SEBIProvider().fetch_and_normalize()

    all_items = rbi_items + pib_items + sebi_items

    async with AsyncSessionLocal() as db:
        new_ids = await _persist_articles(db, all_items)
        new_id_set = set(new_ids)
        policies_saved = await _persist_policies(db, all_items)
        events_created = await _create_events(db, all_items, new_id_set, "policy")

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info(
        "job.ingest_policy.done",
        rbi=len(rbi_items), pib=len(pib_items), sebi=len(sebi_items),
        new_articles=len(new_ids),
        policies=policies_saved,
        new_events=events_created,
        elapsed_ms=elapsed,
    )

    # Push policy items to the intelligence bus for triage
    if new_ids:
        await _push_to_triage_bus(all_items, set(new_ids), "policy")


# ── Job: AI event enrichment — every 5 min ────────────────────────────────────

async def job_enrich_events() -> None:
    t0 = time.perf_counter()

    from app.repositories.event_repository import EventRepository
    from app.pipeline.event_pipeline import run_event_pipeline

    _BATCH = 5
    _AI_DELAY = 2  # seconds between AI calls

    import asyncio

    async with AsyncSessionLocal() as db:
        repo = EventRepository(db)
        pending = await repo.get_pending_enrichment(limit=_BATCH)

    if not pending:
        log.debug("job.enrich_events.idle")
        return

    log.info("job.enrich_events.start", count=len(pending))
    enriched = 0
    failed   = 0

    for event in pending:
        async with AsyncSessionLocal() as db:
            try:
                ok = await run_event_pipeline(event, db)
                if ok:
                    enriched += 1
                    # Invalidate event cache
                    from app.cache import delete
                    await delete(f"event:{event.id}")
                else:
                    failed += 1
            except Exception as exc:
                log.error("job.enrich_events.error", event_id=event.id, error=str(exc))
                failed += 1
        await asyncio.sleep(_AI_DELAY)

    # Invalidate dashboard cache if events changed
    if enriched:
        from app.cache import delete_pattern
        await delete_pattern("dashboard:*")

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info(
        "job.enrich_events.done",
        enriched=enriched, failed=failed, elapsed_ms=elapsed,
    )

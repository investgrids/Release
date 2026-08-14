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
from app.db.models.macro_release import MacroRelease
from app.providers import NSEProvider, BSEProvider, RSSProvider, RBIProvider, PIBProvider, SEBIProvider, FedProvider, RawItem
from app.repositories.government_policy_repository import GovernmentPolicyRepository
from app.services.macro_extraction import extract_macro_release

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
                # item.source is the real, specific outlet each provider
                # already sets (e.g. "Economic Times", "NSE", "RBI") — was
                # being silently discarded in favor of the broad "news"/
                # "policy" category passed in above, which is why every
                # triaged event's attribution collapsed to the same two
                # generic strings regardless of which of the 6+ real
                # sources it actually came from.
                origin=item.source or "",
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
    # Some providers (e.g. NSE, when an announcement number is missing) hash
    # only the headline text into the id — generic headlines like "Updates" or
    # "Dividend updates" then collide across different companies in the same
    # batch. Dedupe by id here so a same-batch collision can't violate the
    # NewsArticle.id UNIQUE constraint and crash the whole ingest job.
    seen: set[str] = set()
    deduped: list[RawItem] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        deduped.append(item)
    items = deduped

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
    seen: set[str] = set()
    for item in items:
        if item.id not in new_ids or item.id in existing or item.id in seen:
            continue
        seen.add(item.id)
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


async def _persist_macro_releases(db, items: list[RawItem]) -> int:
    """Phase 7 (2026-08 audit): attempts real numeric extraction on RBI/PIB
    items via app.services.macro_extraction. Most items won't match — PIB/
    RBI press releases are often administrative notices with no numeric
    figure at all — and that's correct: only a genuinely parseable release
    gets a MacroRelease row, never a guessed one. Shares its id with the
    Event row created from the same RawItem (see _create_events) so the
    two can be joined without a formal foreign key."""
    if not items:
        return 0
    existing = await _existing_ids(db, MacroRelease, [i.id for i in items])
    saved = 0
    seen: set[str] = set()
    for item in items:
        if item.id in existing or item.id in seen:
            continue
        parsed = extract_macro_release(
            item.headline, item.summary, source=item.source,
            url=item.url, published_at=item.published_at,
        )
        if not parsed:
            continue
        seen.add(item.id)
        db.add(MacroRelease(id=item.id, event_id=item.id, **parsed))
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


# ── Job: policy ingest (RBI + PIB + SEBI + Fed) — every hour ─────────────────

async def job_ingest_policy() -> None:
    t0 = time.perf_counter()
    log.info("job.ingest_policy.start")

    rbi_items  = await RBIProvider().fetch_and_normalize()
    pib_items  = await PIBProvider().fetch_and_normalize()
    sebi_items = await SEBIProvider().fetch_and_normalize()
    fed_items  = await FedProvider().fetch_and_normalize()

    all_items = rbi_items + pib_items + sebi_items + fed_items

    async with AsyncSessionLocal() as db:
        new_ids = await _persist_articles(db, all_items)
        new_id_set = set(new_ids)
        policies_saved = await _persist_policies(db, all_items)
        events_created = await _create_events(db, all_items, new_id_set, "policy")
        # Macro extraction only makes sense for RBI/PIB — SEBI releases are
        # market-conduct/regulatory notices, not economic data prints.
        macro_saved = await _persist_macro_releases(db, rbi_items + pib_items)

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info(
        "job.ingest_policy.done",
        rbi=len(rbi_items), pib=len(pib_items), sebi=len(sebi_items), fed=len(fed_items),
        new_articles=len(new_ids),
        policies=policies_saved,
        new_events=events_created,
        macro_releases=macro_saved,
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

    # Free-tier data track, Stage 2 (2026-08-06): batch raised 5->10. Real
    # daily event volume right now is low (1-5/day typical, confirmed via
    # production query) and doesn't come close to saturating even the old
    # 5-per-5-min ceiling — this is headroom for burst days (one real day,
    # 2026-07-22, saw 50 events) rather than a fix for an active backlog,
    # since none exists today. Left _AI_DELAY and the 300s tick interval
    # unchanged — batch size doesn't change the per-call pacing rate (still
    # sequential, one call per _AI_DELAY within a tick), so this doesn't
    # increase pressure on DeepSeekProvider's own tenacity retry (3
    # attempts, exponential backoff), which stays untouched and unshared
    # with P0's priority system either way — just lets more events clear
    # per tick when a burst does happen.
    # EMERGENCY PAUSE (2026-08-09) LIFTED (2026-08-12): root cause was zero
    # pacing between the pipeline's 7 sequential AI-call stages WITHIN one
    # event — _AI_DELAY below only ever paced between different events, so
    # even a single event alone could burn through a free-tier provider's
    # per-minute quota on its own. event_pipeline.py now sleeps
    # _STAGE_DELAY=1.5s between its own AI-calling stages, which is the
    # "real pacing" this pause was waiting on. _safe_json_call's swallow-
    # and-fallback behavior on exhausted retries is UNCHANGED (touching the
    # shared AI-provider layer risked affecting every other caller — AIPE,
    # AI Search — not just this one pipeline).
    #
    # Correction (2026-08-13, re-audit): the paragraph that used to be here
    # said the "completes as done with impact_score=None" trap was still
    # open. It's now PARTIALLY closed — event_pipeline.py's classify-stage
    # health probe (_CLASSIFY_FALLBACK check) catches the case where the AI
    # is unavailable from the very first call and marks the event 'failed'
    # instead, which get_pending_enrichment already retries. What's still
    # genuinely open: (1) intermittent/partial failure — the AI answers
    # stage 2 for real but then falls back on stage 4, 6, or 8 — still
    # completes as 'done' with partially-fallback data, undetected; (2) no
    # retry cap or backoff — get_pending_enrichment orders by
    # created_at DESC across pending+failed+stale-processing with no
    # retry_count, so a repeatedly-failing old event can be starved
    # indefinitely once enough newer pending events exist, with no
    # dead-letter signal when that happens. Neither is fixed in this pass;
    # both are called out explicitly in this audit's final report rather
    # than left implied.
    #
    # Batch/delay: restarting at a conservative batch (3, not the
    # pre-incident 10) given real volume is 1-5/day typical (confirmed via
    # production query) — this is headroom, not a backlog-clearing push.
    # Watch enrichment_status='pending' counts after this ships; raise back
    # toward 10 only once a few days confirm no repeat rate-limit storm.
    _BATCH = 3
    _AI_DELAY = 3  # seconds between AI calls (raised from 2s alongside the new inter-stage pacing)

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

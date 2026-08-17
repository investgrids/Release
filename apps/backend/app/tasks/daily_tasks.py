"""
Daily tasks — run once per day.

6:00 AM IST:  job_daily_generate  — compute intelligence from DB
7:00 AM IST:  job_daily_precompute — write full API response to Redis
7:30 AM IST:  job_daily_opportunities — generate new opportunities
Startup once: job_seed_opportunities — seed if table is empty
"""
from __future__ import annotations

import time

import structlog

log = structlog.get_logger(__name__)


# ── 5:30 AM — Refresh Fyers access token ─────────────────────────────────────

async def job_refresh_fyers_token() -> None:
    """
    Regenerate the Fyers access token every morning before market open.

    Uses TOTP-based automated login — no user interaction needed.
    Runs at 5:30 AM IST so the token is ready well before 9:15 AM open.
    No-op (silent) if TOTP credentials are not configured in env.
    """
    log.info("job.fyers_token_refresh.start")
    try:
        from app.services.market_data_service import upgrade_to_fyers
        success = await upgrade_to_fyers()
        log.info("job.fyers_token_refresh.done", success=success)
    except Exception as exc:
        log.error("job.fyers_token_refresh.error", error=str(exc))


# ── 6:00 AM — Generate market intelligence objects ───────────────────────────

async def job_daily_generate() -> None:
    """
    Compute and store precomputed intelligence objects:
    - AI market wrap summary
    - Dashboard trending events (top 5 by impact)
    - Sector intelligence snapshots
    - Stories refresh
    """
    t0 = time.perf_counter()
    log.info("job.daily_generate.start")

    # 1. AI market summary
    await _refresh_ai_summary()

    # 2. Sector performance from yfinance
    await _refresh_sector_intelligence()

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info("job.daily_generate.done", elapsed_ms=elapsed)


async def _refresh_ai_summary() -> None:
    """Regenerate and cache the AI market summary."""
    from app.db.session import AsyncSessionLocal
    from app.db.crud import get_trending_events
    from app.services.market_data import get_index_quotes
    from app.services.ai_service import get_market_summary
    from app.cache import set as cache_set, DASHBOARD_AI_KEY, TTL_AI

    try:
        async with AsyncSessionLocal() as db:
            events = await get_trending_events(db, limit=5)
        index_quotes = await get_index_quotes()
        event_dicts  = [
            {"title": e.title, "impact_score": e.impact_score}
            for e in events
        ]
        summary = await get_market_summary(index_quotes, event_dicts, priority="background")
        if summary:
            await cache_set(DASHBOARD_AI_KEY, {"text": summary}, TTL_AI)
            log.info("daily.ai_summary.refreshed")
    except Exception as exc:
        log.error("daily.ai_summary.error", error=str(exc))


async def _refresh_sector_intelligence() -> None:
    """Pre-warm extended indices cache."""
    from app.services.market_data import get_extended_indices
    from app.cache import set as cache_set, TTL_MARKET

    try:
        indices = await get_extended_indices()
        if indices:
            await cache_set("indices:extended:v1", indices, TTL_MARKET * 10)
            log.info("daily.sector_intelligence.refreshed", count=len(indices))
    except Exception as exc:
        log.error("daily.sector_intelligence.error", error=str(exc))


# ── 7:00 AM — Precompute full dashboard API response ─────────────────────────

async def job_daily_precompute() -> None:
    """
    Build the complete /api/dashboard response and write it to Redis.
    Target: < 100 ms API response from this point on.
    """
    t0 = time.perf_counter()
    log.info("job.daily_precompute.start")

    payload = await _build_dashboard_payload()
    if payload:
        from app.cache import set as cache_set, DASHBOARD_KEY, TTL_DASHBOARD
        await cache_set(DASHBOARD_KEY, payload, TTL_DASHBOARD)
        log.info("job.daily_precompute.cached", keys=list(payload.keys()))

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info("job.daily_precompute.done", elapsed_ms=elapsed)


async def _build_dashboard_payload() -> dict | None:
    """Assemble the full dashboard response dict from DB + market data."""
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.db.crud import get_trending_events
    from app.services.market_data import get_index_quotes, get_top_movers
    from app.services.ai_service import get_market_summary
    from app.cache import get as cache_get, DASHBOARD_AI_KEY

    try:
        async with AsyncSessionLocal() as db:
            events = await get_trending_events(db, limit=5)

        index_quotes, movers = await asyncio.gather(
            get_index_quotes(),
            get_top_movers(),
            return_exceptions=True,
        )
        if isinstance(index_quotes, Exception): index_quotes = []
        if isinstance(movers, Exception):       movers = {}

        # AI summary from cache (generated at 6 AM) or live fallback
        cached_ai = await cache_get(DASHBOARD_AI_KEY)
        ai_text   = (cached_ai or {}).get("text", "")
        if not ai_text:
            event_dicts = [{"title": e.title, "impact_score": e.impact_score} for e in events]
            ai_text = await get_market_summary(index_quotes, event_dicts, priority="background")

        trending = [
            {
                "id":           e.id,
                "title":        e.title,
                "summary":      e.summary,
                "category":     e.category or "Macro",
                "impact_score": e.impact_score,
                "confidence":   e.confidence,
                "sectors":      e.sectors,
                "companies":    e.companies,
                "date":         e.published_at.isoformat() if e.published_at else None,
            }
            for e in (events or [])
        ]

        market_snapshot = {
            q["title"].lower().replace(" ", "_"): q["value"]
            for q in (index_quotes or [])
        }

        return {
            "market_snapshot": market_snapshot,
            "index_quotes":    index_quotes or [],
            "aiSummary":       ai_text,
            "trending_events": trending,
            "top_movers":      movers or {},
            "_precomputed_at": time.time(),
        }
    except Exception as exc:
        log.error("daily_precompute.build_error", error=str(exc))
        return None


# ── 7:30 AM — Opportunity pipeline ───────────────────────────────────────────

async def job_daily_opportunities() -> None:
    """Group recent news articles into Opportunity records via AI."""
    t0 = time.perf_counter()
    log.info("job.daily_opportunities.start")

    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models_legacy import NewsArticle
    from app.pipeline.classifier import classify_text
    from app.pipeline.opportunity_generator import generate_opportunity_from_events

    _MIN_GROUP = 3
    cutoff = datetime.now(timezone.utc) - timedelta(hours=26)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(NewsArticle)
            .where(NewsArticle.created_at >= cutoff)
            .order_by(NewsArticle.impact_score.desc())
            .limit(200)
        )
        articles = [
            {
                "id": r.id, "title": r.headline, "summary": r.summary,
                "published_at": r.published_at, "category": "General",
                "companies": r.companies or [],
            }
            for r in result.scalars().all()
        ]

    if len(articles) < _MIN_GROUP:
        log.info("job.daily_opportunities.skipped", reason="insufficient_articles")
        return

    groups: dict[str, list] = {}
    for art in articles:
        text = f"{art['title']} {art['summary']}"
        res  = classify_text(text)
        sector = (res.get("sectors") or ["General"])[0]
        groups.setdefault(sector, []).append(art)

    generated = 0
    async with AsyncSessionLocal() as db:
        for sector, group in groups.items():
            if len(group) < _MIN_GROUP:
                continue
            try:
                opp = await generate_opportunity_from_events(db, group[:10])
                if opp:
                    generated += 1
            except Exception as exc:
                log.error("job.daily_opportunities.error", sector=sector, error=str(exc))

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info("job.daily_opportunities.done", generated=generated, elapsed_ms=elapsed)


# ── Pre-market cache warmup — 8:00 AM IST ────────────────────────────────────

async def job_warm_premarket() -> None:
    """Pre-fetch Asian/US/commodity data at 8 AM so it's cached before 9 AM open."""
    from app.services.market_data import get_premarket_data
    log.info("job.warm_premarket.start")
    try:
        data = await get_premarket_data()
        asian_count = len(data.get("asian", []))
        us_count = len(data.get("us", []))
        log.info("job.warm_premarket.done", asian=asian_count, us=us_count)
    except Exception as exc:
        log.error("job.warm_premarket.error", exc=str(exc))


# ── 4:00 PM IST — Evaluate predictions against market outcomes ───────────────

async def job_evaluate_predictions() -> None:
    """
    Compare stored predictions against actual market data.
    Runs after market close (4:00 PM IST) so day-1 predictions have a full session.
    Also recomputes calibration stats after evaluation.
    """
    import time as _time
    t0 = _time.perf_counter()
    log.info("job.evaluate_predictions.start")
    try:
        from app.services.prediction_evaluator import run_evaluation_cycle
        stats = await run_evaluation_cycle()
        elapsed = round((_time.perf_counter() - t0) * 1000)
        log.info("job.evaluate_predictions.done", elapsed_ms=elapsed, **stats)
    except Exception as exc:
        log.error("job.evaluate_predictions.error", error=str(exc))


# ── 4:30 PM IST — Quant Intelligence: incremental daily OHLCV refresh ────────

async def job_quant_price_refresh() -> None:
    """
    Phase 2B §4/§20 — refresh the PriceBar warehouse for the NIFTY 50 V1
    universe. Scheduled after job_evaluate_predictions (4:00 PM) so both
    post-close jobs don't compete for yfinance calls at the same instant
    (Phase 2A §20's own finding: this window was open before Phase 2B).
    Optional by design (Phase 2A §29) — a failure here never raises past
    this wrapper, and nothing else in the app reads PriceBar synchronously
    on the request path, so a missed refresh degrades to "tomorrow's
    baseline generation sees slightly stale history," never an outage.
    """
    import time as _time
    t0 = _time.perf_counter()
    log.info("job.quant_price_refresh.start")
    try:
        from app.services.quant.refresh import run_daily_refresh
        stats = await run_daily_refresh()
        elapsed = round((_time.perf_counter() - t0) * 1000)
        log.info("job.quant_price_refresh.done", elapsed_ms=elapsed,
                  succeeded=stats["succeeded"], failed=stats["failed"],
                  bars_inserted=stats["total_bars_inserted"])
    except Exception as exc:
        log.error("job.quant_price_refresh.error", error=str(exc))


# ── 5:00 PM IST — Intelligence Observation snapshot (Phase 2E.1) ────────────

async def job_intelligence_observation_snapshot() -> None:
    """
    Phase 2E.1 — write one CompanyIntelligenceObservation row per NIFTY 50
    symbol, using the same safe-source evidence (EventTriage,
    AICompanySignal, CompanyAnnouncement) the Phase 2E.2 pilot reads.
    Scheduled after job_quant_price_refresh (4:30 PM) so the day's price
    data is already in the warehouse before this runs, though this job
    itself only reads intelligence tables, not PriceBar. Never mutates a
    prior observation — always inserts a fresh row — so this table can
    never end up on the "silently overwritten" list the Phase 2E audit
    found elsewhere. A failure here never raises past this wrapper —
    same optional-by-design convention as quant_price_refresh.
    """
    import time as _time
    t0 = _time.perf_counter()
    log.info("job.intelligence_observation_snapshot.start")
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.intelligence_research.observation_builder import build_daily_observations
        async with AsyncSessionLocal() as db:
            stats = await build_daily_observations(db)
        elapsed = round((_time.perf_counter() - t0) * 1000)
        log.info("job.intelligence_observation_snapshot.done", elapsed_ms=elapsed, stored=stats["stored"])
    except Exception as exc:
        log.error("job.intelligence_observation_snapshot.error", error=str(exc))


# ── 3:00 AM IST — Economic Calendar full sync (Phase 5A.7) ──────────────────

async def job_economic_calendar_full_sync() -> None:
    """
    Phase 5A.7 — daily full sync of every real (Tier 1) economic
    calendar source: RBI MPC, MOSPI CPI/IIP, Fed FOMC, BLS CPI, BLS
    jobs. Scheduled at a quiet hour, clear of both market-open (9:15 AM
    IST) and the existing 16:30/17:00 IST quant/observation jobs — this
    is a pure external-fetch job, not a market-data-dependent one, so
    there's no reason to compete with those for the same window.
    Delegates entirely to sync_orchestrator.run_full_sync(), which
    isolates each source's failure from the others (one source down
    never blocks the rest) and logs a loud, distinct warning if EVERY
    source returns zero rows on the same run — a much stronger signal
    of a shared parsing/site-change problem than a routine per-source
    miss. No frontend/API writes, no LLM calls happen here — this job
    only reaches EconomicCalendarEvent via the existing sync engine.
    """
    import time as _time
    t0 = _time.perf_counter()
    log.info("job.economic_calendar_full_sync.start")
    try:
        from app.services.economic_calendar.sync_orchestrator import run_full_sync
        summary = await run_full_sync()
        elapsed = round((_time.perf_counter() - t0) * 1000)
        log.info("job.economic_calendar_full_sync.done", elapsed_ms=elapsed,
                  total_fetched=summary["total_fetched"],
                  results=[{"source": r["source"], "ok": r.get("ok"), "fetched": r.get("fetched", 0)} for r in summary["results"]])
    except Exception as exc:
        log.error("job.economic_calendar_full_sync.error", error=str(exc))


# ── Every 6 hours IST — Economic Calendar imminent recheck (Phase 5A.7) ─────

async def job_economic_calendar_imminent_recheck() -> None:
    """
    Phase 5A.7 — owner's explicit instruction: "do not repeatedly poll
    every source all day." Runs 4x/day, but only actually re-fetches a
    source when it has a real, already-stored, is_current row scheduled
    within the next ~24 hours — otherwise it's a single cheap DB query
    and no network calls at all. Catches a same-day postponement or
    cancellation of an imminent release without polling sources that
    have nothing coming up soon.
    """
    import time as _time
    t0 = _time.perf_counter()
    log.info("job.economic_calendar_imminent_recheck.start")
    try:
        from app.services.economic_calendar.sync_orchestrator import run_imminent_recheck
        summary = await run_imminent_recheck()
        elapsed = round((_time.perf_counter() - t0) * 1000)
        log.info("job.economic_calendar_imminent_recheck.done", elapsed_ms=elapsed,
                  checked_sources=summary.get("checked_sources", []))
    except Exception as exc:
        log.error("job.economic_calendar_imminent_recheck.error", error=str(exc))


# ── Every 6 hours IST — Macro Rate Intelligence sync (Phase 5F.3) ───────────

async def job_macro_rates_sync() -> None:
    """
    Phase 5F.3 — Phase 5C's macro_rates package (US Treasury, Fed H.15,
    RBI WSS) had no scheduled job at all: get_macro_rate_state() was
    only ever called reactively, from opening_prediction_service.py's
    on-demand requests and weekend_intelligence's Sat/Sun-only
    checkpoint cycle. On an ordinary weekday with no request triggering
    that path within its own 6h TTL, the cache could go stale with zero
    visibility — confirmed by audit as a real, currently-invisible gap,
    the same class already found and fixed for BSE (Phase 5D) and event
    enrichment (Phase 5F.2a). This job keeps the cache genuinely warm on
    a fixed schedule and gives source_health a real signal for these 3
    sources (also added this phase — see source_health.py's
    KNOWN_SOURCES) instead of depending entirely on traffic patterns.
    Scheduled every 6h to exactly match get_macro_rate_state's own TTL,
    offset from the economic-calendar imminent-recheck slots so they
    don't compete for the same window.
    """
    import time as _time
    t0 = _time.perf_counter()
    log.info("job.macro_rates_sync.start")
    try:
        from app.services.macro_rates.service import get_macro_rate_state
        state = await get_macro_rate_state(force_refresh=True)
        elapsed = round((_time.perf_counter() - t0) * 1000)
        log.info(
            "job.macro_rates_sync.done", elapsed_ms=elapsed,
            india_data_status=state.india_data_status, us_data_status=state.us_data_status,
            interest_rate_trend=state.interest_rate_trend,
        )
    except Exception as exc:
        log.error("job.macro_rates_sync.error", error=str(exc))


# ── Startup once — seed opportunities if table is empty ─────────────────────

async def job_seed_opportunities() -> None:
    """Seed static radar opportunities on first run if table is empty."""
    from sqlalchemy import select, func
    from app.db.session import AsyncSessionLocal
    from app.db.models.opportunity import Opportunity

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(Opportunity))).scalar()
        if count and count > 0:
            log.debug("job.seed_opportunities.skip", existing=count)
            return

    log.info("job.seed_opportunities.start")
    # Delegate to the existing opportunity worker seed logic
    from app.workers.opportunity_worker import _seed_static_opportunities
    async with AsyncSessionLocal() as db:
        await _seed_static_opportunities(db)
    log.info("job.seed_opportunities.done")


# ── 2:00 AM IST — Backup the database ────────────────────────────────────────

async def job_backup_database() -> None:
    """Snapshot the database to the persistent volume. Off-peak hour so the
    (brief) SQLite backup-API lock doesn't compete with live traffic."""
    import asyncio
    from app.db.backup import backup_database

    log.info("job.backup_database.start")
    result = await asyncio.to_thread(backup_database)
    log.info("job.backup_database.done", **result)


# ── Startup once — repair evergreen articles contaminated by the ───────────
# continuous updater's global-market-mood injection bug (fixed in
# continuous_updater.py's find_updatable_articles, which now excludes
# is_evergreen articles from its eligibility query going forward). This job
# only cleans up rows the OLD, buggy version already wrote before that fix
# shipped — confirmed live: an ITC-vs-HUL comparison page showing a
# key_takeaway about Cholamandalam Finance Q1 results, and a why_it_matters
# block with an unrelated appended "Update HH:MM AM/PM IST" market-pulse
# note, neither of which has anything to do with ITC or HUL.
#
# Naturally idempotent — repaired rows have update_count reset to 0, so the
# `update_count > 0` filter below never matches them again on a later boot.
import re as _re
_UPDATE_NOTE_RE = _re.compile(r"\n\n\*\*Update \d{1,2}:\d{2} [AP]M IST:\*\*.*", _re.DOTALL)


async def job_repair_evergreen_contamination() -> None:
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_article import IntelligenceArticle

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.is_evergreen.is_(True))
            .where(IntelligenceArticle.update_count > 0)
        )
        rows = result.scalars().all()
        if not rows:
            log.debug("job.repair_evergreen_contamination.skip", found=0)
            return

        log.info("job.repair_evergreen_contamination.start", found=len(rows))
        for a in rows:
            # The original key_takeaway is unrecoverable (overwritten in
            # place, not versioned before this fix) — executive_summary is
            # real, on-topic content already on the same row, so it's the
            # honest substitute rather than leaving contaminated text live.
            a.key_takeaway = a.executive_summary or None
            why = a.why_it_matters or ""
            cleaned = _UPDATE_NOTE_RE.sub("", why).strip()
            a.why_it_matters = cleaned or None
            # Unrecoverable and, per this app's own "never fabricate" rule,
            # better empty than false — same principle already applied
            # elsewhere (e.g. highestRiskDisplay's honest fallback strings).
            a.what_to_watch_next = []
            a.update_history = []
            a.update_count = 0
            a.last_updated = None
            a.lifecycle_status = "published"
            db.add(a)
            log.info("job.repair_evergreen_contamination.fixed", slug=a.slug)

        await db.commit()
        log.info("job.repair_evergreen_contamination.done", repaired=len(rows))


async def job_repair_event_slugs() -> None:
    """One-off backfill for the "nse-" slug leak found live (2026-08-08):
    every event slug used to end with eid[:8] as its collision
    disambiguator, and since ids look like "nse-4cc93acbc1", that suffix
    is literally "nse-4cc9" — the source prefix embedded in what's meant to
    be an opaque-source-id-free public URL. event_pipeline.py's slug
    generator (_make_unique_slug) already stopped doing this for new
    events; this repairs everything ingested before that fix.

    Regenerates only the affected rows (slug ending in a source prefix +
    hex fragment), using the same app-owned numeric-suffix collision
    strategy new events already get. middleware.ts's 301 redirect covers
    every already-indexed/bookmarked URL built from the OLD slug — this
    repair doesn't need to preserve them, just stop generating new ones.

    Naturally idempotent — a repaired slug no longer matches the pattern,
    so later boots find nothing left to do.

    Detection is deliberately a broad substring match, not a regex trying
    to reverse-engineer eid[:8]'s exact old shape — found live, that
    disambiguator produced at least three different tail shapes depending
    on the source id's own format ("-nse-4cc9", a bare trailing "-nse-"
    for ids with a doubled "nse-nse-" prefix, and single-character tails
    like "-nse-bm-f" for "nse-bm-..." ids). A normal title-derived slug
    essentially never organically contains "-nse-" or "-bse-" as
    substrings, so treating any hit as a leak is safe and doesn't need to
    match the bug's exact historical output shape.

    Also repairs NULL/empty slugs and slugs starting with "nse-"/"bse-"
    outright — found live (2026-08-08 final SEO audit): a freshly-ingested
    event's row can exist with slug=NULL for the short window between
    insert and _make_unique_slug assigning it, and the sitemap route (with
    its own 1-hour fetch cache) can capture that window and bake a raw
    "nse-bm-..." URL into what it serves. The sitemap's own query now
    filters out slug-less events rather than falling back to the id (see
    sitemap.xml/route.ts's hasCleanSlug), so this no longer reaches a
    user — but a NULL/empty slug is also just a real, incomplete row this
    job should finish, same as any other unassigned slug."""
    from sqlalchemy import select, or_
    from app.db.session import AsyncSessionLocal
    from app.db.models.event import Event
    from app.repositories.event_repository import EventRepository
    from app.pipeline.event_pipeline import _make_unique_slug

    async with AsyncSessionLocal() as db:
        leaked = (await db.execute(
            select(Event).where(or_(
                Event.slug.is_(None),
                Event.slug == "",
                Event.slug.like("nse-%"),
                Event.slug.like("bse-%"),
                Event.slug.like("%-nse-%"),
                Event.slug.like("%-bse-%"),
            ))
        )).scalars().all()
        if not leaked:
            log.debug("job.repair_event_slugs.skip", found=0)
            return

        log.info("job.repair_event_slugs.start", found=len(leaked))
        repo = EventRepository(db)
        for e in leaked:
            old_slug = e.slug
            e.slug = await _make_unique_slug(repo, e.title or "", exclude_id=e.id)
            db.add(e)
            log.info("job.repair_event_slugs.fixed", id=e.id, old_slug=old_slug, new_slug=e.slug)
        await db.commit()
        log.info("job.repair_event_slugs.done", repaired=len(leaked))


async def job_repair_unfilled_placeholders() -> None:
    """One-off cleanup of already-published articles containing a literal
    unfilled template placeholder (e.g. "On [specific date], tensions
    escalated..." — confirmed live in a ripple_intelligence article). The
    quality gate (quality_validator.py's no_unfilled_placeholders check) now
    blocks this from being published going forward; this only cleans up
    what already got through before that check existed. Mechanical text
    removal, not a rewrite — no attempt to guess what the real date/value
    should have been, since that would risk fabricating a fact.

    Naturally idempotent — a repaired row no longer matches the pattern, so
    later boots find nothing to do for it."""
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.aipe.quality_validator import _PLACEHOLDER_RE

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.status == "published")
        )
        # "On [specific date], X happened" is the exact live pattern found —
        # removing just the bracket leaves a dangling "On , X happened".
        # Strip the common leading preposition + placeholder + comma
        # together where present, so the sentence starts clean; the plain
        # bracket-only removal below is the fallback for anywhere else the
        # placeholder shows up mid-sentence.
        leading_re = _re.compile(
            r"^(On|In|During|At|Since)\s+" + _PLACEHOLDER_RE.pattern + r"\s*,\s*",
            _re.IGNORECASE,
        )
        def _clean(val: str) -> str:
            cleaned = leading_re.sub("", val)
            cleaned = _PLACEHOLDER_RE.sub("", cleaned)
            cleaned = " ".join(cleaned.split())  # collapse leftover double-spaces
            if cleaned and cleaned[0].islower():
                cleaned = cleaned[0].upper() + cleaned[1:]
            return cleaned

        rows = result.scalars().all()
        fixed = 0
        for a in rows:
            changed = False
            for field in ("headline", "executive_summary", "key_takeaway", "why_it_matters", "what_happened"):
                val = getattr(a, field, None)
                if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
                    setattr(a, field, _clean(val))
                    changed = True
            # Same leak, list-shaped fields (see quality_validator.py's
            # _PLACEHOLDER_LIST_FIELDS — the live gate now checks these too;
            # this repairs anything already published before that widening).
            for field in ("opportunities", "risks", "faqs"):
                items = getattr(a, field, None) or []
                new_items = []
                field_changed = False
                for item in items:
                    if not isinstance(item, dict):
                        new_items.append(item)
                        continue
                    new_item = dict(item)
                    for key in ("title", "description", "question", "answer"):
                        val = new_item.get(key)
                        if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
                            new_item[key] = _clean(val)
                            field_changed = True
                    new_items.append(new_item)
                if field_changed:
                    setattr(a, field, new_items)
                    changed = True
            watch = a.what_to_watch_next or []
            if any(isinstance(w, str) and _PLACEHOLDER_RE.search(w) for w in watch):
                a.what_to_watch_next = [_clean(w) if isinstance(w, str) else w for w in watch]
                changed = True
            if changed:
                db.add(a)
                fixed += 1
                log.info("job.repair_unfilled_placeholders.fixed", slug=a.slug)

        if fixed:
            await db.commit()
        log.info("job.repair_unfilled_placeholders.done", repaired=fixed)


async def job_repair_comparison_missing_fields() -> None:
    """One-off backfill of what_happened/why_it_matters on already-published
    comparison_intelligence articles that predate compose_what_happened/
    compose_why_it_matters (comparison_publisher.py) — computed from each
    row's OWN already-stored market_context.decision_intelligence, no fresh
    LLM call needed. Naturally idempotent: a row with both fields already
    set is skipped, so a later boot finds nothing left to do."""
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.aipe.comparison_publisher import compose_what_happened, compose_why_it_matters

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.article_type == "comparison_intelligence")
            .where(IntelligenceArticle.status == "published")
        )).scalars().all()

        fixed = 0
        for a in rows:
            if a.what_happened and a.why_it_matters:
                continue
            di = ((a.market_context or {}).get("decision_intelligence")) or {}
            if not di:
                continue
            companies = a.companies_affected or []
            name_a = companies[0].get("name") if len(companies) > 0 else None
            name_b = companies[1].get("name") if len(companies) > 1 else None
            if not name_a or not name_b:
                continue
            changed = False
            if not a.what_happened:
                wh = compose_what_happened(di, name_a, name_b)
                if wh:
                    a.what_happened = wh
                    changed = True
            if not a.why_it_matters:
                wim = compose_why_it_matters(di, name_a, name_b)
                if wim:
                    a.why_it_matters = wim
                    changed = True
            if changed:
                db.add(a)
                fixed += 1
                log.info("job.repair_comparison_missing_fields.fixed", slug=a.slug)

        if fixed:
            await db.commit()
        log.info("job.repair_comparison_missing_fields.done", repaired=fixed)


_UPDATE_NOTE_BLOCK_RE = _re.compile(
    r"\n\n\*\*Update \d{1,2}:\d{2} [AP]M IST:\*\*.*?(?=\n\n\*\*Update \d{1,2}:\d{2} [AP]M IST:\*\*|\Z)",
    _re.DOTALL,
)


async def job_repair_why_it_matters_bloat() -> None:
    """One-off cleanup of already-published, non-evergreen articles whose
    why_it_matters accumulated many stacked "**Update HH:MM AM IST:**" notes
    instead of the single latest one — the old continuous_updater dedup
    check (`update_note[:50] not in current`) always included the fresh
    timestamp in those 50 chars, so it never matched and every update cycle
    just appended. Confirmed live: one article had 34 stacked notes, 8.7KB,
    many near-identical, across 35 updates. continuous_updater.py now
    replaces rather than appends going forward; this repairs what already
    accumulated before that fix, keeping only the base explanation + the
    single most recent update note. Naturally idempotent — a repaired row
    has at most one update block left, so later boots find nothing to do."""
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_article import IntelligenceArticle

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.status == "published")
            .where(IntelligenceArticle.is_evergreen.isnot(True))
        )).scalars().all()

        fixed = 0
        for a in rows:
            why = a.why_it_matters or ""
            blocks = _UPDATE_NOTE_BLOCK_RE.findall(why)
            if len(blocks) <= 1:
                continue
            base = _UPDATE_NOTE_RE.sub("", why).strip()
            a.why_it_matters = base + blocks[-1]
            db.add(a)
            fixed += 1
            log.info("job.repair_why_it_matters_bloat.fixed", slug=a.slug, blocks_removed=len(blocks) - 1)

        if fixed:
            await db.commit()
        log.info("job.repair_why_it_matters_bloat.done", repaired=fixed)


async def job_repair_pipe_enum_leaks() -> None:
    """One-off cleanup of already-published articles carrying a literal
    unresolved pipe-joined enum value (e.g. companies_affected[].impact =
    "positive|neutral", opportunities[].timeframe = "months|years") —
    confirmed live, renders on the frontend as garbled text like
    "Positive|Neutral". Same normalization as article_generator.py's
    _normalize_pipe_enum_leaks (now applied going forward at generation
    time); this only repairs rows published before that fix shipped.
    Naturally idempotent — a repaired row no longer contains "|", so later
    boots find nothing to do for it."""
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.aipe.article_generator import _ENUM_FIELD_SPECS

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.status == "published")
        )).scalars().all()

        fixed = 0
        for a in rows:
            changed = False
            for list_field, keys in _ENUM_FIELD_SPECS:
                items = getattr(a, list_field, None) or []
                new_items = []
                field_changed = False
                for item in items:
                    if not isinstance(item, dict):
                        new_items.append(item)
                        continue
                    new_item = dict(item)
                    for key in keys:
                        val = new_item.get(key)
                        if isinstance(val, str) and "|" in val:
                            first = val.split("|", 1)[0].strip()
                            if first:
                                new_item[key] = first
                                field_changed = True
                    new_items.append(new_item)
                if field_changed:
                    setattr(a, list_field, new_items)
                    changed = True
            if changed:
                db.add(a)
                fixed += 1
                log.info("job.repair_pipe_enum_leaks.fixed", slug=a.slug)

        if fixed:
            await db.commit()
        log.info("job.repair_pipe_enum_leaks.done", repaired=fixed)


async def job_backfill_company_signals() -> None:
    """One-off backfill of AICompanySignal rows for articles/opportunities
    published before the AI Company Intelligence Score engine shipped (see
    company_score_engine.py). Both extraction functions are already
    idempotent per source row (skip if signals exist for that source_id),
    so this is safe to leave registered permanently — a normal boot with
    nothing new to backfill just does a no-op pass over already-covered
    rows."""
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.db.models.opportunity import Opportunity
    from app.services.aipe.company_score_engine import extract_company_signals, extract_opportunity_signals

    async with AsyncSessionLocal() as db:
        articles = (await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.status == "published")
        )).scalars().all()
        article_signals = 0
        for a in articles:
            article_signals += await extract_company_signals(db, a, auto_commit=False)

        opportunities = (await db.execute(select(Opportunity))).scalars().all()
        opp_signals = 0
        for o in opportunities:
            opp_signals += await extract_opportunity_signals(db, o.id, o.created_at, auto_commit=False)

        # One commit for the whole backfill instead of one per article/
        # opportunity (up to ~300 individual commits on a boot with a large
        # existing corpus) — real, avoidable overhead on every deploy.
        if article_signals or opp_signals:
            await db.commit()

        log.info(
            "job.backfill_company_signals.done",
            articles_scanned=len(articles), article_signals=article_signals,
            opportunities_scanned=len(opportunities), opportunity_signals=opp_signals,
        )

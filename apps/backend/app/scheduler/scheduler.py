"""
APScheduler configuration.
Uses AsyncIOScheduler (no separate thread pool needed — all jobs are async).
IST timezone (UTC+5:30) used for daily jobs so 6 AM / 7 AM means IST.
"""
from __future__ import annotations

from datetime import timezone, timedelta

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=_IST)
    return _scheduler


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all background jobs on the scheduler."""
    from app.tasks.ingest_tasks import (
        job_ingest_news,
        job_ingest_policy,
        job_enrich_events,
    )
    from app.tasks.daily_tasks import (
        job_refresh_fyers_token,
        job_daily_generate,
        job_daily_precompute,
        job_daily_opportunities,
        job_opportunity_v2_shadow_pass,
        job_seed_opportunities,
        job_warm_premarket,
        job_evaluate_predictions,
        job_quant_price_refresh,
        job_intelligence_observation_snapshot,
        job_economic_calendar_full_sync,
        job_economic_calendar_imminent_recheck,
        job_macro_rates_sync,
        job_development_memory_sync,
        job_backup_database_daily,
        job_check_ingestion_silence,
    )
    from app.services.intelligence.theme_worker import run_theme_scoring
    from app.services.intelligence.price_monitor import run_price_monitor_cycle
    from app.services.intelligence.engine import refresh_mie_state

    # ── 5:30 AM — Fyers token refresh (before market open at 9:15 AM) ───────────
    scheduler.add_job(
        job_refresh_fyers_token,
        CronTrigger(hour=5, minute=30, timezone=_IST),
        id="fyers_token_refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── High-frequency ingest ─────────────────────────────────────────────────
    scheduler.add_job(
        job_ingest_news,
        IntervalTrigger(seconds=settings.ingest_news_interval_sec),
        id="ingest_news",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        job_ingest_policy,
        IntervalTrigger(seconds=settings.ingest_policy_interval_sec),
        id="ingest_policy",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        job_enrich_events,
        IntervalTrigger(seconds=settings.event_enrichment_interval_sec),
        id="enrich_events",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # ── Daily intelligence generation — 6:00 AM IST ───────────────────────────
    scheduler.add_job(
        job_daily_generate,
        CronTrigger(hour=settings.daily_generate_hour_ist, minute=0, timezone=_IST),
        id="daily_generate",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Daily precompute & cache warm — 7:00 AM IST ───────────────────────────
    scheduler.add_job(
        job_daily_precompute,
        CronTrigger(hour=settings.daily_precompute_hour_ist, minute=0, timezone=_IST),
        id="daily_precompute",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Daily opportunity pipeline (V1) — 7:30 AM IST ────────────────────────
    # V2-B, 2026-08-24: gated on the promotion flag — "when V1 stops
    # receiving new writes" IS this job no longer registering. Not deleted
    # (the owner's explicit non-goal for V2-B is deleting V1 code/tables) —
    # simply not scheduled once settings.opportunity_read_source="v2".
    if not settings.opportunity_v2_promoted:
        scheduler.add_job(
            job_daily_opportunities,
            CronTrigger(hour=7, minute=30, timezone=_IST),
            id="daily_opportunities",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )

    # ── Opportunity V2 shadow/production pass — 7:30 AM IST ──────────────────
    # Runs unconditionally, before AND after promotion (V2-B, 2026-08-24) —
    # this is what accumulates the real observation-window data a promotion
    # decision needs, and it's the ongoing sole writer once promoted. Same
    # time slot as V1's job above is deliberate (matches the original
    # remediation plan's "matching V1's own job_daily_opportunities()
    # schedule" instruction) — the two jobs write to entirely separate
    # tables (opportunities vs. opportunities_v2), so running them
    # concurrently is safe.
    scheduler.add_job(
        job_opportunity_v2_shadow_pass,
        CronTrigger(hour=7, minute=30, timezone=_IST),
        id="opportunity_v2_shadow_pass",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Pre-market cache warm — 8:00 AM IST ──────────────────────────────────
    scheduler.add_job(
        job_warm_premarket,
        CronTrigger(hour=8, minute=0, timezone=_IST),
        id="warm_premarket",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Prediction evaluation — 4:00 PM IST (after market close) ────────────
    scheduler.add_job(
        job_evaluate_predictions,
        CronTrigger(hour=16, minute=0, timezone=_IST),
        id="evaluate_predictions",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # ── Quant Intelligence: OHLCV daily refresh — 4:30 PM IST (Phase 2B §4/§20,
    #    after evaluate_predictions so both post-close jobs don't compete for
    #    yfinance calls at the same instant) ─────────────────────────────────
    scheduler.add_job(
        job_quant_price_refresh,
        CronTrigger(hour=16, minute=30, timezone=_IST),
        id="quant_price_refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # ── Intelligence Observation snapshot — 5:00 PM IST (Phase 2E.1) ────────
    scheduler.add_job(
        job_intelligence_observation_snapshot,
        CronTrigger(hour=17, minute=0, timezone=_IST),
        id="intelligence_observation_snapshot",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # ── Economic Calendar full sync — 3:00 AM IST (Phase 5A.7) — a quiet
    #    hour clear of market open (9:15 AM IST) and the 16:30/17:00 IST
    #    quant/observation jobs; this is a pure external-fetch job with no
    #    market-data dependency, so it has no reason to share that window ──
    scheduler.add_job(
        job_economic_calendar_full_sync,
        CronTrigger(hour=3, minute=0, timezone=_IST),
        id="economic_calendar_full_sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # ── Economic Calendar imminent recheck — every 6 hours IST (Phase 5A.7)
    #    — owner: "do not repeatedly poll every source all day." Offset from
    #    the full sync and other fixed jobs; only does real work (a network
    #    fetch) when something is actually scheduled within ~24h — see
    #    run_imminent_recheck's own single-DB-query short-circuit ──────────
    scheduler.add_job(
        job_economic_calendar_imminent_recheck,
        CronTrigger(hour="2,8,14,20", minute=30, timezone=_IST),
        id="economic_calendar_imminent_recheck",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Macro Rate Intelligence sync — every 6h IST (Phase 5F.3) — offset
    #    15 min from both the economic-calendar full sync (3:00) and its
    #    imminent recheck (2,8,14,20:30) so they never compete for the
    #    same window; matches get_macro_rate_state's own 6h TTL exactly
    #    so the cache never has a chance to go stale between runs ──────────
    scheduler.add_job(
        job_macro_rates_sync,
        CronTrigger(hour="3,9,15,21", minute=15, timezone=_IST),
        id="macro_rates_sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Development Memory sync — every 30 min (Phase 6A). Deliberately
    #    frequent relative to its own 2h lookback window (sync.py) so
    #    overlap is large and a missed run is harmless ───────────────────────
    scheduler.add_job(
        job_development_memory_sync,
        IntervalTrigger(minutes=30),
        id="development_memory_sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=900,
    )

    # ── Database backup — 2:00 AM IST (off-peak) ─────────────────────────────
    scheduler.add_job(
        job_backup_database_daily,
        CronTrigger(hour=2, minute=0, timezone=_IST),
        id="backup_database",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # ── Ingestion silence detector — every 30 minutes ────────────────────────
    # See job_check_ingestion_silence's own docstring: a real multi-day
    # EventTriage gap (2026-08-26 disk-full incident) went undetected for
    # weeks. This only logs (no DB write), so it keeps working during the
    # exact disk-full scenario it exists to catch.
    scheduler.add_job(
        job_check_ingestion_silence,
        IntervalTrigger(minutes=30),
        id="ingestion_silence_check",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # ── Theme scoring — every 10 minutes ─────────────────────────────────────
    scheduler.add_job(
        run_theme_scoring,
        IntervalTrigger(seconds=600),
        id="theme_scoring",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # ── Price threshold monitor — every 2 minutes ─────────────────────────────
    scheduler.add_job(
        run_price_monitor_cycle,
        IntervalTrigger(seconds=120),
        id="price_monitor",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )

    # ── Company Announcements ingestion — every 30 minutes ───────────────────
    from app.services.company_announcements_service import ingest_announcements
    scheduler.add_job(
        ingest_announcements,
        IntervalTrigger(seconds=1800),
        id="ingest_announcements",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # ── Market Intelligence Engine refresh — every 5 minutes ─────────────────
    # Aggregates all producer outputs (story, themes, events) into a single
    # cached state object. Every page consumes from this instead of running
    # its own isolated intelligence computation.
    scheduler.add_job(
        refresh_mie_state,
        IntervalTrigger(seconds=300),
        id="mie_refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # ── AIPE — Autonomous Intelligence Publishing Engine — every 5 minutes ──────
    from app.services.aipe.publisher import run_aipe_cycle, run_evergreen_cycle, run_historical_cycle
    scheduler.add_job(
        run_aipe_cycle,
        IntervalTrigger(seconds=300),
        id="aipe_publish_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # ── AIPE Evergreen — non-event-driven explainer content — 9:00 AM IST ───────
    scheduler.add_job(
        run_evergreen_cycle,
        CronTrigger(hour=9, minute=0, timezone=_IST),
        id="aipe_evergreen_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── AIPE Historical Intelligence — pattern pages, one per day — 9:30 AM IST ─
    scheduler.add_job(
        run_historical_cycle,
        CronTrigger(hour=9, minute=30, timezone=_IST),
        id="aipe_historical_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Comparison pages — up to 5 pairs/run, twice a day (10:00 AM & 3:00 PM
    # IST) — see comparison_scheduler.py's own docstring for the pair-
    # selection and staleness-refresh logic. Two runs/day (not one) so a
    # cycle interrupted by a run of quality-gate failures still gets a
    # second attempt at its remaining pairs the same day.
    from app.services.aipe.comparison_scheduler import run_comparison_cycle
    scheduler.add_job(
        run_comparison_cycle,
        CronTrigger(hour=10, minute=0, timezone=_IST),
        id="comparison_cycle_morning",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        run_comparison_cycle,
        CronTrigger(hour=15, minute=0, timezone=_IST),
        id="comparison_cycle_afternoon",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    # ── Media generation worker — every 60s ──────────────────────────────────
    # Drains the GeneratedMedia job queue (see app/services/media/). Decoupled
    # from AIPE on purpose — publishing never waits on this. Short interval
    # so a fresh article's hero image shows up quickly, but the worker itself
    # only claims a small batch per tick since the provider is slow under load.
    from app.services.media.image_worker import run_image_generation_cycle
    scheduler.add_job(
        run_image_generation_cycle,
        IntervalTrigger(seconds=60),
        id="media_generation",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # ── Live Intelligence signal publisher — every 5 minutes ─────────────────
    # P0-B (2026-09-01): the sole real writer for live-signal
    # IntelligenceArticle rows. Was previously GET /api/live-intelligence/
    # feed's own request-time side effect (a public, unauthenticated GET
    # creating/updating durable publication state on every cache-cold hit)
    # -- moved to this controlled, scheduled producer instead. Same 5-
    # minute cadence the feed's own cache TTL already used, so real page
    # freshness for users is unchanged; the feed handler itself is now
    # read-only (see live_intelligence.py, api/live_intelligence.py).
    from app.services.aipe.signal_publisher import run_signal_publish_cycle
    scheduler.add_job(
        run_signal_publish_cycle,
        IntervalTrigger(seconds=300),
        id="signal_publish_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # Same decoupling principle as media_generation above — publish_signal
    # (now run_signal_publish_cycle's own scheduled job, see above) stays
    # fast and LLM-free; this separately, asynchronously backfills real
    # why_it_matters/what_happened/opportunities/risks/FAQs onto live_signal
    # rows that are still thin (see signal_publisher.py's enrichment section
    # docstring — roadmap Stage 2's "Live Feed explanations" / "one-click
    # article generation from every feed item" ask).
    from app.services.aipe.signal_publisher import run_signal_enrichment_cycle
    scheduler.add_job(
        run_signal_enrichment_cycle,
        IntervalTrigger(seconds=300),
        id="signal_enrichment",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # ── Weekend Intelligence checkpoints — Sat/Sun 09:00 & 18:00 IST ─────────
    # Phase 1B (see WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §17/§27's
    # "Option C — scheduled checkpoints + dirty flag" recommendation). The
    # first day_of_week-restricted CronTrigger in this scheduler — every
    # other job here runs unrestricted 7 days a week; this is the one
    # genuinely new pattern this phase introduces, not a general scheduler
    # change. Same function backs both jobs (checkpoint label is computed
    # from the real current time inside run_weekend_checkpoint_cycle, not
    # hardcoded per job) — expensive synthesis only actually runs when the
    # checkpoint's own material-change gate says something changed (see
    # checkpoints.py); most firings are expected to be cheap no-ops.
    from app.services.weekend_intelligence.checkpoints import run_weekend_checkpoint_cycle
    scheduler.add_job(
        run_weekend_checkpoint_cycle,
        CronTrigger(hour=9, minute=0, day_of_week="sat,sun", timezone=_IST),
        id="weekend_intelligence_checkpoint_morning",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        run_weekend_checkpoint_cycle,
        CronTrigger(hour=18, minute=0, day_of_week="sat,sun", timezone=_IST),
        id="weekend_intelligence_checkpoint_evening",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    log.info("scheduler.jobs_registered", count=len(scheduler.get_jobs()))


async def start_scheduler() -> AsyncIOScheduler:
    """Build, register, and start the scheduler. Returns the running instance."""
    scheduler = get_scheduler()

    # Seed opportunities on startup if table is empty (one-time only)
    from app.tasks.daily_tasks import job_seed_opportunities, job_backup_database_boot
    scheduler.add_job(
        job_seed_opportunities,
        id="seed_opportunities_startup",
        max_instances=1,
        trigger="date",  # runs once immediately
    )

    # These boot-time repair/backfill jobs all used to fire with the exact
    # same immediate `trigger="date"` (no run_date), which APScheduler
    # doesn't serialize — they'd all start concurrently, each holding its
    # own full-table query result (every published article, now 226+ rows
    # in production and growing daily) in memory at once. Confirmed live:
    # a deploy crashed with "Worker was sent SIGKILL! Perhaps out of
    # memory?" during exactly this boot window. Staggering by run_date
    # forces them to run one at a time instead, bounding peak memory to
    # roughly one job's worth rather than all seven simultaneously — cheap
    # (adds well under 2 minutes to full boot-repair completion) and safe
    # (every one of these jobs is already independently idempotent).
    from datetime import datetime
    from app.tasks.daily_tasks import job_repair_evergreen_contamination, job_repair_unfilled_placeholders, job_repair_comparison_missing_fields, job_repair_why_it_matters_bloat, job_repair_pipe_enum_leaks, job_backfill_company_signals, job_repair_event_slugs

    _boot_now = datetime.now(timezone.utc)
    _boot_jobs = [
        (job_backup_database_boot, "backup_database_startup"),
        (job_repair_evergreen_contamination, "repair_evergreen_contamination_startup"),
        (job_repair_unfilled_placeholders, "repair_unfilled_placeholders_startup"),
        (job_repair_comparison_missing_fields, "repair_comparison_missing_fields_startup"),
        (job_repair_why_it_matters_bloat, "repair_why_it_matters_bloat_startup"),
        # Normalizes already-published articles' literal unresolved
        # pipe-enum values (see article_generator.py's
        # _normalize_pipe_enum_leaks, applied going forward at generation
        # time; this only repairs rows published before that fix).
        (job_repair_pipe_enum_leaks, "repair_pipe_enum_leaks_startup"),
        # SEO URL migration backfill — regenerates any event slug that
        # still leaks its source id ("...-nse-4cc9") via the old eid[:8]
        # disambiguator. See daily_tasks.py's job_repair_event_slugs.
        (job_repair_event_slugs, "repair_event_slugs_startup"),
        # Backfills AICompanySignal rows for articles/opportunities
        # published before the AI Company Intelligence Score engine
        # shipped (see daily_tasks.py's job_backfill_company_signals
        # docstring) — the heaviest of these jobs, scheduled last.
        (job_backfill_company_signals, "backfill_company_signals_startup"),
    ]
    for i, (job_fn, job_id) in enumerate(_boot_jobs):
        scheduler.add_job(
            job_fn,
            id=job_id,
            max_instances=1,
            trigger="date",
            run_date=_boot_now + timedelta(seconds=15 * i),
        )

    register_jobs(scheduler)
    scheduler.start()
    log.info("scheduler.started")
    return scheduler


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
    _scheduler = None

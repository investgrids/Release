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
        job_seed_opportunities,
        job_warm_premarket,
        job_evaluate_predictions,
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

    # ── Daily opportunity pipeline — 7:30 AM IST ─────────────────────────────
    scheduler.add_job(
        job_daily_opportunities,
        CronTrigger(hour=7, minute=30, timezone=_IST),
        id="daily_opportunities",
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
    from app.services.aipe.publisher import run_aipe_cycle
    scheduler.add_job(
        run_aipe_cycle,
        IntervalTrigger(seconds=300),
        id="aipe_publish_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    log.info("scheduler.jobs_registered", count=len(scheduler.get_jobs()))


async def start_scheduler() -> AsyncIOScheduler:
    """Build, register, and start the scheduler. Returns the running instance."""
    scheduler = get_scheduler()

    # Seed opportunities on startup if table is empty (one-time only)
    from app.tasks.daily_tasks import job_seed_opportunities
    scheduler.add_job(
        job_seed_opportunities,
        id="seed_opportunities_startup",
        max_instances=1,
        trigger="date",  # runs once immediately
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

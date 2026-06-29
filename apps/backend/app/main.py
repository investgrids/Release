"""
IG Market Intelligence — FastAPI application entry point.

Startup sequence:
  1. Configure structlog
  2. Create / migrate DB tables
  3. Seed initial content
  4. Start APScheduler (ingest + daily jobs)
  5. Warm the dashboard cache once if Redis is available

All long-running work happens in APScheduler jobs, not asyncio.create_task loops.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging

# Configure logging before anything else
configure_logging(level=settings.log_level, json_logs=settings.json_logs)
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. Database ───────────────────────────────────────────────────────────
    from app.db.session import engine
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("db.tables_ready")

    # ── 2. Seed ───────────────────────────────────────────────────────────────
    from app.db.session import AsyncSessionLocal
    from app.db.seed import seed

    async with AsyncSessionLocal() as db:
        await seed(db)
    log.info("db.seed_done")

    # ── 3. APScheduler ────────────────────────────────────────────────────────
    from app.scheduler import start_scheduler, stop_scheduler
    scheduler = await start_scheduler()

    # ── 4. Warm dashboard cache (async, non-blocking) ─────────────────────────
    asyncio.create_task(_warm_dashboard_cache(), name="cache-warmup")

    log.info("app.started", env="production" if settings.json_logs else "development")

    yield  # Application is live

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await stop_scheduler()
    from app.core.redis import close_redis
    await close_redis()
    await engine.dispose()
    log.info("app.stopped")


async def _warm_dashboard_cache() -> None:
    """Warm the dashboard cache once at startup if it's cold."""
    from app.cache import get as cache_get, DASHBOARD_KEY
    from app.tasks.daily_tasks import _build_dashboard_payload, job_seed_opportunities
    from app.cache import set as cache_set, TTL_DASHBOARD

    # Let the DB settle
    await asyncio.sleep(5)

    cached = await cache_get(DASHBOARD_KEY)
    if cached:
        log.info("cache.warmup.skipped", reason="already_warm")
        return

    log.info("cache.warmup.start")
    payload = await _build_dashboard_payload()
    if payload:
        await cache_set(DASHBOARD_KEY, payload, TTL_DASHBOARD)
        log.info("cache.warmup.done")
    else:
        log.warning("cache.warmup.failed")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="IG Market Intelligence API",
    description="Backend API for event-driven market intelligence",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import dashboard, events, news, stories, radar, calendar, stocks, sectors, indices  # noqa: E402

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(events.router,    prefix="/api/events",    tags=["events"])
app.include_router(news.router,      prefix="/api/news",      tags=["news"])
app.include_router(stories.router,   prefix="/api/stories",   tags=["stories"])
app.include_router(radar.router,     prefix="/api/radar",     tags=["radar"])
app.include_router(calendar.router,  prefix="/api/calendar",  tags=["calendar"])
app.include_router(stocks.router,    prefix="/api/stocks",    tags=["stocks"])
app.include_router(sectors.router,   prefix="/api/sectors",   tags=["sectors"])
app.include_router(indices.router,   prefix="/api/indices",   tags=["indices"])


@app.get("/health")
async def health_check():
    from app.cache import get as cache_get
    from app.db.session import engine
    redis_ok = False
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        redis_ok = r is not None
    except Exception:
        pass
    return {
        "status":   "ok",
        "redis":    "connected" if redis_ok else "unavailable",
        "database": settings.database_url.split("://")[0],
    }

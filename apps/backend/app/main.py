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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

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
        from app.db.schema_patches import apply_schema_patches
        await apply_schema_patches(conn)
    log.info("db.tables_ready")

    # ── 2. Seed ───────────────────────────────────────────────────────────────
    from app.db.session import AsyncSessionLocal
    from app.db.seed import seed

    async with AsyncSessionLocal() as db:
        await seed(db)
    from app.db.seed import seed_missing_stories, seed_missing_calendar, seed_missing_events
    async with AsyncSessionLocal() as db:
        await seed_missing_stories(db)
    async with AsyncSessionLocal() as db:
        await seed_missing_calendar(db)
    async with AsyncSessionLocal() as db:
        await seed_missing_events(db)
    log.info("db.seed_done")

    # ── 3. APScheduler ────────────────────────────────────────────────────────
    from app.scheduler import start_scheduler, stop_scheduler
    scheduler = await start_scheduler()

    # ── 4. Fyers auto-auth (TOTP) — upgrades provider before cache warmup ────
    asyncio.create_task(_try_fyers_upgrade(), name="fyers-auto-auth")

    # ── 5. Intelligence workers (TriageWorker + StoryEngine + EnrichmentWorker) ──
    from app.services.intelligence.triage_worker import get_triage_worker
    from app.services.intelligence.story_engine import get_story_engine
    from app.services.enrichment_worker import get_enrichment_worker
    _triage_worker = get_triage_worker()
    _story_engine  = get_story_engine()
    _enrichment_worker = get_enrichment_worker()
    await _triage_worker.start()
    await _story_engine.start()
    await _enrichment_worker.start()

    # ── 6. Warm caches (async, non-blocking) ─────────────────────────────────
    asyncio.create_task(_warm_dashboard_cache(), name="cache-warmup")
    asyncio.create_task(_warm_market_cache(), name="market-cache-warmup")
    asyncio.create_task(_seed_opportunities_if_empty(), name="opportunity-seed")
    asyncio.create_task(_warm_mie_state(), name="mie-warmup")
    asyncio.create_task(_seed_historical_memory(), name="historical-memory-seed")
    asyncio.create_task(_seed_intelligence_graph(), name="intelligence-graph-seed")

    log.info("app.started", env="production" if settings.json_logs else "development")

    yield  # Application is live

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await _triage_worker.stop()
    await _story_engine.stop()
    await _enrichment_worker.stop()
    await stop_scheduler()
    from app.core.redis import close_redis
    await close_redis()
    await engine.dispose()
    log.info("app.stopped")


async def _try_fyers_upgrade() -> None:
    """Try TOTP-based Fyers auth at startup. Swaps provider from YFinance → Fyers."""
    try:
        from app.services.market_data_service import upgrade_to_fyers
        await upgrade_to_fyers()
    except Exception as exc:
        log.warning("startup.fyers_upgrade_error error=%s", str(exc))


async def _seed_opportunities_if_empty() -> None:
    """Directly insert static opportunities on first boot without AI calls."""
    await asyncio.sleep(5)
    try:
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import select, func
        from app.db.models.opportunity import Opportunity, OpportunityCompany, OpportunityMetric
        import re

        async with AsyncSessionLocal() as db:
            count = (await db.execute(select(func.count()).select_from(Opportunity))).scalar_one()
            if count and count > 0:
                log.info("opportunities.already_seeded", count=count)
                return

        log.info("opportunities.empty_on_boot.seeding_direct")

        SEEDS = [
            {
                "slug": "ai-infrastructure-boom",
                "title": "AI Infrastructure Boom",
                "summary": "India's AI mission with ₹10,372 Cr allocation and data center capacity tripling by 2027 creates structural growth for infrastructure and technology companies.",
                "opportunity_score": 91.0, "confidence": 0.89, "trend": "Strongly Positive",
                "risk_level": "Medium", "time_horizon": "3-5 Years",
                "sectors": ["Infrastructure", "Technology"],
                "companies": [("TCS", "TCS"), ("INFY", "Infosys"), ("LTIM", "LTIMindtree"), ("NTPC", "NTPC")],
                "metrics": ("₹2.5L Cr+", "22-28%", "18-25%", "3-5 Years", "₹10,372 Cr TAM"),
            },
            {
                "slug": "railway-modernization",
                "title": "Railway Modernization Wave",
                "summary": "Record ₹2.65 lakh crore capex, Vande Bharat expansion, and Kavach safety rollout create a multi-year order pipeline for rail infrastructure companies.",
                "opportunity_score": 88.0, "confidence": 0.86, "trend": "Strongly Positive",
                "risk_level": "Low", "time_horizon": "3-5 Years",
                "sectors": ["Railways", "Infrastructure"],
                "companies": [("RVNL", "Rail Vikas Nigam"), ("IRCON", "Ircon International"), ("BEML", "BEML"), ("LT", "Larsen & Toubro")],
                "metrics": ("₹2.65L Cr", "18-24%", "20-28%", "3-5 Years", "₹8L Cr+ pipeline"),
            },
            {
                "slug": "green-energy-transition",
                "title": "Green Energy Transition",
                "summary": "India's 500 GW renewable target and ₹19,744 Cr green hydrogen mission drive long-term structural demand for clean energy producers and infrastructure players.",
                "opportunity_score": 85.0, "confidence": 0.83, "trend": "Positive",
                "risk_level": "Medium", "time_horizon": "5-7 Years",
                "sectors": ["Energy", "Infrastructure"],
                "companies": [("NTPC", "NTPC"), ("ADANIGREEN", "Adani Green"), ("TATAPOWER", "Tata Power"), ("SJVN", "SJVN")],
                "metrics": ("₹19,744 Cr+", "15-20%", "12-18%", "5-7 Years", "500 GW target"),
            },
            {
                "slug": "defence-indigenisation",
                "title": "Defence Manufacturing Indigenisation",
                "summary": "India's $5B defence export target and positive indigenisation list blocking 4,000+ imports creates a structural tailwind for domestic defence manufacturers.",
                "opportunity_score": 86.0, "confidence": 0.85, "trend": "Strongly Positive",
                "risk_level": "Low", "time_horizon": "3-5 Years",
                "sectors": ["Defence", "Manufacturing"],
                "companies": [("HAL", "HAL"), ("BEL", "Bharat Electronics"), ("BHEL", "BHEL"), ("COCHINSHIP", "Cochin Shipyard")],
                "metrics": ("₹40,000 Cr", "20-28%", "22-30%", "3-5 Years", "$5B export goal"),
            },
            {
                "slug": "digital-banking-transformation",
                "title": "Digital Banking Transformation",
                "summary": "UPI crossing 14 billion monthly transactions and RBI's CBDC rollout positions leading banks and fintech platforms for a decade of digital-led growth.",
                "opportunity_score": 84.0, "confidence": 0.82, "trend": "Positive",
                "risk_level": "Medium", "time_horizon": "1-3 Years",
                "sectors": ["Banking", "Technology"],
                "companies": [("HDFCBANK", "HDFC Bank"), ("ICICIBANK", "ICICI Bank"), ("SBIN", "State Bank of India"), ("KOTAKBANK", "Kotak Bank")],
                "metrics": ("₹50,000 Cr+", "18-22%", "15-20%", "1-3 Years", "₹1.4T UPI economy"),
            },
            {
                "slug": "ev-supply-chain-buildout",
                "title": "EV Supply Chain Build-out",
                "summary": "India's 1.5M EV unit sales and FAME III ₹25,000 Cr subsidy scheme accelerate EV adoption, benefiting OEMs, battery makers, and charging infrastructure players.",
                "opportunity_score": 82.0, "confidence": 0.80, "trend": "Positive",
                "risk_level": "High", "time_horizon": "3-5 Years",
                "sectors": ["Automotive", "Manufacturing"],
                "companies": [("TATAMOTORS", "Tata Motors"), ("MAHINDRA", "Mahindra"), ("BAJAJ-AUTO", "Bajaj Auto"), ("EXIDEIND", "Exide Industries")],
                "metrics": ("₹25,000 Cr", "25-35%", "20-28%", "3-5 Years", "₹50,000 Cr market"),
            },
        ]

        async with AsyncSessionLocal() as db:
            for s in SEEDS:
                opp = Opportunity(
                    slug=s["slug"], title=s["title"], summary=s["summary"],
                    opportunity_score=s["opportunity_score"], confidence=s["confidence"],
                    trend=s["trend"], risk_level=s["risk_level"],
                    time_horizon=s["time_horizon"], sectors=s["sectors"],
                    ai_summary={"matters": s["summary"], "benefits": "", "risks": [], "invalidate": "", "why_bullets": []},
                )
                db.add(opp)
                await db.flush()
                for sym, name in s["companies"]:
                    db.add(OpportunityCompany(
                        opportunity_id=opp.id, company_id=sym, company_name=name,
                        impact_score=0.8, confidence=0.8, impact_label="High", trend="up", reason="",
                    ))
                r, c, e, cy, m = s["metrics"]
                db.add(OpportunityMetric(
                    opportunity_id=opp.id,
                    revenue_potential=r, expected_cagr=c, eps_growth=e,
                    investment_cycle=cy, market_size=m,
                ))
            await db.commit()
        log.info("opportunities.seeded_direct", count=len(SEEDS))
    except Exception as exc:
        log.warning("opportunities.seed_failed", error=str(exc))


async def _warm_market_cache() -> None:
    """Pre-warm indices/sectors/movers caches so first user request is instant."""
    await asyncio.sleep(3)
    try:
        from app.services.market_data import get_extended_indices, get_sector_changes, get_top_movers
        await asyncio.gather(get_extended_indices(), get_sector_changes(), get_top_movers())
        log.info("market.cache.warmed")
    except Exception as exc:
        log.warning("market.cache.warmup.failed", error=str(exc))


async def _seed_historical_memory() -> None:
    """Seed Historical Market Memory with verified past events on first boot."""
    await asyncio.sleep(6)
    try:
        from app.services.historical_memory_service import seed_historical_events, apply_incremental_patches
        await seed_historical_events()
        await apply_incremental_patches()
    except Exception as exc:
        log.warning("historical_memory.seed_error", error=str(exc))


async def _seed_intelligence_graph() -> None:
    """Seed the Market Intelligence Graph on first boot."""
    await asyncio.sleep(10)
    try:
        from app.services.intelligence_graph_service import seed_intelligence_graph, apply_incremental_patches
        await seed_intelligence_graph()
        await apply_incremental_patches()
    except Exception as exc:
        log.warning("intelligence_graph.seed_error", error=str(exc))


async def _warm_mie_state() -> None:
    """Pre-compute and cache the MIE state on startup."""
    await asyncio.sleep(8)  # wait for DB/Redis and workers to settle
    try:
        from app.services.intelligence.engine import refresh_mie_state
        state = await refresh_mie_state()
        log.info("mie.warmup_complete",
                 session=state.get("market_session"),
                 events=len(state.get("top_events", [])),
                 themes=len(state.get("themes", [])))
    except Exception as exc:
        log.warning("mie.warmup_error", error=str(exc))


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

# ── Rate limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from app.core.config import _default_cors  # noqa: E402
_cors_origins = list({*_default_cors(), *settings.backend_cors_origins})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", path=str(request.url), exc=str(exc), exc_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import dashboard, events, news, stories, radar, calendar, stocks, sectors, indices, ai_search, premarket, market, commodities, ipo, alerts, ripple, market_data, multi_horizon, thesis, checklist, scenario, pattern, related, companies, stream, intelligence_market, mie, historical_memory, graph, predictions, intelligence_pages, announcements, publishing  # noqa: E402

app.include_router(dashboard.router,    prefix="/api/dashboard",    tags=["dashboard"])
app.include_router(events.router,       prefix="/api/events",       tags=["events"])
app.include_router(news.router,         prefix="/api/news",         tags=["news"])
app.include_router(stories.router,      prefix="/api/stories",      tags=["stories"])
app.include_router(radar.router,        prefix="/api/radar",        tags=["radar"])
app.include_router(calendar.router,     prefix="/api/calendar",     tags=["calendar"])
app.include_router(stocks.router,       prefix="/api/stocks",       tags=["stocks"])
app.include_router(sectors.router,      prefix="/api/sectors",      tags=["sectors"])
app.include_router(indices.router,      prefix="/api/indices",      tags=["indices"])
app.include_router(ai_search.router,    prefix="/api/ai",           tags=["ai-search"])
app.include_router(premarket.router,    prefix="/api/premarket",    tags=["premarket"])
app.include_router(market.router,       prefix="/api/market",       tags=["market"])
app.include_router(commodities.router,  prefix="/api/commodities",  tags=["commodities"])
app.include_router(ipo.router,          prefix="/api/ipo",          tags=["ipo"])
app.include_router(alerts.router,       prefix="/api/alerts",       tags=["alerts"])
app.include_router(ripple.router,       prefix="/api/ripple",       tags=["ripple"])
# Market Data Service — clean provider-agnostic API
app.include_router(market_data.router,  prefix="/api/data",         tags=["market-data"])
# Multi-Horizon Investment Outlook
app.include_router(multi_horizon.router, prefix="/api/intelligence", tags=["intelligence"])
# Investment Thesis — AI-generated structured thesis for any entity
app.include_router(thesis.router,       prefix="/api/thesis",       tags=["thesis"])
# Monitoring Checklist — AI-generated monitoring items for any entity
app.include_router(checklist.router,    prefix="/api/checklist",    tags=["checklist"])
# Scenario Analysis — Bull/Base/Bear AI scenarios for any entity
app.include_router(scenario.router,     prefix="/api/scenario",     tags=["scenario"])
# Pattern Intelligence — AI historical pattern matching for any entity
app.include_router(pattern.router,      prefix="/api/pattern",      tags=["pattern"])
# Related Content — cross-entity related intelligence for RelatedContent component
app.include_router(related.router,      prefix="/api/related",      tags=["related"])
app.include_router(companies.router,          prefix="/api/companies",            tags=["companies"])
# SSE live broadcast
app.include_router(stream.router,             prefix="/api/stream",               tags=["stream"])
# Intelligence market endpoints (story, themes, feed, explain)
app.include_router(intelligence_market.router, prefix="/api/intelligence/market",  tags=["intelligence-market"])
# ── Market Intelligence Engine — single source of truth ──────────────────────
app.include_router(mie.router, prefix="/api/mie", tags=["mie"])
# ── Historical Market Memory — verified past events for AI grounding ──────────
app.include_router(historical_memory.router, prefix="/api/historical", tags=["historical"])
# ── Market Intelligence Graph — entity relationship engine ────────────────────
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
# ── Prediction Learning Engine — tracks predictions vs reality over time ───────
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
# ── Universal Intelligence API — every page consumes from one intelligence layer
app.include_router(intelligence_pages.router, prefix="/api/intelligence", tags=["intelligence"])
# ── Company Announcements — BSE/NSE corporate filings feed ───────────────────
app.include_router(announcements.router, prefix="/api/announcements", tags=["announcements"])
# ── AIPE Publishing Engine — autonomous intelligence article publishing ────────
app.include_router(publishing.router, prefix="/api/publishing", tags=["publishing"])


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

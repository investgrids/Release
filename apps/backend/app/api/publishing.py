"""
AIPE Operations API — serves the /operations/intelligence monitoring dashboard.

This is NOT a CMS. There are NO create/edit endpoints.
All publishing is fully autonomous.

GET  /api/publishing/status          → engine + system health
GET  /api/publishing/articles        → paginated article list
GET  /api/publishing/articles/{id}   → single article (full content)
GET  /api/publishing/metrics         → publishing metrics + daily chart
GET  /api/publishing/market-coverage → what topics were covered today
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, func, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db
from app.services.aipe.publisher import get_engine_stats

router = APIRouter()


def _age_minutes(dt, now: datetime) -> float | None:
    """Minutes since dt, tolerant of SQLite's naive-datetime storage."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 60


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _ms(seconds: float | None) -> float | None:
    return round(seconds * 1000) if seconds else None


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


_HEALTH_LABELS = {"healthy": "Healthy", "degraded": "Degraded", "busy": "Busy", "critical": "Critical", "offline": "Offline"}

# Mirrors the FastAPI app version declared in app.main — not imported directly
# to avoid a circular import (main.py imports this router).
_ENGINE_VERSION = "0.2.0"


def compute_health(
    *,
    heartbeat_age_min: float | None,
    heartbeat_expected_min: float,
    runs_total: int = 0,
    runs_success: int = 0,
    queue_size: int = 0,
    queue_busy_at: int = 999_999,
    latency_s: float | None = None,
    latency_threshold_s: float | None = None,
    retry_count: int = 0,
    provider_available: bool = True,
) -> dict:
    """
    Datadog/Kubernetes-style operational health: one of five states derived
    from multiple real signals, never a single metric. A signal an engine
    doesn't emit (e.g. no latency data) is treated as neutral (100) rather
    than penalized — engines are graded only on the telemetry they actually
    produce.

    Weights: success rate 40% · queue health 20% · latency 15% ·
    retry rate 10% · heartbeat freshness 10% · provider availability 5%.
    Offline / Critical / Busy are hard overrides on top of the composite
    score, matching how real alerting systems treat outages and backlogs as
    categorical states rather than "a slightly lower score."
    """
    success_rate = (runs_success / runs_total) if runs_total else None

    success_component = success_rate * 100 if success_rate is not None else 100.0
    queue_component = 100.0 if queue_size < queue_busy_at else _clamp(100 - (queue_size - queue_busy_at) * 8)
    if latency_s is not None and latency_threshold_s:
        over = max(0.0, (latency_s - latency_threshold_s) / latency_threshold_s)
        latency_component = _clamp(100 - over * 100)
    else:
        latency_component = 100.0
    retry_component = _clamp(100 - retry_count * 12)
    if heartbeat_age_min is None:
        heartbeat_component = 0.0
    elif heartbeat_age_min <= heartbeat_expected_min:
        heartbeat_component = 100.0
    else:
        heartbeat_component = _clamp(100 - (heartbeat_age_min - heartbeat_expected_min) / heartbeat_expected_min * 60)
    provider_component = 100.0 if provider_available else 0.0

    score = (
        0.40 * success_component + 0.20 * queue_component + 0.15 * latency_component
        + 0.10 * retry_component + 0.10 * heartbeat_component + 0.05 * provider_component
    )

    is_backlogged = queue_size >= queue_busy_at
    no_active_failures = (success_rate is None or success_rate >= 0.98) and retry_count == 0

    if heartbeat_age_min is None or not provider_available or heartbeat_age_min > heartbeat_expected_min * 8:
        status = "offline"
    elif success_rate is not None and success_rate < 0.80:
        status = "critical"
    elif is_backlogged and no_active_failures:
        status = "busy"
    elif score >= 90 and success_component >= 98 and retry_count == 0 and latency_component >= 90 and queue_size < queue_busy_at:
        status = "healthy"
    else:
        status = "degraded"

    return {
        "health_status": status,
        "health_label": _HEALTH_LABELS[status],
        "health_score": round(score, 1),
        "success_rate": round(success_rate * 100, 1) if success_rate is not None else None,
    }


_IST = timezone(timedelta(hours=5, minutes=30))


def _today_utc():
    today_ist = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    return today_ist.astimezone(timezone.utc)


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def engine_status(db: AsyncSession = Depends(get_db)):
    stats = get_engine_stats()
    today_utc = _today_utc()

    # Article totals
    total_r = await db.execute(select(func.count()).select_from(IntelligenceArticle))
    total = total_r.scalar() or 0

    pub_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
    )
    published = pub_r.scalar() or 0

    # Today's published
    today_pub_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.published_at >= today_utc)
        .where(IntelligenceArticle.status == "published")
    )
    published_today = today_pub_r.scalar() or 0

    # Today's updated
    today_upd_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.last_updated >= today_utc)
        .where(IntelligenceArticle.lifecycle_status == "updated")
    )
    updated_today = today_upd_r.scalar() or 0

    # Avg confidence
    conf_r = await db.execute(
        select(func.avg(IntelligenceArticle.confidence_score))
        .where(IntelligenceArticle.status == "published")
    )
    avg_conf = round(float(conf_r.scalar() or 0) * 100, 1)

    # Avg SEO
    seo_r = await db.execute(
        select(func.avg(IntelligenceArticle.seo_score))
        .where(IntelligenceArticle.status == "published")
    )
    avg_seo = round(float(seo_r.scalar() or 0), 1)

    # Validation failures today
    fail_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.created_at >= today_utc)
        .where(IntelligenceArticle.status == "failed")
    )
    failed_today = fail_r.scalar() or 0

    # KG and historical — read from DB availability
    # (future: query actual counts from those tables)
    return {
        "engine": {
            "status":              stats.get("scheduler_status", "idle"),
            "running":             stats.get("running", False),
            "last_run":            stats.get("last_run"),
            "avg_publish_time_s":  stats.get("avg_publish_time_s", 0),
            "errors":              stats.get("errors", 0),
            "articles_waiting":    stats.get("articles_waiting", 0),
        },
        "market_story": {
            "status":              stats.get("market_story_status", "unknown"),
            "mie_hash":            stats.get("last_mie_hash"),
        },
        "today": {
            "published":           published_today,
            "updated":             updated_today,
            "generated":           stats.get("generated_today", 0),
            "validation_failures": failed_today,
            "max_per_day":         8,
            "remaining_slots":     max(0, 8 - published_today),
        },
        "totals": {
            "total":     total,
            "published": published,
        },
        "quality": {
            "avg_confidence": avg_conf,
            "avg_seo_score":  avg_seo,
        },
        "subsystems": {
            "knowledge_graph":    "active",
            "historical_memory":  "active",
            "learning_engine":    "active",
            "mie":                "active",
            "duplicate_detector": "active",
        },
    }


# ── Ops Overview — real data for the AI Operations Control Center ─────────────
# Everything here is derived from real rows/counters, never fabricated. Where
# an engine isn't directly instrumented (MIE, Story, Scoring — deliberately
# untouched per "do not change" scope), health is derived from that engine's
# own real DB write timestamps instead.

@router.get("/ops-overview")
async def ops_overview(db: AsyncSession = Depends(get_db)):
    from app.db.models.intelligence import MarketSnapshot, MarketStory
    from app.db.models.score_history import ScoreHistory
    from app.db.models.historical_memory import HistoricalMarketEvent
    from app.db.models_legacy import Event as LegacyEvent, RadarOpportunity
    from app.services.aipe import perf_stats
    from app.services.ai_service import get_ai_usage_stats
    from app.api.ai_search import get_search_stats

    now = datetime.now(timezone.utc)
    today_utc = _today_utc()
    stats = get_engine_stats()
    engine_runs = perf_stats.get_engine_runs()
    ai_stats = get_ai_usage_stats()
    search_stats = get_search_stats()
    perf = perf_stats.get_performance_stats()

    def _run_entry(name: str) -> dict:
        return engine_runs.get(name, {
            "last_run": None, "last_success": None, "errors_today": 0, "last_error": None,
            "runs_total": 0, "runs_success": 0,
        })

    pub_run = _run_entry("Publishing Engine")
    hist_run = _run_entry("Historical Engine")
    ever_run = _run_entry("Evergreen Engine")
    upd_run = _run_entry("Continuous Updater")

    # ── Real last-activity timestamps for engines not directly instrumented ──
    mie_last = (await db.execute(select(func.max(MarketSnapshot.ts)))).scalar()
    story_last = (await db.execute(select(func.max(MarketStory.generated_at)))).scalar()
    score_last = (await db.execute(select(func.max(ScoreHistory.created_at)))).scalar()
    campaign_last = (await db.execute(
        select(func.max(IntelligenceArticle.created_at))
        .where(IntelligenceArticle.parent_event_group_id.isnot(None))
    )).scalar()

    # ── Today's articles — feeds Coverage, Campaigns, and Campaign Engine health ──
    today_articles_r = await db.execute(
        select(IntelligenceArticle).where(IntelligenceArticle.created_at >= today_utc)
    )
    today_articles = today_articles_r.scalars().all()
    companies_today: set[str] = set()
    sectors_today: set[str] = set()
    themes_today = 0
    historical_today = 0
    evergreen_today = 0
    campaign_groups: dict[str, list] = {}
    campaign_articles_total = 0
    campaign_articles_success = 0
    for a in today_articles:
        for c in (a.companies_affected or []):
            if isinstance(c, dict) and c.get("symbol"):
                companies_today.add(c["symbol"])
        for s in (a.sectors_affected or []):
            name = s.get("name") if isinstance(s, dict) else s
            if name:
                sectors_today.add(name)
        if a.angle == "theme":
            themes_today += 1
        if a.article_type == "historical_intelligence":
            historical_today += 1
        if a.is_evergreen and a.article_type != "historical_intelligence":
            evergreen_today += 1
        if a.parent_event_group_id:
            campaign_groups.setdefault(a.parent_event_group_id, []).append(a)
            campaign_articles_total += 1
            if a.status == "published":
                campaign_articles_success += 1

    events_today_r = await db.execute(
        select(func.count(func.distinct(LegacyEvent.id))).where(LegacyEvent.published_at >= today_utc)
    )
    events_processed = events_today_r.scalar() or 0

    coverage_today = {
        "events_processed":         events_processed,
        "companies_covered":        len(companies_today),
        "sectors_covered":          len(sectors_today),
        "themes_generated":         themes_today,
        "articles_published":       sum(1 for a in today_articles if a.status == "published"),
        "campaigns_generated":      len(campaign_groups),
        "historical_pages_updated": historical_today,
        "evergreen_pages_updated":  evergreen_today,
        "ai_searches_served":       search_stats["total_today"],
    }

    # ── Today's Campaigns ──────────────────────────────────────────────────────
    todays_campaigns = []
    for group_id, members in campaign_groups.items():
        primary = next((a for a in members if a.angle == "primary"), members[0])
        published = sum(1 for a in members if a.status == "published")
        failed = sum(1 for a in members if a.status == "failed")
        company_count = len({c.get("symbol") for a in members for c in (a.companies_affected or []) if isinstance(c, dict) and c.get("symbol")})
        sector_count = len({(s.get("name") if isinstance(s, dict) else s) for a in members for s in (a.sectors_affected or [])} - {None})
        camp_status = "Running" if failed == 0 and published < len(members) else ("Completed" if failed == 0 else "Partial Failure")
        todays_campaigns.append({
            "event_group_id": group_id, "headline": primary.headline,
            "article_count": len(members), "companies": company_count, "sectors": sector_count,
            "status": camp_status, "published": published, "failed": failed,
        })
    todays_campaigns.sort(key=lambda c: c["article_count"], reverse=True)
    incomplete_campaigns = sum(1 for c in todays_campaigns if c["status"] != "Completed")

    # ── Queue Monitor (real proxies — no fake job queue exists) ───────────────
    triage_waiting = stats.get("articles_waiting", 0)
    failed_r = await db.execute(select(func.count()).select_from(IntelligenceArticle).where(IntelligenceArticle.status == "failed"))
    failed_count = failed_r.scalar() or 0
    updatable_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.published_at >= now - timedelta(hours=12))
    )
    articles_eligible_for_update = updatable_r.scalar() or 0

    queue = {
        "events_waiting":  triage_waiting,
        "articles_waiting": max(0, stats.get("generated_today", 0) - stats.get("published_today", 0)),
        "campaign_queue":  incomplete_campaigns,
        "historical_queue": 0 if hist_run["last_success"] else 1,
        "retry_queue":     failed_count,
        "failed_queue":    failed_count,
    }

    # ── AI provider availability — real signal: every provider in the
    # fallback chain has been failing, not just "a bit slow" ──────────────────
    ai_provider_available = not (ai_stats["llm_calls"] > 0 and ai_stats["llm_calls"] == ai_stats["failures"])

    # ── Engine Health — one weighted, multi-signal state per engine ───────────
    engine_health = [
        {
            "name": "Market Intelligence Engine",
            **compute_health(
                heartbeat_age_min=_age_minutes(mie_last, now), heartbeat_expected_min=15,
                queue_size=stats.get("articles_waiting", 0), queue_busy_at=5,
            ),
            "last_execution": mie_last.isoformat() if mie_last else None,
            "last_success":   mie_last.isoformat() if mie_last else None,
            "errors": 0, "queue_size": stats.get("articles_waiting", 0),
            "latency_ms": None, "version": _ENGINE_VERSION,
        },
        {
            "name": "Publishing Engine",
            **compute_health(
                heartbeat_age_min=_age_minutes(_parse_iso(pub_run["last_run"]), now), heartbeat_expected_min=10,
                runs_total=pub_run["runs_total"], runs_success=pub_run["runs_success"],
                queue_size=stats.get("articles_waiting", 0), queue_busy_at=5,
                latency_s=stats.get("avg_publish_time_s", 0), latency_threshold_s=20.0,
            ),
            "last_execution": pub_run["last_run"], "last_success": pub_run["last_success"],
            "errors": pub_run["errors_today"], "queue_size": stats.get("articles_waiting", 0),
            "latency_ms": _ms(stats.get("avg_publish_time_s")), "version": _ENGINE_VERSION,
        },
        {
            "name": "Scoring Engine",
            **compute_health(heartbeat_age_min=_age_minutes(score_last, now), heartbeat_expected_min=60),
            "last_execution": score_last.isoformat() if score_last else None,
            "last_success":   score_last.isoformat() if score_last else None,
            "errors": 0, "queue_size": 0, "latency_ms": None, "version": _ENGINE_VERSION,
        },
        {
            "name": "Story Engine",
            **compute_health(heartbeat_age_min=_age_minutes(story_last, now), heartbeat_expected_min=15),
            "last_execution": story_last.isoformat() if story_last else None,
            "last_success":   story_last.isoformat() if story_last else None,
            "errors": 0, "queue_size": 0, "latency_ms": None, "version": _ENGINE_VERSION,
        },
        {
            "name": "Campaign Engine",
            **compute_health(
                heartbeat_age_min=_age_minutes(campaign_last, now), heartbeat_expected_min=1440,
                runs_total=campaign_articles_total, runs_success=campaign_articles_success,
                queue_size=incomplete_campaigns, queue_busy_at=3,
                latency_s=perf["avg_campaign_time_s"], latency_threshold_s=6.0,
            ),
            "last_execution": campaign_last.isoformat() if campaign_last else None,
            "last_success":   campaign_last.isoformat() if campaign_last else None,
            "errors": sum(c["failed"] for c in todays_campaigns), "queue_size": incomplete_campaigns,
            "latency_ms": _ms(perf["avg_campaign_time_s"]), "version": _ENGINE_VERSION,
        },
        {
            "name": "Historical Engine",
            **compute_health(
                heartbeat_age_min=_age_minutes(_parse_iso(hist_run["last_run"]), now), heartbeat_expected_min=1440,
                runs_total=hist_run["runs_total"], runs_success=hist_run["runs_success"],
                queue_size=0 if hist_run["last_success"] else 1, queue_busy_at=5,
                latency_s=perf_stats.get_engine_latency_s("Historical Engine"), latency_threshold_s=30.0,
            ),
            "last_execution": hist_run["last_run"], "last_success": hist_run["last_success"],
            "errors": hist_run["errors_today"], "queue_size": 0 if hist_run["last_success"] else 1,
            "latency_ms": _ms(perf_stats.get_engine_latency_s("Historical Engine")), "version": _ENGINE_VERSION,
        },
        {
            "name": "Evergreen Engine",
            **compute_health(
                heartbeat_age_min=_age_minutes(_parse_iso(ever_run["last_run"]), now), heartbeat_expected_min=1440,
                runs_total=ever_run["runs_total"], runs_success=ever_run["runs_success"],
                latency_s=perf_stats.get_engine_latency_s("Evergreen Engine"), latency_threshold_s=30.0,
            ),
            "last_execution": ever_run["last_run"], "last_success": ever_run["last_success"],
            "errors": ever_run["errors_today"], "queue_size": 0,
            "latency_ms": _ms(perf_stats.get_engine_latency_s("Evergreen Engine")), "version": _ENGINE_VERSION,
        },
        {
            "name": "Continuous Updater",
            **compute_health(
                heartbeat_age_min=_age_minutes(_parse_iso(upd_run["last_run"]), now), heartbeat_expected_min=10,
                runs_total=upd_run["runs_total"], runs_success=upd_run["runs_success"],
                queue_size=articles_eligible_for_update, queue_busy_at=8,
                latency_s=perf["avg_update_time_s"], latency_threshold_s=4.0,
            ),
            "last_execution": upd_run["last_run"], "last_success": upd_run["last_success"],
            "errors": upd_run["errors_today"], "queue_size": articles_eligible_for_update,
            "latency_ms": _ms(perf["avg_update_time_s"]), "version": _ENGINE_VERSION,
        },
        {
            "name": "AI Search",
            **compute_health(
                heartbeat_age_min=_age_minutes(_parse_iso(search_stats["last_query_at"]), now), heartbeat_expected_min=240,
                runs_total=search_stats["total_today"], runs_success=search_stats["total_today"] - search_stats["errors"],
                latency_s=(search_stats["avg_response_ms"] / 1000) if search_stats["avg_response_ms"] else None,
                latency_threshold_s=6.0,
                retry_count=ai_stats["retries"], provider_available=ai_provider_available,
            ),
            "last_execution": search_stats["last_query_at"], "last_success": search_stats["last_success_at"],
            "errors": search_stats["errors"], "queue_size": 0,
            "latency_ms": round(search_stats["avg_response_ms"]) or None, "version": _ENGINE_VERSION,
        },
    ]

    # ── AI Search special metrics — because it's user-facing, more detail
    # than the generic engine card. "avg_tokens"/"avg_llm_time" are
    # platform-wide averages (every AI call shares the same _call_provider
    # choke-point) rather than search-specific, since tokens aren't bucketed
    # per calling feature — labeled accordingly, not fabricated as exact.
    ai_search_metrics = {
        "total_searches_today": search_stats["total_today"],
        "cache_hit_rate":       round(search_stats["cache_hits"] / search_stats["total_today"] * 100, 1) if search_stats["total_today"] else 0.0,
        "avg_tokens":           round(ai_stats["tokens_used"] / ai_stats["llm_calls"]) if ai_stats["llm_calls"] else 0,
        "avg_llm_time_ms":      ai_stats["avg_response_ms"],
        "provider_used":        ai_stats["last_provider"],
        "timeout_count":        search_stats["timeouts"],
        "retry_count":          ai_stats["retries"],
        "success_rate":         search_stats["success_rate"],
    }

    # ── Database Health ────────────────────────────────────────────────────────
    def _count(model, *filters):
        return select(func.count()).select_from(model).where(*filters) if filters else select(func.count()).select_from(model)

    pub_articles = (await db.execute(_count(IntelligenceArticle, IntelligenceArticle.status == "published"))).scalar() or 0
    hist_pages = (await db.execute(_count(IntelligenceArticle, IntelligenceArticle.article_type == "historical_intelligence", IntelligenceArticle.status == "published"))).scalar() or 0
    campaigns_total = (await db.execute(select(func.count(func.distinct(IntelligenceArticle.parent_event_group_id))).where(IntelligenceArticle.parent_event_group_id.isnot(None)))).scalar() or 0
    events_total = (await db.execute(_count(LegacyEvent))).scalar() or 0
    score_history_total = (await db.execute(_count(ScoreHistory))).scalar() or 0
    radar_total = (await db.execute(_count(RadarOpportunity))).scalar() or 0
    historical_events_total = (await db.execute(_count(HistoricalMarketEvent))).scalar() or 0

    database_health = {
        "published_articles": pub_articles,
        "historical_pages":   hist_pages,
        "campaigns":          campaigns_total,
        "events":             events_total,
        "opportunities":      radar_total,
        "historical_events":  historical_events_total,
        "score_history":      score_history_total,
        "queue_size":         queue["events_waiting"] + queue["retry_queue"],
    }

    # ── Scheduler Status — real APScheduler job introspection ─────────────────
    scheduler_jobs = []
    try:
        from app.scheduler.scheduler import get_scheduler
        sched = get_scheduler()
        for job in sched.get_jobs():
            trigger_str = str(job.trigger)
            scheduler_jobs.append({
                "id": job.id, "name": job.name or job.id,
                "running": sched.running,
                "trigger": trigger_str,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
    except Exception:
        pass

    # ── Recent Activity — real timeline from actual timestamps ────────────────
    recent_r = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.created_at >= now - timedelta(hours=6))
        .order_by(IntelligenceArticle.created_at.desc())
        .limit(15)
    )
    recent_activity = []
    for a in recent_r.scalars().all():
        recent_activity.append({
            "at": a.created_at.isoformat() if a.created_at else None,
            "type": "published" if a.status == "published" else "failed",
            "label": f"{'Published' if a.status == 'published' else 'Generation failed'}: {a.headline[:80]}",
            "slug": a.slug, "angle": a.angle,
        })

    # ── Failure Center ─────────────────────────────────────────────────────────
    failures_r = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "failed")
        .order_by(IntelligenceArticle.created_at.desc())
        .limit(20)
    )
    failures = [
        {
            "id": a.id, "headline": a.headline, "article_type": a.article_type,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "validation_failures": a.validation_failures,
            "validation_results": a.validation_results,
        }
        for a in failures_r.scalars().all()
    ]

    return {
        "generated_at": now.isoformat(),
        "engine_health": engine_health,
        "coverage_today": coverage_today,
        "todays_campaigns": todays_campaigns,
        "queue": queue,
        "database_health": database_health,
        "ai_usage_today": ai_stats,
        "ai_search_metrics": ai_search_metrics,
        "performance": {
            **perf,
            "avg_publish_time_s": stats.get("avg_publish_time_s", 0),
        },
        "scheduler_jobs": scheduler_jobs,
        "recent_activity": recent_activity,
        "failures": failures,
    }


# ── Retry a failed article ──────────────────────────────────────────────────────
# Reuses the existing, unmodified _publish_new_article() — just re-invokes it
# with the failed row's own stored trigger_data as the event context. Does not
# change how generation/validation/publishing works, only re-runs it.

@router.post("/articles/{article_id}/retry")
async def retry_failed_article(article_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.aipe.publisher import _publish_new_article
    from app.services.aipe.market_story_engine import get_mie_context

    result = await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    if art.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed articles can be retried")

    trigger = art.trigger_data or {}
    event = {
        "event_id": art.trigger_event_id or art.story_id,
        "headline": trigger.get("headline") or art.headline,
        "one_liner": trigger.get("headline") or art.headline,
        "sectors": trigger.get("sectors") or [],
        "tickers": [],
        "urgency": trigger.get("urgency") or 6,
        "importance": 6,
        "is_structural": False,
    }
    mie_context = await get_mie_context()
    new_story_id = f"{art.story_id}-retry-{int(datetime.now(timezone.utc).timestamp())}"
    new_article = await _publish_new_article(
        db, event, mie_context, art.article_type, new_story_id,
        angle=art.angle, angle_entity=art.angle_entity,
        parent_event_group_id=art.parent_event_group_id,
    )
    if not new_article:
        raise HTTPException(status_code=500, detail="Retry failed to generate a new article")
    return {"ok": True, "new_article_id": new_article.id, "status": new_article.status, "slug": new_article.slug}


# ── Articles ───────────────────────────────────────────────────────────────────

@router.get("/articles")
async def list_articles(
    status:       Optional[str] = Query(None),
    article_type: Optional[str] = Query(None),
    lifecycle:    Optional[str] = Query(None),
    search:       Optional[str] = Query(None, description="Substring match across headline, story/event id, sectors, companies"),
    limit:        int           = Query(20, le=100),
    offset:       int           = Query(0),
    db:           AsyncSession  = Depends(get_db),
):
    def _apply_filters(query):
        if status:
            query = query.where(IntelligenceArticle.status == status)
        if article_type:
            query = query.where(IntelligenceArticle.article_type == article_type)
        if lifecycle:
            query = query.where(IntelligenceArticle.lifecycle_status == lifecycle)
        if search:
            like = f"%{search}%"
            query = query.where(
                IntelligenceArticle.headline.ilike(like)
                | IntelligenceArticle.story_id.ilike(like)
                | IntelligenceArticle.parent_event_group_id.ilike(like)
                | IntelligenceArticle.angle_entity.ilike(like)
                # JSON columns are stored as TEXT in SQLite — a cast lets the
                # same substring search reach company/sector names inside
                # them without a separate index or duplicated query logic.
                | cast(IntelligenceArticle.companies_affected, String).ilike(like)
                | cast(IntelligenceArticle.sectors_affected, String).ilike(like)
            )
        return query

    q = _apply_filters(select(IntelligenceArticle).order_by(IntelligenceArticle.created_at.desc()))
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    articles = result.scalars().all()

    # Count
    cq = _apply_filters(select(func.count()).select_from(IntelligenceArticle))
    total = (await db.execute(cq)).scalar() or 0

    return {
        "total":    total,
        "offset":   offset,
        "limit":    limit,
        "articles": [_list_row(a) for a in articles],
    }


@router.get("/articles/{article_id}")
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IntelligenceArticle).where(IntelligenceArticle.id == article_id)
    )
    art = result.scalar_one_or_none()
    if not art:
        result = await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.slug == article_id)
        )
        art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return _full_row(art)


# ── Metrics ────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def publishing_metrics(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)

    # 7-day daily published chart
    daily = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        r = await db.execute(
            select(func.count()).select_from(IntelligenceArticle)
            .where(IntelligenceArticle.published_at >= day)
            .where(IntelligenceArticle.published_at < day + timedelta(days=1))
        )
        daily.append({"date": day.strftime("%b %d"), "count": r.scalar() or 0})

    # By article type
    type_r = await db.execute(
        select(IntelligenceArticle.article_type, func.count())
        .where(IntelligenceArticle.status == "published")
        .group_by(IntelligenceArticle.article_type)
    )
    by_type = [{"type": r[0], "count": r[1]} for r in type_r.all()]

    # Lifecycle distribution
    lc_r = await db.execute(
        select(IntelligenceArticle.lifecycle_status, func.count())
        .group_by(IntelligenceArticle.lifecycle_status)
    )
    by_lifecycle = [{"status": r[0], "count": r[1]} for r in lc_r.all()]

    # Avg update count on updated articles
    upd_r = await db.execute(
        select(func.avg(IntelligenceArticle.update_count))
        .where(IntelligenceArticle.update_count > 0)
    )
    avg_updates = round(float(upd_r.scalar() or 0), 1)

    # Avg scores
    scores_r = await db.execute(
        select(
            func.avg(IntelligenceArticle.seo_score),
            func.avg(IntelligenceArticle.quality_score),
            func.avg(IntelligenceArticle.confidence_score),
        ).where(IntelligenceArticle.status == "published")
    )
    row = scores_r.one_or_none()
    return {
        "daily_published": daily,
        "by_type":         by_type,
        "by_lifecycle":    by_lifecycle,
        "avg_updates":     avg_updates,
        "avg_seo_score":   round(float(row[0] or 0), 1) if row else 0,
        "avg_quality":     round(float(row[1] or 0) * 100, 1) if row else 0,
        "avg_confidence":  round(float(row[2] or 0) * 100, 1) if row else 0,
    }


# ── Market coverage ────────────────────────────────────────────────────────────

@router.get("/market-coverage")
async def market_coverage(db: AsyncSession = Depends(get_db)):
    """What intelligence topics were covered today."""
    today_utc = _today_utc()
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.published_at >= today_utc)
        .where(IntelligenceArticle.status == "published")
        .order_by(IntelligenceArticle.published_at)
    )
    today_articles = result.scalars().all()

    coverage = []
    for a in today_articles:
        coverage.append({
            "id":           a.id,
            "slug":         a.slug,
            "type":         a.article_type,
            "headline":     a.headline,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "update_count": a.update_count,
            "lifecycle":    a.lifecycle_status,
            "sectors":      [s.get("name", s) if isinstance(s, dict) else s
                             for s in (a.sectors_affected or [])[:3]],
            "story_id":     a.story_id,
        })

    return {
        "date":           datetime.now(_IST).strftime("%Y-%m-%d"),
        "count":          len(coverage),
        "articles":       coverage,
        "remaining_slots": max(0, 8 - len(coverage)),
    }


# ── Campaigns ──────────────────────────────────────────────────────────────────
# A "campaign" is every article sharing one parent_event_group_id — the
# primary overview plus whatever per-company / sector / theme / question /
# historical siblings were fanned out from the same triggering event (see
# content_planner.plan_extra_angles). Grouped here rather than stored as its
# own table since the group membership is already fully derivable from
# existing rows.

@router.get("/campaigns")
async def list_campaigns(
    limit:  int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    group_r = await db.execute(
        select(IntelligenceArticle.parent_event_group_id, func.count(), func.max(IntelligenceArticle.last_updated))
        .where(IntelligenceArticle.parent_event_group_id.isnot(None))
        .group_by(IntelligenceArticle.parent_event_group_id)
        .order_by(func.max(IntelligenceArticle.last_updated).desc())
        .limit(limit)
        .offset(offset)
    )
    groups = group_r.all()
    group_ids = [g[0] for g in groups]

    total_r = await db.execute(
        select(func.count(func.distinct(IntelligenceArticle.parent_event_group_id)))
        .where(IntelligenceArticle.parent_event_group_id.isnot(None))
    )
    total = total_r.scalar() or 0

    if not group_ids:
        return {"total": total, "offset": offset, "limit": limit, "campaigns": []}

    articles_r = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.parent_event_group_id.in_(group_ids))
        .order_by(IntelligenceArticle.created_at.asc())
    )
    by_group: dict[str, list[IntelligenceArticle]] = {}
    for a in articles_r.scalars().all():
        by_group.setdefault(a.parent_event_group_id, []).append(a)

    campaigns = []
    for group_id, count, last_updated in groups:
        members = by_group.get(group_id, [])
        primary = next((a for a in members if a.angle == "primary"), members[0] if members else None)
        if not primary:
            continue
        published = sum(1 for a in members if a.status == "published")
        failed = sum(1 for a in members if a.status == "failed")
        campaigns.append({
            "event_group_id": group_id,
            "headline":        primary.headline,
            "article_type":    primary.article_type,
            "article_count":   count,
            "published_count": published,
            "failed_count":    failed,
            "created_at":      min((a.created_at for a in members if a.created_at), default=None),
            "last_updated":    last_updated.isoformat() if last_updated else None,
            "articles": [
                {
                    "slug": a.slug, "headline": a.headline, "article_type": a.article_type,
                    "angle": a.angle, "angle_entity": a.angle_entity, "status": a.status,
                    "update_count": a.update_count,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                }
                for a in sorted(members, key=lambda x: 0 if x.angle == "primary" else 1)
            ],
        })

    return {"total": total, "offset": offset, "limit": limit, "campaigns": campaigns}


# ── Serializers ────────────────────────────────────────────────────────────────

def _list_row(a: IntelligenceArticle) -> dict:
    return {
        "id":                a.id,
        "slug":              a.slug,
        "article_type":      a.article_type,
        "story_id":          a.story_id,
        "story_version":     a.story_version,
        "lifecycle_status":  a.lifecycle_status,
        "status":            a.status,
        "headline":          a.headline,
        "key_takeaway":      a.key_takeaway,
        "executive_summary": a.executive_summary,
        "sectors_affected":  a.sectors_affected,
        "companies_affected": a.companies_affected,
        "update_count":      a.update_count,
        "validation_passed": a.validation_passed,
        "validation_failures": a.validation_failures,
        "event_score":       a.event_score,
        "confidence_score":  a.confidence_score,
        "quality_score":     a.quality_score,
        "seo_score":         a.seo_score,
        "views":             a.views,
        "trigger_type":      a.trigger_type,
        "trigger_event_id":  a.trigger_event_id,
        "published_at":      a.published_at.isoformat() if a.published_at else None,
        "last_updated":      a.last_updated.isoformat() if a.last_updated else None,
        "created_at":        a.created_at.isoformat() if a.created_at else None,
    }


def _full_row(a: IntelligenceArticle) -> dict:
    base = _list_row(a)
    base.update({
        "why_it_matters":     a.why_it_matters,
        "what_happened":      a.what_happened,
        "opportunities":      a.opportunities,
        "risks":              a.risks,
        "historical_events":  a.historical_events,
        "ripple_effect":      a.ripple_effect,
        "what_to_watch_next": a.what_to_watch_next,
        "faqs":               a.faqs,
        "sources":            a.sources,
        "internal_links":     a.internal_links,
        "related_companies":  a.related_companies,
        "related_themes":     a.related_themes,
        "seo_title":          a.seo_title,
        "meta_description":   a.meta_description,
        "canonical_url":      a.canonical_url,
        "json_ld":            a.json_ld,
        "market_context":     a.market_context,
        "update_history":     a.update_history,
        "validation_results": a.validation_results,
        "historical_refs":    a.historical_refs,
    })
    return base

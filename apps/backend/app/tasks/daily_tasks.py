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
        summary = await get_market_summary(index_quotes, event_dicts)
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
            ai_text = await get_market_summary(index_quotes, event_dicts)

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
        rows = result.scalars().all()
        fixed = 0
        for a in rows:
            changed = False
            for field in ("headline", "executive_summary", "key_takeaway", "why_it_matters", "what_happened"):
                val = getattr(a, field, None)
                if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
                    cleaned = leading_re.sub("", val)
                    cleaned = _PLACEHOLDER_RE.sub("", cleaned)
                    cleaned = " ".join(cleaned.split())  # collapse leftover double-spaces
                    if cleaned and cleaned[0].islower():
                        cleaned = cleaned[0].upper() + cleaned[1:]
                    setattr(a, field, cleaned)
                    changed = True
            if changed:
                db.add(a)
                fixed += 1
                log.info("job.repair_unfilled_placeholders.fixed", slug=a.slug)

        if fixed:
            await db.commit()
        log.info("job.repair_unfilled_placeholders.done", repaired=fixed)

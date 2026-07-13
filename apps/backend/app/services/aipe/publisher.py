"""
AIPE Publisher — the orchestrator of the full autonomous pipeline.

Pipeline (called every 5 minutes by the scheduler):

  1. Fetch MIE context (story, themes, session, mood)
  2. Fetch high-urgency EventTriage (last 3 hours)
  3. Apply intelligence filter (3-8 stories/day limit, intelligence-first)
  4. For each approved signal:
     a. Content planner → article_type + story_id
     b. Duplicate detector → update or create?
     c. If update: run continuous_updater
     d. If create: fetch historical context → generate article → validate → publish
  5. Run continuous_updater on existing published articles
  6. Update engine stats

Produces 3-8 high-quality intelligence stories per trading day.
Each story is a living document that evolves throughout the day.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe.article_generator import compute_seo_score, generate_intelligence_article
from app.services.aipe.content_planner import select_article_type, should_generate_today
from app.services.aipe.continuous_updater import run_continuous_update_cycle
from app.services.aipe.duplicate_detector import (
    count_today_articles,
    find_duplicate,
    get_today_story_ids,
)
from app.services.aipe.intelligence_filter import filter_triage_batch
from app.services.aipe.market_story_engine import (
    fetch_historical_context,
    get_high_urgency_triage,
    get_latest_market_snapshot,
    get_mie_context,
    has_mie_changed,
)
from app.services.aipe.quality_validator import validate

log = structlog.get_logger(__name__)

# ── Engine stats (in-process, resets on deploy) ───────────────────────────────
_STATS: dict[str, Any] = {
    "running":             False,
    "last_run":            None,
    "generated_today":     0,
    "published_today":     0,
    "updated_today":       0,
    "validation_failures": 0,
    "articles_waiting":    0,
    "errors":              0,
    "last_mie_hash":       None,
    "market_story_status": "unknown",
    "scheduler_status":    "idle",
    "avg_publish_time_s":  0.0,
    "_total_publish_time": 0.0,
    "_total_published":    0,
}

_MAX_PER_DAY = 8


def get_engine_stats() -> dict[str, Any]:
    s = dict(_STATS)
    s.pop("_total_publish_time", None)
    s.pop("_total_published", None)
    return s


# ── Single article publish ────────────────────────────────────────────────────

async def _publish_new_article(
    db,
    triage_event: dict[str, Any],
    mie_context: dict[str, Any],
    article_type: str,
    story_id: str,
) -> IntelligenceArticle | None:
    """Generate, validate, and persist a new intelligence article."""
    start = datetime.now(timezone.utc)

    # Fetch real historical context (never hallucinate)
    sectors = triage_event.get("sectors") or []
    keywords = triage_event.get("themes") or []
    historical = await fetch_historical_context(db, sectors, keywords, limit=3)

    # Generate using type-specific template
    article_data = await generate_intelligence_article(
        article_type=article_type,
        event=triage_event,
        mie_context=mie_context,
        historical=historical,
    )

    if not article_data:
        log.warning("publisher.generation_failed", type=article_type)
        _STATS["errors"] += 1
        return None

    _STATS["generated_today"] += 1

    # SEO + validation
    seo_score = compute_seo_score(article_data)
    passed, results, quality_score = validate(article_data, seo_score)

    now = datetime.now(timezone.utc)
    article_id = str(uuid.uuid4())
    slug = article_data.get("slug", article_id)
    site_url = "https://marketripple.com"

    # Build JSON-LD (Article + FAQPage if FAQs present)
    json_ld: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article_data.get("headline", ""),
        "description": article_data.get("meta_description", ""),
        "datePublished": now.isoformat(),
        "dateModified": now.isoformat(),
        "author": {"@type": "Organization", "name": "MarketRipple AI Intelligence Engine"},
        "publisher": {"@type": "Organization", "name": "MarketRipple"},
        "mainEntityOfPage": f"{site_url}/insights/{slug}",
    }
    faqs = article_data.get("faqs") or []
    if faqs:
        json_ld["@type"] = ["Article", "FAQPage"]
        json_ld["mainEntity"] = [
            {
                "@type": "Question",
                "name": f.get("question", ""),
                "acceptedAnswer": {"@type": "Answer", "text": f.get("answer", "")},
            }
            for f in faqs[:5]
        ]

    # Build internal links
    internal_links: list[dict] = []
    for co in (article_data.get("companies_affected") or [])[:4]:
        sym = co.get("symbol", "").upper()
        if sym:
            internal_links.append({"text": co.get("name", sym), "href": f"/companies/{sym}", "type": "company"})
    for sec in (article_data.get("sectors_affected") or [])[:3]:
        name = sec.get("name", "")
        if name:
            internal_links.append({"text": name, "href": "/themes", "type": "sector"})
    internal_links += [
        {"text": "AI Search", "href": "/ai-search", "type": "tool"},
        {"text": "Market Intelligence", "href": "/market-intelligence", "type": "tool"},
        {"text": "Daily Brief", "href": "/daily-brief", "type": "tool"},
    ]

    # Related entity lists
    related_companies = [
        {"symbol": c.get("symbol", ""), "name": c.get("name", ""), "link": f"/companies/{c.get('symbol', '')}"}
        for c in (article_data.get("companies_affected") or [])[:6]
        if c.get("symbol")
    ]
    related_sectors = [
        {"theme": s.get("name", ""), "link": "/themes"}
        for s in (article_data.get("sectors_affected") or [])[:4]
        if s.get("name")
    ]

    # Historical refs
    hist_refs = [h.get("id", "") for h in historical if h.get("id")]

    # Market context snapshot
    snap = await get_latest_market_snapshot(db)
    market_ctx = {
        **snap,
        "session":     mie_context.get("session"),
        "mood":        mie_context.get("mood"),
        "story":       mie_context.get("story", "")[:200],
        "themes":      mie_context.get("themes", []),
        "story_hash":  mie_context.get("story_hash"),
    }

    status = "published" if passed else "failed"
    lifecycle = "published" if passed else "failed"

    article = IntelligenceArticle(
        id=article_id,
        slug=slug,
        article_type=article_type,
        story_id=story_id,
        story_version=1,
        lifecycle_status=lifecycle,
        status=status,
        update_count=0,
        update_history=[],
        # Content
        headline=article_data.get("headline", triage_event.get("headline", "Intelligence")),
        executive_summary=article_data.get("executive_summary"),
        key_takeaway=article_data.get("key_takeaway"),
        why_it_matters=article_data.get("why_it_matters"),
        what_happened=article_data.get("what_happened"),
        # Sections
        companies_affected=article_data.get("companies_affected", []),
        sectors_affected=article_data.get("sectors_affected", []),
        opportunities=article_data.get("opportunities", []),
        risks=article_data.get("risks", []),
        historical_events=article_data.get("historical_similar_events", []),
        ripple_effect=article_data.get("ripple_effect", []),
        what_to_watch_next=article_data.get("what_to_watch_next", []),
        faqs=faqs,
        sources=article_data.get("sources", ["MarketRipple Intelligence Engine"]),
        # Relationships
        related_article_ids=[],
        internal_links=internal_links,
        related_companies=related_companies,
        related_events=[],
        related_themes=related_sectors,
        knowledge_graph_refs=[],
        historical_refs=hist_refs,
        prediction_refs=[],
        # SEO
        seo_title=article_data.get("seo_title"),
        meta_description=article_data.get("meta_description"),
        canonical_url=f"{site_url}/insights/{slug}",
        json_ld=json_ld,
        # Context
        market_context=market_ctx,
        mie_story_hash=mie_context.get("story_hash"),
        # Trigger
        trigger_event_id=triage_event.get("event_id"),
        trigger_triage_id=triage_event.get("id"),
        trigger_type="high_urgency_triage",
        trigger_data={
            "headline": triage_event.get("headline"),
            "urgency":  triage_event.get("urgency"),
            "sectors":  sectors[:4],
        },
        # Scores
        event_score=float(triage_event.get("urgency") or 0) * 10,
        confidence_score=float(article_data.get("confidence_score") or 0.7),
        quality_score=quality_score,
        seo_score=seo_score,
        # Validation
        validation_passed=passed,
        validation_results=results,
        validation_failures=sum(1 for v in results.values() if not v),
        # Timestamps
        published_at=now if passed else None,
        last_updated=now,
        created_at=now,
    )

    db.add(article)
    await db.commit()
    await db.refresh(article)

    # Update timing stats
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    _STATS["_total_publish_time"] = _STATS.get("_total_publish_time", 0) + elapsed
    _STATS["_total_published"] = _STATS.get("_total_published", 0) + 1
    total = _STATS["_total_published"]
    _STATS["avg_publish_time_s"] = round(_STATS["_total_publish_time"] / total, 1)

    if passed:
        _STATS["published_today"] += 1
        log.info("publisher.published", slug=slug, type=article_type, seo=seo_score)

        # Store article opportunities as predictions in the learning engine
        asyncio.create_task(
            _store_article_predictions(article_id, article_data, triage_event),
            name="aipe-prediction-store",
        )
    else:
        _STATS["validation_failures"] += 1
        log.warning("publisher.validation_failed", slug=slug, results=results)

    return article


async def _store_article_predictions(
    article_id: str,
    article_data: dict[str, Any],
    triage_event: dict[str, Any],
) -> None:
    """Extract directional predictions from a published article and store them."""
    try:
        from app.services.prediction_service import store_prediction, SECTOR_TICKERS

        opportunities = article_data.get("opportunities") or []
        sectors = triage_event.get("sectors") or []
        tickers = triage_event.get("tickers") or triage_event.get("companies") or []
        confidence_score = float(article_data.get("confidence_score") or 0.7) * 100

        # Build target entities from affected companies + sectors
        entities: list[dict] = []
        for sym in (tickers or [])[:2]:
            if isinstance(sym, str) and sym:
                entities.append({"type": "company", "symbol": sym, "name": sym, "ticker": sym})
        for sec in (sectors or [])[:1]:
            if isinstance(sec, str):
                sec_lower = sec.lower()
                tick = next((v for k, v in SECTOR_TICKERS.items() if k in sec_lower), None)
                if tick:
                    entities.append({"type": "sector", "name": sec, "baseline_ticker": tick})

        if not entities or not opportunities:
            return

        # Determine overall direction from opportunities vs risks sentiment
        opp_count = len(opportunities)
        risk_count = len(article_data.get("risks") or [])
        if opp_count > risk_count:
            direction = "up"
        elif risk_count > opp_count:
            direction = "down"
        else:
            direction = "sideways"

        headline = article_data.get("headline", "")[:400]
        summary = article_data.get("key_takeaway") or article_data.get("executive_summary") or headline

        await store_prediction(
            source="aipe",
            prediction_text=summary[:400],
            direction=direction,
            prediction_type="fundamental",
            target_entities=entities,
            confidence_score=confidence_score,
            confidence_level=(
                "Very High" if confidence_score >= 85 else
                "High"      if confidence_score >= 70 else
                "Medium"    if confidence_score >= 55 else "Low"
            ),
            horizon_days=7,
            headline=headline,
        )
        log.debug("aipe.prediction_stored", article_id=article_id, direction=direction)
    except Exception as exc:
        log.debug("aipe.prediction_store_skip", error=str(exc))


# ── Scheduled article builder ─────────────────────────────────────────────────

_IST = timezone(timedelta(hours=5, minutes=30))


async def _build_scheduled_event(db, session: str) -> dict[str, Any] | None:
    """
    When EventTriage is empty, synthesize a virtual event from recent news
    to drive the session's scheduled article (morning_intelligence / market_wrap).
    Returns None if no news data is available.
    """
    from sqlalchemy import select as sa_select
    from app.db.models_legacy import NewsArticle

    # Pull the 10 most recent news items
    try:
        result = await db.execute(
            sa_select(NewsArticle)
            .order_by(NewsArticle.created_at.desc())
            .limit(10)
        )
        rows = result.scalars().all()
    except Exception:
        return None

    if not rows:
        return None

    # Build a rich synthetic event from the top stories
    headlines = [r.headline for r in rows if r.headline][:5]
    summaries = [r.summary for r in rows if r.summary][:3]
    companies_raw = []
    for r in rows[:5]:
        try:
            import json as _json
            companies_raw.extend(_json.loads(r.companies) if isinstance(r.companies, str) else (r.companies or []))
        except Exception:
            pass

    combined_headline = " | ".join(headlines[:3]) if headlines else "Indian market update"
    combined_summary = " ".join(summaries[:2]) if summaries else combined_headline

    # Deduplicate companies
    seen = set()
    companies = []
    for c in companies_raw:
        key = str(c).lower()
        if key not in seen:
            seen.add(key)
            companies.append({"name": c, "symbol": ""})

    article_type = "morning_intelligence" if session in ("pre_open", "pre_market", "live") else "market_wrap"
    today = datetime.now(_IST).strftime("%Y-%m-%d")

    return {
        "event_id":      f"scheduled-{article_type}-{today}",
        "headline":      combined_headline,
        "urgency":       7,
        "importance":    7,
        "confidence":    0.7,
        "sentiment":     "neutral",
        "market_impact": "medium",
        "is_structural": False,
        "one_liner":     combined_summary[:200],
        "sectors":       [],
        "tickers":       [],
        "themes":        [],
        "companies":     companies[:6],
        "triaged_at":    datetime.now(timezone.utc).isoformat(),
        "_scheduled":    True,
        "_article_type": article_type,
    }


async def _scheduled_article_due(db, session: str, today_story_ids: set) -> bool:
    """
    True when a scheduled (time-based) article hasn't been generated today.
    morning_intelligence → due in pre_open / pre_market / live (before noon)
    market_wrap          → due in post_market / closed (after 15:30 IST)
    """
    today = datetime.now(_IST).strftime("%Y-%m-%d")
    if session in ("pre_open", "pre_market", "live"):
        ist_now = datetime.now(_IST)
        # Only generate morning piece before noon
        if ist_now.hour >= 12:
            return False
        story_id = f"morning-{today}"
        return story_id not in today_story_ids

    if session in ("post_market", "closed"):
        story_id = f"wrap-{today}"
        return story_id not in today_story_ids

    return False


# ── Main cycle ────────────────────────────────────────────────────────────────

async def run_aipe_cycle() -> None:
    """
    Called by the scheduler every 5 minutes.
    Full intelligence-first publishing pipeline.
    """
    if _STATS["running"]:
        log.info("aipe.cycle.skipped_already_running")
        return

    _STATS["running"] = True
    _STATS["scheduler_status"] = "running"
    _STATS["last_run"] = datetime.now(timezone.utc).isoformat()

    try:
        async with AsyncSessionLocal() as db:
            # ── 1. MIE context ────────────────────────────────────────────────
            mie_context = await get_mie_context()
            _STATS["last_mie_hash"] = mie_context.get("story_hash")
            _STATS["market_story_status"] = mie_context.get("mood", "unknown")

            # ── 2. Triage events ──────────────────────────────────────────────
            triage_events = await get_high_urgency_triage(db, min_urgency=6, hours=3)
            _STATS["articles_waiting"] = len(triage_events)

            # ── 3. Intelligence filter ─────────────────────────────────────────
            approved = filter_triage_batch(triage_events, max_per_cycle=3)

            # ── 4. Daily limit check ──────────────────────────────────────────
            daily_count = await count_today_articles(db)
            today_story_ids = await get_today_story_ids(db)

            if daily_count >= _MAX_PER_DAY:
                log.info("aipe.cycle.daily_limit_reached", count=daily_count)
                # Still run updater even if limit reached
            else:
                # ── 5. Process each approved signal ───────────────────────────
                for triage_event, filter_reason in approved:
                    if daily_count >= _MAX_PER_DAY:
                        break

                    article_type, story_id, priority = select_article_type(
                        triage_event, mie_context
                    )

                    should_gen, plan_reason = should_generate_today(
                        article_type, story_id, today_story_ids, daily_count, _MAX_PER_DAY
                    )

                    if not should_gen:
                        log.info("aipe.cycle.skipped", reason=plan_reason)
                        continue

                    # Duplicate detection
                    headline = triage_event.get("headline") or triage_event.get("title") or ""
                    duplicate = await find_duplicate(
                        db,
                        story_id=story_id,
                        article_type=article_type,
                        headline=headline,
                        trigger_event_id=triage_event.get("event_id"),
                    )

                    if duplicate:
                        # Update existing article
                        from app.services.aipe.continuous_updater import update_article
                        updated = await update_article(db, duplicate, mie_context, [triage_event])
                        if updated:
                            _STATS["updated_today"] = _STATS.get("updated_today", 0) + 1
                        log.info("aipe.cycle.updated_duplicate", story_id=story_id)
                    else:
                        # Create new article
                        article = await _publish_new_article(
                            db, triage_event, mie_context, article_type, story_id
                        )
                        if article and article.status == "published":
                            daily_count += 1
                            today_story_ids.add(story_id)

                    # Rate limit between AI calls
                    await asyncio.sleep(2)

            # ── 5b. Scheduled article path (session-triggered, no triage needed) ─
            session = mie_context.get("session", "closed")
            if daily_count < _MAX_PER_DAY and await _scheduled_article_due(db, session, today_story_ids):
                sched_event = await _build_scheduled_event(db, session)
                if sched_event:
                    today_ist = datetime.now(_IST).strftime("%Y-%m-%d")
                    art_type = sched_event["_article_type"]
                    story_id = f"morning-{today_ist}" if art_type == "morning_intelligence" else f"wrap-{today_ist}"

                    should_gen, _ = should_generate_today(art_type, story_id, today_story_ids, daily_count, _MAX_PER_DAY)
                    if should_gen:
                        dup = await find_duplicate(db, story_id=story_id, article_type=art_type,
                                                   headline=sched_event["headline"], trigger_event_id=sched_event["event_id"])
                        if not dup:
                            article = await _publish_new_article(db, sched_event, mie_context, art_type, story_id)
                            if article and article.status == "published":
                                daily_count += 1
                                today_story_ids.add(story_id)
                                log.info("aipe.cycle.scheduled_article", type=art_type, story_id=story_id)

            # ── 6. Continuous update pass ─────────────────────────────────────
            updated_count = await run_continuous_update_cycle(
                db, mie_context, triage_events[:5]
            )
            if updated_count:
                _STATS["updated_today"] = _STATS.get("updated_today", 0) + updated_count
                log.info("aipe.cycle.updates", count=updated_count)

    except Exception as exc:
        log.error("aipe.cycle.error", error=str(exc))
        _STATS["errors"] += 1
    finally:
        _STATS["running"] = False
        _STATS["scheduler_status"] = "idle"

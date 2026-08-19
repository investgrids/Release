"""
Critical Event Coverage Engine.

The audit found two independent event-scoring systems (Event.impact_score,
starved by the paused job_enrich_events; EventTriage, live and unaffected)
but no layer that tracked whether an important EventTriage row actually
ended up covered by a published article — important events could be
silently dropped by the per-cycle cap (max 3), the daily article cap, or
duplicate-detection, with no record that it ever happened.

This module doesn't re-score events — it reuses the existing Intelligence
Priority Queue (app.services.intelligence.engine.compute_priority, already
used by the homepage's live pulse) to classify, then persists an
EventCoverage row and updates it as the event moves through AIPE.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import Event, EventCompany
from app.db.models.event_coverage import EventCoverage
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.macro_release import MacroRelease
from app.services.intelligence.engine import compute_priority

log = structlog.get_logger(__name__)

# Critical/High must never be silently dropped by cycle/daily caps —
# Medium/Low go through the normal pipeline unchanged.
_MUST_COVER_TIERS = ("Critical", "High")

# publisher.py sets trigger_type="high_urgency_triage" only on the
# selection path that generates an article FROM a real, currently-selected
# EventTriage row (confirmed by reading publisher.py directly — the three
# call sites at lines ~412/742/809 all set this alongside a real
# triage_event.get("event_id")). Evergreen/historical/comparison articles
# use a synthetic "evergreen-{slug}" / "historical-{slug}" story_id as
# trigger_event_id instead and never set this trigger_type, so this one
# field is a reliable "was this article generated because of a specific
# triaged event" signal — not inferred, verified against the actual
# call sites.
_EVENT_TRIGGER_TYPE = "high_urgency_triage"

# morning_intelligence/market_wrap are scheduled daily-summary articles
# that publisher.py also tags with trigger_type="high_urgency_triage"
# (they're generated mid-cycle alongside whatever triage event happens to
# be selected that run), but they are not "this specific event got
# covered" — confirmed via a real production query: 4 of 16
# trigger_type='high_urgency_triage' rows were morning_intelligence/
# market_wrap, attributed to whatever event was mid-cycle at generation
# time rather than genuinely triggered by it.
_SCHEDULED_DIGEST_TYPES = ("morning_intelligence", "market_wrap")

# SEO indexability rule v2 (2026-08 audit) — see event_service.py's
# assembly of `summary.why_it_matters`/`aiAnalysis.bull_case` from
# `Event.ai_summary`. Verified live against the 71 event pages Search
# Console had crawled as noindex: 25 matched a substantive category below
# by title, but ALL 25 (and every other checked event, including
# currently-indexable ones sourced from raw corporate filings) still
# carried these exact two strings verbatim in `ai_summary` — the AI
# enrichment pipeline's own hardcoded fallback text when real analysis
# wasn't produced, not real per-event content. Indexing on category alone
# would have shipped 25 pages of "X Limited has informed the Exchange
# about Acquisition" wrapped in a template restating that same sentence —
# exactly the thin/unhelpful content Google's indexing guidance warns
# against, regardless of how important the underlying filing sounds.
_GENERIC_FALLBACK_WHY = "This event may have market implications."
_GENERIC_FALLBACK_BULL = "Positive fundamentals could drive upside."

# Title-text category signal — the exchange's own filing-category label
# (NSE's `desc`/`subject`, e.g. "Financial Results") is never persisted to
# a structured column (see nse_provider.py's _normalize_announcement: it's
# used only as a headline fallback), so the title itself is the only
# reliable signal for "what kind of filing is this." This is a *candidate*
# signal only — see _has_genuine_content_quality below, which every event
# must also pass regardless of category or triage tier.
_SUBSTANTIVE_CATEGORY_RE = re.compile(
    r"(financial results?|\bacquisition\b|\bdisposal\b|\bdivestment\b|"
    r"\bdividend\b|\bbuy[\s-]?back\b|\border win\b|"
    r"\bcapacity (addition|expansion)\b|"
    r"\b(fund[\s-]?raising|preferential issue|rights issue|\bqip\b|fccbs?)\b|"
    r"\bcredit rating\b|\b(litigation|dispute|regulatory action|penalty)\b|"
    r"\b(merger|demerger|amalgamation|scheme of arrangement)\b|"
    r"\b(default|fraud|closure of operations)\b|"
    r"\b(product|business) launch\b)",
    re.IGNORECASE,
)


def _matches_substantive_category(title: str | None) -> bool:
    return bool(title) and bool(_SUBSTANTIVE_CATEGORY_RE.search(title))


def _has_genuine_content_quality(
    *, title: str | None, description: str | None, ai_summary: dict | None,
    impact_score: float | None, confidence: float | None, any_company_has_reason: bool,
    company_count: int,
) -> bool:
    """The content-quality floor every indexable event must clear,
    regardless of triage tier or category — 'important' and 'actually
    analyzed' are different questions (see module docstring above)."""
    ai_summary = ai_summary or {}
    never_expanded = (description or "") == (title or "")
    why = (ai_summary.get("why_it_matters") or "").strip()
    bull = ((ai_summary.get("analysis") or {}).get("bull_case") or "").strip()
    never_scored = impact_score is None and confidence is None
    # An event with zero linked companies (e.g. a pure macro/economy story)
    # isn't penalized for lacking a company reason it was never going to
    # have; one WITH companies but no real per-company reasoning is thin.
    company_reasoning_ok = company_count == 0 or any_company_has_reason
    return (
        not never_expanded
        and why != _GENERIC_FALLBACK_WHY
        and bull != _GENERIC_FALLBACK_BULL
        and not never_scored
        and company_reasoning_ok
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def classify(urgency: int | None, importance: int | None, headline: str | None) -> tuple[int, str]:
    """Thin pass-through to the existing Intelligence Priority Queue —
    kept as its own function here only so coverage_engine has one obvious
    place documenting which tiers are must-cover, not to re-score."""
    return compute_priority(urgency, importance, None, headline)


def is_must_cover(priority_tier: str) -> bool:
    return priority_tier in _MUST_COVER_TIERS


async def compute_indexable_batch(db: AsyncSession, event_ids: list[str]) -> dict[str, bool]:
    """Phase 15 (2026-08 audit), revised v2 in the same month after a
    Search Console coverage export showed real dividend/acquisition/
    financial-results pages sitting noindex purely because they weren't
    Critical/High triage — an urgency signal for the trading feed, not a
    page-quality signal. v1's rule (kept here as the 'significance' input
    below) conflated the two.

    An event is indexable when ALL of:
      - it has a real, clean slug (no canonical URL, no indexing — the
        routing layer's own definition of 'this page has a real address'), AND
      - it clears the content-quality floor (_has_genuine_content_quality)
        — real per-event analysis, not the AI pipeline's hardcoded
        fallback text reflecting the filing's own title back at it, AND
      - it's significant OR a substantive filing category:
          - has a real extracted MacroRelease, OR
          - its EventCoverage priority tier is Critical or High, OR
          - its title matches a substantive category
            (_matches_substantive_category) — financial results,
            acquisitions, dividends, credit ratings, etc.

    Deliberately NOT 'Critical/High is automatically indexable' — a
    Critical/High event that hasn't actually been analyzed yet (still
    carrying the generic fallback text) is exactly as thin as a routine
    filing with the same problem; the quality floor applies to every path,
    not just the category one.

    No EventCoverage row at all (never triaged) is simply absent from
    priority_by_id below, not an error — it just can't satisfy the
    Critical/High branch and falls through to the macro/category checks.
    Returns a dict so callers building a list of summaries can look up
    each event's flag in O(1) rather than one query per event."""
    if not event_ids:
        return {}
    coverage_rows = (await db.execute(
        select(EventCoverage.event_id, EventCoverage.priority)
        .where(EventCoverage.event_id.in_(event_ids))
    )).all()
    priority_by_id = {eid: priority for eid, priority in coverage_rows}

    macro_rows = (await db.execute(
        select(MacroRelease.id).where(
            MacroRelease.id.in_(event_ids), MacroRelease.release_value.is_not(None),
        )
    )).all()
    has_macro = {row[0] for row in macro_rows}

    event_rows = (await db.execute(
        select(
            Event.id, Event.slug, Event.title, Event.description,
            Event.ai_summary, Event.impact_score, Event.confidence,
        ).where(Event.id.in_(event_ids))
    )).all()

    company_rows = (await db.execute(
        select(EventCompany.event_id, EventCompany.reason)
        .where(EventCompany.event_id.in_(event_ids))
    )).all()
    company_count_by_id: dict[str, int] = {}
    any_reason_by_id: dict[str, bool] = {}
    for eid, reason in company_rows:
        company_count_by_id[eid] = company_count_by_id.get(eid, 0) + 1
        if reason and reason.strip():
            any_reason_by_id[eid] = True

    result: dict[str, bool] = {eid: False for eid in event_ids}
    for eid, slug, title, description, ai_summary, impact_score, confidence in event_rows:
        if not slug:
            continue
        significant_or_substantive = (
            eid in has_macro
            or is_must_cover(priority_by_id.get(eid, ""))
            or _matches_substantive_category(title)
        )
        if not significant_or_substantive:
            continue
        result[eid] = _has_genuine_content_quality(
            title=title, description=description, ai_summary=ai_summary,
            impact_score=impact_score, confidence=confidence,
            any_company_has_reason=any_reason_by_id.get(eid, False),
            company_count=company_count_by_id.get(eid, 0),
        )
    return result


async def compute_indexable(db: AsyncSession, event_id: str) -> bool:
    result = await compute_indexable_batch(db, [event_id])
    return result.get(event_id, False)


def classify_article(article_type: str | None, trigger_type: str | None, is_evergreen: bool) -> str:
    """Buckets one IntelligenceArticle for operational reporting, so
    'articles published' is never silently read as 'events covered' —
    the two systems (IntelligenceArticle, EventCoverage) can legitimately
    diverge in both directions: one event can spawn several angle
    articles, and a scheduled digest can publish with zero events behind
    it.

    - COMPARISON / HISTORICAL: distinct recurring content forms, not tied
      to a single triggering event even though historical_intelligence is
      also is_evergreen=True.
    - EVENT_TRIGGERED: generated because a specific triaged event was
      selected (see _EVENT_TRIGGER_TYPE comment above). Per-company /
      sector-rollup fan-out articles from the same event share this same
      trigger_type and a common parent_event_group_id — they're counted
      here too rather than invented as a separate "CAMPAIGN" bucket,
      since there's no concrete evidence of that as a distinct,
      separately-queryable thing in this schema.
    - EVERGREEN: is_evergreen=True and not already classified above
      (e.g. educational_intelligence evergreen topics, which use a
      synthetic trigger_event_id and no high_urgency_triage trigger_type).
    - OTHER: anything left over (e.g. live_signal with no trigger_type).
    """
    if article_type == "comparison_intelligence":
        return "COMPARISON"
    if article_type == "historical_intelligence":
        return "HISTORICAL"
    if trigger_type == _EVENT_TRIGGER_TYPE and article_type not in _SCHEDULED_DIGEST_TYPES:
        return "EVENT_TRIGGERED"
    if is_evergreen:
        return "EVERGREEN"
    return "OTHER"


async def register_event(
    db: AsyncSession, *, event_id: str, source: str | None, headline: str,
    urgency: int, importance: int, sectors: list | None, companies: list | None,
) -> EventCoverage | None:
    """Upsert a coverage row right after EventTriage is stored — every
    triaged event gets one, not just the important ones, so 'what did we
    see today' stays a complete, honest answer rather than only tracking
    the events that turned out to matter."""
    try:
        existing = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if existing:
            existing.last_checked_at = _now()
            await db.commit()
            return existing

        score, tier = classify(urgency, importance, headline)
        row = EventCoverage(
            id=str(uuid.uuid4()),
            event_id=event_id,
            priority=tier,
            priority_score=score,
            detected_at=_now(),
            source=source,
            event_title=(headline or "")[:512],
            sectors=sectors or [],
            companies=companies or [],
            article_required=is_must_cover(tier),
            coverage_status="DETECTED",
            last_checked_at=_now(),
        )
        db.add(row)
        await db.commit()
        return row
    except Exception as exc:
        log.error("coverage.register_failed", error=str(exc), event_id=event_id)
        return None


async def mark_published(db: AsyncSession, *, event_id: str | None, article_id: str) -> None:
    if not event_id:
        return
    try:
        row = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if row:
            row.article_generated = True
            row.article_id = article_id
            row.daily_brief_covered = True
            row.coverage_status = "PUBLISHED"
            row.last_checked_at = _now()
            await db.commit()
    except Exception as exc:
        log.error("coverage.mark_published_failed", error=str(exc), event_id=event_id)


async def mark_covered_by_existing(db: AsyncSession, *, event_id: str | None, article_id: str) -> None:
    if not event_id:
        return
    try:
        row = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if row:
            row.article_generated = True
            row.article_id = article_id
            row.daily_brief_covered = True
            row.coverage_status = "COVERED_BY_EXISTING_ARTICLE"
            row.last_checked_at = _now()
            await db.commit()
    except Exception as exc:
        log.error("coverage.mark_covered_failed", error=str(exc), event_id=event_id)


async def mark_failed(db: AsyncSession, *, event_id: str | None, reason: str) -> None:
    """Records that coverage was attempted and didn't succeed — generation
    failure, validation rejection, or a publish-cycle exception. Without
    this, a failed attempt and 'never attempted' were both just DETECTED
    forever; find_uncovered_critical couldn't tell them apart, and a
    genuinely stuck row looked identical to one still waiting its turn."""
    if not event_id:
        return
    try:
        row = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if row and row.coverage_status not in ("PUBLISHED", "COVERED_BY_EXISTING_ARTICLE"):
            row.coverage_status = "FAILED"
            row.failure_reason = reason[:256]
            row.last_checked_at = _now()
            await db.commit()
    except Exception as exc:
        log.error("coverage.mark_failed_failed", error=str(exc), event_id=event_id)


async def find_uncovered_critical(db: AsyncSession, hours: int = 24) -> list[EventCoverage]:
    """Read-only observability check — Critical/High rows detected within
    the window that never got an article. Does not trigger generation
    itself (that's explicitly a later phase, per the implementation
    order)."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(EventCoverage)
        .where(EventCoverage.priority.in_(list(_MUST_COVER_TIERS)))
        .order_by(EventCoverage.detected_at.desc())
        .limit(500)
    )).scalars().all()
    # SQLite reads DateTime(timezone=True) back tz-naive — same footgun
    # documented elsewhere in this codebase (tools.py, insights.py).
    return [
        r for r in rows
        if r.detected_at and r.detected_at.replace(tzinfo=timezone.utc) >= cutoff
        and r.coverage_status not in ("PUBLISHED", "COVERED_BY_EXISTING_ARTICLE")
    ]


async def funnel_counts(db: AsyncSession, hours: int = 24) -> dict[str, Any]:
    """Publishing funnel observability (Part 25/8) — real counts derived
    from EventCoverage rows detected in the window, not a fabricated or
    estimated figure at any stage.

    Bug fix (2026-08-13 re-audit): this query had a hard .limit(2000) with
    NO ORDER BY — since real production volume is ~800-900 detections/day
    (confirmed live), a 168h (7-day) call was requesting ~6,000+ rows
    against a 2,000 cap, and with no deterministic ordering, which 2,000
    rows the DB engine happened to return was arbitrary — not necessarily
    the most recent ones, and not reproducible between calls. Every
    funnel_counts(hours=168) reading taken before this fix (including this
    audit's own initial production read: "detected: 2000" at hours=168,
    which landing exactly on the cap was itself the tell) was a count over
    an undefined, non-deterministic subset — not a real 7-day total. Now:
    ordered by detected_at DESC (so a truncation always drops the OLDEST
    rows in the window, not an arbitrary mix) and the cap raised to comfortably
    cover a week at current volume with headroom for growth.
    """
    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(EventCoverage)
        .where(EventCoverage.detected_at >= cutoff - timedelta(days=1))  # generous bound, filtered below
        .order_by(EventCoverage.detected_at.desc())
        .limit(10000)
    )).scalars().all()
    recent = [r for r in rows if r.detected_at and r.detected_at.replace(tzinfo=timezone.utc) >= cutoff]
    truncated = len(rows) >= 10000

    detected = len(recent)
    by_tier = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    published = 0
    covered_existing = 0
    failed = 0
    uncovered_critical = 0
    for r in recent:
        by_tier[r.priority] = by_tier.get(r.priority, 0) + 1
        if r.coverage_status == "PUBLISHED":
            published += 1
        elif r.coverage_status == "COVERED_BY_EXISTING_ARTICLE":
            covered_existing += 1
        elif r.coverage_status == "FAILED":
            failed += 1
        if is_must_cover(r.priority) and r.coverage_status not in ("PUBLISHED", "COVERED_BY_EXISTING_ARTICLE"):
            uncovered_critical += 1

    return {
        "window_hours": hours,
        "detected": detected,
        "by_priority": by_tier,
        "critical": by_tier["Critical"],
        "high": by_tier["High"],
        "published": published,
        "covered_by_existing_article": covered_existing,
        "failed": failed,
        "uncovered_critical_or_high": uncovered_critical,
        "possibly_truncated": truncated,
        "generated_at": _now().isoformat(),
    }


async def article_classification_counts(db: AsyncSession, hours: int = 24) -> dict[str, Any]:
    """Phase 12 (2026-08 audit) — same truncation-safety pattern as
    funnel_counts: ordered by created_at DESC with a generous bound and
    cap, rather than an unordered .limit() that could silently drop an
    arbitrary subset."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.created_at >= cutoff - timedelta(days=1))
        .order_by(IntelligenceArticle.created_at.desc())
        .limit(10000)
    )).scalars().all()
    recent = [
        r for r in rows
        if r.created_at and r.created_at.replace(tzinfo=timezone.utc) >= cutoff
        and r.status == "published"
    ]
    truncated = len(rows) >= 10000

    by_category = {"EVENT_TRIGGERED": 0, "EVERGREEN": 0, "HISTORICAL": 0, "COMPARISON": 0, "OTHER": 0}
    event_ids: set[str] = set()
    for r in recent:
        category = classify_article(r.article_type, r.trigger_type, bool(r.is_evergreen))
        by_category[category] += 1
        if category == "EVENT_TRIGGERED" and r.trigger_event_id:
            event_ids.add(r.trigger_event_id)

    return {
        "window_hours": hours,
        "total_articles_published": len(recent),
        "by_category": by_category,
        "event_triggered_articles_published": by_category["EVENT_TRIGGERED"],
        "distinct_events_with_articles": len(event_ids),
        "possibly_truncated": truncated,
        "generated_at": _now().isoformat(),
    }


async def coverage_vs_publishing_summary(db: AsyncSession, hours: int = 24) -> dict[str, Any]:
    """The three headline metrics operational reporting must keep
    distinct (task requirement, Phase 12): total articles published,
    material events covered, and event-triggered articles published.
    'Material events covered' is EventCoverage.PUBLISHED +
    COVERED_BY_EXISTING_ARTICLE — a real event getting an article, not an
    article count. The other two come from IntelligenceArticle directly.
    These are two independent systems and can legitimately diverge either
    way (one event -> several angle articles; a scheduled digest ->
    zero events)."""
    funnel = await funnel_counts(db, hours=hours)
    articles = await article_classification_counts(db, hours=hours)
    material_events_covered = funnel["published"] + funnel["covered_by_existing_article"]
    return {
        "window_hours": hours,
        "total_articles_published": articles["total_articles_published"],
        "material_events_covered": material_events_covered,
        "event_triggered_articles_published": articles["event_triggered_articles_published"],
        "article_categories": articles["by_category"],
        "possibly_truncated": funnel["possibly_truncated"] or articles["possibly_truncated"],
        "generated_at": _now().isoformat(),
    }


async def enrichment_health(db: AsyncSession, hours: int = 24) -> dict[str, Any]:
    """Dashboard Phase 4B — pending/retrying/permanently-failed/completed
    enrichment counts. Reuses event_pipeline's real _MAX_ENRICHMENT_RETRIES
    constant and Event.enrichment_status/retry_count directly rather than
    re-deriving retry-eligibility logic a second time (that logic already
    lives in event_repository.get_pending_enrichment — this just counts by
    status, it doesn't re-decide what's eligible to run next)."""
    from app.pipeline.event_pipeline import _MAX_ENRICHMENT_RETRIES

    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(Event.enrichment_status, func.count(Event.id))
        .where(Event.created_at >= cutoff)
        .group_by(Event.enrichment_status)
    )).all()
    by_status = {status or "unknown": count for status, count in rows}

    retrying = (await db.execute(
        select(func.count(Event.id)).where(
            Event.created_at >= cutoff,
            Event.enrichment_status == "failed",
            Event.retry_count < _MAX_ENRICHMENT_RETRIES,
        )
    )).scalar_one()

    return {
        "window_hours": hours,
        "pending": by_status.get("pending", 0),
        "processing": by_status.get("processing", 0),
        "retrying": retrying,
        "permanently_failed": by_status.get("failed_permanent", 0),
        "completed": by_status.get("done", 0),
        "by_status": by_status,
        "generated_at": _now().isoformat(),
    }


async def publishing_latency(db: AsyncSession, hours: int = 24) -> dict[str, Any]:
    """Dashboard Phase 4 — event-to-publish latency: real elapsed time
    between EventCoverage.detected_at (when the triaged event was first
    seen) and the matched IntelligenceArticle.published_at (when it
    actually went live), for rows that reached PUBLISHED in the window.
    Only computed from rows with both real timestamps present — never
    estimated or defaulted to 0 when either side is missing."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(EventCoverage.detected_at, IntelligenceArticle.published_at)
        .join(IntelligenceArticle, EventCoverage.article_id == IntelligenceArticle.id)
        .where(
            EventCoverage.coverage_status == "PUBLISHED",
            EventCoverage.detected_at >= cutoff - timedelta(days=1),
        )
    )).all()

    samples: list[float] = []
    for detected_at, published_at in rows:
        if not detected_at or not published_at:
            continue
        d = detected_at.replace(tzinfo=timezone.utc) if detected_at.tzinfo is None else detected_at
        p = published_at.replace(tzinfo=timezone.utc) if published_at.tzinfo is None else published_at
        if d < cutoff:
            continue
        delta_minutes = (p - d).total_seconds() / 60
        if delta_minutes >= 0:
            samples.append(delta_minutes)

    return {
        "window_hours": hours,
        "sample_count": len(samples),
        "avg_event_to_publish_minutes": round(sum(samples) / len(samples), 1) if samples else None,
        "min_event_to_publish_minutes": round(min(samples), 1) if samples else None,
        "max_event_to_publish_minutes": round(max(samples), 1) if samples else None,
        "generated_at": _now().isoformat(),
    }

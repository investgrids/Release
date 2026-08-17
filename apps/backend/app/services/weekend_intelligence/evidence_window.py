"""
Evidence window assembly — the "> last trading close AND <= now" bounded
query design doc §17 requires ("do not use `latest N rows` without a
lower timestamp bound — this is one of the core correctness requirements").

Deliberately queries each source table's own guaranteed-non-null ingestion
timestamp column for the WHERE bound (published_at/created_at/ingested_at/
signal_at — see the per-table comment below), even where a given
normalizer's `observed_at` field prefers a different, more "real" column
when one is available (see evidence.py's docstrings). The window boundary
answers "what did we learn about since the last checkpoint"; `observed_at`
on the resulting EvidenceItem is the best-effort "when did this actually
happen" for display/materiality purposes. Those are two different
questions and this module is explicit about only answering the first one
via SQL.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_announcements import CompanyAnnouncement
from app.db.models.company_signal import AICompanySignal
from app.db.models.event import Event, GovernmentPolicy
from app.db.models.intelligence import EventTriage
from app.db.models.opportunity import Opportunity
from app.db.models_legacy import NewsArticle
from app.services.intelligence.engine import compute_priority
from app.services.weekend_intelligence.evidence import (
    EvidenceItem,
    normalize_announcement,
    normalize_company_signal,
    normalize_event,
    normalize_news,
    normalize_opportunity,
    normalize_policy,
)

log = structlog.get_logger(__name__)

# Source-type keys, matching EvidenceItem.source_type exactly — used both
# as the failed_sources vocabulary here and as the lookup key for the
# human-readable labels risk_synthesis.py's confidence-warning generator
# builds from them.
SOURCE_EVENT = "event"
SOURCE_POLICY = "policy"
SOURCE_ANNOUNCEMENT = "announcement"
SOURCE_NEWS = "news"
SOURCE_COMPANY_SIGNAL = "company_signal"
SOURCE_OPPORTUNITY = "opportunity"


# EventTriage.sentiment's own vocabulary -> EvidenceItem.direction's.
# Phase 6E-x: found live that 0/103 real event-sourced Development evidence
# rows carried a direction, purely because nothing read this already-real,
# already-populated field — not a new classification, just a straight
# vocabulary rename of an existing AI-triage output.
_SENTIMENT_TO_DIRECTION = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}


async def _event_triage_context(db: AsyncSession, event_ids: list[str]) -> dict[str, tuple[str, str | None]]:
    """(priority_tier, direction) per event_id, via a single batched
    EventTriage query — not one query per event, not two queries for two
    fields off the same row. Priority tier reuses engine.py's own
    compute_priority (the module's own stated public alias for this exact
    purpose) rather than a new threshold; direction reuses
    EventTriage.sentiment via _SENTIMENT_TO_DIRECTION above. An event with
    no EventTriage row yet (enrichment still pending) simply has neither
    here, not a fabricated one."""
    if not event_ids:
        return {}
    rows = (await db.execute(
        select(EventTriage.event_id, EventTriage.urgency, EventTriage.importance,
               EventTriage.headline, EventTriage.sentiment)
        .where(EventTriage.event_id.in_(event_ids))
    )).all()
    context: dict[str, tuple[str, str | None]] = {}
    for event_id, urgency, importance, headline, sentiment in rows:
        _, tier = compute_priority(urgency, importance, None, headline)
        context[event_id] = (tier, _SENTIMENT_TO_DIRECTION.get(sentiment))
    return context


async def collect_evidence_since(
    db: AsyncSession, since: datetime, until: datetime, *, limit_per_source: int = 200,
    failed_sources: list[str] | None = None,
) -> list[EvidenceItem]:
    """
    Assemble normalized evidence from every Phase 1A-supported source,
    bounded to (since, until]. `limit_per_source` is a defensive cap, not
    a "latest N instead of a real bound" shortcut — the bound itself is
    always the WHERE clause below; the limit only protects against an
    unexpectedly huge window (e.g. a caller passing a multi-week `since`
    by mistake) from loading an unbounded result set into memory.

    Explicitly NOT normalized here (design doc §16's exclusion list):
    Kronos, calendar placeholder rows, the dead economic-calendar
    provider, or any invented supply-chain relationship.

    Per-source failure isolation (Phase 1E hardening, post-review):
    each of the 6 sources below is independently try/except-wrapped —
    the same pattern price_monitor.py's capture_close_snapshot() already
    established for its own secondary sources (VIX, FII/DII, sector
    ETFs, ...). Before this, a single failing source-table query (e.g. a
    transient lock, a malformed row) raised out of this function
    entirely, aborting the WHOLE checkpoint even though the other 5
    sources read fine — real weekend evidence is inherently
    multi-source, so one temporary source problem should not block
    everything else from updating. `failed_sources` is populated
    in-place (never a return-type change — every existing caller/test
    keeps working unmodified) with the EvidenceItem source_type strings
    (see the SOURCE_* constants above) for any source that failed;
    build_weekend_intelligence uses this to force status=degraded and
    surface a plain-English confidence warning naming exactly which
    source was unavailable (risk_synthesis.py), never silently.

    A caught failure isolates via a SAVEPOINT (`db.begin_nested()`), not
    a full `db.rollback()`: a full rollback expires every ORM object
    already loaded earlier in the SAME session (e.g. build_weekend_
    intelligence's own `baseline` MarketSnapshot, fetched before this
    function is even called) — a real bug caught while testing this
    exact refinement, where accessing `baseline.sector_ranks` AFTER a
    plain rollback crashed with SQLAlchemy's MissingGreenlet error
    (accessing a since-expired lazy attribute outside the async
    context). A SAVEPOINT undoes only THIS source's own statements on
    failure, leaving the rest of the outer transaction — including
    already-loaded objects — untouched. Supported by both SQLite
    (aiosqlite) and Postgres, so this degrades safely on both backends
    this codebase runs on.
    """
    items: list[EvidenceItem] = []
    failed = failed_sources if failed_sources is not None else []

    try:
        async with db.begin_nested():
            event_rows = list((await db.execute(
                select(Event)
                .where(Event.published_at > since, Event.published_at <= until)
                .order_by(Event.published_at.desc())
                .limit(limit_per_source)
            )).scalars().all())
            triage_context = await _event_triage_context(db, [e.id for e in event_rows])
            for e in event_rows:
                tier, direction = triage_context.get(e.id, (None, None))
                items.append(normalize_event(e, priority_tier=tier, direction=direction))
    except Exception as exc:
        log.warning("evidence_window.source_failed", source=SOURCE_EVENT, error=str(exc)[:200])
        failed.append(SOURCE_EVENT)

    try:
        async with db.begin_nested():
            policy_rows = (await db.execute(
                select(GovernmentPolicy)
                .where(GovernmentPolicy.created_at > since, GovernmentPolicy.created_at <= until)
                .order_by(GovernmentPolicy.created_at.desc())
                .limit(limit_per_source)
            )).scalars().all()
            items.extend(normalize_policy(p) for p in policy_rows)
    except Exception as exc:
        log.warning("evidence_window.source_failed", source=SOURCE_POLICY, error=str(exc)[:200])
        failed.append(SOURCE_POLICY)

    try:
        async with db.begin_nested():
            announcement_rows = (await db.execute(
                select(CompanyAnnouncement)
                .where(CompanyAnnouncement.ingested_at > since, CompanyAnnouncement.ingested_at <= until)
                .order_by(CompanyAnnouncement.ingested_at.desc())
                .limit(limit_per_source)
            )).scalars().all()
            items.extend(normalize_announcement(a) for a in announcement_rows)
    except Exception as exc:
        log.warning("evidence_window.source_failed", source=SOURCE_ANNOUNCEMENT, error=str(exc)[:200])
        failed.append(SOURCE_ANNOUNCEMENT)

    try:
        async with db.begin_nested():
            news_rows = (await db.execute(
                select(NewsArticle)
                .where(NewsArticle.created_at > since, NewsArticle.created_at <= until)
                .order_by(NewsArticle.created_at.desc())
                .limit(limit_per_source)
            )).scalars().all()
            items.extend(normalize_news(n) for n in news_rows)
    except Exception as exc:
        log.warning("evidence_window.source_failed", source=SOURCE_NEWS, error=str(exc)[:200])
        failed.append(SOURCE_NEWS)

    try:
        async with db.begin_nested():
            signal_rows = (await db.execute(
                select(AICompanySignal)
                .where(AICompanySignal.signal_at > since, AICompanySignal.signal_at <= until)
                .order_by(AICompanySignal.signal_at.desc())
                .limit(limit_per_source)
            )).scalars().all()
            items.extend(normalize_company_signal(s) for s in signal_rows)
    except Exception as exc:
        log.warning("evidence_window.source_failed", source=SOURCE_COMPANY_SIGNAL, error=str(exc)[:200])
        failed.append(SOURCE_COMPANY_SIGNAL)

    try:
        async with db.begin_nested():
            opportunity_rows = (await db.execute(
                select(Opportunity)
                .where(Opportunity.created_at > since, Opportunity.created_at <= until)
                .order_by(Opportunity.created_at.desc())
                .limit(limit_per_source)
            )).scalars().all()
            items.extend(normalize_opportunity(o) for o in opportunity_rows)
    except Exception as exc:
        log.warning("evidence_window.source_failed", source=SOURCE_OPPORTUNITY, error=str(exc)[:200])
        failed.append(SOURCE_OPPORTUNITY)

    if failed:
        log.warning("evidence_window.partial_collection", failed_sources=failed, collected_count=len(items))

    return items

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


async def _event_priority_tiers(db: AsyncSession, event_ids: list[str]) -> dict[str, str]:
    """Priority tier (Critical/High/Medium/Low) per event_id, via a single
    batched EventTriage query — not one query per event. Reuses
    engine.py's own compute_priority (the module's own stated public alias
    for this exact purpose) rather than a new threshold. An event with no
    EventTriage row yet (enrichment still pending) simply has no tier
    here, not a fabricated one."""
    if not event_ids:
        return {}
    rows = (await db.execute(
        select(EventTriage.event_id, EventTriage.urgency, EventTriage.importance,
               EventTriage.headline)
        .where(EventTriage.event_id.in_(event_ids))
    )).all()
    tiers: dict[str, str] = {}
    for event_id, urgency, importance, headline in rows:
        _, tier = compute_priority(urgency, importance, None, headline)
        tiers[event_id] = tier
    return tiers


async def collect_evidence_since(
    db: AsyncSession, since: datetime, until: datetime, *, limit_per_source: int = 200,
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
    """
    items: list[EvidenceItem] = []

    event_rows = list((await db.execute(
        select(Event)
        .where(Event.published_at > since, Event.published_at <= until)
        .order_by(Event.published_at.desc())
        .limit(limit_per_source)
    )).scalars().all())
    tiers = await _event_priority_tiers(db, [e.id for e in event_rows])
    items.extend(normalize_event(e, priority_tier=tiers.get(e.id)) for e in event_rows)

    policy_rows = (await db.execute(
        select(GovernmentPolicy)
        .where(GovernmentPolicy.created_at > since, GovernmentPolicy.created_at <= until)
        .order_by(GovernmentPolicy.created_at.desc())
        .limit(limit_per_source)
    )).scalars().all()
    items.extend(normalize_policy(p) for p in policy_rows)

    announcement_rows = (await db.execute(
        select(CompanyAnnouncement)
        .where(CompanyAnnouncement.ingested_at > since, CompanyAnnouncement.ingested_at <= until)
        .order_by(CompanyAnnouncement.ingested_at.desc())
        .limit(limit_per_source)
    )).scalars().all()
    items.extend(normalize_announcement(a) for a in announcement_rows)

    news_rows = (await db.execute(
        select(NewsArticle)
        .where(NewsArticle.created_at > since, NewsArticle.created_at <= until)
        .order_by(NewsArticle.created_at.desc())
        .limit(limit_per_source)
    )).scalars().all()
    items.extend(normalize_news(n) for n in news_rows)

    signal_rows = (await db.execute(
        select(AICompanySignal)
        .where(AICompanySignal.signal_at > since, AICompanySignal.signal_at <= until)
        .order_by(AICompanySignal.signal_at.desc())
        .limit(limit_per_source)
    )).scalars().all()
    items.extend(normalize_company_signal(s) for s in signal_rows)

    opportunity_rows = (await db.execute(
        select(Opportunity)
        .where(Opportunity.created_at > since, Opportunity.created_at <= until)
        .order_by(Opportunity.created_at.desc())
        .limit(limit_per_source)
    )).scalars().all()
    items.extend(normalize_opportunity(o) for o in opportunity_rows)

    return items

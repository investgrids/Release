"""
Warehouse Read Service — Phase 2 Consumption (owner instruction, 2026-08-25,
following the read-only Warehouse Consumption Audit, artifacts/
warehouse_consumption_audit.md).

Scope was deliberately narrow at first per the audit's own verdict
("WAREHOUSE READY FOR LIMITED CONSUMPTION"): entity-independent
market/macro/sector context only, with entity-linked evidence retrieval
explicitly deferred until RawEvidence had a real, working path to an
entity (the audit's ICICIBANK case study found none — a naive
keyword/title match would have reproduced the exact 3IINFOLTD/IIFL
wrong-entity-contamination bug already fixed once).

That gap is now closed: `EvidenceEntityLink` (built on this branch,
commit 4453009) resolves NSE evidence to a real canonical `entity_id` via
the same `resolve_identifier()` the rest of Company Identity already
uses — never a fuzzy/keyword match. `get_evidence_for_entity()` below is
the method this docstring always said belonged here "only after that gap
is closed" — see AI Article V2 Phase A
(artifacts/ai_article_v2_phase_a_evidence_grounding.md) for its first
real consumer.

This module only ever returns real, stored rows with their real quality
label attached — it never fabricates a value, never silently promotes a
`source_failure`/stale row to look fresh, and never computes a verdict
(bullish/bearish/whatever) from the data. That judgment stays downstream,
in the callers (e.g. `ai_pipeline`'s own fusion/decision layers).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.market_observation import MarketObservation

# A row older than this is not treated as "current" by get_latest_market_
# observations's own freshness flag -- roughly 3x the real 15-minute capture
# cadence (see market_observations.py's _BUCKET_MINUTES), so one missed
# cycle doesn't flip everything to stale, but a genuinely stopped capture
# job does get flagged rather than silently served as if current.
_FRESHNESS_WINDOW = timedelta(minutes=45)


@dataclass(frozen=True)
class ObservationSnapshot:
    metric: str
    value: float | None
    unit: str | None
    quality: str
    observation_time: datetime
    source_id: str
    is_current: bool   # observation_time within _FRESHNESS_WINDOW of "now" (or of the requested `at`)
    extra: dict | None = None

    @property
    def has_real_value(self) -> bool:
        """False for a real, honestly-recorded source_failure row -- never
        drop these silently; callers decide whether/how to surface the gap."""
        return self.value is not None


async def get_latest_market_observations(
    db: AsyncSession, metrics: list[str] | None = None,
) -> dict[str, ObservationSnapshot]:
    """The most recent real row per metric. Returns only metrics that have
    at least one row ever captured; callers must handle a missing key
    themselves (never filled in as a fake zero/absent-but-assumed-normal
    value) -- exactly the discipline market_observations.py's own capture
    path already follows for source_failure rows."""
    query = select(MarketObservation).order_by(MarketObservation.observation_time.desc())
    if metrics:
        query = query.where(MarketObservation.metric.in_(metrics))
    rows = (await db.execute(query)).scalars().all()

    now = datetime.now(timezone.utc)
    out: dict[str, ObservationSnapshot] = {}
    for row in rows:
        if row.metric in out:
            continue   # already have the newest row for this metric (query is DESC)
        obs_time = row.observation_time if row.observation_time.tzinfo else row.observation_time.replace(tzinfo=timezone.utc)
        out[row.metric] = ObservationSnapshot(
            metric=row.metric, value=row.value, unit=row.unit, quality=row.quality,
            observation_time=obs_time, source_id=row.source_id,
            is_current=(now - obs_time) <= _FRESHNESS_WINDOW,
            extra=row.extra,
        )
    return out


async def get_market_context_at(
    db: AsyncSession, at: datetime, metrics: list[str] | None = None,
    window_minutes: int = 30,
) -> dict[str, ObservationSnapshot]:
    """The real observation nearest `at`, per metric, within a bounded
    window either side -- for "what was the market doing when X happened"
    framing. No interpolation, no forward-fill: a metric with nothing in
    the window is simply absent from the result, same discipline as
    get_latest_market_observations."""
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    lo, hi = at - timedelta(minutes=window_minutes), at + timedelta(minutes=window_minutes)

    query = select(MarketObservation).where(
        MarketObservation.observation_time >= lo, MarketObservation.observation_time <= hi,
    )
    if metrics:
        query = query.where(MarketObservation.metric.in_(metrics))
    rows = (await db.execute(query)).scalars().all()

    best: dict[str, tuple[float, MarketObservation]] = {}
    for row in rows:
        obs_time = row.observation_time if row.observation_time.tzinfo else row.observation_time.replace(tzinfo=timezone.utc)
        delta = abs((obs_time - at).total_seconds())
        if row.metric not in best or delta < best[row.metric][0]:
            best[row.metric] = (delta, row)

    out: dict[str, ObservationSnapshot] = {}
    for metric, (_, row) in best.items():
        obs_time = row.observation_time if row.observation_time.tzinfo else row.observation_time.replace(tzinfo=timezone.utc)
        out[metric] = ObservationSnapshot(
            metric=row.metric, value=row.value, unit=row.unit, quality=row.quality,
            observation_time=obs_time, source_id=row.source_id,
            is_current=abs((obs_time - at).total_seconds()) <= window_minutes * 60,
            extra=row.extra,
        )
    return out


@dataclass(frozen=True)
class LinkedEvidence:
    """One real raw_evidence row, already resolved to the canonical entity
    that requested it — never a keyword/title guess, always via the real
    EvidenceEntityLink row (itself built from resolve_identifier())."""
    raw_evidence_id: str
    title: str | None
    source_type: str
    published_at: datetime | None
    source_url: str | None
    relationship_type: str
    resolution_method: str
    link_confidence: float | None


async def get_evidence_for_entity(db: AsyncSession, entity_id: str, limit: int = 20) -> list[LinkedEvidence]:
    """Real, linked evidence for one canonical company — the method this
    module's own docstring named as the next step once EvidenceEntityLink
    existed. Returns only what's actually linked; an entity with zero real
    links returns an empty list, never a fuzzy fallback."""
    from app.db.models.evidence_entity_link import EvidenceEntityLink
    from app.db.models.raw_evidence import RawEvidence

    rows = (await db.execute(
        select(RawEvidence, EvidenceEntityLink)
        .join(EvidenceEntityLink, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
        .where(EvidenceEntityLink.entity_id == entity_id)
        .order_by(RawEvidence.published_at.desc().nullslast())
        .limit(limit)
    )).all()

    return [
        LinkedEvidence(
            raw_evidence_id=ev.id, title=ev.title, source_type=ev.source_type,
            published_at=ev.published_at, source_url=ev.source_url,
            relationship_type=link.relationship_type, resolution_method=link.resolution_method,
            link_confidence=link.confidence,
        )
        for ev, link in rows
    ]

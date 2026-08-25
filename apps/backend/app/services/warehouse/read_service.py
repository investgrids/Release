"""
Warehouse Read Service — Phase 2 Consumption (owner instruction, 2026-08-25,
following the read-only Warehouse Consumption Audit, artifacts/
warehouse_consumption_audit.md).

Scope, deliberately narrow per the audit's own verdict ("WAREHOUSE READY FOR
LIMITED CONSUMPTION"): entity-independent market/macro/sector context only.
No entity-linked evidence retrieval here — the audit proved, on real
production data (the ICICIBANK case study), that RawEvidence currently has
no working path to any entity, and a naive keyword/title match would
reproduce the exact 3IINFOLTD/IIFL wrong-entity-contamination bug already
fixed once. A `get_evidence_for_entity()` method belongs here only after
that gap is closed — not before.

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

"""
Development Memory sync — the standalone job that feeds identity.py's
matching lifecycle. Deliberately NOT run from any of the 3 existing
evidence_clustering call sites (Opportunity Radar, AI Search V2/V3,
Weekend Intelligence aggregator) — those need low-latency per-request
counts, not write-path risk, and Weekend Intelligence only runs Sat/Sun
while Developments need to form every day. Reuses the exact evidence-
collection function Weekend Intelligence already built
(collect_evidence_since) rather than a new one.

Windows overlap by design (LOOKBACK > the job's own schedule interval)
instead of tracking "since last run" state — resolve_development's
evidence_key existence check makes re-processing the same evidence a safe
no-op (see identity.py's "existing" tier), so overlap just trades a
little redundant work for never needing persisted job-run state or
worrying about a missed/late run leaving a real gap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.development_memory.identity import resolve_development, sweep_close_stale
from app.services.weekend_intelligence.evidence_window import collect_evidence_since

LOOKBACK = timedelta(hours=2)  # > the 30-60min schedule interval in scheduler.py — deliberate overlap, see module docstring


async def sync_development_memory(db: AsyncSession) -> dict:
    until = datetime.now(timezone.utc)
    since = until - LOOKBACK
    failed_sources: list[str] = []
    evidence = await collect_evidence_since(db, since, until, failed_sources=failed_sources)

    created = 0
    merged = 0
    already_attached = 0
    tier_counts: dict[str, int] = {}
    for item in evidence:
        result = await resolve_development(db, item)
        tier_counts[result.tier] = tier_counts.get(result.tier, 0) + 1
        if result.created:
            created += 1
        elif result.tier == "existing":
            already_attached += 1
        else:
            merged += 1

    closed = await sweep_close_stale(db)
    await db.commit()

    return {
        "evidence_seen": len(evidence),
        "developments_created": created,
        "evidence_merged": merged,
        "evidence_already_attached": already_attached,
        "developments_closed": closed,
        "failed_sources": failed_sources,
        "tier_counts": tier_counts,
    }

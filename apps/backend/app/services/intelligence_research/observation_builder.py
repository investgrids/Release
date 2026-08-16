"""
Phase 2E.1 — continuous observation collection.

Runs daily (see scheduler wiring), writes one fresh
CompanyIntelligenceObservation row per NIFTY 50 symbol using the same
evidence.py logic the pilot uses. observed_at is "now" at generation
time — this is a live, present-tense snapshot, so resolving sector via
the live universe lookup here is correct (not a historical-leakage
risk); it is FROZEN onto the row so any future read of this specific
row never re-resolves it.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_observation import CompanyIntelligenceObservation
from app.services.intelligence_research.evidence import load_all_evidence, build_evidence_state
from app.services.intelligence_research.safe_sources import OBSERVATION_SCHEMA_VERSION
from app.services.quant.universe import NIFTY_50, SECTOR

log = structlog.get_logger(__name__)

WINDOW_DAYS = 7


async def build_daily_observations(db: AsyncSession, as_of: date | None = None) -> dict:
    as_of = as_of or datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)

    by_symbol = await load_all_evidence(db)
    stored = 0
    for symbol in NIFTY_50:
        events = by_symbol.get(symbol, [])
        state = build_evidence_state(symbol, as_of, events, window_days=WINDOW_DAYS)
        db.add(CompanyIntelligenceObservation(
            id=str(uuid4()), symbol=symbol, observed_at=now, window_days=WINDOW_DAYS,
            event_positive_count=state.positive_count, event_negative_count=state.negative_count,
            event_neutral_count=state.neutral_count, highest_impact_0_100=state.highest_impact_0_100,
            aggregate_signed_magnitude=state.aggregate_signed_magnitude,
            aggregate_confidence_0_100=state.aggregate_confidence_0_100,
            signal_count=state.signal_count, triage_count=state.triage_count,
            announcement_count=state.announcement_count, conflict_bucket=state.conflict_bucket,
            sector_at_observation=SECTOR.get(symbol), evidence_refs=state.evidence_refs,
            schema_version=OBSERVATION_SCHEMA_VERSION,
        ))
        stored += 1
    await db.commit()

    log.info("intelligence_observation.built", stored=stored, as_of=as_of.isoformat())
    return {"stored": stored, "as_of": as_of.isoformat()}

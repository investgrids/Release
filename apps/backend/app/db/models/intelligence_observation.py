"""
CompanyIntelligenceObservation — Phase 2E.1.

A forward-only, continuously-collected snapshot of "what did Market
Ripple's safe intelligence sources say about this company, as of this
moment" — started now, regardless of what the Phase 2E.2 pilot finds
(owner: "From now onward, we start building the dataset we wish we
already had"). Never mutated once written — a fresh row every time the
observation builder runs, never an update to a prior row, so this table
itself never becomes another entry on the "mutated with no history"
list from the Phase 2E audit.

Built from evidence.py's shared evidence-loading/classification logic —
the same normalization the pilot uses, so a future comparison between
"what the pilot found in 5-7 weeks" and "what 3-6 months of this table
shows" is apples-to-apples.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CompanyIntelligenceObservation(Base):
    __tablename__ = "company_intelligence_observations"

    id                          = Column(String(36), primary_key=True)
    symbol                      = Column(String(32), nullable=False, index=True)
    observed_at                 = Column(DateTime(timezone=True), nullable=False, index=True)
    window_days                 = Column(Integer, nullable=False)

    event_positive_count        = Column(Integer, nullable=False, default=0)
    event_negative_count        = Column(Integer, nullable=False, default=0)
    event_neutral_count         = Column(Integer, nullable=False, default=0)
    highest_impact_0_100        = Column(Float, nullable=False, default=0.0)
    aggregate_signed_magnitude  = Column(Float, nullable=False, default=0.0)
    aggregate_confidence_0_100  = Column(Float, nullable=True)

    signal_count                = Column(Integer, nullable=False, default=0)
    triage_count                = Column(Integer, nullable=False, default=0)
    announcement_count          = Column(Integer, nullable=False, default=0)
    conflict_bucket             = Column(String(24), nullable=False)

    sector_at_observation       = Column(String(32), nullable=True)   # frozen at write time — never re-derived on read
    evidence_refs               = Column(JSON, nullable=False, default=list)

    schema_version               = Column(String(32), nullable=False)
    created_at                   = Column(DateTime(timezone=True), nullable=False, default=_now)

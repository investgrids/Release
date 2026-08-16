"""
Phase 2E.2 pilot schema — dedicated tables, same rationale as Phase 2D's
QuantResearchPrediction/Evaluation: isolated from production, isolated
from the continuous CompanyIntelligenceObservation table too (the pilot
is a one-shot exploratory run over a fixed historical window; the
observation table is an ongoing forward collection — different
lifecycles, different tables, both explicitly reproducible via
research_version/schema fields).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IntelligencePilotObservation(Base):
    __tablename__ = "intelligence_pilot_observations"

    id                          = Column(String(36), primary_key=True)
    research_version            = Column(String(32), nullable=False, index=True)
    symbol                      = Column(String(32), nullable=False, index=True)
    as_of_date                  = Column(Date, nullable=False, index=True)      # evidence trigger date
    as_of_bar_date               = Column(Date, nullable=False)                  # nearest trading day <= as_of_date, used for the price outcome
    window_days                  = Column(Integer, nullable=False)

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

    sector_at_observation        = Column(String(32), nullable=True)
    stock_price_as_of            = Column(Float, nullable=False)
    evidence_refs                = Column(JSON, nullable=False, default=list)

    created_at                    = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_ipo_symbol_date", "symbol", "as_of_date"),
    )


class IntelligencePilotEvaluation(Base):
    __tablename__ = "intelligence_pilot_evaluations"

    id                          = Column(String(36), primary_key=True)
    observation_id              = Column(String(36), ForeignKey("intelligence_pilot_observations.id"), nullable=False, index=True)
    horizon_days                = Column(Integer, nullable=False)   # trading sessions ahead

    stock_price_at_horizon      = Column(Float, nullable=True)
    stock_return_pct            = Column(Float, nullable=True)
    benchmark_symbol_used       = Column(String(16), nullable=True)
    benchmark_return_pct        = Column(Float, nullable=True)
    relative_return_pct         = Column(Float, nullable=True)

    actual_direction_absolute   = Column(String(16), nullable=True)
    actual_direction_relative   = Column(String(16), nullable=True)

    outcome_source               = Column(String(16), nullable=False, default="pricebar")   # provenance — never ambiguous, see safe_sources.py
    evaluated_at                  = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_ipe_observation", "observation_id"),
    )

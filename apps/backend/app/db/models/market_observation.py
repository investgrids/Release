"""
MarketObservation — Phase 1B Batch 1 (owner instruction, 2026-08-23).

Correction applied: identity is (metric, source_id, observation_time) —
NOT (metric, market_date, session, source_id) as originally drafted in
the Phase 1A design. The original draft would have collapsed every
intraday tick within the same session into one row, silently discarding
the exact intraday granularity the Phase 1A storage estimate (~140
observations/day across ~20 metrics at intraday cadence) assumed existed.
observation_time is now a real identity component; market_date/session
are denormalized, informational columns for querying, never part of
uniqueness.

Deliberately does NOT duplicate PriceBar — this table covers everything
PriceBar doesn't (VIX, GIFT Nifty, FII/DII, PCR/Max Pain, sector
performance, global indices, commodities, macro rates), reusing
PriceBar's own "one table, a discriminator column" precedent
(`timeframe` there, `metric` here) rather than one typed table per
signal.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Column, Date, DateTime, Float, ForeignKey, Index, JSON, String,
    UniqueConstraint,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MarketObservation(Base):
    __tablename__ = "market_observations"

    id               = Column(String(36), primary_key=True)
    metric           = Column(String(48), nullable=False, index=True)
    # NIFTY50 | BANKNIFTY | INDIAVIX | USDINR | BRENT | GIFT_NIFTY | FII_NET | DII_NET |
    # PCR_NIFTY | MAX_PAIN_NIFTY | SECTOR_<NAME> | US10Y | US2Y | FEDFUNDS | RBI_WSS | ...

    value            = Column(Float, nullable=True)   # nullable: a source_failure quality row is still a real row, never dropped
    unit             = Column(String(16), nullable=True)

    observation_time = Column(DateTime(timezone=True), nullable=False)   # real identity component — when the value is true-as-of
    market_date      = Column(Date, nullable=False, index=True)          # denormalized for querying — NOT identity
    session          = Column(String(16), nullable=True)                 # pre | regular | post | close — informational only

    source_id        = Column(String(64), ForeignKey("sources.id"), nullable=False, index=True)
    captured_at      = Column(DateTime(timezone=True), nullable=False, default=_now)   # when the capture job ran
    quality          = Column(String(24), nullable=False, default="fresh")
    # fresh | stale | estimated | source_failure — mirrors PriceBar.data_quality's existing convention

    extra            = Column(JSON, nullable=True)   # e.g. PCR's put/call OI breakdown, FII/DII session label

    __table_args__ = (
        UniqueConstraint("metric", "source_id", "observation_time", name="ux_market_obs_identity"),
        Index("ix_market_obs_metric_date", "metric", "market_date"),
    )

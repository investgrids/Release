"""
Quant Research schema — Phase 2D.

Dedicated tables, not a reuse of PredictionRecord/PredictionEvaluation.
Deliberate departure from Phase 2B/2C's "maximal reuse" default: at
Phase 2D's scale (~51k predictions x 3 horizons =~ 150k evaluations,
owner's own estimate), routing every row through store_prediction()'s
full target_entities/confidence_factors JSON shape would bloat the
production predictions table with rows nothing production-facing ever
needs, for no benefit — nothing in this app queries QuantResearch*
tables, which is a STRONGER isolation guarantee than a shared table's
`experimental` flag (Phase 2B/2C's mechanism, still correct for that
scale). Every row here still carries `experimental=True` so the
convention that "everything is flagged experimental" holds literally,
even though the enforcement mechanism (a disjoint table) is different.

prediction_evaluator.py and PredictionRecord/PredictionEvaluation are
untouched by this module, exactly as instructed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Float, Integer, String,
    Date, DateTime, ForeignKey, UniqueConstraint, Index,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class QuantResearchPrediction(Base):
    """One directional call per (run_tag, symbol, as_of_date, model) —
    same call graded against multiple horizons/outcome types in
    QuantResearchEvaluation, mirroring Phase 2C's one-call-many-
    evaluations pattern."""
    __tablename__ = "quant_research_predictions"

    id                = Column(String(36), primary_key=True)
    run_tag           = Column(String(32), nullable=False, index=True)   # e.g. "phase2d-v1"
    symbol            = Column(String(32), nullable=False, index=True)
    sector            = Column(String(32), nullable=True)
    model_name        = Column(String(32), nullable=False, index=True)   # "ma_momentum" etc — bare baseline name
    as_of_date        = Column(Date, nullable=False, index=True)
    direction         = Column(String(16), nullable=False)   # up | down | sideways
    expected_return    = Column(Float, nullable=True)
    expected_volatility = Column(Float, nullable=True)
    stock_price_as_of  = Column(Float, nullable=False)
    own_trend_regime   = Column(String(16), nullable=True)   # trending_up | trending_down | unknown
    experimental       = Column(Boolean, nullable=False, default=True)
    created_at          = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("run_tag", "symbol", "as_of_date", "model_name", name="ux_qrp_run_symbol_date_model"),
        Index("ix_qrp_run_symbol", "run_tag", "symbol"),
    )


class QuantResearchEvaluation(Base):
    """One row per (prediction, horizon) — carries BOTH the absolute and
    the Nifty-relative outcome for that horizon, computed together since
    both need the same two price lookups (as-of and as-of+horizon)."""
    __tablename__ = "quant_research_evaluations"

    id                        = Column(String(36), primary_key=True)
    prediction_id             = Column(String(36), ForeignKey("quant_research_predictions.id"), nullable=False, index=True)
    horizon_days              = Column(Integer, nullable=False)   # trading sessions ahead: 1 | 5 | 20

    stock_price_at_horizon    = Column(Float, nullable=True)
    stock_return_pct          = Column(Float, nullable=True)

    benchmark_symbol_used     = Column(String(16), nullable=True)   # "NIFTY50" | "NIFTYBEES"
    benchmark_price_as_of     = Column(Float, nullable=True)
    benchmark_price_at_horizon = Column(Float, nullable=True)
    benchmark_return_pct      = Column(Float, nullable=True)
    relative_return_pct       = Column(Float, nullable=True)   # stock_return_pct - benchmark_return_pct

    actual_direction_absolute = Column(String(16), nullable=True)   # up | down | sideways
    actual_direction_relative = Column(String(16), nullable=True)   # outperform | underperform | inline
    correct_absolute           = Column(Boolean, nullable=True)
    correct_relative            = Column(Boolean, nullable=True)

    evaluated_at               = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("prediction_id", "horizon_days", name="ux_qre_prediction_horizon"),
        Index("ix_qre_prediction", "prediction_id"),
    )

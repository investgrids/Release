"""
Prediction tracking models — the learning engine's persistent store.

Three tables:
  PredictionRecord   — every prediction ever made (never deleted)
  PredictionEvaluation — actual-vs-predicted results at each horizon
  CalibrationStat    — rolling accuracy statistics by confidence level
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Float, Integer, String,
    DateTime, Text, JSON, ForeignKey, Index,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionRecord(Base):
    __tablename__ = "prediction_records"

    id               = Column(String(36),  primary_key=True)          # UUID
    source           = Column(String(32),  nullable=False, index=True) # ai_search | triage | graph
    query            = Column(Text,        nullable=True)              # original query
    headline         = Column(Text,        nullable=True)              # for triage events

    prediction_text  = Column(Text,        nullable=False)
    direction        = Column(String(16),  nullable=False)             # up | down | sideways
    prediction_type  = Column(String(32),  nullable=False)             # overall | company | sector
    # [{type, symbol, name, baseline_price, baseline_ticker}]
    target_entities  = Column(JSON,        nullable=False, default=list)

    confidence_score  = Column(Float,      nullable=False, default=50.0)
    confidence_level  = Column(String(16), nullable=False, default="Medium")
    confidence_factors= Column(JSON,       nullable=True)              # breakdown dict

    horizon_days     = Column(Integer,     nullable=False, default=7)  # 1 | 3 | 7 | 30
    status           = Column(String(16),  nullable=False, default="pending", index=True)
    # pending → evaluating → complete

    created_at       = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    evaluate_by      = Column(DateTime(timezone=True), nullable=True)
    completed_at     = Column(DateTime(timezone=True), nullable=True)

    # Phase 2B §5/§6/§11 — Quantitative Intelligence shadow-mode fields.
    # `experimental` is the field the Phase 2A audit flagged as the one
    # gap that actually matters: without it, a shadow prediction that
    # reaches status="complete" would silently blend into
    # get_stats()/CalibrationStat's production accuracy numbers, since
    # neither is source-scoped. Every quant/baseline/Kronos prediction
    # MUST be written with experimental=True — see
    # recompute_calibration()/get_stats() in prediction_service.py,
    # both now filter on this column explicitly, not by `source` string
    # matching (which would be one `if` away from silently regressing).
    experimental     = Column(Boolean,     nullable=False, default=False, index=True)
    # e.g. "baseline-random_walk-v1", "kronos-v1" — distinct from `source`
    # (a coarse category: ai_search|triage|weekend_intelligence|quant),
    # this identifies exactly which model+revision produced the row.
    model_version    = Column(String(64),  nullable=True)
    # Numeric point forecast, only when the model genuinely produces one
    # (e.g. a regression's predicted % return) — categorical `direction`
    # above remains the field every non-quant source still uses.
    expected_return    = Column(Float,     nullable=True)
    expected_volatility = Column(Float,    nullable=True)

    __table_args__ = (
        Index("ix_pred_source_status", "source", "status"),
        Index("ix_pred_created_level", "created_at", "confidence_level"),
        Index("ix_pred_experimental", "experimental"),
    )


class PredictionEvaluation(Base):
    __tablename__ = "prediction_evaluations"

    id               = Column(String(36),  primary_key=True)
    prediction_id    = Column(
        String(36),
        ForeignKey("prediction_records.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    horizon_days     = Column(Integer,     nullable=False)             # 1 | 3 | 7 | 30
    evaluated_at     = Column(DateTime(timezone=True), nullable=False, default=_now)

    verdict          = Column(String(16),  nullable=False)             # correct | partial | incorrect | inconclusive
    actual_direction = Column(String(16),  nullable=True)              # up | down | sideways
    actual_move_pct  = Column(Float,       nullable=True)              # % change over horizon

    score            = Column(Float,       nullable=False, default=0.0) # 1.0 correct, 0.5 partial, 0 incorrect
    evidence         = Column(JSON,        nullable=True)              # entity-level price data
    notes            = Column(Text,        nullable=True)

    __table_args__ = (
        Index("ix_eval_pred_horizon", "prediction_id", "horizon_days"),
    )


class CalibrationStat(Base):
    """Accuracy statistics by confidence level. Recomputed after each evaluation cycle."""
    __tablename__ = "calibration_stats"

    id                   = Column(Integer,     primary_key=True, autoincrement=True)
    confidence_level     = Column(String(16),  nullable=False, unique=True, index=True)
    # "Low" | "Medium" | "High" | "Very High"

    total_predictions    = Column(Integer,     nullable=False, default=0)
    correct_count        = Column(Integer,     nullable=False, default=0)
    partial_count        = Column(Integer,     nullable=False, default=0)
    incorrect_count      = Column(Integer,     nullable=False, default=0)
    inconclusive_count   = Column(Integer,     nullable=False, default=0)

    # (correct + 0.5 * partial) / (total - inconclusive)
    accuracy_rate        = Column(Float,       nullable=False, default=0.5)
    avg_confidence_score = Column(Float,       nullable=False, default=50.0)

    # actual_accuracy / expected_accuracy — multiplier applied to future scores
    calibration_factor   = Column(Float,       nullable=False, default=1.0)

    last_updated         = Column(DateTime(timezone=True), nullable=False, default=_now)

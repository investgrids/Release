"""
Score History — a durable record of every ScoreUpdate the Intelligence
Orchestrator has ever broadcast. ScoreUpdate over SSE is ephemeral (only
subscribers connected at that exact moment see it); this table is what
lets a user who opens a page *after* a score changed still see the
83 -> 87 -> 91 progression, the reasons behind each step, and how
confidence evolved as evidence accumulated.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, JSON, String

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    entity_type    = Column(String(32),  nullable=False, index=True)   # event | company | sector | theme | opportunity | risk
    entity_id      = Column(String(128), nullable=False, index=True)
    model          = Column(String(64),  nullable=False)               # event_impact | company_impact | ripple_propagation | ...
    score          = Column(Float, nullable=True)
    previous_score = Column(Float, nullable=True)
    confidence     = Column(Float, nullable=True)
    status         = Column(String(32), nullable=False)                # ok | insufficient_data | ripple_signal
    data_status    = Column(String(32), nullable=False, default="preliminary")  # preliminary | verified | live
    version        = Column(String(64), nullable=False)
    breakdown      = Column(JSON, nullable=False, default=dict)
    top_contributors = Column(JSON, nullable=False, default=list)
    reasoning      = Column(JSON, nullable=False, default=list)
    trigger        = Column(String(32), nullable=False, default="unknown")  # new_event | ripple_propagation | enrichment_complete | ...
    created_at     = Column(DateTime(timezone=True), default=_now, index=True)

    __table_args__ = (
        Index("ix_score_history_entity_created", "entity_type", "entity_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "model": self.model,
            "score": self.score,
            "previous_score": self.previous_score,
            "confidence": self.confidence,
            "status": self.status,
            "data_status": self.data_status,
            "version": self.version,
            "breakdown": self.breakdown or {},
            "top_contributors": self.top_contributors or [],
            "reasoning": self.reasoning or [],
            "trigger": self.trigger,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

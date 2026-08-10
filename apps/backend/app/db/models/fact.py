import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, JSON
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class Fact(Base):
    """Fact Registry — a fact computed once per IST trading day and reused
    everywhere the Daily Brief (or any future content surface) needs it,
    instead of the LLM re-deriving/rewriting the same real number in
    several sections independently. Each row already carries its own
    Claim/Evidence/Entity/Source/Timestamp/Confidence — no separate
    Evidence table, since splitting a 1:1 relationship into two tables
    would just be a second form of the duplication this is meant to fix.
    See app/services/fact_registry.py for how these are computed."""
    __tablename__ = "facts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fact_key = Column(String(160), nullable=False, unique=True, index=True)
    valid_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD, IST trading day
    entity_type = Column(String(24), nullable=False, index=True)  # market_index|commodity|forex|event|macro
    entity_key = Column(String(80), nullable=False)
    name = Column(String(160), nullable=False)
    claim = Column(Text, nullable=False)
    value = Column(String(64), nullable=True)
    numeric_value = Column(Float, nullable=True)
    unit = Column(String(16), nullable=True)
    direction = Column(String(8), nullable=True)   # up|down|flat
    change_pct = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)       # 0.0-1.0, null when no real confidence exists
    source = Column(String(160), nullable=False)
    evidence = Column(JSON, nullable=True)
    affected_sectors = Column(JSON, nullable=False, default=list)
    affected_companies = Column(JSON, nullable=False, default=list)
    observed_at = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), default=_now)

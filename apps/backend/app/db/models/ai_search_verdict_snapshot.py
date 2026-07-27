import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class AISearchVerdictSnapshot(Base):
    """One row per (subject, day) — the persistence layer behind Phase 2B's
    Investment Watch panel. Written by pipeline.py after every non-degraded
    V3 response that resolves to exactly one subject (a single company, or
    a single sector with no company entities — anything more ambiguous is
    skipped rather than guessed at). Overwritten in place if the same
    subject is searched again the same day, so "Last Change" always compares
    two genuinely different days, never two queries minutes apart.

    subject_key is "company:{symbol}" or "sector:{name}" — deliberately not
    a foreign key, since companies/sectors here are plain strings shared
    with the rest of ai_search, not a dedicated entity table.
    """
    __tablename__ = "ai_search_verdict_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_key = Column(String(80), nullable=False, index=True)
    subject_type = Column(String(16), nullable=False)   # company | sector
    subject_label = Column(String(128), nullable=False)

    query = Column(Text, nullable=True)
    response_id = Column(String(64), nullable=True)

    verdict_scale = Column(String(32), nullable=True)
    rating = Column(String(32), nullable=True)
    confidence = Column(Integer, nullable=False, default=50)
    why = Column(Text, nullable=True)

    snapshot_date = Column(String(10), nullable=False, default=_today, index=True)  # YYYY-MM-DD, UTC
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("subject_key", "snapshot_date", name="uq_verdict_subject_date"),
    )

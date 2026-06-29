"""
Event detail models — canonical source for the events table and all related tables.
The `events` table is shared with legacy code; new columns are additive.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Core event table (enhanced) ───────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    slug = Column(String(256), nullable=True, index=True)

    # Identity
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=True)          # legacy / list endpoint
    description = Column(Text, nullable=True)       # enriched description
    source = Column(String(128), nullable=True, index=True)
    event_type = Column(String(64), nullable=True, index=True)

    # Dates
    event_date = Column(DateTime(timezone=True), nullable=True, index=True)
    published_at = Column(DateTime(timezone=True), default=_now)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Scores
    impact_score = Column(Float, nullable=True, default=0.0)
    confidence = Column(Float, nullable=True, default=0.0)

    # AI output
    ai_summary = Column(JSON, nullable=True)

    # Legacy flat JSON (kept for list endpoint backward compat)
    sectors = Column(JSON, nullable=True, default=list)
    companies = Column(JSON, nullable=True, default=list)
    category = Column(String(64), nullable=True)

    # Pipeline state
    enrichment_status = Column(String(32), nullable=False, default="pending")


# ── Related tables ────────────────────────────────────────────────────────────

class EventCompany(Base):
    __tablename__ = "event_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False)
    name = Column(String(256), nullable=True)
    impact_type = Column(String(32), nullable=False, default="neutral")  # beneficiary|loser|neutral
    impact_score = Column(Float, nullable=True, default=5.0)
    reason = Column(Text, nullable=True)


class EventSector(Base):
    __tablename__ = "event_sectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    sector = Column(String(128), nullable=False)
    impact = Column(String(32), nullable=False, default="neutral")  # positive|negative|neutral
    impact_score = Column(Float, nullable=True, default=5.0)


class EventTimeline(Base):
    __tablename__ = "event_timeline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(64), nullable=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0)


class EventNews(Base):
    __tablename__ = "event_news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    news_id = Column(String, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)
    relevance_score = Column(Float, nullable=True, default=1.0)

    __table_args__ = (
        UniqueConstraint("event_id", "news_id", name="uq_event_news"),
    )


class EventGraphNode(Base):
    __tablename__ = "event_graph_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(64), nullable=False)
    label = Column(String(256), nullable=False)
    node_type = Column(String(64), nullable=False, default="entity")
    node_metadata = Column(JSON, nullable=True, default=dict)


class EventGraphEdge(Base):
    __tablename__ = "event_graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(64), nullable=False)
    target = Column(String(64), nullable=False)
    edge_relationship = Column(String(128), nullable=False, default="impacts")


class EventSimilar(Base):
    __tablename__ = "event_similar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    similar_event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=True, default=0.0)
    reason = Column(Text, nullable=True)


class GovernmentPolicy(Base):
    __tablename__ = "government_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(128), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    ministry = Column(String(256), nullable=True)
    announcement_date = Column(DateTime(timezone=True), nullable=True)
    summary = Column(Text, nullable=True)
    url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class EventPolicy(Base):
    """Junction table linking events to relevant government policies."""
    __tablename__ = "event_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("government_policies.id", ondelete="CASCADE"), nullable=False)
    relevance = Column(String(128), nullable=True, default="relevant")

    __table_args__ = (
        UniqueConstraint("event_id", "policy_id", name="uq_event_policy"),
    )

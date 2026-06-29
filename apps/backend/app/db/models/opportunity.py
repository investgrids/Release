"""
SQLAlchemy models for the Opportunity Details architecture.
Uses JSON (not JSONB) so models work with both SQLite (dev) and PostgreSQL (prod).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey,
    Integer, String, Text, JSON, Index,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# 1. opportunities
# ─────────────────────────────────────────────────────────────────────────────

class Opportunity(Base):
    __tablename__ = "opportunities"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    slug             = Column(String(200), unique=True, nullable=False, index=True)
    title            = Column(String(500), nullable=False)
    summary          = Column(Text, nullable=False, default="")
    opportunity_score = Column(Float, nullable=False, default=0.0)
    confidence       = Column(Float, nullable=False, default=0.0)
    trend            = Column(String(100), nullable=False, default="Neutral")
    risk_level       = Column(String(50),  nullable=False, default="Medium")
    time_horizon     = Column(String(100), nullable=False, default="")
    sectors          = Column(JSON, nullable=False, default=list)
    # Structured AI summary: {matters, benefits, risks, invalidate, why_bullets}
    ai_summary       = Column(JSON, nullable=True)
    created_at       = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at       = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    # relationships
    metrics          = relationship("OpportunityMetric",             back_populates="opportunity", uselist=False, cascade="all, delete-orphan")
    events           = relationship("OpportunityEvent",              back_populates="opportunity", cascade="all, delete-orphan")
    companies        = relationship("OpportunityCompany",            back_populates="opportunity", cascade="all, delete-orphan")
    news             = relationship("OpportunityNews",               back_populates="opportunity", cascade="all, delete-orphan")
    timeline         = relationship("OpportunityTimeline",           back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityTimeline.order")
    sector_dist      = relationship("OpportunitySectorDistribution", back_populates="opportunity", cascade="all, delete-orphan")
    graph_nodes      = relationship("OpportunityGraphNode",          back_populates="opportunity", cascade="all, delete-orphan")
    graph_edges      = relationship("OpportunityGraphEdge",          back_populates="opportunity", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# 2. opportunity_events
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityEvent(Base):
    __tablename__ = "opportunity_events"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id        = Column(String(128), nullable=False)       # FK to events.id
    importance      = Column(Float, nullable=False, default=1.0)

    # denormalised display fields (avoids join on read)
    title           = Column(String(512), nullable=False, default="")
    event_date      = Column(String(64),  nullable=False, default="")
    tag             = Column(String(64),  nullable=False, default="")
    description     = Column(Text, nullable=False, default="")

    opportunity     = relationship("Opportunity", back_populates="events")

    __table_args__ = (Index("ix_opp_events_opp_id", "opportunity_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# 3. opportunity_companies
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityCompany(Base):
    __tablename__ = "opportunity_companies"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id      = Column(String(64),  nullable=False)       # NSE symbol
    impact_score    = Column(Float, nullable=False, default=0.0)
    confidence      = Column(Float, nullable=False, default=0.0)
    reason          = Column(Text, nullable=False, default="")

    # denormalised
    company_name    = Column(String(256), nullable=False, default="")
    impact_label    = Column(String(64),  nullable=False, default="High")  # Very High / High / Medium
    trend           = Column(String(10),  nullable=False, default="up")    # up / down / neutral

    opportunity     = relationship("Opportunity", back_populates="companies")

    __table_args__ = (Index("ix_opp_companies_opp_id", "opportunity_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# 4. opportunity_news
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityNews(Base):
    __tablename__ = "opportunity_news"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    news_id         = Column(String(128), nullable=False)       # FK to news_articles.id

    # denormalised
    headline        = Column(String(512), nullable=False, default="")
    source          = Column(String(128), nullable=False, default="")
    published_at    = Column(String(64),  nullable=False, default="")
    url             = Column(Text, nullable=False, default="")

    opportunity     = relationship("Opportunity", back_populates="news")

    __table_args__ = (Index("ix_opp_news_opp_id", "opportunity_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# 5. opportunity_timeline
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityTimeline(Base):
    __tablename__ = "opportunity_timeline"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    order           = Column(Integer, nullable=False, default=0)
    phase           = Column(String(200), nullable=False)
    date_label      = Column(String(100), nullable=False, default="")
    title           = Column(String(300), nullable=False, default="")
    description     = Column(Text, nullable=False, default="")
    status          = Column(String(20),  nullable=False, default="pending")  # done / active / pending

    opportunity     = relationship("Opportunity", back_populates="timeline")

    __table_args__ = (Index("ix_opp_timeline_opp_id", "opportunity_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# 6. opportunity_metrics
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityMetric(Base):
    __tablename__ = "opportunity_metrics"

    opportunity_id   = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True)
    revenue_potential = Column(String(100), nullable=False, default="")
    expected_cagr    = Column(String(100), nullable=False, default="")
    eps_growth       = Column(String(100), nullable=False, default="")
    investment_cycle = Column(String(100), nullable=False, default="")
    market_size      = Column(String(100), nullable=False, default="")

    opportunity      = relationship("Opportunity", back_populates="metrics")


# ─────────────────────────────────────────────────────────────────────────────
# 7. opportunity_sector_distribution
# ─────────────────────────────────────────────────────────────────────────────

class OpportunitySectorDistribution(Base):
    __tablename__ = "opportunity_sector_distribution"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    sector          = Column(String(128), nullable=False)
    percentage      = Column(Float, nullable=False, default=0.0)
    color           = Column(String(20),  nullable=False, default="#6366f1")

    opportunity     = relationship("Opportunity", back_populates="sector_dist")

    __table_args__ = (Index("ix_opp_sector_dist_opp_id", "opportunity_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# 8. opportunity_graph_nodes
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityGraphNode(Base):
    __tablename__ = "opportunity_graph_nodes"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id         = Column(String(64),  nullable=False)   # unique within opportunity
    label           = Column(String(256), nullable=False)
    node_type       = Column(String(64),  nullable=False, default="concept")  # concept/company/sector/policy
    node_metadata   = Column(JSON, nullable=False, default=dict)

    opportunity     = relationship("Opportunity", back_populates="graph_nodes")

    __table_args__ = (Index("ix_opp_graph_nodes_opp_id", "opportunity_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# 9. opportunity_graph_edges
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityGraphEdge(Base):
    __tablename__ = "opportunity_graph_edges"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id  = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    source          = Column(String(64), nullable=False)    # node_id
    target          = Column(String(64), nullable=False)    # node_id
    edge_relationship = Column(String(128), nullable=False, default="related_to")

    opportunity     = relationship("Opportunity", back_populates="graph_edges")

    __table_args__ = (Index("ix_opp_graph_edges_opp_id", "opportunity_id"),)

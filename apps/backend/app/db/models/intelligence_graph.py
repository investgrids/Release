from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, Text, JSON, ForeignKey
from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IGNode(Base):
    """Node in the Market Intelligence Graph.

    id format: "{node_type}:{slug}"  e.g. "commodity:crude-oil", "sector:airlines"
    node_type: company | sector | theme | event | policy | commodity | country | index | currency
    """
    __tablename__ = "ig_nodes"

    id          = Column(String(128), primary_key=True)
    node_type   = Column(String(32),  nullable=False, index=True)
    label       = Column(String(256), nullable=False)
    ticker      = Column(String(32),  nullable=True)
    description = Column(Text,        nullable=True)
    extra       = Column(JSON,        nullable=False, default=dict)
    auto_added  = Column(Boolean,     nullable=False, default=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now)


class IGEdge(Base):
    """Directed edge in the Market Intelligence Graph.

    id: md5 of "{source_id}|{edge_type}|{target_id}"
    edge_type: benefits | hurts | supplies | depends_on | competes_with | influences | triggered_by
    weight:    0.0–1.0  (relationship strength)
    confidence: 0.0–1.0 (certainty)
    lag_days:  typical days before impact materialises
    """
    __tablename__ = "ig_edges"

    id           = Column(String(64),  primary_key=True)
    source_id    = Column(String(128), ForeignKey("ig_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id    = Column(String(128), ForeignKey("ig_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    edge_type    = Column(String(32),  nullable=False, index=True)
    weight       = Column(Float,       nullable=False, default=0.7)
    confidence   = Column(Float,       nullable=False, default=0.8)
    lag_days     = Column(Integer,     nullable=True,  default=0)
    description  = Column(Text,        nullable=True)
    source_event = Column(String(128), nullable=True)
    auto_added   = Column(Boolean,     nullable=False, default=False)
    created_at   = Column(DateTime(timezone=True), nullable=False, default=_now)

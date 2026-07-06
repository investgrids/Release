"""
Ripple Engine — persists AI-generated market dependency graphs.
One graph per event (or scenario). Full graph stored as JSON for fast retrieval.
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class RippleGraph(Base):
    __tablename__ = "ripple_graphs"

    id             = Column(Integer, primary_key=True, index=True)
    event_id       = Column(String(256), nullable=True, index=True)  # ref to events.id (string PKs)
    scenario_type  = Column(String(20), nullable=False, default="event")   # event | scenario | company | theme
    scenario_input = Column(Text, nullable=True)                           # free-text for custom scenarios
    event_title    = Column(String(500), nullable=True)
    event_summary  = Column(Text, nullable=True)
    event_impact   = Column(Float, nullable=True, default=0.0)
    graph_data     = Column(JSON, nullable=True)    # {nodes:[…], edges:[…]}
    insights       = Column(JSON, nullable=True)    # {summary, beneficiaries, losers, …}
    generated_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "event_id":       self.event_id,
            "scenario_type":  self.scenario_type,
            "scenario_input": self.scenario_input,
            "event_title":    self.event_title,
            "event_impact":   self.event_impact,
            "graph_data":     self.graph_data or {"nodes": [], "edges": []},
            "insights":       self.insights or {},
            "generated_at":   self.generated_at.isoformat() if self.generated_at else None,
        }

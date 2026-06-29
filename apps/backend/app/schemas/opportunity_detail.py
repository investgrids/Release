"""
Pydantic schemas for the Opportunity Details API response.
All fields are optional-safe so partial data renders without crashing.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


# ── Sub-schemas ───────────────────────────────────────────────────────────────

class MetricSchema(BaseModel):
    revenue_potential: str = ""
    expected_cagr: str = ""
    eps_growth: str = ""
    investment_cycle: str = ""
    market_size: str = ""


class TimelineStepSchema(BaseModel):
    order: int = 0
    phase: str = ""
    date_label: str = ""
    title: str = ""
    description: str = ""
    status: str = "pending"   # done | active | pending


class EventSchema(BaseModel):
    event_id: str = ""
    title: str = ""
    event_date: str = ""
    tag: str = ""
    description: str = ""
    importance: float = 1.0


class CompanySchema(BaseModel):
    symbol: str = ""
    company_name: str = ""
    impact_score: float = 0.0
    impact_label: str = "High"
    trend: str = "up"
    confidence: float = 0.0
    reason: str = ""


class NewsSchema(BaseModel):
    news_id: str = ""
    headline: str = ""
    source: str = ""
    published_at: str = ""
    url: str = ""


class SectorDistSchema(BaseModel):
    sector: str = ""
    percentage: float = 0.0
    color: str = "#6366f1"


class GraphNodeSchema(BaseModel):
    node_id: str = ""
    label: str = ""
    node_type: str = "concept"
    metadata: Dict[str, Any] = {}


class GraphEdgeSchema(BaseModel):
    source: str = ""
    target: str = ""
    relationship: str = "related_to"


class AISummarySchema(BaseModel):
    matters: str = ""
    benefits: str = ""
    risks: List[str] = []
    invalidate: str = ""
    why_bullets: List[str] = []


# ── Top-level response ────────────────────────────────────────────────────────

class OpportunityDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str = ""
    opportunity_score: float = 0.0
    confidence: float = 0.0
    trend: str = ""
    risk_level: str = ""
    time_horizon: str = ""
    sectors: List[str] = []
    ai_summary: Optional[AISummarySchema] = None

    metrics: Optional[MetricSchema] = None
    timeline: List[TimelineStepSchema] = []
    events: List[EventSchema] = []
    companies: List[CompanySchema] = []
    news: List[NewsSchema] = []
    sector_distribution: List[SectorDistSchema] = []
    graph_nodes: List[GraphNodeSchema] = []
    graph_edges: List[GraphEdgeSchema] = []


# ── Pagination wrapper for list endpoints ─────────────────────────────────────

class OpportunityListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str = ""
    opportunity_score: float = 0.0
    confidence: float = 0.0
    trend: str = ""
    risk_level: str = ""
    time_horizon: str = ""
    sectors: List[str] = []
    company_count: int = 0
    event_count: int = 0


class PaginatedOpportunities(BaseModel):
    items: List[OpportunityListItem]
    total: int
    page: int
    page_size: int
    pages: int

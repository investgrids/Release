"""
Pydantic schemas for the GET /api/events/{id} response.
All fields are optional at the top level so partial enrichment still serialises.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EventInfo(BaseModel):
    id: str
    slug: Optional[str] = None
    title: str
    description: str = ""
    source: str = ""
    event_type: str = "macro"
    event_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    enrichment_status: str = "pending"


class EventSummaryDetail(BaseModel):
    text: str = ""
    why_it_matters: str = ""
    key_bullets: List[str] = []
    immediate_impact: str = "neutral"
    long_term_impact: str = "neutral"
    risk_factors: List[str] = []
    opportunities: List[str] = []


class CompanyDetail(BaseModel):
    symbol: str
    name: str = ""
    impact_type: str = "neutral"
    impact_score: float = 0.0
    reason: str = ""


class BeneficiaryDetail(BaseModel):
    symbol: str
    name: str = ""
    impact_score: float = 0.0
    reason: str = ""


class SectorDetail(BaseModel):
    sector: str
    impact: str = "neutral"
    impact_score: float = 0.0


class TimelineStep(BaseModel):
    date: str = ""
    title: str
    description: str = ""
    order: int = 0


class GovernmentPolicyDetail(BaseModel):
    id: int
    title: str
    ministry: str = ""
    announcement_date: str = ""
    summary: str = ""
    url: str = ""


class HistoricalEventRef(BaseModel):
    id: str
    title: str
    event_date: str = ""
    impact_score: float = 0.0
    similarity_score: float = 0.0
    reason: str = ""


class NewsRef(BaseModel):
    id: str
    headline: str
    source: str = ""
    published_at: str = ""
    summary: str = ""
    url: str = ""


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "entity"
    metadata: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str = "impacts"


class GraphDetail(BaseModel):
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []


class MarketReaction(BaseModel):
    short_term: str = "neutral"
    medium_term: str = "neutral"
    volatility: str = "medium"
    sentiment: str = "neutral"


class AIAnalysis(BaseModel):
    bull_case: str = ""
    bear_case: str = ""
    base_case: str = ""
    key_risks: List[str] = []
    catalysts: List[str] = []
    classification: Dict[str, Any] = {}


class EventDetailResponse(BaseModel):
    event: EventInfo
    summary: EventSummaryDetail = Field(default_factory=EventSummaryDetail)
    impactScore: float = 0.0
    confidence: float = 0.0
    companies: List[CompanyDetail] = []
    beneficiaries: List[BeneficiaryDetail] = []
    losers: List[BeneficiaryDetail] = []
    affectedSectors: List[SectorDetail] = []
    timeline: List[TimelineStep] = []
    governmentPolicies: List[GovernmentPolicyDetail] = []
    historicalEvents: List[HistoricalEventRef] = []
    relatedNews: List[NewsRef] = []
    graph: GraphDetail = Field(default_factory=GraphDetail)
    marketReaction: Dict[str, Any] = Field(default_factory=dict)
    aiAnalysis: Dict[str, Any] = Field(default_factory=dict)

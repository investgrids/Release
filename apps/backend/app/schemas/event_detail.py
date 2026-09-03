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
    # CD3-D (D6) — see app.services.measurement_semantics.IntegrityStatus.
    # Default "unknown" (never "valid"), same fail-safe reasoning as
    # impact_provenance elsewhere in this file — a legacy/pre-D6 row must
    # never be inferred as a genuinely generated summary just because
    # this field is absent.
    integrity_status: str = "unknown"


class CompanyDetail(BaseModel):
    symbol: str
    name: str = ""
    impact_type: str = "neutral"
    impact_score: float = 0.0
    reason: str = ""
    # CD3-B (2026-09-02) — see app.services.claim_provenance.ClaimProvenance.
    # Default "unknown" (not e.g. "analytical_hypothesis") for the same
    # reason get_claim_provenance() defaults there: legacy/unmapped data
    # must never be inferred into a stronger provenance than the response
    # actually set.
    impact_provenance: str = "unknown"


class BeneficiaryDetail(BaseModel):
    symbol: str
    name: str = ""
    impact_score: float = 0.0
    reason: str = ""
    impact_provenance: str = "unknown"


class SectorDetail(BaseModel):
    sector: str
    impact: str = "neutral"
    impact_score: float = 0.0
    impact_provenance: str = "unknown"


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
    slug: str = ""
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
    # CD3-B — see app.services.claim_provenance.RippleEvidenceState.
    # Default "unavailable" (the weakest state), same fail-safe reasoning
    # as impact_provenance above.
    evidence_state: str = "unavailable"


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


class MacroReleaseDetail(BaseModel):
    """Populated only when app.services.macro_extraction confidently
    parsed a real structured figure out of this event's source text (see
    app/db/models/macro_release.py) — absent (None on the parent field),
    never a guessed value, for every other event."""
    metric: str
    release_value: Optional[float] = None
    previous_value: Optional[float] = None
    expected_value: Optional[float] = None
    surprise: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    geography: str = "India"
    importance: Optional[str] = None
    affected_sectors: List[str] = []
    affected_companies: List[str] = []
    source: Optional[str] = None
    source_url: Optional[str] = None


class EventDetailResponse(BaseModel):
    event: EventInfo
    summary: EventSummaryDetail = Field(default_factory=EventSummaryDetail)
    # None means "not yet scored" — must stay distinct from a real 0.
    impactScore: Optional[float] = None
    confidence: Optional[float] = None
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
    macroRelease: Optional[MacroReleaseDetail] = None
    indexable: bool = False

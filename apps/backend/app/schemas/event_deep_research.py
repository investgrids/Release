"""
Deep Research (Layer 2) response schema — GET /api/events/{id}/deep-research
(2026-08 event page redesign).

Every field here is either derived from data already fetched elsewhere on
this page (timeline, historical patterns, risks) or from a SINGLE reused AI
call (scenarios, via the existing generate_scenario_analysis — not a new
prompt). No field on this schema is a fabricated placeholder: scenarios
carry `available=False` rather than fake content when the AI call failed
or degraded, and confidence is always qualitative (High/Medium/Low), never
an invented numeric probability.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class TimelineStep(BaseModel):
    date: Optional[str] = None
    title: str
    description: str = ""
    kind: Literal["detected", "published", "related", "update"] = "update"


class Scenario(BaseModel):
    label: Literal["Bull", "Base", "Bear"]
    outcome: str
    key_drivers: List[str] = []
    # Qualitative only — the underlying AI call's numeric "probability"/
    # "confidence" fields are LLM-invented, not statistically grounded, so
    # they are deliberately never surfaced as a percentage (see the
    # deep_research_service module docstring for the bucket thresholds).
    confidence: Optional[Literal["High", "Medium", "Low"]] = None


class HistoricalPattern(BaseModel):
    id: str
    slug: str = ""
    title: str
    event_date: Optional[str] = None
    similarity_score: Optional[float] = None
    impact_score: Optional[float] = None
    reason: Optional[str] = None


class SecondOrderEffect(BaseModel):
    level: Literal["immediate", "sector", "company", "broader"]
    description: str
    status: Literal["observed", "likely", "potential"]


class RiskItem(BaseModel):
    risk: str
    why_it_matters: Optional[str] = None


class Reasoning(BaseModel):
    data_used: List[str] = []
    sources: List[str] = []
    analysis_timestamp: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None


class DeepResearchResponse(BaseModel):
    event_id: str
    timeline: List[TimelineStep] = []
    scenarios: List[Scenario] = []
    # "shown"          — scenarios is populated with real AI output, render it.
    # "not_applicable" — this event isn't materially uncertain enough to
    #                     warrant Bull/Base/Bear framing (e.g. low impact,
    #                     or high-impact but already well-understood
    #                     direction) — the AI call was never even made.
    #                     Frontend shows nothing, not an error.
    # "unavailable"    — the event DID qualify, the AI call was attempted,
    #                     but it failed or degraded into generic
    #                     boilerplate — frontend shows a plain "temporarily
    #                     unavailable" note, never the fabricated content.
    scenario_status: Literal["shown", "not_applicable", "unavailable"] = "not_applicable"
    historical_patterns: List[HistoricalPattern] = []
    second_order_effects: List[SecondOrderEffect] = []
    risks: List[RiskItem] = []
    reasoning: Reasoning
    generated_at: str

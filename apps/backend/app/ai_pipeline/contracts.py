"""
Shared data contracts passed between pipeline stages.

`DecisionResult` is the load-bearing type: it is computed deterministically
by the Decision Intelligence Engine (no LLM involved) and handed to the
answer template as structured fact. The LLM elaborates on these fields in
prose; it is never the source of the verdict, confidence, drivers, or any
numeric claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.services.confidence_service import ConfidenceResult

Polarity = Literal["positive", "negative", "neutral", "uncertain"]
Direction = Literal["tailwind", "headwind", "mixed"]


@dataclass
class Evidence:
    """One atomic, sourced fact contributed by a retriever."""
    id: str                    # stable dedupe key: f"{source}:{entity}:{hash(claim)}"
    source: str                 # retriever key that produced it, e.g. "event", "news"
    entity: str | None          # ticker/sector/theme this evidence is about, if any
    claim: str                  # human-readable normalized statement
    polarity: Polarity
    magnitude: float            # 0-1 normalized strength
    confidence: float           # 0-1 source-level confidence
    timestamp: datetime | None = None
    raw: dict = field(default_factory=dict)   # original payload, for traceability/citation


@dataclass
class DriverScore:
    """A ranked, named factor behind the decision (e.g. 'Government Defence Spending: 96')."""
    label: str
    score: float                 # 0-100
    contributing_evidence_ids: list[str]
    direction: Direction


@dataclass
class DecisionResult:
    """
    Deterministic output of the Decision Intelligence Engine. This is the
    structured input the LLM is given — it may explain and elaborate on
    these fields, but must not introduce new numeric claims or conclusions
    not present here.
    """
    verdict: str | None
    confidence: ConfidenceResult
    risk_level: str
    horizon: str
    mood: str
    drivers: list[DriverScore]
    opportunities: list[dict]
    risks: list[dict]
    historical_probability: dict | None
    ripple_reach: dict | None
    beneficiaries: list[str]
    losers: list[str]
    missing_data: list[str]


@dataclass
class ValidatorReport:
    passed: bool
    missing_sections: list[str]
    repair_attempted: bool
    final_sections_present: list[str]


@dataclass
class PipelineResult:
    intent: str
    query: str
    evidence: list[Evidence]
    drivers: list[DriverScore]
    decision: DecisionResult
    answer: dict
    validator: ValidatorReport

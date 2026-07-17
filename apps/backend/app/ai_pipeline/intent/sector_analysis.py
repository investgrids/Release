"""Sector Analysis intent — 'Best sectors for next 6 months', 'Banking outlook'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("sector_analysis")(IntentSpec(
    key="sector_analysis",
    label="Sector Analysis",
    retrievers=["market", "event", "intelligence_publishing"],
    template="exploratory_template",
    decision_profile="informational",
    priority=22,
    patterns=(
        r"\bbest sectors?\b",
        r"\bsector outlook\b",
        r"\b(?:banking|it|pharma|auto|fmcg|energy|defence|metals?|realty|telecom)\s+(?:sector\s+)?outlook\b",
        r"\b(?:which|what)\s+sectors?\b",
        r"\bsector rotation\b",
    ),
))

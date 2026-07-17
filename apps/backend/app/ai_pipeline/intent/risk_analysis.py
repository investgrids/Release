"""Risk Analysis intent — 'Biggest risks for IT', 'Risks to Indian economy'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("risk_analysis")(IntentSpec(
    key="risk_analysis",
    label="Risk Analysis",
    retrievers=["event", "market", "macro", "intelligence_publishing"],
    template="exploratory_template",
    decision_profile="informational",
    priority=15,
    patterns=(
        r"\b(?:biggest |key |major |main )?risks?\b",
        r"\bwhat could go wrong\b",
        r"\bheadwinds?\b",
        r"\bdownside\b",
        r"\bthreats?\b.{1,20}\bto\b",
    ),
))

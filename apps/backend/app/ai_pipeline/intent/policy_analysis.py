"""Policy Analysis intent — 'New GST impact', 'SEBI regulations'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("policy_analysis")(IntentSpec(
    key="policy_analysis",
    label="Policy Analysis",
    retrievers=["event", "historical_similarity", "intelligence_publishing"],
    template="impact_template",
    decision_profile="informational",
    priority=18,
    patterns=(
        r"\bsebi\b",
        r"\bgst\b",
        r"\bnew (?:policy|regulation|law|rule)\b",
        r"\bregulatory\b",
        r"\bcompliance\b.{1,20}\brequirement\b",
        r"\bgovernment (?:policy|scheme)\b",
    ),
))

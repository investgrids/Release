"""Historical Analysis intent — 'What happened after Budget 2023?', 'Similar events'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("historical_analysis")(IntentSpec(
    key="historical_analysis",
    label="Historical Analysis",
    retrievers=["historical_similarity", "event"],
    template="briefing_template",
    decision_profile="informational",
    priority=14,
    patterns=(
        r"\bwhat happened (?:after|when|during)\b",
        r"\bsimilar (?:events|situations|precedents)\b",
        r"\bhas this happened before\b",
        r"\bhistorical(?:ly)?\b.{1,20}\b(?:precedent|comparison|similar)\b",
        r"\blast time\b",
    ),
))

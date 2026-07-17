"""Ripple Analysis intent — 'Who benefits from falling crude?', 'Companies affected by RBI decision'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("ripple_analysis")(IntentSpec(
    key="ripple_analysis",
    label="Ripple Analysis",
    retrievers=["ripple", "intelligence_graph", "company"],
    template="impact_template",
    decision_profile="informational",
    priority=17,
    patterns=(
        r"\bwho benefits\b",
        r"\bwho (?:loses|is hurt)\b",
        r"\bcompanies affected by\b",
        r"\bwhat happens if\b",
        r"\bif\b.{1,40}\b(?:falls?|rises?|drops?|increases?|cuts?)\b",
        r"\bripple\b",
        r"\bdownstream\b.{1,20}\beffect\b",
        r"\bhow is\b.{1,30}\baffected\b",
    ),
))

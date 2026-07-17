"""Event Impact intent — 'RBI rate cut impact', 'Budget impact', 'US Fed decision'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("event_impact")(IntentSpec(
    key="event_impact",
    label="Event Impact",
    retrievers=["event", "news", "intelligence_publishing"],
    template="impact_template",
    decision_profile="informational",
    priority=20,
    patterns=(
        r"\bimpact\b",
        r"\beffect\b",
        r"\brbi\b.*\b(?:cut|hike|decision|policy|rate)\b",
        r"\bbudget\b",
        r"\bfed\b.*\bdecision\b",
        r"\bgst\b",
        r"\bpolicy\b.*\b(?:effect|impact)\b",
        r"\bafter\b.*\b(?:rbi|budget|fed|gst|election)\b",
        r"\bexplain\b.*\b(?:rbi|budget|policy|decision)\b",
    ),
))

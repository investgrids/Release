"""Company Analysis intent — 'Analyze TCS', 'Explain HDFC Bank', 'Is Infosys undervalued?'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("company_analysis")(IntentSpec(
    key="company_analysis",
    label="Company Analysis",
    retrievers=["company", "event", "market", "intelligence_graph"],
    template="profile_template",
    decision_profile="informational",
    priority=12,
    patterns=(
        r"\banaly[sz]e\b",
        r"\bis\s+[\w &.]{2,30}\s+(?:undervalued|overvalued)\b",
        r"\bcompany profile\b",
        r"\bbusiness (?:model|quality)\b",
        r"\bfundamentals? of\b",
    ),
))

"""
News Intelligence intent — 'Explain today's biggest news'. Also the default
fallback for any query that doesn't match a more specific registered intent
(in Phase 1, that's most queries — only 3 intents exist so far; unmatched
queries such as sector/theme/historical questions still get a grounded,
evidence-based answer rather than an error).
"""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("news_intelligence")(IntentSpec(
    key="news_intelligence",
    label="News Intelligence",
    retrievers=["news", "event", "intelligence_publishing"],
    template="briefing_template",
    decision_profile="informational",
    priority=40,
    patterns=(
        r"\bexplain\b.*\bnews\b",
        r"\btoday'?s?\b.*\bnews\b",
        r"\bbiggest news\b",
        r"\bwhat'?s happening\b",
        r"\blatest news\b",
    ),
    is_default=True,
))

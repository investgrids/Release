"""
General Education intent — 'Explain repo rate', 'What is EV/EBITDA?'.

Deliberately light on retrieval: a definitional question about a financial
term has no real "evidence" to ground against the way a market-decision
query does. It still runs through the same pipeline (so validator/
transparency guarantees hold), but with a minimal retriever set — one
market-context retriever for light grounding, not the full evidence stack.
"""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("general_education")(IntentSpec(
    key="general_education",
    label="General Education",
    retrievers=["intelligence_publishing"],
    template="education_template",
    decision_profile="informational",
    priority=35,
    patterns=(
        r"\bwhat is\b.{1,40}\?",
        r"\bwhat does\b.{1,40}\bmean\b",
        r"\bdefine\b",
        r"\bexplain\b.{1,20}\b(?:repo rate|ev.?ebitda|p.?e ratio|market cap|dividend yield|"
        r"basis points?|derivatives?|hedge|short selling|circuit breaker)\b",
        r"\bhow does\b.{1,40}\bwork\b",
    ),
))

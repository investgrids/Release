"""Investment Decision intent — 'Should I invest in defence stocks?', 'Is HAL a buy?'"""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("investment_decision")(IntentSpec(
    key="investment_decision",
    label="Investment Decision",
    retrievers=["event", "news", "intelligence_publishing"],
    template="verdict_template",
    decision_profile="verdict",
    priority=10,
    patterns=(
        r"\bshould i (?:invest|buy|put money)\b",
        r"\bworth (?:buying|investing)\b",
        r"\bis\s+[\w &.]{2,30}\s+a\s+(?:buy|good (?:investment|buy))\b",
        r"\bgood (?:time )?to (?:buy|invest)\b",
        r"\bsafe to invest\b",
        r"\bshould i buy\b",
    ),
))

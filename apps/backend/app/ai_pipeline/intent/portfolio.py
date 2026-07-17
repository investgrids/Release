"""Portfolio intent — 'Replace Reliance with BEL?', 'My holdings affected?'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("portfolio")(IntentSpec(
    key="portfolio",
    label="Portfolio",
    retrievers=["company", "market", "ripple"],
    template="profile_template",
    decision_profile="informational",
    priority=8,
    patterns=(
        r"\bmy portfolio\b",
        r"\bmy holdings\b",
        r"\breplace\b.{1,30}\bwith\b",
        r"\bswitch(?:ing)?\b",
        r"\brotate\b.{1,20}\bto\b",
        r"\bconcentration risk\b",
        r"\basset allocation\b",
        r"\brebalance\b",
    ),
))

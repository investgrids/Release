"""Theme Discovery intent — 'AI stocks', 'Defence theme', 'EV ecosystem'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("theme_discovery")(IntentSpec(
    key="theme_discovery",
    label="Theme Discovery",
    retrievers=["intelligence_publishing", "market", "event"],
    template="exploratory_template",
    decision_profile="informational",
    priority=25,
    patterns=(
        r"\btheme\b",
        r"\becosystem\b",
        r"\b(?:ai|ev|electric vehicle|semiconductor|renewable|green energy)\s+stocks?\b",
        r"\bemerging trend\b",
        r"\bstocks? to watch\b",
    ),
))

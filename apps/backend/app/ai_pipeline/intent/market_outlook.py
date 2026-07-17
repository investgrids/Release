"""Market Outlook intent — 'Tomorrow market prediction', 'Weekly outlook'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("market_outlook")(IntentSpec(
    key="market_outlook",
    label="Market Outlook",
    retrievers=["market", "macro", "intelligence_publishing"],
    template="exploratory_template",
    decision_profile="informational",
    priority=30,
    patterns=(
        r"\btomorrow'?s?\s+market\b",
        r"\bmarket\b.{1,15}\btomorrow\b",
        r"\boutlook\b.{1,30}\bmarket\b",
        r"\bweekly outlook\b",
        r"\bmarket prediction\b",
        r"\bmarket outlook\b",
        r"\bhow (?:will|is) the market\b",
        r"\bnifty (?:target|prediction|outlook)\b",
    ),
))

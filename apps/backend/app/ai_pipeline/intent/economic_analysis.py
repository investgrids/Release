"""Economic Analysis intent — 'Inflation impact', 'GDP effect'."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("economic_analysis")(IntentSpec(
    key="economic_analysis",
    label="Economic Analysis",
    retrievers=["macro", "market", "historical_similarity"],
    template="impact_template",
    decision_profile="informational",
    priority=19,
    patterns=(
        r"\binflation\b",
        r"\bgdp\b",
        r"\bcurrency\b.{1,20}\b(?:depreciat\w*|appreciat\w*|impact)\b",
        r"\bfiscal deficit\b",
        r"\btrade deficit\b",
        r"\beconomic (?:growth|slowdown|outlook)\b",
    ),
))

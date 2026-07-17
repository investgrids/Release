"""Company Comparison intent — 'HAL vs BEL', 'Reliance vs ONGC'. Reuses verdict_template's shape."""
from __future__ import annotations

from app.ai_pipeline.intent.base import IntentSpec
from app.ai_pipeline.registry import INTENT_REGISTRY

INTENT_REGISTRY.register("company_comparison")(IntentSpec(
    key="company_comparison",
    label="Company Comparison",
    retrievers=["company", "market", "quant_signal"],
    template="verdict_template",
    decision_profile="verdict",
    priority=5,
    patterns=(
        r"\bvs\.?\b",
        r"\bversus\b",
        r"\bcompare\b",
        r"\bwhich is better\b",
        r"\bbetter than\b",
        r"\bwhich (?:one|company|stock)\b",
    ),
))

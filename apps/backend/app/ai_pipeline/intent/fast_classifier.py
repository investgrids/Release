"""
Intent Detection Agent — regex-only, no network call, target <100ms.

Seeded from the pattern vocabulary already proven in
`app/services/ai_search_service.py::_DECISION_INTENTS` (that table
distinguishes buy/sell/switch/compare sub-flavors *within* a single
decision-shaped query; this classifier operates one level up, choosing
which top-level intent — and therefore which retrievers/template — applies
to the query at all).

Classification is purely data-driven: every registered `IntentSpec` carries
its own patterns and priority (see intent/base.py), so this module never
needs to change when a new intent is added elsewhere.
"""
from __future__ import annotations

from app.ai_pipeline.registry import INTENT_REGISTRY


def fast_classify(query: str) -> str:
    """Return the best-matching registered intent key for `query`."""
    specs = sorted(INTENT_REGISTRY.all().values(), key=lambda s: s.priority)

    for spec in specs:
        for pattern in spec.compiled_patterns():
            if pattern.search(query):
                return spec.key

    default = next((s for s in specs if s.is_default), None)
    if default is not None:
        return default.key
    if specs:
        return specs[0].key
    raise RuntimeError("No intents registered — cannot classify query")

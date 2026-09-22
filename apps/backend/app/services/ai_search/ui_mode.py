"""
ui_mode classification — a minimal, additive projection from the
EXISTING classification signals (decision_intent.py's 12 labels, Market
Pulse detection, pipeline.py::_route_specialist's specialist_kind,
entities.py's policy/sector matches) onto one of the 8 first-release AI
Answer UI modes.

This is deliberately NOT the full "one explicit IntentResolution
contract" the 2026-09-21 intent audit's Phase 2 remediation calls for
(that consolidation replaces the 4 competing classifiers themselves,
end to end) — this module is a thin, isolated projection over their
CURRENT outputs, so the frontend can start rendering intent-aware UI
now without waiting for that larger backend refactor. Its public
contract (the 8 ui_mode string values below) is designed to survive
that later migration unchanged; only this module's internals would be
replaced by the real IntentResolution classifier.

Known limitation, inherited from the classifiers this reads (not
introduced here — see the audit): sector detection requires the literal
word "sector"/"industry" in the query, so a query like "why are banking
stocks down today?" resolves to company_specialist (not sector) and
therefore direct_company_research here, not sector_theme_research. This
is exactly the "expanded sector/policy entity vocabulary" gap the
audit's Phase 3 names as separate follow-up work.
"""
from __future__ import annotations

import re

UI_MODES = (
    "direct_company_research",
    "switch_analysis",
    "company_comparison",
    "factual_lookup",
    "policy_macro_impact",
    "market_pulse",
    "event_impact",
    "sector_theme_research",
)

# Decision-intent labels (decision_intent.py) that read as a personal
# holding decision rather than a neutral side-by-side comparison, when
# BOTH a holding and a target were actually resolved. Public (2026-09-22):
# aev2/switch_analysis.py imports this SAME set to decide whether a
# 2-company comparison query is switch-shaped before assembling a
# "current holding vs proposed alternative" object — the one real
# distinguishing signal between switch_analysis and a neutral
# comparison, never duplicated as a second literal set there.
SWITCH_LIKE_INTENTS = {"switch", "hold", "sell", "buy", "decision"}

_FACTUAL_RE = re.compile(
    r"^\s*what\s+(?:was|is|were|are)\b.{0,80}\?\s*$|"
    r"\bhow\s+much\b|\bhow\s+many\b|"
    r"\bq[1-4]\s+(?:revenue|profit|earnings|results)\b|"
    r"\b(?:revenue|profit|eps|market\s+cap)\s+(?:of|for)\b",
    re.IGNORECASE,
)


def _looks_factual(query: str) -> bool:
    """Deliberately conservative — a heuristic, not a classifier. False
    negatives fall back to direct_company_research (a safe default: that
    layout still shows the real answer text, just without factual_
    lookup's more compact framing), never a crash or a wrong-shaped
    schema requirement."""
    return bool(_FACTUAL_RE.search(query or ""))


def classify_ui_mode(
    *, specialist_kind: str | None, intent_data: dict | None, entities: dict | None, query: str,
) -> str:
    """Pure function — no I/O, no new classification signal beyond what
    the caller already computed. Called once, in pipeline.py's
    _assemble_response, after intent_data/entities/specialist_kind are
    already resolved; never re-derives them."""
    intent_data = intent_data or {}
    entities = entities or {}
    intent = intent_data.get("intent", "general")
    holding = intent_data.get("holding")
    target = intent_data.get("target")

    if specialist_kind == "sector":
        return "sector_theme_research"

    if specialist_kind == "comparison":
        if holding and target and intent in SWITCH_LIKE_INTENTS:
            return "switch_analysis"
        return "company_comparison"

    if intent == "news_reaction":
        return "event_impact"

    if entities.get("policies"):
        return "policy_macro_impact"

    if _looks_factual(query):
        return "factual_lookup"

    return "direct_company_research"

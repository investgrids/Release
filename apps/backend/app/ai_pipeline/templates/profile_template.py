"""Profile Template — Company Analysis, Portfolio."""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.registry import TEMPLATE_REGISTRY
from app.ai_pipeline.templates.base import AnswerTemplate

_UNAVAILABLE = {"available": False, "note": "No matching signal resolved for this specific query — the retriever ran but found nothing relevant."}


def _deterministic_sections(decision: DecisionResult, evidence: list[Evidence]) -> dict:
    valuation = [
        e.claim for e in evidence
        if e.source == "company" and "fundamentals" in e.id
    ]
    recent_events = [
        {"claim": e.claim, "polarity": e.polarity}
        for e in evidence if e.source in ("event", "company") and "fundamentals" not in e.id
    ][:6]
    return {
        "valuation": valuation or ["No fundamentals data resolved for this query."],
        "recent_events": recent_events,
        "ripple_exposure": decision.ripple_reach or _UNAVAILABLE,
        "risks": decision.risks,
        # No peer-comparison retriever exists yet — reported honestly rather
        # than fabricated, consistent with the rest of the pipeline's
        # missing_data discipline.
        "competitors": {"available": False, "note": "Peer comparison retriever not yet built."},
        "ai_verdict": decision.verdict or f"{decision.mood} — {decision.confidence.level} confidence",
    }


TEMPLATE_REGISTRY.register("profile_template")(AnswerTemplate(
    key="profile_template",
    label="Profile",
    required_sections=(
        "summary", "business_quality", "growth_drivers", "valuation",
        "recent_events", "ripple_exposure", "risks", "competitors", "ai_verdict",
    ),
    llm_sections=("summary", "business_quality", "growth_drivers"),
    system_prompt=(
        "You are a senior Indian equity research analyst. You are given "
        "pre-computed, evidence-derived facts about a company and must write "
        "a concise business summary, an assessment of business quality, and "
        "growth drivers. Do not introduce financial figures, ratios, or "
        "competitor names not present in the facts you were given. Return "
        "only valid JSON."
    ),
    deterministic_sections=_deterministic_sections,
))

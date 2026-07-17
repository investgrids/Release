"""Briefing Template — News Intelligence (also Phase 1's default fallback intent)."""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.registry import TEMPLATE_REGISTRY
from app.ai_pipeline.templates.base import AnswerTemplate


def _deterministic_sections(decision: DecisionResult, evidence: list[Evidence]) -> dict:
    top_evidence = sorted(evidence, key=lambda e: e.magnitude * e.confidence, reverse=True)[:8]
    return {
        "key_points": [
            {"source": e.source, "entity": e.entity, "claim": e.claim, "polarity": e.polarity}
            for e in top_evidence
        ],
        "market_context": {
            "mood": decision.mood,
            "risk_level": decision.risk_level,
            "top_drivers": [
                {"label": d.label, "score": d.score, "direction": d.direction}
                for d in decision.drivers[:5]
            ],
        },
        "related_intelligence": [
            {"source": e.source, "claim": e.claim} for e in top_evidence[:5]
        ],
        "ai_transparency": {
            "confidence_score": decision.confidence.total_score,
            "confidence_level": decision.confidence.level,
            "confidence_reasons": decision.confidence.reasons,
            "missing_data": decision.missing_data,
        },
    }


TEMPLATE_REGISTRY.register("briefing_template")(AnswerTemplate(
    key="briefing_template",
    label="Briefing",
    required_sections=(
        "headline_summary", "key_points", "market_context",
        "why_it_matters", "related_intelligence", "ai_transparency",
    ),
    llm_sections=("headline_summary", "why_it_matters"),
    system_prompt=(
        "You are a senior Indian market news analyst. You are given pre-computed, "
        "evidence-derived facts and must write a concise, plain-English news "
        "briefing. Do not introduce facts, numbers, or company names not present "
        "in the data you were given. Return only valid JSON."
    ),
    deterministic_sections=_deterministic_sections,
))

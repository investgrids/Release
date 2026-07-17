"""Verdict Template — Investment Decision (and, in later phases, Company Comparison)."""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.registry import TEMPLATE_REGISTRY
from app.ai_pipeline.templates.base import AnswerTemplate

_UNAVAILABLE = {"available": False, "note": "No matching signal resolved for this specific query — the retriever ran but found nothing relevant."}


def _deterministic_sections(decision: DecisionResult, evidence: list[Evidence]) -> dict:
    top_evidence = sorted(evidence, key=lambda e: e.magnitude * e.confidence, reverse=True)[:6]
    return {
        "verdict": decision.verdict,
        "key_drivers": [
            {"label": d.label, "score": d.score, "direction": d.direction}
            for d in decision.drivers
        ],
        "ripple_effects": decision.ripple_reach or _UNAVAILABLE,
        "opportunities": decision.opportunities,
        "risks": decision.risks,
        "historical_similarity": decision.historical_probability or _UNAVAILABLE,
        "related_intelligence": [
            {"source": e.source, "claim": e.claim} for e in top_evidence
        ],
        "ai_transparency": {
            "confidence_score": decision.confidence.total_score,
            "confidence_level": decision.confidence.level,
            "confidence_reasons": decision.confidence.reasons,
            "missing_data": decision.missing_data,
        },
    }


TEMPLATE_REGISTRY.register("verdict_template")(AnswerTemplate(
    key="verdict_template",
    label="Verdict",
    required_sections=(
        "verdict", "executive_summary", "why_this_conclusion", "key_drivers",
        "ripple_effects", "opportunities", "risks", "historical_similarity",
        "what_changes_this_view", "related_intelligence", "ai_transparency",
    ),
    llm_sections=("executive_summary", "why_this_conclusion", "what_changes_this_view"),
    system_prompt=(
        "You are a senior Indian equity market analyst. You are given pre-computed, "
        "evidence-derived facts and must write concise, plain-English prose that "
        "explains and elaborates on them for an investor. You do not have the "
        "authority to reach a different verdict, invent a confidence score, or "
        "cite numbers not present in the facts you were given. Return only valid JSON."
    ),
    deterministic_sections=_deterministic_sections,
))

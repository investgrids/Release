"""Exploratory Template — Sector Analysis, Theme Discovery, Market Outlook, Risk Analysis."""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.registry import TEMPLATE_REGISTRY
from app.ai_pipeline.templates.base import AnswerTemplate


def _deterministic_sections(decision: DecisionResult, evidence: list[Evidence]) -> dict:
    top_evidence = sorted(evidence, key=lambda e: e.magnitude * e.confidence, reverse=True)[:8]
    return {
        "key_drivers": [
            {"label": d.label, "score": d.score, "direction": d.direction}
            for d in decision.drivers
        ],
        "opportunities": decision.opportunities,
        "risks": decision.risks,
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


TEMPLATE_REGISTRY.register("exploratory_template")(AnswerTemplate(
    key="exploratory_template",
    label="Exploratory",
    required_sections=(
        "overview", "key_drivers", "opportunities", "risks",
        "bull_case", "bear_case", "related_intelligence", "ai_transparency",
    ),
    llm_sections=("overview", "bull_case", "bear_case"),
    system_prompt=(
        "You are a senior Indian market strategist. You are given pre-computed, "
        "evidence-derived facts and must write a concise overview plus balanced "
        "bull and bear cases. Do not introduce statistics, sectors, or companies "
        "not present in the facts you were given. Return only valid JSON."
    ),
    deterministic_sections=_deterministic_sections,
))

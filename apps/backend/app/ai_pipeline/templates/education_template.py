"""Education Template — General Education ('Explain repo rate', 'What is EV/EBITDA?')."""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.registry import TEMPLATE_REGISTRY
from app.ai_pipeline.templates.base import AnswerTemplate


def _deterministic_sections(decision: DecisionResult, evidence: list[Evidence]) -> dict:
    top_evidence = sorted(evidence, key=lambda e: e.magnitude * e.confidence, reverse=True)[:4]
    return {
        "related_context": [
            {"source": e.source, "claim": e.claim} for e in top_evidence
        ],
        "follow_up_questions": [
            "How does this affect my existing investments?",
            "What's a real recent example of this in the Indian market?",
            "How is this different from related concepts?",
        ],
    }


TEMPLATE_REGISTRY.register("education_template")(AnswerTemplate(
    key="education_template",
    label="Education",
    required_sections=("explanation", "why_it_matters", "related_context", "follow_up_questions"),
    llm_sections=("explanation", "why_it_matters"),
    system_prompt=(
        "You are a patient financial educator explaining concepts to a retail "
        "investor learning about Indian capital markets. Explain the concept "
        "the user asked about clearly and simply, then say why it matters for "
        "investors. Use the current market context provided only as light "
        "color, not as the core of your explanation. Return only valid JSON."
    ),
    deterministic_sections=_deterministic_sections,
))

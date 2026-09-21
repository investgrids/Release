"""
The one shared fail-closed response SKELETON both real degraded paths
build from — pipeline.py's `_build_degraded_response` (a genuinely failed
synthesis, was_degraded=True from specialist.run()) and safety_gate.py's
`build_v3_safety_degraded_response` (a synthesis that parsed fine but
whose generated conclusion text failed the recommendation-language
check). Before this module existed, both hand-wrote the same ~40-key
dict independently — a real risk that a future field addition would land
in one and silently not the other, producing two different "degraded"
shapes the frontend's synthesis_incomplete gating would then have to
handle inconsistently.

This module owns only the SHAPE — every key, and which keys are always
null/empty because no degraded response may show a verdict, confidence,
horizon, or scenario. It deliberately does NOT decide what's safe to
preserve from the pre-degradation response, because that answer differs
by caller: pipeline's caller has NOTHING trustworthy yet (the specialist
call itself failed, so companies/sectors/news/policies are all wiped),
while safety_gate's caller has a response that already passed full
validation upstream (`validation.py`'s `_verify_companies_exist` and
narrative-consistency check) and is only unsafe in its free-text
conclusion fields — so companies/sectors/news/policies/citations are
kept there. Callers pass in exactly what they trust; this function never
guesses.
"""
from __future__ import annotations


def empty_investment_verdict() -> dict:
    """The one honest-empty investment_verdict shape every degraded path
    uses — including /api/ai/search/refine's own degraded response
    (ai_search_refine.py), which returns only investment_verdict/
    decision_engine_v2/ai_conclusion, not this module's full response
    shape, but must still agree on what "no verdict" looks like."""
    return {
        "rating": "Not Applicable", "direction": "neutral", "confidence": None,
        "horizon": None, "top_picks": [], "risks": [], "catalysts": [],
        "opportunity_score": None, "risk_level": "", "suitable_for": "",
        "engine_verdict": None,
    }


def build_degraded_shape(
    *,
    query: str,
    response_id: str | None,
    schema_version: str | None,
    specialist_kind: str | None,
    degraded_reason: str | None,
    summary: str,
    companies: list | None = None,
    sectors: list | None = None,
    related_events: list | None = None,
    news: list | None = None,
    policies: list | None = None,
    citations: list | None = None,
    source_attribution: list | None = None,
    evidence_score: dict | None = None,
    validation: dict | None = None,
    sources_count: int = 0,
) -> dict:
    """Pure function — no I/O, no logging (each caller logs its own
    reason/field before calling this). Every list/dict default is a
    fresh honest-empty value, never a shared mutable default."""
    related_events = related_events if related_events is not None else []
    return {
        "query": query, "response_id": response_id, "schema_version": schema_version,
        "specialist": specialist_kind,
        "degraded_reason": degraded_reason,
        "synthesis_incomplete": True,
        "answer": {
            "summary": summary, "bottom_line": summary,
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "what_priced_in": "",
            "risks": [], "opportunities": [],
            "confidence": None, "confidence_level": "unscored",
            "sentiment": "neutral", "sources_count": sources_count,
        },
        "key_drivers": [], "insights": [],
        "companies": companies if companies is not None else [],
        "sectors": sectors if sectors is not None else [],
        "related_events": related_events,
        "news": news if news is not None else [],
        "policies": policies if policies is not None else [],
        "timeline": [], "historical_comparison": [], "ripple_chain": [],
        "scenarios": {}, "monitoring": {"items": []},
        "follow_up_questions": [], "follow_up_groups": [],
        "investment_verdict": empty_investment_verdict(),
        "market_chart": {"labels": [], "series": []},
        "graph": {"nodes": [], "edges": []},
        "citations": citations if citations is not None else [],
        "decision_intelligence": None,
        "confidence_data": {"level": "unscored", "score": None, "reasons": [], "breakdown": {}, "caveats": []},
        "decision_engine_v2": {}, "timeline_intelligence": {}, "opportunity_risk_matrix": {},
        "ai_conclusion": {},
        "evidence_score": evidence_score if evidence_score is not None else {
            "stars": None, "checklist": {},
            "source_count": sources_count, "development_count": sources_count,
            "corroborating_source_count": sources_count,
        },
        "confidence_breakdown": {"final_confidence": None, "level": "unscored"},
        "source_attribution": source_attribution if source_attribution is not None else [],
        "validation": validation if validation is not None else {"repairs": [], "omissions": [], "contradiction_flagged": False},
        "market_impact_horizons": {}, "what_to_monitor": [], "ai_reasoning_methods": [],
    }

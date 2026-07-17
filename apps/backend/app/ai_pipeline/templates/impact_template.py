"""Impact Template — Event Impact (and, in later phases, Ripple/Policy/Economic Analysis)."""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.registry import TEMPLATE_REGISTRY
from app.ai_pipeline.templates.base import AnswerTemplate

_UNAVAILABLE = {"available": False, "note": "No matching signal resolved for this specific query — the retriever ran but found nothing relevant."}


def _deterministic_sections(decision: DecisionResult, evidence: list[Evidence]) -> dict:
    affected_sectors = [
        {"sector": e.entity, "claim": e.claim, "polarity": e.polarity}
        for e in evidence
        if e.source == "event" and e.entity and ":sector:" in e.id
    ]
    affected_companies = [
        {"symbol": e.entity, "claim": e.claim, "polarity": e.polarity}
        for e in evidence
        if e.source == "event" and e.entity and ":company:" in e.id
    ]

    # The enriched top event's raw payload (from EventService.get_event_detail)
    # carries a real timeline when available — reuse it rather than inventing one.
    timeline: list[dict] = []
    top_event_evidence = next(
        (e for e in evidence if e.source == "event" and e.id.count(":") == 1), None
    )
    if top_event_evidence and isinstance(top_event_evidence.raw, dict):
        timeline = top_event_evidence.raw.get("timeline", []) or []

    return {
        "affected_sectors": affected_sectors,
        "affected_companies": affected_companies,
        "timeline": timeline,
        "ripple_chain": decision.ripple_reach or _UNAVAILABLE,
        "historical_comparison": decision.historical_probability or _UNAVAILABLE,
        "risks": decision.risks,
    }


TEMPLATE_REGISTRY.register("impact_template")(AnswerTemplate(
    key="impact_template",
    label="Impact",
    required_sections=(
        "event_summary", "affected_sectors", "affected_companies", "timeline",
        "ripple_chain", "historical_comparison", "risks", "what_to_watch",
    ),
    llm_sections=("event_summary", "what_to_watch"),
    system_prompt=(
        "You are a senior Indian market event analyst. You are given pre-computed, "
        "evidence-derived facts about a market event and must write concise, "
        "plain-English prose summarizing the event and what to watch next. Do not "
        "introduce sectors, companies, or numbers not present in the facts you "
        "were given. Return only valid JSON."
    ),
    deterministic_sections=_deterministic_sections,
))

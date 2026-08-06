"""
Company specialist — company analysis + catch-all for macro/historical/
event-impact/etc. (the query router only defines 3 routes in Phase 1; per
the plan, anything not clearly Comparison or Sector lands here, same as V2's
generic `_build_prompt` path today).

Extends V2's proven `_build_prompt` schema (ai_search_service.py:1207) rather
than starting fresh — these are V2's already-strong categories (Company
Analysis, Macro, Historical, Event Impact all scored well in the frozen
baseline) so the goal here is consolidation (fold insights/scenarios/
monitoring into this one call) and adding the new Decision Engine v2
primitives, not redesigning what already works. Schema is nested (see
schema.py's module docstring) per the Phase 1C reliability fix.
"""
from __future__ import annotations

from app.services.ai_search.schema import (
    EVIDENCE_GROUP,
    EXTRAS_GROUP,
    MONITORING_COUNT_NOTE,
    RISKS_GROUP,
    TIMELINE_GROUP,
    render_decision_group,
    render_investment_group,
)
from app.services.ai_search.specialists.base import PRIORITY_INSTRUCTIONS, parse_specialist_json, research_framing_rules

SPECIALIST_SYSTEM = (
    "You are a senior Indian equity market analyst at an institutional fund. "
    "Generate structured market intelligence for professional investors. "
    "Respond with valid JSON only. No markdown fences. No commentary."
)

# See sector.py/comparison.py for the shared tuning history — 9,000 caused
# real HTTP 413s on Groq's fast fallback model; 6,500 fits the nested schema
# (smaller than the flat one it replaced) with safety margin.
MAX_TOKENS = 6500


def build_prompt(query: str, evidence, intent_data: dict, entities: dict) -> str:
    from app.services.ai_search.enrichment import _commodity_safety_note, _intent_overlay
    from app.services.ai_search.regexes import _OUTLOOK_LABELS
    from app.api.companies import _NSE_UNIVERSE

    evs = "\n".join(f"- [{e['category']}] {e['title']} (score:{e['impact_score']:.0f})" for e in evidence.events[:5]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in evidence.news[:5]) or "None"
    pols = "\n".join(f"- {p['title']} [{p['ministry']}]" for p in evidence.policies[:3]) or "None"
    extra_context = evidence.to_context_text()

    # Phase 1.7 — when session context merged in companies the query text
    # itself didn't name (e.g. "What about BEML?" following a HAL vs BEL
    # discussion), the entity list is the only place that context survives
    # — nothing else in this prompt references `entities` at all, so
    # without this the merge would be a no-op from the model's point of
    # view. Only fires when there's more than one company to address;
    # a single-company entities list needs no extra instruction.
    session_companies = entities.get("companies") or []
    session_note = ""
    if len(session_companies) > 1:
        names = [next((c["name"] for c in _NSE_UNIVERSE if c["symbol"] == sym), sym) for sym in session_companies]
        session_note = (
            f"\n\nRESEARCH SESSION CONTEXT: This question continues an existing discussion of "
            f"{', '.join(names)}. Directly address ALL of these companies in your answer — "
            f"populate \"companies\" with all of them (not just whichever one this specific "
            f"question names), and make the investment view explicitly comparative across them."
        )

    investment_group = render_investment_group()
    decision_group = render_decision_group(is_comparison=False)

    return f"""Query: "{query}"

DB Events: {evs}
News: {nws}
Policies: {pols}

{PRIORITY_INSTRUCTIONS}
Return ONLY this JSON (no fences, no extra keys):
{{
{investment_group}
{decision_group}
{EVIDENCE_GROUP}
  "companies": [
    {{"symbol": "SYMBOL1", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 90, "confidence": 85, "reason": "specific 1-line reason tied to the query"}},
    {{"symbol": "SYMBOL2", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 85, "confidence": 80, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL3", "name": "Full Company Name", "impact_type": "neutral", "impact_score": 65, "confidence": 60, "reason": "specific 1-line reason"}}
  ],
  "sectors": [
    {{"name": "Most Relevant Sector", "score": 90, "confidence": 85, "outlook": "Strong Growth", "positive": true, "explanation": "1 sentence"}},
    {{"name": "Second Sector", "score": 70, "confidence": 65, "outlook": "Moderate", "positive": true, "explanation": "1 sentence"}}
  ],
{TIMELINE_GROUP}
{RISKS_GROUP}
{EXTRAS_GROUP}
}}

CRITICAL RULES:
{research_framing_rules(_OUTLOOK_LABELS)}
{MONITORING_COUNT_NOTE}
- "evidence.key_drivers[].icon" must be ONE lowercase keyword from: procurement, policy, manufacturing, export, valuation, risk, demand, technology, capex, regulation, earnings, supply-chain, currency, commodity, credit.
- "extras.insights" titles must be SPECIFIC to the query "{query}". Use real NSE symbols, actual rupee amounts, and genuine Indian market context throughout.{_commodity_safety_note(query)}{_intent_overlay(intent_data, extra_context)}{session_note}"""


async def run(query: str, evidence, intent_data: dict, entities: dict) -> tuple[dict, bool]:
    """Single _call_with_fallback call. Returns (parsed_json, was_degraded)."""
    from app.services.ai_service import _call_with_fallback

    prompt = build_prompt(query, evidence, intent_data, entities)
    raw = await _call_with_fallback(prompt, SPECIALIST_SYSTEM, max_tokens=MAX_TOKENS, priority="interactive")
    return parse_specialist_json(raw, query)

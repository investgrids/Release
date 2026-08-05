"""
Sector specialist — NEW prompt, no V2 equivalent to extend.

V2 has no dedicated sector-analysis prompt at all: a "how is the banking
sector doing" query fell through to the generic `_build_prompt` path, with
only sector *evidence* injected into extra_context (via the _SECTOR_TRIGGER
block) — the LLM was still asked for a generic company/event-shaped
narrative. This is the direct, named cause of Sector Analysis being one of
V2's two worst-performing categories.

This specialist asks a genuinely sector-shaped question instead: Sector
Score, Current Trend, Money Flow, Government Drivers, Macro Drivers, Sector
Leaders, Sector Risks, Catalysts, Timeline, Investment Outlook — grounded in
the real live per-sector % change data already fetched into the
EvidenceBundle (evidence.sector_rows). Schema is nested (see schema.py's
module docstring) per the Phase 1C reliability fix.
"""
from __future__ import annotations

from app.services.ai_search.schema import (
    EXTRAS_GROUP,
    MONITORING_COUNT_NOTE,
    TIMELINE_GROUP,
    render_decision_group,
    render_investment_group,
)
from app.services.ai_search.specialists.base import PRIORITY_INSTRUCTIONS, parse_specialist_json, research_framing_rules

SPECIALIST_SYSTEM = (
    "You are a senior Indian equity sector strategist at an institutional fund. "
    "You analyze sectors, not individual companies in isolation — money flow, "
    "policy tailwinds/headwinds, macro sensitivity, and relative positioning "
    "versus other sectors. Respond with valid JSON only. No markdown fences. No commentary."
)

# See company.py's MAX_TOKENS comment — 9,000 triggers HTTP 413 on Groq's
# fast-tier fallback model; 6,500 fits the nested schema with safety margin.
MAX_TOKENS = 6500


def _identify_sector(query: str, sector_rows: list[dict]) -> str | None:
    q_lower = query.lower()
    for s in sector_rows:
        name = s.get("name", "")
        if any(tok in q_lower for tok in name.lower().split() if len(tok) > 3):
            return name
    return None


def build_prompt(query: str, evidence, intent_data: dict, entities: dict) -> str:
    from app.services.ai_search_service import _OUTLOOK_LABELS

    sector_rows = evidence.sector_rows
    target_sector = _identify_sector(query, sector_rows)
    sector_lines = "\n".join(f"- {s['name']}: {s['value']} (1-day change, real live data)" for s in sector_rows[:12]) or "None available"
    evs = "\n".join(f"- [{e['category']}] {e['title']} (score:{e['impact_score']:.0f})" for e in evidence.events[:6]) or "None"
    pols = "\n".join(f"- {p['title']} [{p['ministry']}]" for p in evidence.policies[:4]) or "None"
    extra_context = evidence.to_context_text()

    investment_group = render_investment_group()
    decision_group = render_decision_group(is_comparison=False)

    return f"""Query: "{query}"

Target sector (best match against real live sector data, may be null if the query names no specific sector — analyze broadly in that case): {target_sector or "not clearly identified — infer from the query text"}

Real live sector performance (1-day % change, all tracked sectors — use this to ground "current_trend" and to compare the target sector's relative positioning, do not invent numbers not shown here):
{sector_lines}

Related policy actions (real, filed/announced): {pols}
Related market events (real, from DB): {evs}
{f"Additional real context: {extra_context}" if extra_context else ""}

{PRIORITY_INSTRUCTIONS}
Return ONLY this JSON (no fences, no extra keys):
{{
{investment_group}
{decision_group}
  "evidence": {{
    "what_happened": "1 factual sentence",
    "why_it_happened": "1 contextual sentence",
    "immediate_impact": "1 sentence on near-term market effect",
    "medium_term": "1 sentence on 3-12 month outlook",
    "long_term": "1 sentence on structural implications",
    "what_priced_in": "1-2 sentences",
    "key_drivers": [
      {{"icon": "policy", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 85}},
      {{"icon": "demand", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 78}}
    ]
  }},
  "sector_analysis": {{
    "sector_score": "0-100 composite score reflecting current momentum + fundamentals + policy tailwind, NOT just the 1-day % change",
    "current_trend": "1-2 sentences citing the REAL % change data above",
    "money_flow": "1-2 sentences — is institutional money rotating in/out, and why; say plainly if this is inferred from price action rather than confirmed flow data",
    "government_drivers": ["specific real policy/government driver 1", "specific real policy/government driver 2"],
    "macro_drivers": ["specific macro driver 1", "specific macro driver 2"],
    "sector_leaders": [
      {{"symbol": "SYMBOL1", "name": "Full Company Name", "reason": "why this company leads the sector right now"}},
      {{"symbol": "SYMBOL2", "name": "Full Company Name", "reason": "specific reason"}}
    ],
    "sector_laggards": [
      {{"symbol": "SYMBOL3", "name": "Full Company Name", "reason": "why this company is lagging"}}
    ]
  }},
  "companies": [
    {{"symbol": "SYMBOL1", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 88, "confidence": 82, "reason": "specific 1-line reason tied to this sector's dynamics"}},
    {{"symbol": "SYMBOL2", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 80, "confidence": 75, "reason": "specific 1-line reason"}}
  ],
  "sectors": [
    {{"name": "{target_sector or 'Target Sector'}", "score": 78, "confidence": 80, "outlook": "Positive", "positive": true, "explanation": "1 sentence tying sector_score to the mechanism"}}
  ],
{TIMELINE_GROUP}
  "risks": {{
    "risks": ["specific sector risk 1", "specific sector risk 2", "specific sector risk 3"],
    "opportunities": ["specific opportunity 1", "specific opportunity 2"],
    "opportunity_matrix": {{"high": ["item"], "medium": ["item"], "low": ["item"]}},
    "risk_matrix": {{"high": ["item"], "medium": ["item"], "low": ["item"]}},
    "catalysts": ["specific upcoming catalyst 1", "specific upcoming catalyst 2"]
  }},
{EXTRAS_GROUP}
}}

CRITICAL RULES:
{research_framing_rules(_OUTLOOK_LABELS)}
{MONITORING_COUNT_NOTE}
- "sector_analysis.sector_score" must be a number 0-100, not a string, not a letter grade.
- "sector_analysis.current_trend" and "money_flow" must reference the REAL sector % change data given above — never invent a number not shown.
- "sector_analysis.sector_leaders"/"sector_laggards" must be real, listed NSE equities genuinely in this sector.
- "evidence.key_drivers[].icon" must be ONE lowercase keyword from: procurement, policy, manufacturing, export, valuation, risk, demand, technology, capex, regulation, earnings, supply-chain, currency, commodity, credit.
- Every field must be SPECIFIC to "{query}" and the identified sector — no generic "the sector faces headwinds and tailwinds" filler."""


async def run(query: str, evidence, intent_data: dict, entities: dict) -> tuple[dict, bool]:
    """Single _call_with_fallback call. Returns (parsed_json, was_degraded)."""
    from app.services.ai_service import _call_with_fallback

    prompt = build_prompt(query, evidence, intent_data, entities)
    raw = await _call_with_fallback(prompt, SPECIALIST_SYSTEM, max_tokens=MAX_TOKENS, priority="interactive")
    parsed, degraded = parse_specialist_json(raw, query)
    if not degraded:
        # sector_analysis is sector.py-specific (not part of the shared
        # flatten_nested mapping in schema.py, which only knows the 6 groups
        # common to all 3 specialists) — merge its fields into the flat
        # shape here, at the one call site that knows about it.
        try:
            import json as _json
            clean = raw.strip()
            if clean.startswith("```"):
                import re as _re
                clean = _re.sub(r"^```(?:json)?\s*", "", clean)
                clean = _re.sub(r"\s*```$", "", clean).strip()
            raw_nested = _json.loads(clean)
            sa = raw_nested.get("sector_analysis") or {}
            parsed["sector_score"] = sa.get("sector_score")
            parsed["current_trend"] = sa.get("current_trend", "")
            parsed["money_flow"] = sa.get("money_flow", "")
            parsed["government_drivers"] = sa.get("government_drivers", [])
            parsed["macro_drivers"] = sa.get("macro_drivers", [])
            parsed["sector_leaders"] = sa.get("sector_leaders", [])
            parsed["sector_laggards"] = sa.get("sector_laggards", [])
        except Exception:
            pass
    return parsed, degraded

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
    EVIDENCE_GROUP,
    EXTRAS_GROUP,
    MONITORING_COUNT_NOTE,
    TIMELINE_GROUP,
    CLAIM_SOURCES_GROUP,
    render_decision_group,
    render_investment_group,
)
from app.services.ai_search.specialists.base import PRIORITY_INSTRUCTIONS, premise_note, parse_specialist_json, research_framing_rules

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
    from app.services.ai_search.regexes import _OUTLOOK_LABELS

    sector_rows = evidence.sector_rows
    target_sector = _identify_sector(query, sector_rows)
    sector_lines = "\n".join(f"- {s['name']}: {s['value']} (1-day change, real live data)" for s in sector_rows[:12]) or "None available"
    # Phase 5E.5: deduped view — see specialists/company.py's comment.
    evs = "\n".join(f"- [E{i}] [{e['category']}] {e['title']} (score:{e['impact_score']:.0f})" for i, e in enumerate(evidence.deduped_events()[:6], 1)) or "None"
    pols = "\n".join(f"- [P{i}] {p['title']} [{p['ministry']}]" for i, p in enumerate(evidence.policies[:4], 1)) or "None"
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
{premise_note(evidence)}

{PRIORITY_INSTRUCTIONS}
Return ONLY this JSON (no fences, no extra keys):
{{
{investment_group}
{decision_group}
{CLAIM_SOURCES_GROUP}
{EVIDENCE_GROUP}
  "sector_analysis": {{
    "current_trend": "1-2 sentences citing the REAL % change data above",
    "government_drivers": ["real policy/government driver that appears in the evidence above (0-2)"],
    "macro_drivers": ["macro driver that appears in the evidence above (0-2)"]
  }},
  "companies": [
    {{"symbol": "SYMBOL1", "name": "Full Company Name", "reason": "1 grounded sentence tied to this sector's dynamics"}}
  ],
  "sectors": [
    {{"name": "{target_sector or 'Target Sector'}", "explanation": "1 grounded sentence"}}
  ],
{TIMELINE_GROUP}
  "risks": {{
    "risks": ["grounded sector risk or evidence limitation (0-3)"],
    "opportunities": ["grounded opportunity (0-2)"]
  }},
{EXTRAS_GROUP}
}}

CRITICAL RULES:
{research_framing_rules(_OUTLOOK_LABELS)}
{MONITORING_COUNT_NOTE}
- "sector_analysis.current_trend" must reference the REAL sector % change data given above — never invent a number not shown.
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

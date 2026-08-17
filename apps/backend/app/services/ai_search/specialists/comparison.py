"""
Comparison specialist — extends V2's `_build_decision_prompt` schema
(ai_search_service.py:1028), V2's richest existing structure. What's added:
an explicit "winner" field, "best_investor_type" (who should choose which
side), and the shared Phase 1 consolidation (insights/scenarios/monitoring
folded in) + decision_engine_v2 (with explain_why_not, comparison-specific).
Schema is nested (see schema.py's module docstring) per the Phase 1C
reliability fix. Routing to this specialist is deterministic (intent.py),
not another LLM call — see pipeline.py's _route_specialist / the Phase 1B fix.

This was V2's other proven weak category — the Top-50-Worst list showed
comparisons ("SPICEJET or Shree Cement?", "TRENT vs ZOMATO") degrading to
generic boilerplate more than almost any other category.
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
    "You are a senior Indian market analyst specializing in comparative equity "
    "research. You never give generic paragraphs — every comparison names a "
    "specific winner and explains the specific trade-off with numbers, not vibes. "
    "Respond with valid JSON only. No markdown fences. No commentary."
)

# See company.py's MAX_TOKENS comment for the tuning history (9,000 -> real
# HTTP 413s). This is the richest schema of the 3 specialists (decision_
# intelligence is substantial), kept at 7,000 rather than trimmed further to
# 6,500 like the other two.
MAX_TOKENS = 7000


def _build_multi_compare_prompt(query: str, evidence, entities: dict) -> str:
    """Phase 6G Slice 1 — 3+ named companies ("Compare TCS, Infosys, and
    Wipro") get parallel per-entity analyses (decision_intelligence.
    entity_analyses[]) instead of the pairwise holding_analysis/
    target_analysis/comparison[]/tradeoff{}/decision_framework{} shape
    build_prompt() below produces for exactly 2 entities — explicitly
    NOT a genuine N-way dimension comparison, same minimum-bar scope
    V2's original _build_multi_compare_prompt (ai_search_service.py)
    had. Before this port, V3 only disclosed which companies got
    dropped (degraded_reason="multi_entity_partial") rather than
    actually analyzing all of them — see pipeline.py's is_multi_compare
    handling.

    Uses V3's actual nested schema groups (schema.py) throughout —
    investment/decision/evidence/companies/sectors/timeline/risks — NOT
    V2's old flat template. A first version of this port copied V2's
    flat JSON shape verbatim and it does not conform to this pipeline's
    parse_specialist_json/flatten_nested contract (missing the nested
    groups schema.py's REQUIRED_KEYS/flatten_nested expect) — confirmed
    live: real parse failures and companies silently dropped.

    EXTRAS_GROUP is deliberately OMITTED (not just deprioritized in
    text) and entities capped at 3 (not the other blocks' usual 6) —
    also confirmed live: even after fixing the schema shape, a genuine
    3-entity request with the full standard schema plus 3x company/
    entity_analysis objects still truncated mid-JSON before MAX_TOKENS.
    Cutting the lowest-priority group from the schema itself guarantees
    the token savings that just telling the model "extras is lowest
    priority" (PRIORITY_INSTRUCTIONS, still true for the groups that
    remain) didn't reliably achieve on its own. Only the
    decision_intelligence content differs from build_prompt()'s pairwise
    case; everything else matches it exactly."""
    from app.services.ai_search.regexes import _OUTLOOK_LABELS
    from app.services.ai_search.schema import (
        EVIDENCE_GROUP,
        RISKS_GROUP,
        TIMELINE_GROUP,
        render_decision_group,
        render_investment_group,
    )

    symbols = entities.get("companies") or []
    matches = entities.get("company_matches") or []
    names = [m.get("name") for m in matches if m.get("name")] or symbols
    display_names = (names if names else symbols)[:3]  # capped tighter than other blocks' usual 6 -- see token-budget note above
    entity_list = ", ".join(display_names)

    evs = "\n".join(f"- {e['title']}" for e in evidence.deduped_events()[:4]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in evidence.deduped_news()[:4]) or "None"
    extra_context = evidence.to_context_text()
    ctx_block = f"\nCONTEXT:\n{extra_context}\n" if extra_context else ""

    analysis_rows = ",\n".join(
        f'''      {{"entity": "{name}", "symbol": "", "sector": "", "thesis": "",
        "strengths": ["", ""], "risks": ["", ""], "catalysts": [""],
        "near_term_outlook": "neutral", "confidence": 65}}'''
        for name in display_names
    )
    companies_rows = ",\n".join(
        f'    {{"symbol": "", "name": "{name}", "impact_type": "neutral", "impact_score": 65, "confidence": 60, "reason": ""}}'
        for name in display_names
    )

    investment_group = render_investment_group()
    decision_group = render_decision_group(is_comparison=False)  # no single winner to explain-why-not against

    return f"""You are a senior Indian market analyst. The user asked to compare {len(display_names)} companies: {entity_list}.
{ctx_block}
QUERY: "{query}"
COMPANIES TO ANALYZE (all {len(display_names)}, not just one or two): {entity_list}
MARKET NEWS: {nws}
RELATED EVENTS: {evs}

INSTRUCTIONS:
- This is a MULTI-ENTITY comparison ({len(display_names)} companies), not a two-way one. Provide a parallel
  analysis of EACH company in "decision_intelligence.entity_analyses" — do not silently drop any of
  them or only discuss two.
- Do NOT invent pairwise head-to-head framing (no "X beats Y") — a genuine dimension-by-dimension
  comparison across {len(display_names)} entities isn't what this response computes; parallel individual
  analyses are.

{PRIORITY_INSTRUCTIONS}
Return ONLY this JSON (no fences, no extra keys):
{{
{investment_group}
{decision_group}
{EVIDENCE_GROUP}
  "companies": [
{companies_rows}
  ],
  "sectors": [
    {{"name": "Most Relevant Sector", "score": 65, "confidence": 60, "outlook": "Moderate", "positive": true, "explanation": "1 sentence"}}
  ],
{TIMELINE_GROUP}
{RISKS_GROUP}
  "decision_intelligence": {{
    "intent": "compare_multi", "context_complete": true, "missing_context": [],
    "decision_summary": "1-2 sentences: what distinguishes each company from the others on the metric that matters most for this query",
    "entity_analyses": [
{analysis_rows}
    ]
  }}
}}

CRITICAL RULES:
{research_framing_rules(_OUTLOOK_LABELS)}
- Use the real NSE ticker for each company's "symbol" field, in both "companies" and
  "decision_intelligence.entity_analyses"."""


def build_prompt(query: str, evidence, intent_data: dict, entities: dict) -> str:
    from app.services.ai_search.regexes import (
        _COMMODITY_TICKERS,
        _OUTLOOK_LABELS,
    )

    # Phase 6G Slice 1 — 3+ resolved companies get the parallel-analysis
    # prompt above, matching V2's exact detection formula
    # (len(entities["companies"]) >= 3, checked before anything else).
    if len(entities.get("companies") or []) >= 3:
        return _build_multi_compare_prompt(query, evidence, entities)

    holding = intent_data.get("holding") or "Asset A"
    target = intent_data.get("target") or "Asset B"
    horizon = intent_data.get("horizon") or "medium-term"
    risk = intent_data.get("risk") or "moderate"
    intent = intent_data.get("intent", "decision")

    holding_is_commodity = intent_data.get("holding_is_commodity", False)
    target_is_commodity = intent_data.get("target_is_commodity", False)
    holding_is_sector = intent_data.get("holding_is_sector", False)
    target_is_sector = intent_data.get("target_is_sector", False)

    def entity_label(name: str, is_commodity: bool, is_sector: bool) -> str:
        if is_commodity:
            return f"{name} (commodity/asset class)"
        if is_sector:
            return f"{name} (market sector)"
        return name

    def symbol_hint(name: str, is_commodity: bool, is_sector: bool) -> str:
        if is_commodity:
            tick = _COMMODITY_TICKERS.get(name.lower(), "null")
            return f'Set "symbol" to "{tick}" (ETF proxy) or null. Do NOT use equity tickers.'
        if is_sector:
            return 'Set "symbol" to null. This is a sector, not a single stock.'
        return 'Set "symbol" to the real NSE ticker (e.g. TATAMOTORS, RELIANCE, HDFCBANK).'

    a_label = entity_label(holding, holding_is_commodity, holding_is_sector)
    b_label = entity_label(target, target_is_commodity, target_is_sector)

    # Phase 5E.5: deduped views — see specialists/company.py's comment.
    evs = "\n".join(f"- {e['title']}" for e in evidence.deduped_events()[:4]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in evidence.deduped_news()[:4]) or "None"
    extra_context = evidence.to_context_text()
    ctx_block = f"\nCONTEXT:\n{extra_context}\n" if extra_context else ""

    if holding_is_commodity or target_is_commodity:
        comp_dims = ["Inflation Hedge", "Liquidity", "Volatility", "Store of Value", "Growth Potential", "Correlation to Equity"]
    elif holding_is_sector or target_is_sector:
        comp_dims = ["Sector Outlook", "Policy Tailwinds", "Valuation", "Earnings Growth", "Risk Profile", "FII Interest"]
    else:
        comp_dims = [
            "Business Model", "Valuation", "Growth Drivers", "Margins", "ROE",
            "Cash Flow", "Debt", "Order Book", "Risk Profile", "Market Position",
        ]
    comp_rows = "\n".join(
        f'      {{"dimension": "{d}", "holding": "", "target": "", "advantage": "neutral"}},' for d in comp_dims
    ).rstrip(",")

    investment_group = render_investment_group()
    decision_group = render_decision_group(is_comparison=True)

    return f"""You are a senior Indian market analyst. Analyse this investor query and return a single JSON object.
{ctx_block}
QUERY: "{query}"
ENTITY A (holding/first): {a_label}
ENTITY B (target/second): {b_label}
HORIZON: {horizon} | RISK TOLERANCE: {risk}
MARKET NEWS: {nws}
RELATED EVENTS: {evs}

INSTRUCTIONS:
- Fill every string field with real, specific analysis about {holding} and {target}. Name real numbers (valuation multiples, growth rates, margins) wherever you have a basis to estimate them.
- This is a RESEARCH platform, not an advisory one. Never say Buy/Sell/Hold/Strong Buy/Strong Sell/Accumulate/Reduce anywhere.
- Entity A symbol hint: {symbol_hint(holding, holding_is_commodity, holding_is_sector)}
- Entity B symbol hint: {symbol_hint(target, target_is_commodity, target_is_sector)}
- Use the entity name exactly as given in "entity" field (e.g. "{holding}", "{target}").
- "advantage" in comparison rows must be "holding", "target", or "neutral".
- "winner" must be "holding", "target", or "neither" (use "neither" only if genuinely a toss-up).

{PRIORITY_INSTRUCTIONS}
JSON to fill and return:
{{
{investment_group}
{decision_group}
  "evidence": {{
    "what_happened": "", "why_it_happened": "", "immediate_impact": "", "medium_term": "", "long_term": "",
    "what_priced_in": "1-2 sentences: how much of this trade-off is already reflected in current prices for {holding} and {target}?",
    "key_drivers": [
      {{"icon": "valuation", "title": "2-4 word driver name", "explanation": "1 sentence mechanism behind this trade-off", "confidence": 85}},
      {{"icon": "risk", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 76}}
    ]
  }},
  "companies": [
    {{"symbol": "", "name": "{holding}", "impact_type": "neutral", "impact_score": 70, "confidence": 68, "reason": ""}},
    {{"symbol": "", "name": "{target}", "impact_type": "neutral", "impact_score": 70, "confidence": 68, "reason": ""}}
  ],
  "sectors": [
    {{"name": "", "score": 65, "confidence": 62, "outlook": "Moderate", "positive": true, "explanation": "1 sentence"}}
  ],
{TIMELINE_GROUP}
  "risks": {{
    "risks": ["", "", ""], "opportunities": ["", ""],
    "opportunity_matrix": {{"high": ["item"], "medium": ["item"], "low": ["item"]}},
    "risk_matrix": {{"high": ["item"], "medium": ["item"], "low": ["item"]}}
  }},
  "decision_intelligence": {{
    "intent": "{intent}", "context_complete": true, "missing_context": [], "decision_summary": "",
    "winner": "<holding | target | neither>",
    "best_investor_type": {{"holding": "e.g. Conservative / income-focused investors", "target": "e.g. Aggressive / growth-focused investors"}},
    "holding_analysis": {{
      "entity": "{holding}", "symbol": "", "sector": "", "thesis": "",
      "strengths": ["", "", ""], "risks": ["", "", ""], "catalysts": ["", ""],
      "near_term_outlook": "neutral", "confidence": 65
    }},
    "target_analysis": {{
      "entity": "{target}", "symbol": "", "sector": "", "thesis": "",
      "strengths": ["", "", ""], "risks": ["", "", ""], "catalysts": ["", ""],
      "near_term_outlook": "neutral", "confidence": 65
    }},
    "comparison": [
{comp_rows}
    ],
    "tradeoff": {{
      "reasons_to_switch": ["", "", ""], "reasons_to_hold": ["", "", ""],
      "risks_of_switching": ["", ""], "risks_of_holding": ["", ""], "when_to_wait": ""
    }},
    "decision_framework": {{
      "supports_switch": ["", "", ""], "argues_against": ["", ""], "key_unknowns": ["", ""], "ai_stance": ""
    }}
  }},
{EXTRAS_GROUP}
}}

{MONITORING_COUNT_NOTE}
{research_framing_rules(_OUTLOOK_LABELS)}"""


async def run(query: str, evidence, intent_data: dict, entities: dict) -> tuple[dict, bool]:
    """Single _call_with_fallback call. Returns (parsed_json, was_degraded)."""
    from app.services.ai_service import _call_with_fallback

    prompt = build_prompt(query, evidence, intent_data, entities)
    raw = await _call_with_fallback(prompt, SPECIALIST_SYSTEM, max_tokens=MAX_TOKENS, priority="interactive")
    parsed, degraded = parse_specialist_json(raw, query)
    if not degraded:
        # decision_intelligence is comparison.py-specific and already passed
        # through unchanged by flatten_nested (schema.py) when present at
        # the nested top level — nothing further needed here.
        pass
    return parsed, degraded

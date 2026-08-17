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
from app.services.ai_search.specialists.base import (
    PRIORITY_INSTRUCTIONS,
    degraded_response,
    parse_specialist_json,
    research_framing_rules,
)

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


# Step 2B (6G Cutover Gate) — multi-compare degraded-provider resilience.
#
# Confirmed live during the V2/V3 parity harness: the full multi-compare
# schema above (investment/decision/evidence/companies/sectors/timeline/
# risks/entity_analyses) reproducibly truncates mid-JSON on the weakest
# fallback model this session's providers keep cascading down to under heavy
# load -- not a routing or entity-resolution bug (ai_search_v3.routed always
# showed all 3 entities correctly resolved and routed), a token-budget
# problem specific to this, the heaviest of the 3 specialists' schemas.
#
# Fix is exactly the shape V2's own generic degraded-fallback pattern uses
# (base.py's degraded_response), scoped to this one specialist rather than
# touched in the shared parser: one bounded retry with a deliberately tiny,
# purpose-built schema when the full schema fails to parse, and if THAT also
# fails, an honest degraded response that still names every company that was
# asked about. What it must never do: silently answer as if only 2 (or 0)
# companies were named when the user asked about 3.
MULTI_COMPARE_COMPACT_MAX_TOKENS = 2200  # ~3 short entity blocks + 4 fields -- deliberately far below the 7000 the full schema gets


def _build_multi_compare_compact_prompt(query: str, display_names: list[str]) -> str:
    """The fallback schema for when the full multi-compare schema has
    already failed to parse once. Keeps the essential capability contract
    (all N symbols, one concise view per company, a comparative conclusion,
    key tradeoffs, confidence) and drops everything else that could plausibly
    be the reason the previous attempt truncated: no timeline, no risk/
    opportunity matrices, no extras, no duplicated summary fields, no
    per-entity sector/catalysts/near_term_outlook."""
    entity_list = ", ".join(display_names)
    rows = ",\n".join(
        f'    "{name}": {{"view": "", "strengths": ["", ""], "risks": ["", ""]}}'
        for name in display_names
    )
    return f"""Compare these {len(display_names)} companies for an investor: {entity_list}.
QUERY: "{query}"

Return ONLY this compact JSON (no fences, no extra keys, no additional fields):
{{
  "entity_analyses": {{
{rows}
  }},
  "comparison_summary": "1-2 sentences: what distinguishes each company on the metric that matters most",
  "best_for": "which of {entity_list} looks strongest right now, and one reason why",
  "key_tradeoffs": ["", ""],
  "confidence": 55
}}

RULES:
- Analyze all {len(display_names)} companies -- never drop one, even briefly.
- This is a RESEARCH platform, not advisory -- never say Buy/Sell/Hold/Accumulate/Reduce.
- Keep every string SHORT -- one sentence per field, not a paragraph."""


def _parse_compact_json(raw: str) -> dict | None:
    """Same fence-stripping/regex-salvage pattern as base.py's
    parse_specialist_json, kept separate rather than reused because the
    compact schema's success condition (needs "entity_analyses") is
    specific to this fallback, not the general specialist contract."""
    import json
    import re

    if not raw:
        return None
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        return json.loads(clean)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                return None
    return None


def _compact_to_flat(query: str, compact: dict, display: list[dict]) -> dict:
    """Maps the compact schema's answer into the same flat internal shape
    every other specialist path produces (base.py's degraded_response is the
    known-good complete shell every downstream consumer -- validate_and_repair,
    _assemble_response -- already handles), overriding only the fields this
    thinner schema actually has real content for. A real, non-degraded answer
    -- the compact retry succeeding is a genuine (if shorter) synthesis, not
    a failure."""
    flat = degraded_response(query)
    entity_analyses_in = compact.get("entity_analyses") or {}
    confidence = compact.get("confidence")
    confidence = int(confidence) if isinstance(confidence, (int, float)) else 55

    summary = compact.get("comparison_summary") or flat["summary"]
    best_for = compact.get("best_for") or ""
    flat["degraded"] = False
    flat["summary"] = summary
    flat["bottom_line"] = f"{summary} {best_for}".strip()
    flat["confidence"] = confidence
    flat["risks"] = [r for r in (compact.get("key_tradeoffs") or []) if r] or flat["risks"]

    flat["companies"] = [
        {
            "symbol": m.get("symbol", ""), "name": m.get("name", ""),
            "impact_type": "neutral", "impact_score": confidence, "confidence": confidence,
            "reason": (entity_analyses_in.get(m.get("name", ""), {}) or {}).get("view", ""),
        }
        for m in display
    ]
    flat["decision_intelligence"] = {
        "intent": "compare_multi", "context_complete": True, "missing_context": [],
        "decision_summary": summary,
        "entity_analyses": [
            {
                "entity": m.get("name", ""), "symbol": m.get("symbol", ""), "sector": "",
                "thesis": (entity_analyses_in.get(m.get("name", ""), {}) or {}).get("view", ""),
                "strengths": (entity_analyses_in.get(m.get("name", ""), {}) or {}).get("strengths") or [],
                "risks": (entity_analyses_in.get(m.get("name", ""), {}) or {}).get("risks") or [],
                "catalysts": [], "near_term_outlook": "neutral", "confidence": confidence,
            }
            for m in display
        ],
    }
    return flat


def _multi_compare_entity_preserving_degraded(query: str, display: list[dict]) -> dict:
    """The last resort, when both the full schema AND the compact retry
    failed to parse. Still not the generic degraded_response() shell as-is
    (that returns companies: [], silently losing every entity) -- this
    variant honestly says synthesis didn't complete, while still naming and
    structurally preserving every company the user actually asked about, so
    a 3-company question can never silently read back as a 2-company (or
    0-company) answer."""
    names = [m.get("name", "") for m in display if m.get("name")]
    entity_list = ", ".join(names) if names else "the companies you asked about"
    flat = degraded_response(query)
    flat["summary"] = (
        f"You asked to compare {entity_list} ({len(display)} companies), but a full comparative "
        "analysis didn't complete under current conditions. Real per-company data is available "
        "below; try again shortly for the full comparison."
    )
    flat["bottom_line"] = flat["summary"]
    flat["_degraded_reason"] = "multi_compare_capacity"
    flat["companies"] = [
        {
            "symbol": m.get("symbol", ""), "name": m.get("name", ""),
            "impact_type": "neutral", "impact_score": None, "confidence": None,
            "reason": "Comparative analysis did not complete for this company under current conditions.",
        }
        for m in display
    ]
    flat["decision_intelligence"] = {
        "intent": "compare_multi", "context_complete": False,
        "missing_context": ["Full comparative analysis did not complete"],
        "decision_summary": flat["summary"],
        "entity_analyses": [
            {
                "entity": m.get("name", ""), "symbol": m.get("symbol", ""), "sector": "",
                "thesis": "Analysis unavailable -- synthesis did not complete under current provider conditions.",
                "strengths": [], "risks": [], "catalysts": [], "near_term_outlook": "neutral", "confidence": None,
            }
            for m in display
        ],
    }
    return flat


async def _run_multi_compare_compact_retry(query: str, entities: dict) -> tuple[dict, bool]:
    from app.services.ai_service import _call_with_fallback

    matches = entities.get("company_matches") or []
    symbols = entities.get("companies") or []
    display = matches[:3] if matches else [{"symbol": s, "name": s} for s in symbols[:3]]
    display_names = [m.get("name") or m.get("symbol", "") for m in display]

    prompt = _build_multi_compare_compact_prompt(query, display_names)
    raw = await _call_with_fallback(prompt, SPECIALIST_SYSTEM, max_tokens=MULTI_COMPARE_COMPACT_MAX_TOKENS, priority="interactive")
    compact = _parse_compact_json(raw)

    if compact and compact.get("entity_analyses"):
        return _compact_to_flat(query, compact, display), False
    return _multi_compare_entity_preserving_degraded(query, display), True


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
    """Single _call_with_fallback call for the normal (pairwise or
    multi-compare) path, plus one bounded compact-schema retry for the
    multi-compare case specifically -- see the Step 2B block above build_prompt()."""
    from app.services.ai_service import _call_with_fallback

    is_multi = len(entities.get("companies") or []) >= 3
    prompt = build_prompt(query, evidence, intent_data, entities)
    raw = await _call_with_fallback(prompt, SPECIALIST_SYSTEM, max_tokens=MAX_TOKENS, priority="interactive")
    parsed, degraded = parse_specialist_json(raw, query)

    if degraded and is_multi:
        parsed, degraded = await _run_multi_compare_compact_retry(query, entities)

    return parsed, degraded

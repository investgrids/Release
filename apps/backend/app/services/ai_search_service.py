"""
AI Search Service — Market Intelligence Research Engine.

Pipeline:
  1. In-process / Redis cache check
  2. Entity extraction (regex + keyword — fast, no AI call)
  3. Parallel DB search (events, news, policies)
  4. AI generation (single structured JSON call)
  5. Live price enrichment (yfinance, best-effort)
  6. Network graph + market chart assembly
  7. Cache store + return
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.event import Event, GovernmentPolicy
from app.db.models_legacy import NewsArticle as NewsModel
from app.services.ai_service import _call_with_fallback
from app.services.ai_search.session_context import resolve_context, check_ambiguous_group, _REFERENTIAL_RE
from app.services.ai_search.timeline_checks import TIMELINE_DIFFERENTIATION_INSTRUCTION as _TIMELINE_DIFFERENTIATION_RULE
from app.services.news_fetcher import get_live_news

# P5 Stage 1 (2026-08-06): the following were relocated out of this file into
# ai_search/ so V3 no longer depends on this module at import time — moved
# as complete closures (each symbol + everything it privately depended on),
# zero behavior change. V2 imports them back here since it still needs all
# of them for its own operation; only their defining file changed.
# P5 Stage 2 (2026-08-07): _run_market_pulse_search also relocated (into
# ai_search/market_pulse.py, alongside the prompt-building it already
# shared with V3) — closes one of V3's two remaining direct imports from
# this file. _unrecognized_company_response stays V2-only (V3 now has its
# own native version, pipeline.py's _unrecognized_company_response_v3).
from app.services.ai_search.cache import _CACHE
from app.services.ai_search.horizon import compute_horizon as _compute_horizon
from app.services.ai_search.market_pulse import _run_market_pulse_search
from app.services.ai_search.decision_intent import (
    _BUDGET_RE, _COMPARE_RE, _COMPARE_RE_3, _COMPARE_RE_AND, _DECISION_INTENTS,
    _HOLDING_RE, _HORIZON_RE, _RISK_RE, _SECTOR_NAMES, _SWITCH_FROM_TO_RE,
    _TARGET_RE, _detect_decision_intent,
)
from app.services.ai_search.enrichment import (
    _classify_ripple_position, _commodity_safety_note, _enrich_sync,
    _fetch_chart_sync, _fetch_valuation_sync, _fetch_vix_sync,
    _intent_overlay, _sector_status, _sector_time_horizon,
)
from app.services.ai_search.entities import (
    _COMPANY_BARE_RE, _COMPANY_SUFFIX_RE, _GENERIC_STOCK_PREFIX,
    _SINGLE_WORD_STOCK_RE, _looks_like_unrecognized_company, _match_companies,
)
from app.services.ai_search.market_pulse import (
    _MARKET_PULSE_RE, _build_market_pulse_prompt, _classify_market_pulse_llm,
    _detect_market_pulse, _detect_market_pulse_async,
)
from app.services.ai_search.regexes import (
    _COMMODITY_NAMES, _COMMODITY_TICKERS, _MACRO_TRIGGER, _OPPORTUNITY_TRIGGER,
    _OUTLOOK_LABELS, _POLICIES, _RESULTS_TRIGGER, _RISK_TRIGGER, _SECTOR_TRIGGER,
    _SECTORS, _STOPWORDS, _THEME_TRIGGER, _VALUATION_TRIGGERS, _VIX_TRIGGER,
)
from app.services.ai_search.retrieval import (
    _HIST_CATEGORY_KEYWORDS, _HIST_SECTOR_NAMES, _event_row_to_dict,
    _infer_historical_category, _infer_historical_sectors, _search_events,
    _search_news, _search_policies, _symbols_to_names, _words,
)
from app.services.ai_search.ripple_graph import _build_ripple_chain

log = structlog.get_logger(__name__)

_TTL = 1800  # 30 min


def _ck(query: str, entities: dict | None = None) -> str:
    """Cache key. P2 fix: when entities is provided, the key incorporates
    the RESOLVED companies/sectors (post session-context merge), not just
    query text — otherwise two sessions asking the identical literal text
    ("What about its main competitor?") but resolving to different prior
    companies would collide on one cache entry and the second session would
    silently get the first session's answer. Keyed on resolved output, not
    raw session_context: two sessions that happen to resolve to the SAME
    entities correctly still share a cache hit (that's the point of
    caching); only genuinely different resolved entities fragment it.
    entities=None (market pulse, and anything not yet entity-aware) keeps
    the original query-only behavior unchanged."""
    base = query.lower().strip()
    if entities:
        sig = "companies=" + ",".join(sorted(entities.get("companies") or []))
        sig += "|sectors=" + ",".join(sorted(entities.get("sectors") or []))
        base = f"{base}::{sig}"
    return hashlib.md5(base.encode()).hexdigest()


def _cget(key: str, ttl: int = _TTL) -> Any | None:
    e = _CACHE.get(key)
    return e[1] if e and time.time() - e[0] < ttl else None


def _cset(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


def resolve_cache_key(query: str, session_context: dict | None = None) -> str:
    """Computes the same entity-aware cache key run_ai_search resolves
    internally — exposed so the route handler's pre-pipeline cache
    pre-checks (in-process AND Redis, in api/ai_search.py) can check/write
    the same cache namespace without duplicating the
    _extract_entities/resolve_context wiring, and without silently reading/
    writing a stale query-text-only key that bypasses the P2 cache-key fix
    entirely (found live: the Redis pre-check had its own independent
    query-only key, computed before run_ai_search ever resolves entities —
    a hit there would return a cached answer without ever re-checking
    session context, the exact collision run_ai_search's own fix closes)."""
    entities = _extract_entities(query)
    entities, _ = resolve_context(query, entities, session_context)
    return _ck(query, entities)


# ── Entity extraction ─────────────────────────────────────────────────────────
# _SECTORS/_POLICIES/_match_companies/_COMPANY_SUFFIX_RE/_COMPANY_BARE_RE/
# _GENERIC_STOCK_PREFIX/_SINGLE_WORD_STOCK_RE/_looks_like_unrecognized_company
# now live in ai_search/entities.py + ai_search/regexes.py (P5 Stage 1),
# imported above.


def _unrecognized_company_response(query: str) -> dict:
    """P5 Stage 1 (2026-08-06): deliberately NOT relocated to ai_search/,
    unlike the other symbols V3 imports from this file — this builds V2's
    full flat SearchResult schema, which is genuinely V2-specific; V3's
    pipeline.py imports this function directly rather than having its own
    equivalent. Flagged for a Stage 2 decision (give V3 its own version in
    its nested schema shape, vs. keep sharing this one) — not a Stage 1
    extraction target since it isn't a clean behavior-neutral relocation.

    Minimal but schema-complete SearchResult.

    P3: this is the "unsupported entity" response the task named (Apple-
    stock case). P5 Stage 2 (2026-08-07): previously set
    synthesis_incomplete=False alongside degraded_reason="unsupported_entity",
    reasoning that "did synthesis fail" and "is this a confident
    classification" were different questions — but the actual decision made
    for the unification (see historical_memory-adjacent P5 Stage 2 task
    file) is that degraded_reason is the single source of truth and
    synthesis_incomplete is purely derived from it (degraded_reason is not
    None), no independently-tracked exceptions. This isn't a full analysis
    either way — fixed to True to match."""
    summary = (
        f"No verified company found matching this query. MarketRipple only analyzes "
        f"companies in its tracked NSE universe, and nothing in “{query}” matched a "
        f"real, listed entity — double-check the spelling/ticker, or it may not be "
        f"publicly listed on the NSE."
    )
    return {
        "query": query, "synthesis_incomplete": True, "degraded_reason": "unsupported_entity",
        "answer": {
            "summary": summary, "bottom_line": summary,
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "what_priced_in": "",
            "risks": [], "opportunities": [],
            "confidence": None, "confidence_level": "unscored",
            "sentiment": "neutral", "sources_count": 0,
        },
        "key_drivers": [], "insights": [], "companies": [], "sectors": [],
        "related_events": [], "news": [], "policies": [], "timeline": [],
        "historical_comparison": [], "ripple_chain": [], "scenarios": {},
        "market_impact_horizons": [], "what_to_monitor": [],
        "ai_reasoning_methods": [], "follow_up_questions": [
            "Which real companies are in this sector?",
            "Show me the correct ticker for this company",
        ],
        "investment_verdict": {
            "rating": "Not Applicable", "direction": "neutral", "confidence": None,
            "horizon": "", "top_picks": [], "risks": [], "catalysts": [],
            "opportunity_score": None, "risk_level": "", "suitable_for": "",
        },
        "market_chart": {"labels": [], "series": []},
        "graph": {"nodes": [], "edges": []},
        "citations": [], "decision_intelligence": None,
        "confidence_data": {"level": "unscored", "score": None, "reasons": [], "breakdown": {}, "caveats": []},
    }


def _referential_no_context_response(query: str) -> dict:
    """Schema-complete SearchResult for a referential query ("What about
    its main competitor?") that resolved to nothing — no companies/sectors
    of its own, and no prior session context to merge in either. P2: this
    is what used to silently reach the LLM with empty entities (or, before
    the "it"/IT-sector fix, a confidently wrong sector match) — now an
    honest admission instead. synthesis_incomplete=True (unlike
    _unrecognized_company_response's False) because this genuinely isn't a
    complete analysis, it's missing information, not a confident
    classification."""
    summary = (
        "This looks like a follow-up question, but there's no prior company or sector "
        "in this session to resolve it against. Try naming the company or sector directly, "
        "or ask this right after discussing one."
    )
    return {
        "query": query, "synthesis_incomplete": True,
        # P4: closes the one gap the P3 labeling pass left — this was the
        # only one of the honest-degradation responses shipping with no
        # degraded_reason at all (not even None-as-a-value; the key was
        # simply absent), indistinguishable from a normal response by this
        # field alone.
        "degraded_reason": "referential_no_context",
        "answer": {
            "summary": summary, "bottom_line": summary,
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "what_priced_in": "",
            "risks": [], "opportunities": [],
            "confidence": None, "confidence_level": "unscored",
            "sentiment": "neutral", "sources_count": 0,
        },
        "key_drivers": [], "insights": [], "companies": [], "sectors": [],
        "related_events": [], "news": [], "policies": [], "timeline": [],
        "historical_comparison": [], "ripple_chain": [], "scenarios": {},
        "market_impact_horizons": [], "what_to_monitor": [],
        "ai_reasoning_methods": [], "follow_up_questions": [
            "Name the company or sector you're asking about",
        ],
        "investment_verdict": {
            "rating": "Not Applicable", "direction": "neutral", "confidence": None,
            "horizon": "", "top_picks": [], "risks": [], "catalysts": [],
            "opportunity_score": None, "risk_level": "", "suitable_for": "",
        },
        "market_chart": {"labels": [], "series": []},
        "graph": {"nodes": [], "edges": []},
        "citations": [], "decision_intelligence": None,
        "confidence_data": {"level": "unscored", "score": None, "reasons": [], "breakdown": {}, "caveats": []},
    }


def _ambiguous_entity_response(query: str, ambiguous: dict) -> dict:
    """Schema-complete SearchResult for a bare conglomerate name ("What is
    the investment case for Tata?") that names a real family but not a
    specific member — P3. `ambiguous` is check_ambiguous_group()'s return
    shape: {"term": str, "candidates": [{"symbol","name"}]}.

    P5 Stage 2 (2026-08-07): previously set synthesis_incomplete=False
    ("confident classification, not a failure" — P3's original framing)
    while still carrying a real degraded_reason. The unification decision
    made degraded_reason the single source of truth with
    synthesis_incomplete purely derived from it — fixed to True (this
    genuinely isn't a full analysis, regardless of how confidently it was
    classified as ambiguous)."""
    names = ", ".join(f'{c["name"]} ({c["symbol"]})' for c in ambiguous["candidates"])
    summary = (
        f'"{ambiguous["term"]}" names a group with multiple listed companies, not one '
        f"specific stock — MarketRipple can't tell which you mean. Did you mean one of: "
        f"{names}?"
    )
    return {
        "query": query, "synthesis_incomplete": True, "degraded_reason": "ambiguous_entity",
        "answer": {
            "summary": summary, "bottom_line": summary,
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "what_priced_in": "",
            "risks": [], "opportunities": [],
            "confidence": None, "confidence_level": "unscored",
            "sentiment": "neutral", "sources_count": 0,
        },
        "key_drivers": [], "insights": [], "companies": [], "sectors": [],
        "related_events": [], "news": [], "policies": [], "timeline": [],
        "historical_comparison": [], "ripple_chain": [], "scenarios": {},
        "market_impact_horizons": [], "what_to_monitor": [],
        "ai_reasoning_methods": [], "follow_up_questions": [
            f"Tell me about {c['name']} ({c['symbol']})" for c in ambiguous["candidates"][:4]
        ],
        "investment_verdict": {
            "rating": "Not Applicable", "direction": "neutral", "confidence": None,
            "horizon": "", "top_picks": [], "risks": [], "catalysts": [],
            "opportunity_score": None, "risk_level": "", "suitable_for": "",
        },
        "market_chart": {"labels": [], "series": []},
        "graph": {"nodes": [], "edges": []},
        "citations": [], "decision_intelligence": None,
        "confidence_data": {"level": "unscored", "score": None, "reasons": [], "breakdown": {}, "caveats": []},
        # P3: not part of the schema every other response type uses —
        # frontend-specific addition so the clarification UI can render
        # real pickable candidates without re-deriving them from
        # follow_up_questions text.
        "ambiguous_candidates": ambiguous["candidates"],
    }


# P2 fix: bare substring `in` checks let a short sector/policy token match
# inside an unrelated longer word — the exact bug that made "it" (from
# "IT sector") match inside "its" ("What about its main competitor?"),
# producing a confidently wrong sector match with no degradation signal.
# "pli" (Production Linked Incentive) has the identical profile — it's a
# substring of "compliance" ("SEBI compliance requirements" would
# spuriously register a PLI policy match). Only these two get word-boundary
# anchoring: everything else in _SECTORS/_POLICIES is either a multi-word
# phrase or long/distinctive enough that a real collision hasn't been found
# (and \b-anchoring every entry risks breaking legitimate substring
# matches this codebase has no evidence about either way — e.g. "auto"
# inside "automobile", "telecom" inside "telecommunications" — left alone,
# out of scope for this fix).
_SHORT_TOKEN_RE = {
    "it": re.compile(r"\bit\b"),
    "pli": re.compile(r"\bpli\b"),
}


def _term_in_query(term: str, q: str) -> bool:
    pat = _SHORT_TOKEN_RE.get(term)
    return bool(pat.search(q)) if pat else term in q


def _extract_entities(query: str) -> dict:
    q = query.lower()
    return {
        "companies": _match_companies(q),
        "sectors":   [s for s in _SECTORS  if _term_in_query(s, q)],
        "policies":  [p for p in _POLICIES if _term_in_query(p, q)],
    }


# ── Market Pulse intent — real-data-first, never LLM-ranked ──────────────────
# _MARKET_PULSE_RE/_detect_market_pulse/_MARKET_PULSE_CLASSIFY_SYSTEM/
# _classify_market_pulse_llm/_detect_market_pulse_async now live in
# ai_search/market_pulse.py (P5 Stage 1), imported above.


# ── DB search helpers ─────────────────────────────────────────────────────────
# _STOPWORDS/_words/_event_row_to_dict/_search_events/_symbols_to_names/
# _search_news/_search_policies now live in ai_search/retrieval.py +
# ai_search/regexes.py (P5 Stage 1), imported above.


# ── Intent detection ──────────────────────────────────────────────────────────
# _DECISION_INTENTS/_HOLDING_RE/_TARGET_RE/_HORIZON_RE/_RISK_RE/_COMPARE_RE/
# _COMPARE_RE_AND/_SWITCH_FROM_TO_RE/_COMPARE_RE_3/_BUDGET_RE/_SECTOR_NAMES/
# _detect_decision_intent now live in ai_search/decision_intent.py.
# _COMMODITY_NAMES/_COMMODITY_TICKERS/_VALUATION_TRIGGERS/_VIX_TRIGGER/
# _SECTOR_TRIGGER/_OPPORTUNITY_TRIGGER/_THEME_TRIGGER/_RISK_TRIGGER/
# _MACRO_TRIGGER/_RESULTS_TRIGGER now live in ai_search/regexes.py.
# _commodity_safety_note now lives in ai_search/enrichment.py.
# (P5 Stage 1, all imported above.)


# ── Research outlook enum (replaces Buy/Sell/Hold advisory language) ──────────
# This is a research platform, not an advisory platform — no recommendation
# language is allowed to reach the response. Enforced twice: the prompt asks
# for one of these exact 8 labels, and _normalize_outlook() below forcibly
# remaps whatever the AI actually returns, so a model ignoring instructions
# (or an older cached response) can never leak "Buy"/"Sell"/"Hold" to the UI.
# _OUTLOOK_LABELS itself now lives in ai_search/regexes.py (imported above)
# — shared with V3's specialists/validation.py, which is why it moved.
_OUTLOOK_LABELS_LOWER = {lbl.lower(): lbl for lbl in _OUTLOOK_LABELS}
_ADVISORY_LANGUAGE_MAP = {
    "strong buy": "Strongly Constructive", "buy": "Constructive", "accumulate": "Constructive",
    "outperform": "Positive Outlook", "add": "Positive Outlook",
    "hold": "Neutral", "market perform": "Neutral",
    "reduce": "Cautious", "underperform": "Cautious", "trim": "Cautious",
    "sell": "Elevated Risk", "underweight": "Elevated Risk",
    "strong sell": "High Uncertainty", "avoid": "High Uncertainty",
}


def _normalize_outlook(rating: str, direction: str, confidence: float, opportunity_score: float) -> str:
    """Coerce any rating string into one of the 8 allowed research-outlook labels."""
    r = (rating or "").strip().lower()
    if r in _OUTLOOK_LABELS_LOWER:
        return _OUTLOOK_LABELS_LOWER[r]
    for phrase, mapped in _ADVISORY_LANGUAGE_MAP.items():
        if phrase in r:
            return mapped
    # No usable rating string at all — derive purely from the numeric signals.
    d = (direction or "neutral").lower()
    conf = confidence or 0
    opp = opportunity_score or 0
    if d == "bullish":
        if opp >= 85 and conf >= 80:
            return "Strongly Constructive"
        if opp >= 70:
            return "Constructive"
        return "Positive Outlook"
    if d == "bearish":
        if opp <= 30 or conf < 40:
            return "High Uncertainty"
        return "Elevated Risk"
    if conf < 50:
        return "Cautious"
    return "Selectively Constructive" if opp >= 55 else "Neutral"


def _suitable_for(horizon: str, risk_level: str) -> str:
    h = (horizon or "").lower()
    r = (risk_level or "").lower()
    long_term = any(k in h for k in ("12", "18", "24", "2 year", "3 year", "long"))
    short_term = any(k in h for k in ("day", "week", "1 month", "intraday", "short"))
    if "high" in r or "aggressive" in r:
        return "Active Traders" if short_term else "Growth-Oriented Investors"
    if short_term:
        return "Tactical / Short-Term Investors"
    if long_term:
        return "Long-term Investors"
    return "Balanced / Medium-Term Investors"


# _sector_status/_sector_time_horizon/_classify_ripple_position now live in
# ai_search/enrichment.py. _HIST_CATEGORY_KEYWORDS/_HIST_SECTOR_NAMES/
# _infer_historical_category/_infer_historical_sectors now live in
# ai_search/retrieval.py. (P5 Stage 1, all imported above.)


def _cap_words(text: str, limit: int = 120) -> str:
    """Hard safety net behind the prompt's own word-limit instruction — the
    model doesn't always obey it, and an Executive Summary is worthless if
    it silently balloons into a wall of text."""
    words = (text or "").split()
    if len(words) <= limit:
        return text or ""
    return " ".join(words[:limit]).rstrip(",.;:") + "…"


def _key_difference(hist_query: dict, h: dict) -> str:
    """
    Deterministic, factual diff between the current query's inferred context
    and a matched historical event — never AI-invented, so it can't overstate
    how similar the two situations actually are.
    """
    parts: list[str] = []
    q_cat, h_cat = hist_query.get("category"), h.get("category")
    if q_cat and h_cat:
        parts.append("same category" if q_cat == h_cat else f"category differs ({h_cat} vs current {q_cat})")

    q_sec, h_sec = set(hist_query.get("sectors") or []), set(h.get("sectors") or [])
    if q_sec and h_sec:
        overlap, only_hist = q_sec & h_sec, h_sec - q_sec
        if overlap and only_hist:
            parts.append(f"shares {', '.join(sorted(overlap))} but this event also touched {', '.join(sorted(only_hist))}")
        elif overlap:
            parts.append(f"same sector focus ({', '.join(sorted(overlap))})")
        else:
            parts.append(f"different sectors ({', '.join(sorted(h_sec))} vs current {', '.join(sorted(q_sec))})")

    if not parts:
        return "Limited structured overlap — treat as a loose historical reference only."
    return ("; ".join(parts) + ".")[0].upper() + ("; ".join(parts) + ".")[1:]


def _build_market_horizons(ai: dict, confidence: float, sentiment: str) -> list[dict]:
    """
    Deterministic Immediate/Next Quarter/Long Term confidence bars, replacing
    the old meaningless price-line chart. Confidence naturally decays further
    out — near-term reaction is more predictable than a 6-12 month outcome —
    and each bar reuses the AI's own impact narrative rather than fabricating
    a new one, so it stays grounded in what was actually said.
    """
    direction = "positive" if sentiment == "positive" else ("negative" if sentiment == "negative" else "neutral")
    base = max(0.0, min(100.0, confidence or 0))
    return [
        {
            "horizon": "Immediate", "window": "1-2 weeks",
            "confidence": round(min(95, base + 10)), "direction": direction,
            "description": ai.get("immediate_impact") or "Short-term price action likely to reflect the news within days.",
        },
        {
            "horizon": "Next Quarter", "window": "1-3 months",
            "confidence": round(base), "direction": direction,
            "description": ai.get("medium_term") or "Medium-term fundamentals will determine whether the initial move sustains.",
        },
        {
            "horizon": "Long Term", "window": "6-12 months",
            "confidence": round(max(15, base - 20)), "direction": direction,
            "description": ai.get("long_term") or "Longer-term outcome depends on execution and macro conditions beyond current visibility.",
        },
    ]


def _build_reasoning_methods(
    events: list, similar: list, extra_context_lines: list[str],
    mie_state: dict, ripple_chain: list, companies: list,
    news: list | None = None, policies: list | None = None,
) -> list[dict]:
    """
    Deterministic — reports which data sources ACTUALLY contributed to this
    specific answer, not a hardcoded marketing list. `used: False` entries
    stay visible so the transparency panel is honest about gaps, not just a
    checklist of things that sound good.
    """
    valuation_used = any("P/E" in l or "P/B" in l for l in extra_context_lines)
    return [
        {"label": "News",                  "used": bool(news) or bool(events)},
        {"label": "Policies",              "used": bool(policies)},
        {"label": "Historical Events",     "used": bool(similar)},
        {"label": "Financial Statements",  "used": bool(companies)},
        {"label": "Valuation",             "used": valuation_used},
        {"label": "Intelligence Graph",    "used": bool(ripple_chain)},
        {"label": "Ripple Engine",         "used": bool(ripple_chain)},
        {"label": "Company Relationships", "used": len(companies) >= 2},
    ]


def _confidence_caveats(conf_result: Any, events: list, similar: list, source_count: int) -> list[str]:
    """What would raise or lower trust in this specific answer — derived from
    the same signals `confidence_service` already scored, not a separate
    guess."""
    caveats: list[str] = []
    if not events:
        caveats.append("No matching events found in the database for this query")
    if not similar:
        caveats.append("No closely matching historical precedent found")
    if source_count < 3:
        caveats.append("Limited data coverage — fewer than 3 corroborating sources")
    if conf_result is not None:
        breakdown = conf_result.breakdown or {}
        if breakdown.get("market_confirmation", 0) < 5:
            caveats.append("Live market signals not yet confirming this thesis")
        if breakdown.get("historical", 0) < 5:
            caveats.append("Weak historical match for this scenario")
    return caveats


# ── AI prompt ─────────────────────────────────────────────────────────────────
_SYSTEM = (
    "You are a senior Indian equity market analyst at an institutional fund. "
    "Generate structured market intelligence for professional investors. "
    "Respond with valid JSON only. No markdown fences. No commentary."
)


def _system_with_date() -> str:
    """P4 temporal-context fix: _SYSTEM is a module-level constant, computed
    once at import time — the server process can run for days between
    deploys, so a date baked directly into it would go stale for the whole
    process lifetime. Computed fresh on every call instead; see
    date_context.py's docstring for the confirmed real hallucination this
    traces back to (a report referencing "FY25E" as current ~17 months
    after it had already ended, because no prompt anywhere stated today's
    real date)."""
    from app.services.ai_search.date_context import current_date_context
    return f"{_SYSTEM}\n\n{current_date_context()}"


# _fmt_drivers/_build_market_pulse_prompt now live in ai_search/market_pulse.py
# (P5 Stage 1, imported above).


def _build_decision_prompt(
    query: str,
    intent_data: dict,
    events: list,
    news: list,
    policies: list,
    extra_context: str = "",
) -> str:
    holding = intent_data.get("holding") or "Asset A"
    target  = intent_data.get("target")  or "Asset B"
    horizon = intent_data.get("horizon") or "medium-term"
    risk    = intent_data.get("risk")    or "moderate"
    intent  = intent_data.get("intent",  "decision")

    holding_is_commodity = intent_data.get("holding_is_commodity", False)
    target_is_commodity  = intent_data.get("target_is_commodity",  False)
    holding_is_sector    = intent_data.get("holding_is_sector",    False)
    target_is_sector     = intent_data.get("target_is_sector",     False)

    # Determine entity label and symbol instructions per entity type
    def entity_label(name: str, is_commodity: bool, is_sector: bool) -> str:
        if is_commodity: return f"{name} (commodity/asset class)"
        if is_sector:    return f"{name} (market sector)"
        return name

    def symbol_hint(name: str, is_commodity: bool, is_sector: bool) -> str:
        if is_commodity:
            tick = _COMMODITY_TICKERS.get(name.lower(), "null")
            return f'Set "symbol" to "{tick}" (ETF proxy) or null. Do NOT use equity tickers.'
        if is_sector:
            return f'Set "symbol" to null. This is a sector, not a single stock.'
        return f'Set "symbol" to the real NSE ticker (e.g. TATAMOTORS, RELIANCE, HDFCBANK).'

    a_label = entity_label(holding, holding_is_commodity, holding_is_sector)
    b_label = entity_label(target,  target_is_commodity,  target_is_sector)

    evs = "\n".join(f"- {e['title']}" for e in events[:4]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in news[:4]) or "None"

    # Comparison dimensions differ for commodity vs equity queries
    if holding_is_commodity or target_is_commodity:
        comp_dims = [
            "Inflation Hedge", "Liquidity", "Volatility", "Store of Value",
            "Growth Potential", "Correlation to Equity"
        ]
    elif holding_is_sector or target_is_sector:
        comp_dims = [
            "Sector Outlook", "Policy Tailwinds", "Valuation", "Earnings Growth",
            "Risk Profile", "FII Interest"
        ]
    else:
        comp_dims = [
            "Business Model", "Sector Outlook", "Growth Drivers",
            "Risk Profile", "Market Position", "Valuation"
        ]
    comp_rows = "\n".join(
        f'      {{"dimension": "{d}", "holding": "", "target": "", "advantage": "neutral"}},'
        for d in comp_dims
    ).rstrip(",")

    ctx_block = f"\nCONTEXT:\n{extra_context}\n" if extra_context else ""
    return f"""You are a senior Indian market analyst. Analyse this investor query and return a single JSON object.
{ctx_block}
QUERY: "{query}"
ENTITY A (holding/first): {a_label}
ENTITY B (target/second): {b_label}
HORIZON: {horizon} | RISK TOLERANCE: {risk}
MARKET NEWS: {nws}
RELATED EVENTS: {evs}

INSTRUCTIONS:
- Fill every string field with real, specific analysis about {holding} and {target}.
- All strings must be your original analytical content — never copy field descriptions.
- This is a RESEARCH platform, not an advisory one. Never say Buy/Sell/Hold/Strong Buy/Strong Sell/Accumulate/Reduce anywhere. Explain trade-offs only. No direct financial advice.
- "investment_verdict.rating" MUST be exactly one of these 8 values, nothing else: {", ".join(f'"{l}"' for l in _OUTLOOK_LABELS)}.
- Entity A symbol hint: {symbol_hint(holding, holding_is_commodity, holding_is_sector)}
- Entity B symbol hint: {symbol_hint(target, target_is_commodity, target_is_sector)}
- Use the entity name exactly as given in "entity" field (e.g. "{holding}", "{target}").
- "advantage" in comparison rows must be "holding", "target", or "neutral".
- "near_term_outlook" must be "positive", "cautious", "neutral", or "negative".
- "sentiment" must be "bullish", "bearish", or "neutral".
- "key_drivers[].icon" must be ONE lowercase keyword from: procurement, policy, manufacturing, export, valuation, risk, demand, technology, capex, regulation, earnings, supply-chain, currency, commodity, credit.
- {_TIMELINE_DIFFERENTIATION_RULE}
- Every company named in "summary"/"bottom_line" must also appear in the "companies" list, and vice versa.
- Return valid JSON only. No markdown. No commentary outside the JSON.

JSON to fill and return:
{{
  "summary": "",
  "bottom_line": "MAX 120 WORDS. ONE paragraph answering ONLY this exact question directly — name the specific trade-off between {holding} and {target}, who comes out ahead on the metric that actually matters here, and the one factor most likely to change that. No generic filler.",
  "what_happened": "",
  "why_it_happened": "",
  "immediate_impact": "",
  "medium_term": "",
  "long_term": "",
  "what_priced_in": "1-2 sentences: how much of this trade-off is already reflected in current prices/positioning for {holding} and {target}?",
  "risks": ["", "", ""],
  "opportunities": ["", "", ""],
  "key_drivers": [
    {{"icon": "valuation", "title": "2-4 word driver name", "explanation": "1 sentence mechanism behind this trade-off", "confidence": 85}},
    {{"icon": "risk", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 76}}
  ],
  "confidence": 70,
  "confidence_self_rating": 7,
  "sentiment": "neutral",
  "companies": [
    {{"symbol": "", "name": "{holding}", "impact_type": "neutral", "impact_score": 70, "confidence": 68, "reason": ""}},
    {{"symbol": "", "name": "{target}",  "impact_type": "neutral", "impact_score": 70, "confidence": 68, "reason": ""}}
  ],
  "sectors": [
    {{"name": "", "score": 65, "confidence": 62, "outlook": "Moderate", "positive": true, "explanation": "1 sentence on why this sector is exposed and to what degree"}},
    {{"name": "", "score": 70, "confidence": 65, "outlook": "Moderate", "positive": true, "explanation": "1 sentence"}}
  ],
  "investment_verdict": {{
    "rating": "Selectively Constructive",
    "direction": "neutral",
    "confidence": 68,
    "horizon": "{horizon}",
    "top_picks": [],
    "risks": ["", ""],
    "catalysts": ["", ""],
    "opportunity_score": 65
  }},
  "follow_up_questions": [
    "What is your investment horizon for this decision?",
    "What is your risk tolerance - conservative, moderate, or aggressive?",
    "Are you seeking capital appreciation or dividend income?",
    "Have you considered the tax implications of switching?"
  ],
  "timeline": [
    {{"date": "Near-term", "title": "", "description": ""}},
    {{"date": "3-6 months", "title": "", "description": ""}},
    {{"date": "12 months", "title": "", "description": ""}}
  ],
  "decision_intelligence": {{
    "intent": "{intent}",
    "context_complete": true,
    "missing_context": [],
    "decision_summary": "",
    "holding_analysis": {{
      "entity": "{holding}",
      "symbol": "",
      "sector": "",
      "thesis": "",
      "strengths": ["", "", ""],
      "risks": ["", "", ""],
      "catalysts": ["", ""],
      "near_term_outlook": "neutral",
      "confidence": 65
    }},
    "target_analysis": {{
      "entity": "{target}",
      "symbol": "",
      "sector": "",
      "thesis": "",
      "strengths": ["", "", ""],
      "risks": ["", "", ""],
      "catalysts": ["", ""],
      "near_term_outlook": "neutral",
      "confidence": 65
    }},
    "comparison": [
{comp_rows}
    ],
    "tradeoff": {{
      "reasons_to_switch": ["", "", ""],
      "reasons_to_hold":   ["", "", ""],
      "risks_of_switching": ["", ""],
      "risks_of_holding":   ["", ""],
      "when_to_wait": ""
    }},
    "decision_framework": {{
      "supports_switch": ["", "", ""],
      "argues_against":  ["", ""],
      "key_unknowns":    ["", ""],
      "ai_stance": ""
    }}
  }}
}}"""


def _build_multi_compare_prompt(
    query: str,
    intent_data: dict,
    entities: dict,
    events: list,
    news: list,
    policies: list,
    extra_context: str = "",
) -> str:
    """P3: 3+ named companies ("Compare TCS, Infosys, and Wipro") — minimum
    bar per spec, not full N-way parity with _build_decision_prompt.
    Parallel per-entity analyses (same shape as holding_analysis/
    target_analysis: entity/symbol/sector/thesis/strengths/risks/
    catalysts/near_term_outlook/confidence, looped over N), explicitly
    NOT the pairwise comparison[]/tradeoff{}/decision_framework{} blocks —
    those require a genuine two-way dimension analysis this doesn't
    attempt for 3+. Honestly labeled in the prompt itself so the model
    doesn't invent pairwise framing on its own."""
    symbols = entities.get("companies") or []
    names = _symbols_to_names(symbols)
    display_names = names if names else symbols
    entity_list = ", ".join(display_names)

    evs = "\n".join(f"- {e['title']}" for e in events[:4]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in news[:4]) or "None"
    ctx_block = f"\nCONTEXT:\n{extra_context}\n" if extra_context else ""

    analysis_template = ",\n".join(
        f'''    {{"entity": "{name}", "symbol": "", "sector": "", "thesis": "",
      "strengths": ["", ""], "risks": ["", ""], "catalysts": [""],
      "near_term_outlook": "neutral", "confidence": 65}}'''
        for name in display_names
    )

    companies_template = ",\n".join(
        f'    {{"symbol": "", "name": "{name}", "impact_type": "neutral", "impact_score": 65, "confidence": 60, "reason": ""}}'
        for name in display_names
    )

    return f"""You are a senior Indian market analyst. The user asked to compare {len(display_names)} companies: {entity_list}.
{ctx_block}
QUERY: "{query}"
COMPANIES TO ANALYZE (all {len(display_names)}, not just one or two): {entity_list}
MARKET NEWS: {nws}
RELATED EVENTS: {evs}

INSTRUCTIONS:
- This is a MULTI-ENTITY comparison ({len(display_names)} companies), not a two-way one. Provide a parallel
  analysis of EACH company — do not silently drop any of them or only discuss two.
- Do NOT invent pairwise head-to-head framing (no "X beats Y") — a genuine dimension-by-dimension
  comparison across {len(display_names)} entities isn't what this response computes; parallel individual
  analyses are.
- This is a RESEARCH platform, not an advisory one. Never say Buy/Sell/Hold/Strong Buy/Strong
  Sell/Accumulate/Reduce anywhere. Explain trade-offs only. No direct financial advice.
- "investment_verdict.rating" MUST be exactly one of these 8 values, nothing else: {", ".join(f'"{l}"' for l in _OUTLOOK_LABELS)}.
- Use the real NSE ticker for each company's "symbol" field.
- Return valid JSON only. No markdown. No commentary outside the JSON.

JSON to fill and return:
{{
  "summary": "2-3 sentences covering all {len(display_names)} companies named",
  "bottom_line": "MAX 120 WORDS. Honestly frame this as a {len(display_names)}-way comparison — what
    distinguishes each company from the others on the metric that matters most for this query.",
  "what_priced_in": "",
  "risks": ["", "", ""],
  "opportunities": ["", "", ""],
  "confidence": 60,
  "confidence_self_rating": 6,
  "sentiment": "neutral",
  "companies": [
{companies_template}
  ],
  "investment_verdict": {{
    "rating": "Selectively Constructive",
    "direction": "neutral",
    "confidence": 60,
    "horizon": "medium-term",
    "top_picks": [],
    "risks": ["", ""],
    "catalysts": ["", ""],
    "opportunity_score": 60
  }},
  "decision_intelligence": {{
    "intent": "compare_multi",
    "context_complete": true,
    "missing_context": [],
    "decision_summary": "",
    "entity_analyses": [
{analysis_template}
    ]
  }}
}}"""


def _build_prompt(
    query: str,
    events: list,
    news: list,
    policies: list,
    intent_data: dict | None = None,
    extra_context: str = "",
) -> str:
    evs  = "\n".join(f"- [{e['category']}] {e['title']} (score:{e['impact_score']:.0f})" for e in events[:5]) or "None"
    nws  = "\n".join(f"- {a['headline']}" for a in news[:5]) or "None"
    pols = "\n".join(f"- {p['title']} [{p['ministry']}]" for p in policies[:3]) or "None"

    return f"""Query: "{query}"

DB Events: {evs}
News: {nws}
Policies: {pols}

Return ONLY this JSON (no fences, no extra keys):
{{
  "summary": "2-3 sentence executive summary specific to the query",
  "bottom_line": "MAX 120 WORDS. ONE paragraph that answers ONLY this exact question, directly and specifically. No generic filler, no restating the question, no boilerplate market commentary. Name the specific mechanism (e.g. what actually drives the outcome), who benefits most and why, and the one factor that most determines whether that plays out.",
  "what_happened": "1 factual sentence about what actually happened",
  "why_it_happened": "1 contextual sentence explaining the cause",
  "immediate_impact": "1 sentence on near-term market effect",
  "medium_term": "1 sentence on 3-12 month outlook",
  "long_term": "1 sentence on structural implications",
  "what_priced_in": "1-2 sentences: has the market already priced this in? Reference recent sector/stock performance if you have context for it, and state plainly whether future returns now depend more on new catalysts or on execution of what's already known.",
  "risks": ["specific risk 1", "specific risk 2", "specific risk 3"],
  "opportunities": ["specific opportunity 1", "specific opportunity 2", "specific opportunity 3"],
  "key_drivers": [
    {{"icon": "procurement", "title": "2-4 word driver name", "explanation": "1 sentence on the actual mechanism, not a restatement of the title", "confidence": 92}},
    {{"icon": "policy", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 87}},
    {{"icon": "export", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 74}}
  ],
  "confidence": 78,
  "confidence_self_rating": 7,
  "sentiment": "bullish",
  "companies": [
    {{"symbol": "SYMBOL1", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 90, "confidence": 85, "reason": "specific 1-line reason tied to the query — this is shown to the user as literally why the company matters here"}},
    {{"symbol": "SYMBOL2", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 85, "confidence": 80, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL3", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 78, "confidence": 74, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL4", "name": "Full Company Name", "impact_type": "neutral",     "impact_score": 65, "confidence": 60, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL5", "name": "Full Company Name", "impact_type": "at_risk",     "impact_score": 45, "confidence": 55, "reason": "specific 1-line reason"}}
  ],
  "sectors": [
    {{"name": "Most Relevant Sector", "score": 90, "confidence": 85, "outlook": "Strong Growth", "positive": true, "explanation": "1 sentence on the mechanism connecting this sector to the query"}},
    {{"name": "Second Sector",        "score": 82, "confidence": 78, "outlook": "Positive",      "positive": true, "explanation": "1 sentence"}},
    {{"name": "Third Sector",         "score": 70, "confidence": 65, "outlook": "Moderate",      "positive": true, "explanation": "1 sentence"}},
    {{"name": "Fourth Sector",        "score": 60, "confidence": 58, "outlook": "Neutral",       "positive": true, "explanation": "1 sentence"}},
    {{"name": "Affected Sector",      "score": 45, "confidence": 50, "outlook": "Cautious",      "positive": false, "explanation": "1 sentence"}}
  ],
  "investment_verdict": {{
    "rating": "Constructive",
    "direction": "bullish",
    "confidence": 78,
    "horizon": "12-18 months",
    "top_picks": ["SYMBOL1", "SYMBOL2", "SYMBOL3"],
    "risks": ["Specific risk 1", "Specific risk 2", "Specific risk 3"],
    "catalysts": ["Specific catalyst 1", "Specific catalyst 2", "Specific catalyst 3"],
    "opportunity_score": 85
  }},
  "follow_up_questions": [
    "Specific follow-up question relevant to this query?",
    "Another specific follow-up question?",
    "Third specific follow-up question?",
    "Fourth specific follow-up question?"
  ],
  "timeline": [
    {{"date": "Near-term date", "title": "First milestone title", "description": "What happens at this stage"}},
    {{"date": "Mid-term date",  "title": "Second milestone",      "description": "What happens next"}},
    {{"date": "Later date",     "title": "Third milestone",       "description": "What happens after"}},
    {{"date": "Long-term date", "title": "Final milestone",       "description": "Long-term outcome"}}
  ]
}}

CRITICAL RULES:
- "investment_verdict.rating" MUST be exactly one of these 8 values, nothing else: {", ".join(f'"{l}"' for l in _OUTLOOK_LABELS)}. This is a RESEARCH platform, not an advisory one — never say Buy, Sell, Hold, Strong Buy, Strong Sell, Accumulate, or Reduce anywhere in any field.
- "companies" must ONLY include companies with a direct, specific, mechanistic connection to this exact query. Do not pad the list with generic large-caps (e.g. HUL, Reliance, Tata Motors) unless the query is genuinely and specifically about them. Every entry must be a listed, tradeable equity with a real NSE symbol — never a government body, ministry, PSU research arm, or other unlisted entity (e.g. DRDO is not investable; if relevant, name the listed contractors it drives orders to instead).
- "key_drivers[].icon" must be ONE lowercase keyword from: procurement, policy, manufacturing, export, valuation, risk, demand, technology, capex, regulation, earnings, supply-chain, currency, commodity, credit.
- The "insights" titles must be SPECIFIC to the query "{query}" — choose angles that make sense for this exact topic. Use real NSE symbols, actual rupee amounts, and genuine Indian market context throughout.
- {_TIMELINE_DIFFERENTIATION_RULE}
- The first "timeline" entry (nearest-term) must not contradict "investment_verdict.direction" in tone — a bullish call needs a bullish-or-neutral near-term entry, not a negative one.
- Every company named in "summary"/"bottom_line" must also appear in the "companies" list, and vice versa — don't discuss a company in prose that isn't in the structured list, or list one you never mention.{_commodity_safety_note(query)}{_intent_overlay(intent_data, extra_context)}"""


# _intent_overlay now lives in ai_search/enrichment.py (P5 Stage 1, imported above).


# ── Insight card generation (separate focused call) ───────────────────────────
async def _generate_insights(query: str, summary: str) -> list[dict]:
    """
    Dedicated call for 4 insight cards so the model isn't distracted by
    the large main JSON template. Returns a list of {icon, title, summary}.
    """
    prompt = (
        f'Market query: "{query}"\n'
        f"Context: {summary[:300]}\n\n"
        "Return a JSON array of exactly 4 insight cards for this specific query.\n"
        "Each card: {\"icon\": <single emoji>, \"title\": <4-6 words>, \"summary\": <1 short sentence, max 20 words>}\n\n"
        "The title must be a unique analytical angle relevant to THIS exact query.\n"
        "Example — for 'Infosys Q4 miss': [\"Revenue Guidance Shock\", \"Deal Win Momentum\", \"Margin Pressure Analysis\", \"Peer Valuation Reset\"]\n"
        "Example — for 'RBI rate cut': [\"Rate Transmission Speed\", \"NIM Expansion Outlook\", \"Credit Demand Catalyst\", \"Bond Market Rally\"]\n"
        "Example — for 'Defence CAPEX hike': [\"Order Book Surge\", \"Make-in-India Push\", \"Export Market Entry\", \"R&D Investment Cycle\"]\n\n"
        "Return ONLY the JSON array, no other text."
    )
    raw = await _call_with_fallback(prompt, max_tokens=1000, priority="interactive")
    if not raw:
        return []
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            return parsed[:4]
        # Model returned {"insights": [...]} or similar wrapper
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list) and v:
                    return v[:4]
    except Exception:
        # Truncated JSON — extract any complete array items via regex
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())[:4]
            except Exception:
                pass
        # Try to salvage partial items: find all complete {...} objects inside the array
        items = re.findall(r'\{[^{}]+\}', raw, re.DOTALL)
        result = []
        for item in items[:4]:
            try:
                result.append(json.loads(item))
            except Exception:
                pass
        if result:
            return result
    return []


# _enrich_sync/_fetch_valuation_sync/_fetch_vix_sync/_fetch_chart_sync now
# live in ai_search/enrichment.py (P5 Stage 1, imported above).


# ── Network graph ─────────────────────────────────────────────────────────────
def _build_graph(query: str, sectors: list[dict], companies: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []

    q_label = query[:28] + ("…" if len(query) > 28 else "")
    nodes.append({"id": "q",  "label": q_label, "type": "query",  "x": 360, "y": 0})

    for i, s in enumerate(sectors[:5]):
        sid = f"s{i}"
        nodes.append({"id": sid, "label": s["name"], "type": "sector", "x": i * 180, "y": 140})
        edges.append({"id": f"q-{sid}", "source": "q", "target": sid, "label": "impacts"})

    for j, c in enumerate(companies[:5]):
        cid = f"c{j}"
        nodes.append({"id": cid, "label": c["symbol"], "type": "company", "x": j * 175, "y": 290})
        parent_id = f"s{j % max(len(sectors[:5]), 1)}"
        edges.append({"id": f"{parent_id}-{cid}", "source": parent_id, "target": cid, "label": "benefits"})

    return {"nodes": nodes, "edges": edges}


# ── Ripple chain (real graph traversal — MarketRipple's differentiator) ───────
# _FALL_WORDS/_build_ripple_chain now live in ai_search/ripple_graph.py
# (P5 Stage 1, imported above).


# ── Market Pulse pipeline — real data first, AI explains only ─────────────────
# _parse_json_response now lives in ai_search/market_pulse.py (P5 Stage 2) —
# its only V2 call site was inside _run_market_pulse_search, relocated with it.


# _run_market_pulse_search now lives in ai_search/market_pulse.py (P5 Stage 2,
# imported above) — both pipelines share the single definition.


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def run_ai_search(query: str, db: AsyncSession, session_context: dict | None = None) -> dict:
    """Full AI search pipeline. Returns complete research report dict."""
    # True end-to-end clock from function entry — used for `timing.total_ms`
    # even though the named stage buckets below only start once we're past
    # the market-pulse pre-check (a separate query family, not part of this
    # pipeline's own stage breakdown).
    _overall_t0 = time.monotonic()

    # Market Pulse — real-data-first path, checked before decision-intent
    # detection since it's a distinct query family (top movers / sector
    # performance / market summary), never the "LLM picks, price fetched
    # after" flow the rest of this pipeline still uses for other intents.
    # Not entity/session-context-aware — its own query-text-only cache key
    # is correct and unaffected by P2 (see _ck's docstring: entities=None
    # keeps the original behavior).
    # Short, separate TTL: this is live price data, not evergreen analysis.
    # Async: regex first (free), semantic classifier only when regex misses —
    # see _detect_market_pulse_async docstring for why both tiers exist.
    if await _detect_market_pulse_async(query):
        mp_key = f"mp:{_ck(query)}"
        cached_pulse = _cget(mp_key, ttl=300)
        if cached_pulse:
            log.info("ai_search.market_pulse_cache_hit", query=query[:50])
            return cached_pulse
        log.info("ai_search.market_pulse_start", query=query[:50])
        mp_result = await _run_market_pulse_search(query)
        if not mp_result.get("synthesis_incomplete"):
            _CACHE[mp_key] = (time.time(), mp_result)
        return mp_result

    # Detect intent first — needed to compute the right cache TTL. Timed on
    # its own (not via the checkpoint chain below) since it's the one stage
    # that runs before the cache-hit early-return, which skips the rest of
    # the pipeline — and skips stage timing entirely on a cache hit, since
    # nothing was actually computed on this call.
    _t_intent0  = time.monotonic()
    intent_data = _detect_decision_intent(query)
    intent      = intent_data.get("intent", "general")
    ttl         = 300 if intent == "news_reaction" else _TTL
    _intent_detection_ms = round((time.monotonic() - _t_intent0) * 1000, 1)

    # P2: entities (and any session-context merge) must be resolved BEFORE
    # the cache key/lookup — the cache key needs to reflect what this query
    # actually resolved to, not just its literal text. Previously the cache
    # key was query-text-only, computed before entities existed at all: two
    # sessions asking the identical literal text ("What about its main
    # competitor?") but resolving to different prior companies would have
    # collided on one cache entry, silently serving one session's answer to
    # the other. Keying on resolved entities (not raw session_context)
    # means two sessions that happen to resolve to the SAME entities still
    # correctly share a cache hit — only genuinely different resolved
    # entities fragment it.
    entities = _extract_entities(query)

    # P3: bare conglomerate name ("What is the investment case for Tata?")
    # checked BEFORE the session-context merge — matching V3's own
    # ordering (see session_context.py's docstring: if the query's own
    # text is ambiguous, session context doesn't get a chance to silently
    # pick one member for the user either). check_ambiguous_group is a
    # pure function of the raw query text; reused as-is from V3, no
    # adaptation needed (verified in Step 1).
    ambiguous = check_ambiguous_group(query, entities)
    if ambiguous:
        log.info("ai_search.ambiguous_entity", term=ambiguous["term"])
        result = _ambiguous_entity_response(query, ambiguous)
        _cset(_ck(query, entities), result)
        return result

    entities, context_used = resolve_context(query, entities, session_context)

    ck = _ck(query, entities)
    cached = _cget(ck, ttl=ttl)
    if cached:
        log.info("ai_search.cache_hit", query=query[:50])
        return cached

    log.info("ai_search.start", query=query[:50])
    loop = asyncio.get_running_loop()

    # P2: a referential query ("What about its main competitor?") that
    # still has nothing to anchor on even after attempting the
    # session-context merge above — no companies/sectors of its own, and no
    # prior context to borrow. Previously this either silently reached the
    # LLM with empty entities, or (before the "it"/IT-sector word-boundary
    # fix above) matched the wrong sector entirely and produced a
    # confidently wrong answer with no degradation signal. Honest
    # "I don't have enough context" beats either.
    if _REFERENTIAL_RE.search(query) and not entities.get("companies") and not entities.get("sectors"):
        log.info("ai_search.referential_no_context", query=query[:80])
        result = _referential_no_context_response(query)
        _cset(ck, result)
        return result

    if _looks_like_unrecognized_company(query, entities):
        log.info("ai_search.unrecognized_company", query=query[:80])
        result = _unrecognized_company_response(query)
        _cset(ck, result)
        return result

    log.info("ai_search.intent", intent=intent, is_decision=intent_data["is_decision"])

    # Stage-by-stage wall-clock timing from here on, exposed on the response
    # as `timing` (ms per stage + total) — feeds the benchmark runner's
    # speed reporting. Checkpoint-based (each stage = time since the
    # previous checkpoint), not independently-measured spans, so buckets are
    # approximate groupings of pipeline work rather than a strict profiler —
    # good enough to see which stage dominates a slow request.
    _t_prev = time.monotonic()
    _stage_ms: dict[str, float] = {"intent_detection_ms": _intent_detection_ms}

    def _checkpoint(stage: str) -> None:
        nonlocal _t_prev
        now = time.monotonic()
        _stage_ms[stage] = round((now - _t_prev) * 1000, 1)
        _t_prev = now

    # Parallel: DB search (chart is built after enrichment so it uses the right companies)
    # entities was already computed above (line ~1781) via _extract_entities —
    # P1 fix: threading it through instead of leaving these three query-independent.
    events, news, policies = await asyncio.gather(
        _search_events(db, query, entities=entities),
        _search_news(db, query, entities=entities),
        _search_policies(db, query, entities=entities),
        return_exceptions=True,
    )
    if isinstance(events,   Exception): events   = []
    if isinstance(news,     Exception): news     = []
    if isinstance(policies, Exception): policies = []

    # Optional: fetch valuation data for valuation-focused queries
    extra_context_lines: list[str] = []
    _valuation_map: dict = {}  # captured for the Decision Engine's real P/E comparison
    if _VALUATION_TRIGGERS.search(query):
        co_syms = [c.upper() for c in entities.get("companies", [])[:2]]
        if co_syms:
            try:
                val = await loop.run_in_executor(None, _fetch_valuation_sync, co_syms)
                _valuation_map = val
                for sym, v in val.items():
                    parts = []
                    if v.get("pe"):   parts.append(f"P/E {v['pe']}")
                    if v.get("pb"):   parts.append(f"P/B {v['pb']}")
                    if v.get("52w_high") and v.get("52w_low"):
                        parts.append(f"52W {v['52w_low']}-{v['52w_high']}")
                    if parts:
                        extra_context_lines.append(f"{sym}: {', '.join(parts)}")
            except Exception:
                pass

    # Fetch India VIX — always (used for confidence scoring; injected into context for VIX queries)
    _vix_level: float | None = None
    try:
        _vix_level = await loop.run_in_executor(None, _fetch_vix_sync)
        if _vix_level and _VIX_TRIGGER.search(query):
            extra_context_lines.append(f"India VIX current level: {_vix_level}")
    except Exception:
        pass

    extra_context = "\n".join(extra_context_lines)
    mie_state:  dict = {}  # captured for confidence signals
    similar:    list = []  # captured for confidence signals
    hist_query: dict = {}  # captured for the historical "key difference" note

    # Inject intelligence from the MIE — single source of truth for all AI context
    try:
        from app.services.intelligence.engine import get_intelligence_state
        mie = await get_intelligence_state()
        mie_state = mie  # capture for confidence signals

        intel_lines: list[str] = []

        # Market mood and direction from signals
        signals = mie.get("signals", {})
        if signals.get("mood") and signals.get("direction"):
            intel_lines.append(
                f"[MARKET MOOD] {signals['mood']} · {signals['direction'].upper()} · "
                f"Risk: {signals.get('risk_level', 'MODERATE')} · "
                f"AI confidence: {signals.get('confidence', 0)}%"
            )

        # Top theme
        if signals.get("top_theme"):
            intel_lines.append(f"[TOP THEME] {signals['top_theme']} (score {signals.get('top_theme_score', 0):.0f})")

        # High-urgency events (≥ 5) from MIE top_events (already ranked, last 8h)
        top_evts = [e for e in mie.get("top_events", []) if e.get("urgency", 0) >= 5][:6]
        for e in top_evts:
            intel_lines.append(
                f"[LIVE URGENCY {e['urgency']}/10] {e.get('one_liner') or e.get('headline', '')[:120]}"
            )

        if intel_lines:
            mie_block = "LIVE MARKET INTELLIGENCE (MIE):\n" + "\n".join(intel_lines)
            extra_context = (extra_context + "\n\n" + mie_block) if extra_context else mie_block
    except Exception:
        pass

    # Inject Historical Market Memory — verified past events to replace hallucinated comparisons
    try:
        from app.services.historical_memory_service import find_similar_events, format_for_ai_prompt

        # Derive search attributes from the query text first — live events only
        # ever carry event_type="macro" so they can't drive category matching —
        # falling back to event-derived sectors when the query itself is generic.
        hist_sectors: list[str] = []
        hist_category: str | None = None
        for ev in (events or [])[:3]:
            hist_sectors.extend(ev.get("affected_sectors", ev.get("sectors", [])) or [])
            if not hist_category:
                hist_category = ev.get("event_type") or ev.get("category")

        _query_lower = query.lower()
        hist_query = {
            "category":  _infer_historical_category(_query_lower) or hist_category,
            "sectors":   _infer_historical_sectors(_query_lower) or list(dict.fromkeys(hist_sectors))[:4],
            "sentiment": intent_data.get("sentiment"),
        }

        if hist_query.get("category") or hist_query.get("sectors"):
            similar = await find_similar_events(hist_query, limit=5, min_similarity=25.0)
            if similar:  # noqa: SIM102 — also captures outer `similar` for confidence
                hist_block = format_for_ai_prompt(similar, max_events=5)
                extra_context = (extra_context + "\n\n" + hist_block) if extra_context else hist_block
    except Exception:
        pass

    # ── Category-specific data-first grounding ──────────────────────────────
    # Same principle as market_pulse: fetch real data before the LLM writes
    # anything, for the query families that previously got zero dedicated
    # evidence and fell straight to a generic prompt. Each block is gated by
    # a cheap keyword regex (same pattern as _VALUATION_TRIGGERS/_VIX_TRIGGER
    # above) so untargeted queries don't pay the extra fetch cost. All calls
    # hit real DB/cache-backed services, never another LLM, and every block
    # fails silently to keep the general path's existing behavior intact.

    # Sector Analysis — real live per-sector % change (fixes categories that
    # previously got zero sector-specific grounding, e.g. "how is the
    # banking sector doing").
    if _SECTOR_TRIGGER.search(query):
        try:
            from app.services.market_data import get_sector_changes
            sector_rows = await get_sector_changes()
            q_lower = query.lower()
            named = [
                s for s in sector_rows
                if any(tok in q_lower for tok in s.get("name", "").lower().split() if len(tok) > 3)
            ]

            def _abs_pct(s: dict) -> float:
                try:
                    return abs(float(str(s.get("value", "0")).replace("%", "").replace("+", "")))
                except (ValueError, TypeError):
                    return 0.0

            shown = sorted(named or sector_rows, key=_abs_pct, reverse=True)[:5]
            if shown:
                block = "Sector performance (real, live 1-day change): " + "; ".join(
                    f"{s['name']} {s['value']}" for s in shown
                )
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Opportunities — real Opportunity Engine, not the LLM inventing an
    # opportunities[] list from nothing.
    if _OPPORTUNITY_TRIGGER.search(query):
        try:
            from app.services.opportunity_service import OpportunityService
            terms = (entities.get("companies") or []) + _words(query)
            opps = await OpportunityService(db).list_by_sector_or_theme(terms[:6], limit=5)
            if opps:
                block = "Verified opportunities (real, from the Opportunity Engine): " + "; ".join(
                    f"{o['title']} (score {o['opportunity_score']}, {o['confidence']} confidence, "
                    f"trend {o['trend']}, risk {o['risk_level']})"
                    for o in opps
                )
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Theme Analysis — real live Theme Engine (ThemeState rows), not a
    # generic "theme" the LLM makes up.
    if _THEME_TRIGGER.search(query):
        try:
            from app.services.intelligence.engine import read_themes
            themes = await read_themes()
            q_lower = query.lower()
            named = [
                t for t in themes
                if any(tok in q_lower for tok in (t.get("theme") or "").lower().split() if len(tok) > 3)
            ]
            shown = (named or themes)[:3]
            if shown:
                lines = []
                for t in shown:
                    stocks = ", ".join(
                        (s.get("sym", "") if isinstance(s, dict) else str(s))
                        for s in (t.get("top_stocks") or [])[:3]
                    )
                    lines.append(
                        f"{t.get('theme', 'Theme')} (momentum {t.get('momentum', 'n/a')})"
                        + (f" — top stocks: {stocks}" if stocks else "")
                    )
                block = "Live themes (real, from Theme Engine): " + "; ".join(lines)
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Risk (direct "what are the risks" style asks) — the real deterministic
    # Risk Score formula, same one market_pulse uses, instead of an
    # unconstrained LLM risk list.
    # Fires for "should I sell" too now — that framing is exactly where a
    # real risk score matters most, and excluding it (the original
    # condition) meant the one intent most about risk got none of this.
    if _RISK_TRIGGER.search(query) or intent == "sell":
        try:
            from app.services.market_data import get_sector_changes
            from app.services.market_scoring_engine import score_risk
            risk_sectors = await get_sector_changes()

            def _pct(s: dict) -> float:
                try:
                    return float(str(s.get("value", "0")).replace("%", "").replace("+", ""))
                except (ValueError, TypeError):
                    return 0.0

            lagging = sorted(risk_sectors, key=_pct)[:3]
            bearish_high_urgency = sum(
                1 for e in (mie_state.get("top_events") or [])
                if e.get("sentiment") == "bearish" and (e.get("urgency") or 0) >= 7
            )
            # Enhancement: score_risk() used to be entirely market-wide —
            # every entity got the identical number regardless of what was
            # actually asked. When a specific company is named, count real
            # bearish events tied to THAT company (same tickers/headline
            # match get_symbol_context already uses) so the score can
            # actually differ between two different stocks.
            entity_bearish = 0
            if entities.get("companies"):
                _sym = entities["companies"][0].upper()
                entity_bearish = sum(
                    1 for e in (mie_state.get("top_events") or [])
                    if e.get("sentiment") == "bearish" and (
                        _sym in [str(t).upper() for t in (e.get("tickers") or [])]
                        or _sym in (str(e.get("headline", "")) + " " + str(e.get("one_liner") or "")).upper()
                    )
                )
            risk_val = score_risk(float(_vix_level or 0), bearish_high_urgency, lagging, entity_bearish)
            entity_note = f" · {entity_bearish} bearish events specific to {entities['companies'][0]}" if entity_bearish else ""
            block = (
                f"Computed Risk Score (real, deterministic formula): {risk_val}/100 · "
                f"India VIX {_vix_level or 'n/a'} · {bearish_high_urgency} high-urgency bearish market events · "
                f"weakest sectors: {', '.join(s['name'] for s in lagging) or 'none'}{entity_note}"
            )
            extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Macro — real live index levels beyond just VIX (inflation/rate/GDP/
    # crude/rupee-shaped queries previously got no market-level grounding
    # at all).
    if _MACRO_TRIGGER.search(query):
        try:
            from app.services.market_data import get_extended_indices
            idx_rows = await get_extended_indices()
            want = [i for i in idx_rows if i.get("name") in ("NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX")]
            if want:
                block = "Macro indices (real, live): " + "; ".join(
                    f"{i['name']} {i['value']} ({i['change']})" for i in want
                )
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Company Research — real Intelligence Graph context + real filed
    # announcements for a bare single-company query that isn't already a
    # buy/sell/hold/compare decision (those already get valuation/events/news).
    if intent == "general" and not intent_data.get("is_comparison") and len(entities.get("companies") or []) == 1:
        try:
            from app.services.intelligence.engine import get_symbol_context
            from app.services.company_announcements_service import get_recent_announcements
            sym = entities["companies"][0]
            ctx, ann = await asyncio.gather(
                get_symbol_context(sym), get_recent_announcements(sym, limit=5),
                return_exceptions=True,
            )
            if isinstance(ctx, dict) and ctx.get("story"):
                # story is a dict ({"text": ..., "mood": ..., ...}) from
                # read_story(), not a plain string — pull the text field.
                story_val = ctx["story"]
                story_text = story_val.get("text") if isinstance(story_val, dict) else str(story_val)
                if story_text:
                    block = f"Company context for {sym} (real, from Intelligence Graph): {story_text[:220]}"
                    if ctx.get("market_mood"):
                        block += f" · Mood: {ctx['market_mood']}"
                    extra_context = (extra_context + "\n\n" + block) if extra_context else block
            if isinstance(ann, list) and ann:
                ann_txt = "; ".join(
                    f"{a.get('subject', '')} ({a.get('category', '')}, {a.get('announcement_date', '')})"
                    for a in ann[:5]
                )
                block2 = f"Recent real filed announcements for {sym}: {ann_txt}"
                extra_context = (extra_context + "\n\n" + block2) if extra_context else block2
        except Exception:
            pass

    # Financial Results (post-results, not phrased as a reaction/preview) —
    # real filed results announcements, not an LLM guessing at numbers.
    if _RESULTS_TRIGGER.search(query):
        try:
            from app.services.company_announcements_service import get_recent_announcements
            for sym in (entities.get("companies") or [])[:2]:
                ann = await get_recent_announcements(sym, limit=8)
                results_ann = [
                    a for a in ann
                    if any(k in (a.get("category", "") or "").lower() for k in ("result", "financial"))
                ]
                if results_ann:
                    lines = "; ".join(
                        f"{a['subject']} ({a['announcement_date']})" for a in results_ann[:3]
                    )
                    block = f"Real filed results announcements for {sym}: {lines}"
                    extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Fetch calibration data (memory-cached, does not block significantly)
    _cal_data: dict = {}
    try:
        from app.services.prediction_service import get_calibration_data
        _cal_data = await get_calibration_data()
    except Exception:
        pass

    # Compute pre-AI evidence-based confidence estimate from observable signals
    _pre_factors = None
    _conf_result = None
    try:
        from app.services.confidence_service import ConfidenceFactors, calculate_confidence as _calc_conf
        _mie_sig  = mie_state.get("signals", {})
        _mie_dir  = _mie_sig.get("direction", "")
        _i_sent   = intent_data.get("sentiment", "")
        _macro_ok = (
            (_mie_dir == "up"   and _i_sent == "bullish") or
            (_mie_dir == "down" and _i_sent == "bearish")
        )
        _vix_val  = float(_vix_level or 0)
        _vix_rgm  = (
            "very_high" if _vix_val > 25 else
            "high"      if _vix_val > 18 else
            "low"       if 0 < _vix_val < 12 else
            "normal"
        )
        _hist_acc = (
            sum(s.get("confidence", 80) for s in similar) / (100.0 * len(similar))
            if similar else 0.0
        )
        _pre_factors = ConfidenceFactors(
            source_count=len(events) + len(news),
            historical_count=len(similar),
            historical_accuracy=_hist_acc,
            macro_aligned=_macro_ok,
            macro_reason=_mie_sig.get("top_theme", "") if _macro_ok else "",
            vix_level=_vix_val,
            volatility_regime=_vix_rgm,
            ai_certainty=5,
        )
        _pre_conf    = _calc_conf(_pre_factors)
        extra_context = (extra_context + "\n\n" + _pre_conf.explanation) if extra_context else _pre_conf.explanation
    except Exception:
        pass

    # P3: 3+ resolved companies get the honest multi-entity path, checked
    # BEFORE is_comparison — "TCS vs Infosys vs Wipro" matches BOTH
    # _COMPARE_RE_3 (is_comparison=True, holding=TCS/target=Infosys) AND
    # this check (3 resolved companies); without this ordering, that
    # phrasing would still silently drop Wipro into _build_decision_prompt's
    # two-entity-only prompt, the same bug this task exists to fix — just
    # via a slightly different route than the comma+"and" phrasing.
    is_multi_compare = len(entities.get("companies") or []) >= 3

    # AI generation — only genuine two-asset comparisons (both a holding AND
    # a target actually named by the user) get the switch/hold comparison
    # prompt. Everything else — including single-entity "should I invest in
    # X" questions — is an investment_opportunity query and goes through the
    # general prompt so it never fabricates a placeholder "Asset A".
    _checkpoint("db_search_ms")
    if is_multi_compare:
        prompt  = _build_multi_compare_prompt(query, intent_data, entities, events, news, policies, extra_context=extra_context)
        max_tok = 4500
    elif intent_data["is_comparison"] and intent not in ("list_picks", "portfolio_review", "news_reaction", "earnings_preview", "entry_timing"):
        prompt  = _build_decision_prompt(query, intent_data, events, news, policies, extra_context=extra_context)
        max_tok = 4500
    else:
        prompt  = _build_prompt(query, events, news, policies, intent_data=intent_data, extra_context=extra_context)
        # The JSON schema grew substantially this session (bottom_line,
        # key_drivers, what_priced_in, per-sector explanation, etc.) — 3500
        # was tight enough to truncate mid-JSON on some fallback models,
        # which fails to parse and silently drops to the graceful default.
        max_tok = 4500
    # Bounded total time for the LLM step — a genuine safety net, not a
    # tight SLA. _call_provider's own httpx timeout is 30s *per model*, and
    # a tier can hold multiple models (_GROQ_HIGH has 3), so legitimate
    # (non-hung) completions were already measured up to 65s pre-P0 with no
    # per-tier concurrency gate at all. An initial 18s budget here was set
    # from the task spec's pre-measurement estimate and, once measured live
    # under 4-way concurrent load, cut off far more legitimate completions
    # than it caught real hangs (7-of-8 degraded vs the 21% baseline it was
    # supposed to improve on) — raised to 60s so it only fires on an actual
    # stuck call, not normal contended-tier latency.
    _budget_timed_out = False
    try:
        raw = await asyncio.wait_for(
            _call_with_fallback(prompt, _system_with_date(), max_tokens=max_tok, priority="interactive"),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        _budget_timed_out = True
        raw = ""
    log.info("ai_search.raw_len", chars=len(raw) if raw else 0, starts=raw[:60] if raw else "")

    ai: dict = {}
    if raw:
        try:
            clean = raw.strip()
            # Strip markdown code fences (model often wraps with ```json ... ```)
            if clean.startswith("```"):
                clean = re.sub(r"^```(?:json)?\s*", "", clean)
                clean = re.sub(r"\s*```$", "", clean).strip()
            ai = json.loads(clean)
        except json.JSONDecodeError:
            # Try extracting first JSON object from response
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    ai = json.loads(m.group())
                except Exception:
                    pass
            if not ai:
                log.warning("ai_search.json_parse_fail", raw=raw[:300])
    else:
        # Distinguishes "the LLM never returned usable text" (every tier
        # exhausted its cooldown/slot budget, or the 18s total budget above
        # fired) from ai_search.json_parse_fail above ("got text back,
        # couldn't parse it as JSON") — previously both silently fell
        # through to the same degraded template with no way to tell them
        # apart in logs.
        log.warning("ai_search.degraded_capacity", query=query[:120], budget_timeout=_budget_timed_out)

    # Graceful defaults when AI fails
    if not ai:
        ai = {
            "degraded": True,  # generic template, not real analysis — surfaced to the frontend so it doesn't present this as a completed AI verdict
            # P4: distinguishes the two degraded causes for degraded_reason below —
            # previously only visible in logs (ai_search.degraded_capacity /
            # ai_search.json_parse_fail), never on the response itself, so a
            # capacity-degraded response was indistinguishable from a real
            # successful one by degraded_reason alone (it read as None either way).
            "_degraded_reason": "capacity" if not raw else "parse_failure",
            "summary": f"Market intelligence analysis for: {query}. Analysis based on real-time database events and news.",
            "bottom_line": (
                f"There isn't enough freshly generated analysis to answer “{query}” with confidence right now "
                "— the underlying event and news data is available below, but the synthesis step didn't complete. "
                "Try rephrasing the question or checking back shortly."
            ),
            "what_happened": "A significant market development has been identified related to the queried topic.",
            "why_it_happened": "Multiple macro, policy, and sector-specific factors are driving this development.",
            "immediate_impact": "Near-term markets are reacting to this development with sector-specific movement.",
            "medium_term": "The 3-12 month outlook depends on policy execution and global macro environment.",
            "long_term": "Structural implications are broadly positive for India's capital markets.",
            "what_priced_in": "Insufficient data to assess current positioning — treat any near-term move as unconfirmed.",
            "risks": ["Execution risk", "Global headwinds", "Regulatory uncertainty"],
            "opportunities": ["Sector rotation", "Infrastructure capex", "Export growth"],
            "key_drivers": [],
            "confidence": 40, "sentiment": "neutral",
            "insights": [
                {"icon": "📊", "title": "Market Overview",   "summary": "Current market conditions reflect mixed global and domestic signals with selective sector strength."},
                {"icon": "🏛️", "title": "Policy Framework", "summary": "Government policy remains focused on infrastructure, manufacturing, and economic growth enablement."},
                {"icon": "🏆", "title": "Sector Leaders",   "summary": "Infrastructure and defence sectors are well positioned to outperform peers in this environment."},
                {"icon": "⚠️", "title": "Risk Watch",       "summary": "Monitor global commodity prices, currency movements, and domestic fiscal deficit trajectory."},
            ],
            "companies": [], "sectors": [], "timeline": [],
            "follow_up_questions": ["Which sectors benefit most?", "What is the timeline?", "Key risks?", "Historical precedents?"],
            "investment_verdict": {
                "rating": "Neutral", "direction": "neutral", "confidence": 40,
                "horizon": "6-12 months", "top_picks": [],
                "risks": ["Macro uncertainty"], "catalysts": ["Policy clarity"],
                "opportunity_score": 50,
            },
        }

    # Enrich companies with live prices (in thread executor)
    raw_cos = ai.get("companies", [])
    ai_summary = ai.get("summary", query)
    try:
        companies_enriched = await loop.run_in_executor(None, _enrich_sync, raw_cos) if raw_cos else []
    except Exception as _e:
        log.warning("ai_search.enrich_fail", exc=str(_e)[:80])
        companies_enriched = []

    # De-duplicate by symbol — the AI occasionally returns the same company
    # twice under two different framings (e.g. once as a beneficiary, once
    # flagged as at-risk), which reads as a data-quality bug, not nuance.
    # Keep whichever occurrence has the higher impact score.
    _seen_symbols: dict[str, dict] = {}
    for _c in companies_enriched:
        _sym = (_c.get("symbol") or "").upper()
        if not _sym:
            continue
        _prev = _seen_symbols.get(_sym)
        if _prev is None or float(_c.get("impact_score", 0) or 0) > float(_prev.get("impact_score", 0) or 0):
            _seen_symbols[_sym] = _c
    companies_enriched = list(_seen_symbols.values())

    # Sort by actual impact score (defense-in-depth — don't trust AI ordering)
    # and classify each company's position in the ripple, deterministically.
    companies_enriched.sort(key=lambda c: float(c.get("impact_score", 0) or 0), reverse=True)
    _classify_ripple_position(companies_enriched)
    for _c in companies_enriched:
        _c.setdefault("why_it_matters", _c.get("reason", ""))

    # Sectors: time_horizon + status are computed server-side, not AI-generated,
    # so labeling stays consistent regardless of prompt compliance.
    sectors_raw = ai.get("sectors", [])
    for _s in sectors_raw:
        _status = _sector_status(bool(_s.get("positive", True)), float(_s.get("score", 0) or 0))
        _s["status"] = _status
        _s["time_horizon"] = _sector_time_horizon(_status)
        _s.setdefault("explanation", "")

    # Finalize evidence-based confidence — now that live company prices and
    # sector direction exist, feed the formula genuine market/sector
    # confirmation signals instead of leaving them at 0 (they were computed
    # before enrichment ran, so market_confirming/sector_confirming/
    # company_sensitivity never had real data to work with).
    if _pre_factors is not None:
        try:
            from app.services.confidence_service import calculate_confidence as _calc_conf, _THRESHOLDS
            _thesis = ai.get("sentiment") or "neutral"
            if _thesis == "bullish":
                _pre_factors.market_confirming = sum(
                    1 for c in companies_enriched if c.get("price") != "—" and c.get("positive")
                )
                _pre_factors.sector_confirming = sum(1 for s in sectors_raw if s.get("positive"))
            elif _thesis == "bearish":
                _pre_factors.market_confirming = sum(
                    1 for c in companies_enriched if c.get("price") != "—" and not c.get("positive")
                )
                _pre_factors.sector_confirming = sum(1 for s in sectors_raw if not s.get("positive"))
            _top_impact = max((float(c.get("impact_score", 0) or 0) for c in companies_enriched), default=0)
            _pre_factors.company_sensitivity = "high" if _top_impact >= 80 else ("medium" if _top_impact >= 55 else "low")
            _pre_factors.ai_certainty = min(10, max(1, int(ai.get("confidence_self_rating") or 5)))
            _conf_result = _calc_conf(_pre_factors)

            # Apply historical calibration (only when ≥ 10 verified predictions for this level)
            if _cal_data:
                _lvl_cal = _cal_data.get(_conf_result.level, {})
                _cal_f   = float(_lvl_cal.get("calibration_factor", 1.0))
                _cal_n   = int(_lvl_cal.get("total", 0))
                if _cal_n >= 10 and 0.4 <= _cal_f <= 1.8:
                    _new_score = min(100.0, max(0.0, round(_conf_result.total_score * _cal_f, 1)))
                    _new_level = next(lbl for thr, lbl in _THRESHOLDS if _new_score >= thr)
                    _acc_pct   = round(_lvl_cal.get("accuracy_rate", 0.5) * 100)
                    _conf_result.total_score = _new_score
                    _conf_result.level       = _new_level
                    _conf_result.reasons.append(
                        f"Calibrated from {_cal_n} verified predictions ({_acc_pct}% historical accuracy)"
                    )
        except Exception:
            pass

    # Build context-aware chart: use the query's companies when available, else indices
    _CHART_COLORS = ["#818cf8", "#34d399", "#fb923c", "#f472b6"]
    chart_tickers = []
    for _i, _c in enumerate(companies_enriched[:4]):
        _sym = re.sub(r"\.(NS|BO|BSE|NSE)$", "", _c.get("symbol", "").strip().upper())
        if _sym:
            _name = (_c.get("name") or _sym)[:22]
            chart_tickers.append((_name, f"{_sym}.NS", _CHART_COLORS[_i % 4]))

    # Everything below is independent — run it all concurrently rather than
    # as a chain of sequential awaits.
    top_sector = sectors_raw[0]["name"] if sectors_raw else None
    _entity_type = "search"

    # P4: generate_scenario_analysis/generate_monitoring_checklist render
    # this title straight into fallback-template text (e.g. "Strong
    # performance for {title} driven by...") whenever the underlying call
    # degrades — passing the raw literal query produced text like "Strong
    # performance for What's the investment case for Infosys? driven by...".
    # Prefer a resolved entity name (up to 2 companies, else the top
    # sector); only fall back to the raw query when nothing resolved at all.
    _resolved_title = (
        ", ".join(
            c.get("name") or c.get("symbol", "")
            for c in companies_enriched[:2] if c.get("name") or c.get("symbol")
        )
        or top_sector
        or query
    )

    async def _safe(coro, default, label: str):
        try:
            return await coro
        except Exception as _e:
            log.warning(f"ai_search.{label}_fail", exc=str(_e)[:120])
            return default

    from app.services.ai_service import generate_scenario_analysis, generate_monitoring_checklist

    (
        chart, insights, ripple_chain, scenarios, monitoring_raw,
    ) = await asyncio.gather(
        _safe(loop.run_in_executor(None, _fetch_chart_sync, chart_tickers), {"labels": [], "series": []}, "chart"),
        _safe(_generate_insights(query, ai_summary), [], "insights"),
        _safe(_build_ripple_chain(query), [], "ripple_chain"),
        _safe(
            generate_scenario_analysis(_entity_type, ck, title=_resolved_title, description=ai_summary, sector=top_sector or "", priority="interactive"),
            {}, "scenarios",
        ),
        _safe(
            generate_monitoring_checklist(_entity_type, ck, title=_resolved_title, description=ai_summary, sector=top_sector or "", priority="interactive"),
            {}, "monitoring",
        ),
    )
    _checkpoint("llm_ms")
    horizons_raw = _build_market_horizons(
        ai, _conf_result.total_score if _conf_result else ai.get("confidence", 50), ai.get("sentiment", "neutral"),
    )

    what_to_monitor = [
        {
            "title": item.get("label", ""),
            "why_it_matters": item.get("why_it_matters", ""),
            "importance": item.get("importance", "medium"),
            "frequency": item.get("frequency", ""),
        }
        for item in (monitoring_raw.get("items", []) if isinstance(monitoring_raw, dict) else [])
    ]

    graph = _build_graph(query, sectors_raw, companies_enriched)
    _checkpoint("graph_generation_ms")

    # Extract decision_intelligence block when present — only for genuine
    # two-asset comparisons; a single-entity "should I invest in X" question
    # has no holding to compare against and must not render the
    # switch/hold comparison panel at all.
    raw_di = ai.get("decision_intelligence")
    decision_intelligence: dict | None = None
    if is_multi_compare and isinstance(raw_di, dict):
        # P3: entity_analyses (not holding_analysis/target_analysis) — see
        # _build_multi_compare_prompt. No detected_holding/target/third or
        # entity_type tagging here; those are 2-entity-specific fields that
        # don't apply to an N-way list.
        decision_intelligence = raw_di
        decision_intelligence.setdefault("intent", "compare_multi")
        decision_intelligence.setdefault("detected_entities", entities.get("companies") or [])
    elif intent_data["is_comparison"] and isinstance(raw_di, dict):
        decision_intelligence = raw_di
        decision_intelligence.setdefault("intent",            intent_data["intent"])
        decision_intelligence.setdefault("detected_holding",  intent_data.get("holding"))
        decision_intelligence.setdefault("detected_target",   intent_data.get("target"))
        decision_intelligence.setdefault("detected_horizon",  intent_data.get("horizon"))
        decision_intelligence.setdefault("detected_risk",     intent_data.get("risk"))
        decision_intelligence.setdefault("detected_budget",   intent_data.get("budget"))
        decision_intelligence.setdefault("detected_third",    intent_data.get("third_entity"))
        # Tag entity_type so the frontend renders sectors/commodities vs companies differently
        type_map = {
            "holding_analysis": ("holding_is_commodity", "holding_is_sector"),
            "target_analysis":  ("target_is_commodity",  "target_is_sector"),
        }
        for side, (comm_flag, sec_flag) in type_map.items():
            block = decision_intelligence.get(side)
            if isinstance(block, dict):
                if intent_data.get(comm_flag):
                    block["entity_type"] = "commodity"
                elif intent_data.get(sec_flag):
                    block["entity_type"] = "sector"
                else:
                    block["entity_type"] = "company"
    elif intent_data["is_comparison"]:
        decision_intelligence = {
            "intent":           intent_data["intent"],
            "detected_holding": intent_data.get("holding"),
            "detected_target":  intent_data.get("target"),
            "detected_horizon": intent_data.get("horizon"),
            "detected_risk":    intent_data.get("risk"),
            "detected_budget":  intent_data.get("budget"),
            "context_complete": True,
            "missing_context":  [],
            "decision_summary": ai.get("summary", ""),
        }

    _final_confidence = round(_conf_result.total_score) if _conf_result else ai.get("confidence", 65)

    # Research Outlook — rating is forced through the 8-label enum regardless
    # of what the AI returned; this is a research platform, never advisory.
    _verdict_raw  = ai.get("investment_verdict", {}) or {}
    # P5 Stage 3, item 4 — real horizon only when the AI didn't state one;
    # a real AI-stated horizon is always kept as-is. Shared with V3's
    # equivalent fallback (pipeline.py's _assemble_response) via horizon.py.
    _verdict_horizon = _verdict_raw.get("horizon") or _compute_horizon(
        _vix_level, similar, ai.get("medium_term"), ai.get("long_term"),
    )
    _verdict_risk    = "High" if _final_confidence < 50 else ("Medium" if _final_confidence < 75 else "Low")

    if intent == "list_picks":
        # "Top N Picks Identified" isn't a research-outlook rating — it's a
        # different response shape entirely (a ranked list, not a verdict on
        # one entity). Forcing it through the 8-label enum (pre-existing
        # behavior) or reconciling it against the Verdict Engine would
        # silently destroy it. Leave it exactly as the AI wrote it.

        # AI Recommendation Engine (Phase 2) — real, sector/theme-matched
        # candidates from the Opportunity Engine, cross-referenced against
        # the real NSE universe, replace the AI's own free-invented list.
        _engine_picks: list[dict] = []
        try:
            from app.services.ai_recommendation_engine import compute_recommendations
            # _words() only filters len>=2 — fine for the OR-based event/news
            # search it was built for, but the Opportunity Engine's title
            # match is a plain substring test, so short stopwords produce
            # false positives (e.g. "me" from "give ME top 5..." matches
            # inside every "X Invest-ME-nt Opportunity" title regardless of
            # actual relevance — caught live: a "banking stocks" query
            # returned Automotive names via a "Defence Investment
            # Opportunity" row). Drop stopwords and anything under 4 chars
            # before it reaches that search.
            _pick_stopwords = {
                "give", "me", "the", "top", "best", "and", "for", "which", "what",
                "are", "should", "recommend", "picks", "pick", "stock", "stocks",
                "companies", "shares", "invest", "buy", "list", "some", "with",
            }
            _pick_terms = (entities.get("sectors") or []) + [
                w for w in _words(query) if w not in _pick_stopwords and len(w) >= 4
            ]
            _engine_picks = await compute_recommendations(db, _pick_terms, intent_data.get("pick_count") or 3)
        except Exception:
            _engine_picks = []

        investment_verdict = {
            **_verdict_raw,
            "confidence": _final_confidence,
            "risk_level": _verdict_risk,
            "suitable_for": _suitable_for(_verdict_horizon, _verdict_risk),
            "verdict_basis": "real_screener" if _engine_picks else "ai_only_no_real_match",
            "engine_verdict": None,
            "engine_recommendations": _engine_picks,
            # Real picks take precedence when the screener found any; the
            # AI's own list is kept only as a fallback when no real
            # sector/theme opportunity matched the query at all.
            "top_picks": [c["symbol"] for c in _engine_picks] or _verdict_raw.get("top_picks", []),
        }
    else:
        _ai_rating = _normalize_outlook(
            _verdict_raw.get("rating", ""), _verdict_raw.get("direction", "neutral"),
            _verdict_raw.get("confidence", _final_confidence), _verdict_raw.get("opportunity_score", 50),
        )

        # Investment Verdict Engine (Phase 2) — compute the rating from real
        # signals (MIE direction, the blended real confidence score, live VIX,
        # and a real Opportunity Engine score when the named entity/sector has
        # one) rather than trusting the AI's free-text rating outright. Close
        # agreement keeps the AI's label (it may carry stock-specific nuance
        # the formula can't see); a real disagreement is overridden by the
        # computed verdict, since real data wins over an unconstrained guess.
        _engine_verdict = None
        try:
            from app.services.investment_verdict_engine import compute_investment_verdict, _OUTLOOK_LABELS as _VE_LABELS
            _opp_score_for_verdict = None
            try:
                _verdict_terms = (entities.get("companies") or []) + (entities.get("sectors") or [])
                if _verdict_terms:
                    from app.services.opportunity_service import OpportunityService
                    _opp_hits = await OpportunityService(db).list_by_sector_or_theme(_verdict_terms[:4], limit=1)
                    if _opp_hits:
                        _opp_score_for_verdict = _opp_hits[0]["opportunity_score"]
            except Exception:
                pass
            _engine_verdict = compute_investment_verdict(
                direction=mie_state.get("signals", {}).get("direction", "sideways"),
                confidence_score=_final_confidence,
                opportunity_score=_opp_score_for_verdict,
                vix_level=_vix_level,
            )
            _tier_ai = _VE_LABELS.index(_ai_rating) if _ai_rating in _VE_LABELS else 4
            _tier_engine = _engine_verdict["tier"]
            if abs(_tier_ai - _tier_engine) <= 1:
                _final_rating, _verdict_basis = _ai_rating, "ai_aligned_with_data"
            else:
                _final_rating, _verdict_basis = _engine_verdict["rating"], "data_overridden_ai"
        except Exception:
            _final_rating, _verdict_basis = _ai_rating, "ai_only_engine_unavailable"

        investment_verdict = {
            **_verdict_raw,
            "rating": _final_rating,
            # Same canonical-confidence fix already applied on the frontend
            # this session (displayConfidence()) — investment_verdict.confidence
            # used to keep whatever number the AI itself wrote (or the
            # degraded-template default), which could silently disagree with
            # confidence_data.score. Force it to the one real blended number.
            "confidence": _final_confidence,
            "risk_level": _verdict_risk,
            "suitable_for": _suitable_for(_verdict_horizon, _verdict_risk),
            "verdict_basis": _verdict_basis,
            "engine_verdict": _engine_verdict,
        }

    # Decision Engine (Phase 2) — for a genuine two-entity decision (both a
    # holding AND a target actually named), compute which side the real data
    # favors: two independent Investment Verdict Engine reads (same
    # market-wide direction/confidence/VIX, each entity's own real
    # Opportunity Engine score when one matches) plus a real P/E comparison
    # when the valuation trigger already fetched both sides. No LLM call.
    # P3: excluded for is_multi_compare — this is a genuine two-entity
    # pairwise computation (engine_recommendation between exactly
    # holding/target), the same "pairwise dimension content isn't computed
    # for 3+" boundary _build_multi_compare_prompt draws. Without this
    # exclusion, "TCS vs Infosys vs Wipro" (which sets is_comparison=True
    # via _COMPARE_RE_3 AND is_multi_compare=True via 3 resolved
    # companies) would silently compute a TCS-vs-Infosys verdict and drop
    # Wipro here even though the prompt above correctly analyzed all 3.
    if intent_data["is_comparison"] and not is_multi_compare and decision_intelligence is not None:
        try:
            from app.services.decision_engine import compute_decision
            from app.services.opportunity_service import OpportunityService
            _sym_a = next(iter(_match_companies((intent_data.get("holding") or "").lower())), None)
            _sym_b = next(iter(_match_companies((intent_data.get("target") or "").lower())), None)
            if _sym_a and _sym_b:
                async def _opp_for(sym: str) -> float | None:
                    hits = await OpportunityService(db).list_by_sector_or_theme([sym], limit=1)
                    return hits[0]["opportunity_score"] if hits else None
                _opp_a, _opp_b = await asyncio.gather(_opp_for(_sym_a), _opp_for(_sym_b))
                decision_intelligence["engine_recommendation"] = compute_decision(
                    entity_a_symbol=_sym_a, entity_b_symbol=_sym_b,
                    direction=mie_state.get("signals", {}).get("direction", "sideways"),
                    confidence_score=_final_confidence, vix_level=_vix_level,
                    opportunity_score_a=_opp_a, opportunity_score_b=_opp_b,
                    valuation_a=_valuation_map.get(_sym_a), valuation_b=_valuation_map.get(_sym_b),
                )
        except Exception:
            pass

    # Historical Comparison — real, structured data from historical_memory_service
    # (verified seed events with real per-company returns), never AI-invented.
    historical_comparison = [
        {
            "event_title":  h.get("event_title", ""),
            "event_date":   str(h.get("event_date", ""))[:10],
            "similarity":   h.get("similarity", 0),
            "key_lesson":   h.get("key_lesson", ""),
            "key_difference": _key_difference(hist_query, h),
            "what_happened": h.get("what_happened", ""),
            "sector_reactions":  h.get("sector_reactions", {}),
            "historical_winners": h.get("historical_winners", []),
            "historical_losers":  h.get("historical_losers", []),
            "nifty_1w": h.get("nifty_1w"),
            "nifty_1m": h.get("nifty_1m"),
        }
        for h in similar
    ]

    ai_reasoning_methods = _build_reasoning_methods(
        events, similar, extra_context_lines, mie_state, ripple_chain, companies_enriched,
        news=news, policies=policies,
    )
    confidence_caveats = _confidence_caveats(_conf_result, events, similar, len(news) + len(events))

    # Surfaced to the frontend so a failed LLM synthesis renders as an honest
    # "couldn't complete analysis" state instead of a confident-looking report
    # built entirely from generic fallback templates (main answer and/or the
    # separately-generated scenarios/checklist can each degrade independently).
    #
    # P5 Stage 2, item 5 (V2-side audit, 2026-08-07): degraded_reason is the
    # single source of truth; synthesis_incomplete is derived from it below,
    # never set independently. Computed here (before degraded_reason, which
    # needs it) — three real gaps closed:
    #  1. is_multi_compare (3+ entities, main answer succeeded) previously
    #     set degraded_reason="multi_entity_partial" while this flag stayed
    #     False — the exact inconsistency this unification targets.
    #  2. scenarios.get("degraded") (the separately-generated scenarios call
    #     failed independently of the main answer) previously set this flag
    #     True with degraded_reason staying None whenever the query also
    #     wasn't a multi-compare — "the scenarios.degraded-only case found
    #     during P4 verification" the original task note referenced.
    #  3. _unrecognized_company_response/_ambiguous_entity_response (P3)
    #     hardcoded this False alongside a real degraded_reason — see those
    #     functions directly, fixed the same way.
    _scenario_only_degraded = bool(isinstance(scenarios, dict) and scenarios.get("degraded")) and not ai.get("degraded")
    _synthesis_incomplete = bool(ai.get("degraded")) or _scenario_only_degraded or is_multi_compare
    _checkpoint("assembly_ms")
    # True end-to-end time from function entry, not a sum of the named
    # buckets — the market-pulse pre-check (before intent detection even
    # starts) runs on every call and isn't individually attributed to a
    # named stage. The gap between total_ms and the sum of named buckets
    # is exactly that overhead.
    _stage_ms["total_ms"] = round((time.monotonic() - _overall_t0) * 1000, 1)

    result = {
        "query": query,
        "synthesis_incomplete": _synthesis_incomplete,
        "entities": entities,
        # P2: honestly reports what (if anything) session context
        # contributed to this answer — same field V3 already exposes via
        # session_context.resolve_context, now shared by V2 too.
        "context_used": context_used,
        # P3: labels a real, non-canned response that's still honestly not
        # a full analysis — a 3+-entity compare got parallel per-entity
        # summaries, not the pairwise dimension analysis a 2-entity compare
        # gets. None for a normal single/two-entity response.
        # P4: capacity/parse_failure take priority over multi_entity_partial
        # when both are true (a 3+-entity query where the LLM call itself
        # also failed) — nothing usable was generated at all, which is more
        # fundamental than the multi-compare response-shape nuance. Closes
        # the real live gap: these two states previously shipped with
        # degraded_reason=None despite synthesis_incomplete=True, making
        # them indistinguishable from a normal successful response by this
        # field alone.
        #
        # P5 Stage 2 (2026-08-07): added scenario_degraded — the
        # scenarios-only-failed case (main answer succeeded, the separately-
        # generated scenarios call didn't) previously left this None too.
        "degraded_reason": (
            ai.get("_degraded_reason") if ai.get("degraded")
            else "multi_entity_partial" if is_multi_compare
            else "scenario_degraded" if _scenario_only_degraded
            else None
        ),
        "answer": {
            "summary":          ai.get("summary", ""),
            "bottom_line":      _cap_words(ai.get("bottom_line", ai.get("summary", "")), 120),
            "what_happened":    ai.get("what_happened", ""),
            "why_it_happened":  ai.get("why_it_happened", ""),
            "immediate_impact": ai.get("immediate_impact", ""),
            "medium_term":      ai.get("medium_term", ""),
            "long_term":        ai.get("long_term", ""),
            "what_priced_in":   ai.get("what_priced_in", ""),
            "risks":            ai.get("risks", []),
            "opportunities":    ai.get("opportunities", []),
            "confidence":       _final_confidence,
            "confidence_level": _conf_result.level if _conf_result else "Medium",
            "sentiment":        ai.get("sentiment", "neutral"),
            "sources_count":    len(news) + len(events),
        },
        "key_drivers":          ai.get("key_drivers", []),
        "insights":             insights or ai.get("insights", []),
        "companies":            companies_enriched,
        "sectors":              sectors_raw,
        "related_events":       events[:6],
        "news":                 news[:6],
        "policies":             policies[:4],
        "timeline":             ai.get("timeline", []),
        "historical_comparison": historical_comparison,
        "ripple_chain":         ripple_chain,
        "scenarios":            scenarios if isinstance(scenarios, dict) else {},
        "market_impact_horizons": horizons_raw if isinstance(horizons_raw, list) else [],
        "what_to_monitor":      what_to_monitor,
        "ai_reasoning_methods": ai_reasoning_methods,
        "follow_up_questions":  ai.get("follow_up_questions", []),
        "investment_verdict":   investment_verdict,
        "market_chart":         chart,
        "graph":                graph,
        "citations":            list({a.get("source", "") for a in news if a.get("source")}),
        "decision_intelligence": decision_intelligence,
        "confidence_data": {
            "level":     _conf_result.level if _conf_result else "Medium",
            "score":     _final_confidence,
            "reasons":   list(_conf_result.reasons) if _conf_result else [],
            "breakdown": dict(_conf_result.breakdown) if _conf_result else {},
            "caveats":   confidence_caveats,
        },
        "timing": dict(_stage_ms),
    }

    # P4: same post-hoc consistency checks V3 already runs via validate_and_repair
    # (validation.py) — built as shared functions in timeline_checks.py so
    # neither pipeline's checking can silently diverge from the other's again.
    # V2 has no validate_and_repair-style report object, so each finding is
    # logged (same graceful-degrade-and-log convention already used
    # throughout this function) and the offending timeline entries are
    # dropped from the list rather than left in place.
    try:
        from app.services.ai_search.timeline_checks import (
            check_near_duplicate_entries, check_numeric_range_contradiction,
            check_verdict_tense_contradiction,
        )
        _tl_entries = [
            (str(item.get("date", "")), f"{item.get('title', '')} {item.get('description', '')}".strip())
            for item in result["timeline"] if isinstance(item, dict)
        ]
        _tl_bad: set[str] = set()
        _tense_flags = check_verdict_tense_contradiction(_tl_entries, investment_verdict.get("direction", "neutral"))
        if _tense_flags:
            _tl_bad.update(_tense_flags)
            log.warning("ai_search.timeline_tense_contradiction", query=query[:80], entries=_tense_flags)
        _numeric_flags = check_numeric_range_contradiction(_tl_entries)
        if _numeric_flags:
            _tl_bad.update(_numeric_flags)
            log.warning("ai_search.timeline_numeric_contradiction", query=query[:80], entries=_numeric_flags)
        _dup_pairs = check_near_duplicate_entries(_tl_entries)
        if _dup_pairs:
            _tl_bad.update(b for _, b in _dup_pairs)
            log.warning("ai_search.timeline_near_duplicate", query=query[:80], pairs=_dup_pairs)
        if _tl_bad:
            result["timeline"] = [
                item for item in result["timeline"]
                if not (isinstance(item, dict) and str(item.get("date", "")) in _tl_bad)
            ]
    except Exception:
        pass

    try:
        from app.services.ai_search.validation import _narrative_company_mentions
        _narrative = f"{result['answer'].get('summary', '')} {result['answer'].get('bottom_line', '')}"
        _mentioned = _narrative_company_mentions(_narrative)
        _listed = {(c.get("symbol") or "").upper() for c in result["companies"] if isinstance(c, dict)}
        _missing = {sym: name for sym, name in _mentioned.items() if sym not in _listed}
        if _missing:
            log.warning("ai_search.companies_narrative_mismatch", query=query[:80], missing=_missing)
    except Exception:
        pass

    if not _synthesis_incomplete:
        # Don't cache a degraded result for 30 minutes — a provider that
        # recovers moments later (or a different one in the fallback chain)
        # should get a real answer on the next identical query, not the same
        # fabricated report.
        _CACHE[ck] = (time.time(), result)  # store with current timestamp; TTL applied on read

    # Asynchronously persist predictions for the learning engine (non-blocking)
    asyncio.create_task(
        _store_search_predictions(result, _conf_result),
        name="prediction-store",
    )

    # Free-tier data track, Stage 1 (2026-08-06): query-pattern instrumentation
    # — entities + a thin_evidence flag, so real traffic can eventually answer
    # "are users hitting well-covered names or the long tail" once enough of
    # this has accumulated. thin_evidence reuses the exact source_count < 3
    # threshold _confidence_caveats already uses — no new detection logic.
    log.info(
        "ai_search.done", query=query[:50], cos=len(companies_enriched), events=len(events), intent=intent,
        entities=entities, thin_evidence=(len(events) + len(news) < 3),
    )
    return result


def _map_horizon(horizon_str: str) -> int:
    """Map investment_verdict.horizon text to calendar days."""
    h = (horizon_str or "").lower()
    if "intraday" in h or ("1" in h and "day" in h):    return 1
    if "week" in h or "3" in h and "day" in h:          return 3
    if "1 month" in h or "short" in h and "term" in h:  return 7
    return 30  # default: 30-day horizon for longer-term predictions


async def _store_search_predictions(result: dict, conf_result: Any) -> None:
    """Extract and persist predictions from an AI search result."""
    try:
        from app.services.prediction_service import store_prediction

        query    = result.get("query", "")
        verdict  = result.get("investment_verdict") or {}
        answer   = result.get("answer") or {}
        companies_list = result.get("companies") or []

        direction = (verdict.get("direction") or answer.get("sentiment") or "sideways").lower()
        if direction == "bullish":  direction = "up"
        if direction == "bearish":  direction = "down"
        if direction not in ("up", "down"): direction = "sideways"

        horizon   = _map_horizon(verdict.get("horizon", ""))
        conf_score = float((conf_result.total_score if conf_result else None) or verdict.get("confidence", 60) or 60)
        conf_level = (conf_result.level if conf_result else None) or "Medium"
        conf_break = dict(conf_result.breakdown) if conf_result else {}

        # 1) Overall market direction prediction (top company as primary entity)
        top_cos = [c for c in companies_list[:2] if c.get("symbol")]
        if top_cos or verdict.get("direction"):
            entities = [
                {
                    "type":   "company",
                    "symbol": c.get("symbol", ""),
                    "name":   c.get("name", ""),
                    "ticker": c.get("symbol", ""),
                }
                for c in top_cos[:2]
            ]
            pred_text = (
                f"{direction.upper()} on {', '.join(c.get('symbol','') for c in top_cos) or 'market'} "
                f"— {answer.get('immediate_impact', '')[:120]}"
            )
            await store_prediction(
                source="ai_search",
                prediction_text=pred_text,
                direction=direction,
                prediction_type="overall",
                target_entities=entities,
                confidence_score=conf_score,
                confidence_level=conf_level,
                confidence_factors=conf_break,
                horizon_days=horizon,
                query=query[:400],
            )

        # 2) Individual company predictions (beneficiary = up, at_risk = down)
        for company in companies_list[:3]:
            sym = company.get("symbol", "").strip()
            if not sym:
                continue
            impact = (company.get("impact_type") or "neutral").lower()
            co_dir = "up" if impact == "beneficiary" else "down" if impact == "at_risk" else "sideways"
            co_conf = min(100, max(0, float(company.get("confidence", conf_score) or conf_score)))
            await store_prediction(
                source="ai_search",
                prediction_text=f"{co_dir.upper()} on {sym}: {company.get('reason', '')[:120]}",
                direction=co_dir,
                prediction_type="company",
                target_entities=[{
                    "type":   "company",
                    "symbol": sym,
                    "name":   company.get("name", sym),
                    "ticker": sym,
                }],
                confidence_score=co_conf,
                confidence_level=conf_level,
                confidence_factors=conf_break,
                horizon_days=horizon,
                query=query[:400],
            )
    except Exception as exc:
        log.debug("prediction.store_search_fail", error=str(exc)[:80])

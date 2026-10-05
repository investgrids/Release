"""
Deterministic recommendation-language safety net for Market Pulse — the
same class of check safety_gate.py runs for the main V3 response
(app.services.ai_search.safety_gate), applied to Market Pulse's own field
set. safety_gate.py cannot see this at all: it scans answer.bottom_line/
answer.summary/ai_conclusion.investor_action_note/decision_engine_v2.why,
none of which exist on Market Pulse's response shape ({"type":
"market_pulse", "market_summary": str, "ai_conclusion": str, ...} — a
structurally different dict, not a SearchResult). Confirmed via the
2026-09-21 intent audit: Market Pulse's generated prose passed through
finalize_v3_response completely unscanned.

Scans exactly the fields Market Pulse's own prompt generates (see
market_pulse.py::_build_market_pulse_prompt's JSON template) — never the
real, deterministic data sitting alongside them (index values, company
names, tickers, prices, dates, verified_drivers) which are facts about
the market, not this platform's own advisory language.

Uses advisory_language.py's shared, context-aware scan() — Market
Pulse's own prompt has no "never say Buy/Sell/Hold" instruction at all
(it isn't built on specialists/base.py's research_framing_rules — a
separate prompt entirely), making this arguably MORE exposed than the
main specialists, not less. Context-aware hold matters especially here:
Market Pulse legitimately narrates real monetary-policy and corporate
events ("RBI held rates", "the company will hold its AGM") that a bare
"hold" ban would have wrongly degraded.
"""
from __future__ import annotations

import structlog

from app.services.ai_search.advisory_language import scan as _scan

log = structlog.get_logger(__name__)

_SCALAR_FIELDS = ("market_summary", "sector_narrative", "ai_conclusion", "what_to_watch_summary")
_MOVER_GROUPS = ("top_gainers", "top_losers")


def find_market_pulse_violation(result: dict) -> str | None:
    """Returns the first violating field's label, or None if clean.
    Read-only. Field labels for movers are "top_gainers.<TICKER>" /
    "top_losers.<TICKER>" so the log line (see
    build_market_pulse_degraded_response) identifies which entry without
    ever logging the matched text itself."""
    for field in _SCALAR_FIELDS:
        text = result.get(field)
        if isinstance(text, str) and _scan(text):
            return field
    for group in _MOVER_GROUPS:
        for item in (result.get(group) or []):
            if not isinstance(item, dict):
                continue
            narrative = item.get("narrative")
            if isinstance(narrative, str) and _scan(narrative):
                return f"{group}.{item.get('ticker', '?')}"
    return None


def build_market_pulse_degraded_response(result: dict, field_label: str) -> dict:
    """Never mutates `result` — returns a new dict. Keeps every real,
    deterministic field untouched (indices, market_status, sectors,
    verified_drivers, the calendar, biggest_opportunity/biggest_risk —
    none of these are LLM-generated, see market_pulse.py's own docstring:
    "every stock, sector, and number... was fetched... BEFORE this
    prompt was built"). Clears only the generated-prose fields to an
    honest empty/fallback state, and strips `narrative` from every mover
    (the frontend renders a mover's real verified_drivers chips
    regardless — see DegradedMarketPulse / PulseMoverCard)."""
    log.warning(
        "ai_search.market_pulse_recommendation_language_violation",
        field=field_label, violation_code="recommendation_language_pattern_match",
    )
    result = result or {}

    def _strip_narratives(items: list) -> list:
        return [{**item, "narrative": ""} for item in (items or []) if isinstance(item, dict)]

    return {
        **result,
        "synthesis_incomplete": True,
        "degraded_reason": "recommendation_language_violation",
        "market_summary": (
            "A written market summary could not be shown because the generated text did not "
            "pass the research-language check. The real index and mover data below is unaffected."
        ),
        "sector_narrative": "",
        "ai_conclusion": "",
        "what_to_watch_summary": "",
        "top_gainers": _strip_narratives(result.get("top_gainers")),
        "top_losers": _strip_narratives(result.get("top_losers")),
    }

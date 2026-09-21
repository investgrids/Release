"""
Market Pulse safety gate — Phase 1 fix (2026-09-21 intent audit finding
1): Market Pulse's own generated prose (market_summary, sector_narrative,
ai_conclusion, what_to_watch_summary, mover narratives) previously passed
through finalize_v3_response completely unscanned, since safety_gate.py's
fixed field paths don't exist on Market Pulse's response shape.
"""
from __future__ import annotations

import structlog.testing

from app.services.ai_search import market_pulse_safety
from app.services.ai_search.response_finalize import finalize_v3_response

_CLEAN_PULSE = {
    "type": "market_pulse", "query": "market summary today", "synthesis_incomplete": False,
    "generated_at": "2026-09-21T10:00:00Z",
    "market_status": {"status": "open", "time_ist": "10:00"},
    "indices": [{"ticker": "NIFTY", "name": "Nifty 50", "value": "25,000", "change": "+0.5%", "positive": True}],
    "market_mood": "Neutral", "market_direction": "sideways",
    "market_summary": "Markets are trading flat with mixed cues from global indices.",
    "sector_narrative": "IT and banking are leading while metals lag.",
    "leading_sectors": [], "lagging_sectors": [],
    "top_gainers": [{
        "company": "Reliance Industries", "ticker": "RELIANCE", "value": "+2.1%", "subtitle": "1,402.50",
        "positive": True, "verified_drivers": [], "narrative": "Reliance gained on strong quarterly results.",
    }],
    "top_losers": [{
        "company": "Tata Motors", "ticker": "TATAMOTORS", "value": "-1.2%", "subtitle": "950.00",
        "positive": False, "verified_drivers": [], "narrative": "Tata Motors slipped on weak volumes data.",
    }],
    "most_active": [], "biggest_opportunity": None, "biggest_risk": None,
    "ai_conclusion": "Today's move looks broad-based across sectors.",
    "what_to_watch_next": [], "what_to_watch_summary": "Watch for the RBI policy meeting next week.",
    "scores": {},
}


def _pulse_with(**overrides) -> dict:
    result = {**_CLEAN_PULSE}
    result.update(overrides)
    return result


# ── find_market_pulse_violation ─────────────────────────────────────────────

def test_clean_pulse_has_no_violation():
    assert market_pulse_safety.find_market_pulse_violation(_CLEAN_PULSE) is None


def test_advisory_language_in_market_summary_is_caught():
    result = _pulse_with(market_summary="Nifty remains a solid buy candidate right now.")
    assert market_pulse_safety.find_market_pulse_violation(result) == "market_summary"


def test_advisory_language_in_sector_narrative_is_caught():
    result = _pulse_with(sector_narrative="IT stocks are a strong buy heading into results.")
    assert market_pulse_safety.find_market_pulse_violation(result) == "sector_narrative"


def test_advisory_language_in_ai_conclusion_is_caught():
    result = _pulse_with(ai_conclusion="Investors should buy the dip across banking names.")
    assert market_pulse_safety.find_market_pulse_violation(result) == "ai_conclusion"


def test_advisory_language_in_what_to_watch_summary_is_caught():
    result = _pulse_with(what_to_watch_summary="Accumulate ahead of the RBI meeting.")
    assert market_pulse_safety.find_market_pulse_violation(result) == "what_to_watch_summary"


def test_bare_hold_is_caught_even_though_shared_pattern_list_lacks_it():
    result = _pulse_with(ai_conclusion="Investors should hold their current positions.")
    assert market_pulse_safety.find_market_pulse_violation(result) == "ai_conclusion"


def test_advisory_language_in_a_gainer_narrative_is_caught():
    result = _pulse_with(top_gainers=[{**_CLEAN_PULSE["top_gainers"][0], "narrative": "This is a strong buy right now."}])
    assert market_pulse_safety.find_market_pulse_violation(result) == "top_gainers.RELIANCE"


def test_advisory_language_in_a_loser_narrative_is_caught():
    result = _pulse_with(top_losers=[{**_CLEAN_PULSE["top_losers"][0], "narrative": "Investors should sell this stock now."}])
    assert market_pulse_safety.find_market_pulse_violation(result) == "top_losers.TATAMOTORS"


def test_immutable_market_data_never_flagged():
    """Index values, company names, tickers, prices — none of these are
    scanned; only the 4 scalar fields and mover .narrative are."""
    result = _pulse_with(query="Should I buy or sell right now?")  # advisory words in the QUERY, not generated prose
    assert market_pulse_safety.find_market_pulse_violation(result) is None


# ── build_market_pulse_degraded_response ────────────────────────────────────

def test_degraded_response_clears_narrative_fields_keeps_real_data():
    result = market_pulse_safety.build_market_pulse_degraded_response(_CLEAN_PULSE, "ai_conclusion")
    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "recommendation_language_violation"
    assert result["sector_narrative"] == ""
    assert result["ai_conclusion"] == ""
    assert result["what_to_watch_summary"] == ""
    assert "research-language check" in result["market_summary"]
    # Real data untouched.
    assert result["indices"] == _CLEAN_PULSE["indices"]
    assert result["market_status"] == _CLEAN_PULSE["market_status"]


def test_degraded_response_strips_all_mover_narratives_not_just_the_offender():
    result = market_pulse_safety.build_market_pulse_degraded_response(_CLEAN_PULSE, "top_gainers.RELIANCE")
    assert all(g["narrative"] == "" for g in result["top_gainers"])
    assert all(l["narrative"] == "" for l in result["top_losers"])
    # Real mover data (company/ticker/value/verified_drivers) untouched.
    assert result["top_gainers"][0]["ticker"] == "RELIANCE"
    assert result["top_gainers"][0]["value"] == "+2.1%"


def test_degraded_response_never_mutates_the_input():
    before = {**_CLEAN_PULSE}
    market_pulse_safety.build_market_pulse_degraded_response(_CLEAN_PULSE, "ai_conclusion")
    assert _CLEAN_PULSE == before


def test_degraded_response_logs_only_field_and_code():
    with structlog.testing.capture_logs() as logs:
        market_pulse_safety.build_market_pulse_degraded_response(_CLEAN_PULSE, "ai_conclusion")
    events = [e for e in logs if e.get("event") == "ai_search.market_pulse_recommendation_language_violation"]
    assert len(events) == 1
    assert events[0]["field"] == "ai_conclusion"
    assert events[0]["violation_code"] == "recommendation_language_pattern_match"
    assert "solid buy" not in repr(events[0]) and "Today's move" not in repr(events[0])


# ── finalize_v3_response dispatches Market Pulse through this gate ─────────

def test_finalize_v3_response_degrades_unsafe_market_pulse():
    unsafe = _pulse_with(ai_conclusion="This is a solid buy candidate across the board.")
    result = finalize_v3_response("market summary today", unsafe)
    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "recommendation_language_violation"
    assert result["ai_conclusion"] == ""


def test_finalize_v3_response_leaves_clean_market_pulse_unchanged():
    result = finalize_v3_response("market summary today", dict(_CLEAN_PULSE))
    assert result == _CLEAN_PULSE


def test_finalize_v3_response_never_attaches_aev2_or_core_answer_concepts_to_market_pulse():
    unsafe = _pulse_with(ai_conclusion="Investors should hold across the board.")
    result = finalize_v3_response("market summary today", unsafe)
    assert "answer_experience_v2" not in result
    assert "confidence_breakdown" not in result or result.get("confidence_breakdown") == _CLEAN_PULSE.get("confidence_breakdown")


def test_finalize_v3_response_market_pulse_never_mutates_the_cached_object():
    import copy
    cached = _pulse_with(ai_conclusion="This is a solid buy candidate.")
    before = copy.deepcopy(cached)
    finalize_v3_response("market summary today", cached, was_cached=True)
    assert cached == before

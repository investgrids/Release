"""
CoreMarketPulse — the market-pulse variant of the canonical core (see
core_market_pulse.py's own docstring for the CanonicalAnswerCore
discriminated-union design). Follows core_answer.py's test conventions:
build a plain market-pulse result dict, project it through the real
from_market_pulse_response(), never construct a CoreMarketPulse by hand
except where directly testing the dataclass's own frozen behavior.
"""
from __future__ import annotations

import copy

import pytest

from app.services.ai_search.core_market_pulse import CoreMarketPulse, from_market_pulse_response

_RAW = {
    "type": "market_pulse", "query": "top gainers today", "response_id": "mp-resp-1",
    "synthesis_incomplete": False, "degraded_reason": None,
    "generated_at": "2026-09-22T10:06:08+00:00",
    "market_session": "live",
    "market_status": {"status": "open", "time_ist": "11:00 AM", "date": "22 Sep 2026"},
    "indices": [{"name": "NIFTY 50", "ticker": "^NSEI", "value": "23,329.00", "change": "-0.43%", "chart": []}],
    "leading_sectors": [{"id": "realty", "name": "Realty", "value": "+0.5%", "momentum_score": 57.5}],
    "lagging_sectors": [{"id": "it", "name": "IT", "value": "-0.9%", "momentum_score": 20.0}],
    "top_gainers": [{
        "company": "Coal India", "ticker": "COALINDIA", "value": "+3.21%", "subtitle": "428.00",
        "positive": True, "verified_drivers": [], "narrative": "No verified driver identified for this move.",
    }],
    "top_losers": [{
        "company": "Tata Motors", "ticker": "TATAMOTORS", "value": "-1.2%", "subtitle": "950.00",
        "positive": False, "verified_drivers": [], "narrative": "Tata Motors slipped on weak volumes.",
    }],
    "most_active": [],
    "theme_momentum": [{"theme": "Banking", "score": 61.0, "momentum": "rising", "price_signal": 0.8, "news_signal": 40.0}],
    "biggest_opportunity": {"title": "IPO rush", "href": "/opportunity-radar/36", "opportunity_score": 98.0},
    "biggest_risk": {"source": "tracked_event", "event_id": "evt-1", "headline": "FII outflows accelerate", "reason": "FII outflows accelerate", "sectors": [], "tickers": [], "confidence": 70, "published_at": "2026-09-22T09:00:00+00:00"},
    "market_summary": "Markets traded lower today, led by IT.",
    "ai_conclusion": "Today's move looks broad-based.",
    "what_to_watch_next": [{"id": "cal-1", "category": "rbi", "title": "RBI Policy", "date": "Sep 28, 2026", "description": "High importance."}],
    "scores": {},
}


def test_projects_every_real_field():
    core = from_market_pulse_response(_RAW)
    assert core.kind == "market_pulse"
    assert core.query == "top gainers today"
    assert core.response_id == "mp-resp-1"
    assert core.as_of == "2026-09-22T10:06:08+00:00"
    assert core.market_session == "live"
    assert core.market_status == "open"
    assert len(core.indices) == 1 and core.indices[0]["ticker"] == "^NSEI"
    assert len(core.leading_sectors) == 1 and core.leading_sectors[0]["id"] == "realty"
    assert len(core.lagging_sectors) == 1
    assert len(core.top_gainers) == 1 and core.top_gainers[0]["ticker"] == "COALINDIA"
    assert len(core.top_losers) == 1
    assert core.most_active == ()
    assert len(core.theme_momentum) == 1 and core.theme_momentum[0]["theme"] == "Banking"
    assert core.biggest_opportunity["title"] == "IPO rush"
    assert core.risk_context["source"] == "tracked_event"
    assert len(core.upcoming_events) == 1
    assert core.generated_summary == "Markets traded lower today, led by IT."
    assert core.generated_conclusion == "Today's move looks broad-based."
    assert core.gainer_narratives["COALINDIA"] == "No verified driver identified for this move."
    assert core.loser_narratives["TATAMOTORS"] == "Tata Motors slipped on weak volumes."


def test_missing_optional_fields_default_honestly():
    minimal = {"type": "market_pulse", "query": "market summary"}
    core = from_market_pulse_response(minimal)
    assert core.indices == ()
    assert core.biggest_opportunity is None
    assert core.risk_context is None
    assert core.generated_summary == ""
    assert core.generated_conclusion == ""


def test_none_result_produces_an_empty_honest_core():
    core = from_market_pulse_response(None)
    assert core.query == ""
    assert core.indices == ()
    assert core.risk_context is None


# ── Frozen + deep-copy immutability (mirrors core_answer.py's own tests) ──

def test_dataclass_is_frozen():
    core = from_market_pulse_response(_RAW)
    with pytest.raises(Exception):
        core.query = "mutated"  # type: ignore[misc]


def test_mutating_the_original_dict_after_projection_never_reaches_the_core():
    raw = copy.deepcopy(_RAW)
    core = from_market_pulse_response(raw)
    raw["indices"][0]["value"] = "TAMPERED"
    raw["top_gainers"][0]["ticker"] = "TAMPERED"
    raw["biggest_opportunity"]["title"] = "TAMPERED"
    assert core.indices[0]["value"] == "23,329.00"
    assert core.top_gainers[0]["ticker"] == "COALINDIA"
    assert core.biggest_opportunity["title"] == "IPO rush"


def test_mutating_a_core_tuple_item_never_reaches_a_second_projection():
    """Two independent projections from the same raw dict never alias
    the same nested dict objects — same guarantee core_answer.py's
    from_v3_response provides."""
    raw = copy.deepcopy(_RAW)
    core1 = from_market_pulse_response(raw)
    core2 = from_market_pulse_response(raw)
    core1.indices[0]["value"] = "TAMPERED"
    assert core2.indices[0]["value"] == "23,329.00"


# ── Calendar freshness stays an upstream (read_upcoming_calendar)
# responsibility — the projection passes it through unfiltered, never
# re-deriving its own (possibly buggy) notion of "still upcoming." ──────

def test_upcoming_events_pass_through_without_reinterpreting_dates():
    core = from_market_pulse_response(_RAW)
    assert core.upcoming_events[0]["date"] == "Sep 28, 2026"
    assert core.upcoming_events[0]["id"] == "cal-1"

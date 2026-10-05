"""
aev2/market_pulse.py — the AEV2 presenter for CoreMarketPulse. See that
module's own docstring for the risk-provenance asymmetry (tracked_event
vs ai_synthesis) and the generated-text validation rules this covers.
"""
from __future__ import annotations

from app.services.ai_search.aev2 import market_pulse as mp_aev2
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_market_pulse import CoreMarketPulse, from_market_pulse_response

RELIANCE_GAINER = {
    "company": "Reliance Industries", "ticker": "RELIANCE", "value": "+2.10%", "subtitle": "1,402.50",
    "positive": True,
    "verified_drivers": [{
        "driver": "Strong Results", "driver_type": "corporate_results", "confidence_tier": "High",
        "evidence": "Reliance reported strong quarterly results.", "related_event_ids": ["evt-reliance-1"],
        "driver_strength": 80.0,
    }],
    "narrative": "Reliance gained on strong quarterly results.",
}
TATAMOTORS_LOSER = {
    "company": "Tata Motors", "ticker": "TATAMOTORS", "value": "-1.20%", "subtitle": "950.00",
    "positive": False, "verified_drivers": [], "narrative": "No verified driver identified for this move.",
}

_BASE = {
    "type": "market_pulse", "query": "top gainers and losers today", "response_id": "mp-resp-1",
    "synthesis_incomplete": False, "degraded_reason": None,
    "generated_at": "2026-09-22T10:06:08+00:00", "market_session": "live",
    "market_status": {"status": "open"},
    "indices": [{"name": "NIFTY 50", "ticker": "^NSEI", "value": "23,329.00", "change": "-0.43%", "chart": []}],
    "leading_sectors": [{"id": "realty", "name": "Realty", "value": "+0.5%", "momentum_score": 57.5}],
    "lagging_sectors": [{"id": "it", "name": "IT", "value": "-0.9%", "momentum_score": 20.0}],
    "top_gainers": [dict(RELIANCE_GAINER)],
    "top_losers": [dict(TATAMOTORS_LOSER)],
    "most_active": [],
    "theme_momentum": [{"theme": "Banking", "score": 61.0, "momentum": "rising", "price_signal": 0.8, "news_signal": 40.0}],
    "biggest_opportunity": {"title": "IPO rush: 9 companies to launch issues", "href": "/opportunity-radar/36", "opportunity_score": 98.0},
    "biggest_risk": None,
    "market_summary": "Reliance Industries led gainers up 2.10% while Tata Motors led losers down 1.20%.",
    "ai_conclusion": "Today's move looks broad-based across NIFTY 50 constituents.",
    "what_to_watch_next": [{"id": "cal-1", "category": "rbi", "title": "RBI Policy", "date": "Sep 28, 2026", "description": "High importance."}],
    "scores": {},
}


def _pulse_with(**overrides) -> dict:
    result = {**_BASE}
    result.update(overrides)
    return result


def _assemble(**overrides) -> dict:
    core = from_market_pulse_response(_pulse_with(**overrides))
    return assemble_aev2(core, mode=AEV2Mode.PUBLIC)


# ── Structural output always present, regardless of generated-text state ──

def test_structured_output_survives_synthesis_failure():
    result = _assemble(market_summary="", ai_conclusion="")
    assert result["kind"] == "market_pulse"
    assert len(result["indices"]) == 1
    assert len(result["movers"]["gainers"]) == 1
    assert len(result["sector_movement"]["leading"]) == 1
    assert len(result["upcoming_events"]) == 1
    assert result["synthesis_status"] == "unavailable"
    assert result["generated_summary"] is None


def test_synthesis_complete_when_generated_text_validates():
    result = _assemble()
    assert result["synthesis_status"] == "complete"
    assert result["generated_summary"]["text"] == _BASE["market_summary"]
    assert result["generated_summary"]["validation_status"] == "validated"


# ── Risk: discriminated union, tracked_event vs ai_synthesis asymmetry ───

def test_tracked_event_risk_renders_with_real_event_citation():
    result = _assemble(biggest_risk={
        "source": "tracked_event", "event_id": "evt-risk-1", "headline": "FII outflows accelerate",
        "reason": "FII outflows accelerate", "sectors": [], "tickers": [], "confidence": 70,
        "published_at": "2026-09-22T09:00:00+00:00",
    })
    risk = result["risk_context"]
    assert risk is not None
    assert risk["source"] == "tracked_event"
    assert risk["event_id"] == "evt-risk-1"
    assert risk["evidence_refs"] == ["event:evt-risk-1"]
    assert "confidence" not in risk


def test_ai_synthesis_risk_is_always_omitted_no_real_evidence_exists():
    """Spec rule: 'Never substitute uncited narrative merely because no
    tracked Event exists.' ai_synthesis has no real Event/structured
    fact behind it in this slice, so it can never produce a valid
    evidence_refs entry — it is always None, not a fallback render."""
    result = _assemble(biggest_risk={
        "source": "ai_synthesis", "headline": None, "reason": "Renewed FII outflows could pressure markets.",
        "sectors": [], "tickers": [], "confidence": 68,
    })
    assert result["risk_context"] is None


def test_missing_risk_resolves_to_null():
    result = _assemble(biggest_risk=None)
    assert result["risk_context"] is None


def test_tracked_and_ai_risk_never_share_a_label_field():
    """The two branches' own `source` discriminant must always differ
    when both hypothetically existed — proven by construction: only
    "tracked_event" ever survives to a non-null risk_context."""
    tracked = _assemble(biggest_risk={
        "source": "tracked_event", "event_id": "evt-1", "headline": "h", "reason": "h",
        "sectors": [], "tickers": [], "confidence": 70, "published_at": "2026-09-22T09:00:00+00:00",
    })["risk_context"]
    ai = _assemble(biggest_risk={
        "source": "ai_synthesis", "headline": None, "reason": "r", "sectors": [], "tickers": [], "confidence": 68,
    })["risk_context"]
    assert tracked["source"] == "tracked_event"
    assert ai is None  # never rendered at all, so it can never carry the SAME label as tracked


def test_self_rated_confidence_is_structurally_unreachable():
    result = _assemble(biggest_risk={
        "source": "tracked_event", "event_id": "evt-1", "headline": "h", "reason": "h",
        "sectors": [], "tickers": [], "confidence": 999, "published_at": "2026-09-22T09:00:00+00:00",
    })
    assert "confidence" not in result["risk_context"]
    assert "999" not in str(result["risk_context"])


# ── Opportunity ───────────────────────────────────────────────────────────

def test_opportunity_labels_score_as_opportunity_score_not_forecast():
    result = _assemble()
    opp = result["biggest_opportunity"]
    assert opp["opportunity_score"] == 98.0
    assert "probability" not in opp
    assert "forecast" not in opp


def test_missing_opportunity_resolves_to_null():
    result = _assemble(biggest_opportunity=None)
    assert result["biggest_opportunity"] is None


def test_v2_current_strength_also_labeled_as_opportunity_score():
    """V2's read path names the same real signal current_strength (see
    intelligence/engine.py::read_opportunities) — AEV2 must present ONE
    consistent field name regardless of which version produced it."""
    result = _assemble(biggest_opportunity={"title": "V2 opp", "href": "/opportunity-radar/slug-1", "current_strength": 71.5})
    assert result["biggest_opportunity"]["opportunity_score"] == 71.5


def test_shadow_opportunity_shaped_input_never_leaks_a_status_flag():
    """Defense in depth: even if a shadow-shaped dict somehow reached
    this presenter (it shouldn't — read_opportunities already excludes
    shadow V2 rows upstream), the presenter itself has no field that
    could surface a public_status/is_shadow flag either way — it only
    ever reads title/href/score."""
    result = _assemble(biggest_opportunity={
        "title": "Should never render", "href": "/opportunity-radar/unpublished-1",
        "opportunity_score": 50.0, "public_status": "shadow", "is_shadow": True,
    })
    assert set(result["biggest_opportunity"].keys()) == {"title", "href", "opportunity_score"}
    assert "public_status" not in result["biggest_opportunity"]
    assert "is_shadow" not in result["biggest_opportunity"]


# ── Verified drivers ──────────────────────────────────────────────────────

def test_driver_ids_resolve_to_real_events():
    result = _assemble()
    driver = result["movers"]["gainers"][0]["verified_drivers"][0]
    assert driver["evidence_refs"] == ["event:evt-reliance-1"]


def test_empty_drivers_render_honestly_not_fabricated():
    result = _assemble()
    loser = result["movers"]["losers"][0]
    assert loser["verified_drivers"] == []
    assert result["evidence_coverage"]["movers_with_driver"] == 1
    assert result["evidence_coverage"]["movers_total"] == 2
    assert result["evidence_coverage"]["tracked_event_count"] == 1


# ── Generated-text validation ────────────────────────────────────────────

def test_advisory_language_fails_closed():
    result = _assemble(ai_conclusion="This is a solid buy candidate across the board.")
    assert result["generated_conclusion"] is None


def test_numbers_that_do_not_match_the_structured_payload_are_rejected():
    result = _assemble(market_summary="Reliance Industries gained 47.00% today.")
    assert result["generated_summary"] is None


def test_unknown_symbol_mentioned_in_generated_text_fails_validation():
    result = _assemble(ai_conclusion="INFY also rallied sharply alongside the broader market today.")
    assert result["generated_conclusion"] is None


def test_mover_narrative_independently_validated_not_just_the_summary():
    bad_gainer = {**RELIANCE_GAINER, "narrative": "This stock is a screaming buy right now."}
    result = _assemble(top_gainers=[bad_gainer])
    assert result["movers"]["gainers"][0]["narrative"] is None
    # The real mover data itself is untouched.
    assert result["movers"]["gainers"][0]["ticker"] == "RELIANCE"


def test_clean_mover_narrative_renders():
    result = _assemble()
    assert result["movers"]["gainers"][0]["narrative"] == "Reliance gained on strong quarterly results."


def test_empty_narrative_is_honestly_absent_not_a_placeholder():
    result = _assemble(top_gainers=[{**RELIANCE_GAINER, "narrative": ""}])
    assert result["movers"]["gainers"][0]["narrative"] is None


# ── Sector taxonomy structural isolation from SectorData ────────────────

def test_module_never_imports_sector_data_or_the_fabricated_sectors_api():
    """Static proof, not just behavioral: this presenter has no import
    path to the fabricated SectorData table or api/sectors.py's
    _SECTOR_STOCKS at all — the only sector source it can ever read is
    whatever CoreMarketPulse.leading_sectors/lagging_sectors carries,
    which itself comes exclusively from the real ETF feed (get_sector_
    changes) — see market_intelligence_service.py's own sourcing."""
    import inspect
    source = inspect.getsource(mp_aev2)
    assert "SectorData" not in source
    assert "api.sectors" not in source
    assert "_SECTOR_STOCKS" not in source


def test_sector_move_source_label_is_the_real_etf_feed_never_sector_data():
    result = _assemble()
    leading = result["sector_movement"]["leading"][0]
    assert leading["change"]["source"] == "yfinance_sector_etf"


# ── Provenance envelope ───────────────────────────────────────────────────

def test_every_index_and_mover_value_carries_provenance():
    result = _assemble()
    idx = result["indices"][0]
    assert idx["price"]["as_of"] == _BASE["generated_at"]
    assert idx["price"]["session"] == "live"
    assert idx["price"]["source"] == "yfinance_nse_index"
    gainer = result["movers"]["gainers"][0]
    assert gainer["change"]["source"] == "yfinance_top_movers"


# ── No standard research confidence formula ──────────────────────────────

def test_no_research_confidence_fields_leak_onto_market_pulse():
    result = _assemble()
    assert "confidence" not in result
    assert "confidence_breakdown" not in result
    assert "historical_similarity" not in str(result)

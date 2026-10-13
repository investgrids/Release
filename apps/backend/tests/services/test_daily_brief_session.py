"""Daily Brief V2, Phase 0: canonical session state, realized (not forecast) verdicts outside the pre-open window, and no
opening-prediction call after the close, on weekends or on holidays. No network, no DB, no LLM."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app.api.daily_brief_intelligence as brief
import app.services.fact_registry as fact_registry
import app.services.opening_prediction_service as ops
from app.services import daily_brief_composer as composer
from app.services.market_session_state import (
    AFTER_CLOSE, HOLIDAY, OPEN, PRE_OPEN, WEEKEND, classify_session, next_trading_day, previous_trading_day,
)

IST = ZoneInfo("Asia/Kolkata")


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


# 2026-10-12 is a Monday and a normal trading day; 2026-10-02 (Fri) and 2026-10-20 (Tue) are NSE holidays in the calendar.
@pytest.mark.parametrize("when,state", [
    (at(2026, 10, 12, 8, 30), PRE_OPEN),
    (at(2026, 10, 12, 9, 14), PRE_OPEN),
    (at(2026, 10, 12, 9, 15), OPEN),
    (at(2026, 10, 12, 15, 30), OPEN),
    (at(2026, 10, 12, 15, 31), AFTER_CLOSE),
    (at(2026, 10, 12, 23, 59), AFTER_CLOSE),
    (at(2026, 10, 10, 11, 0), WEEKEND),
    (at(2026, 10, 11, 20, 0), WEEKEND),
    (at(2026, 10, 2, 10, 0), HOLIDAY),
    (at(2026, 10, 20, 8, 0), HOLIDAY),
])
def test_session_state(when, state):
    assert classify_session(when).state == state


def test_reference_and_forecast_dates():
    pre = classify_session(at(2026, 10, 12, 8, 30))
    assert pre.shows_forecast and pre.forecast_target_date.isoformat() == "2026-10-12" and pre.reference_session_date.isoformat() == "2026-10-09"
    after = classify_session(at(2026, 10, 12, 17, 0))
    assert not after.shows_forecast and after.reference_session_date.isoformat() == "2026-10-12" and after.forecast_target_date.isoformat() == "2026-10-13"
    sat = classify_session(at(2026, 10, 10, 12, 0))
    assert sat.reference_session_date.isoformat() == "2026-10-09" and sat.forecast_target_date.isoformat() == "2026-10-12"
    hol = classify_session(at(2026, 10, 20, 12, 0))
    assert hol.reference_session_date.isoformat() == "2026-10-19" and hol.forecast_target_date.isoformat() == "2026-10-21"
    assert previous_trading_day(hol.ist_date).isoformat() == "2026-10-19" and next_trading_day(hol.ist_date).isoformat() == "2026-10-21"


def test_late_utc_evening_is_still_the_same_ist_day():
    # 2026-10-12 20:30 UTC is already 2026-10-13 02:00 IST: the IST date, not the UTC date, decides the session
    from datetime import timezone
    s = classify_session(datetime(2026, 10, 12, 20, 30, tzinfo=timezone.utc))
    assert s.ist_date.isoformat() == "2026-10-13" and s.state == PRE_OPEN


SNAPSHOT_OCT_12 = {
    "nifty": {"name": "NIFTY 50", "value": "22,363.45", "change": "-156.90 (-0.70%)", "pct": -0.70, "positive": False},
    "sensex": {"name": "SENSEX", "value": "73,010.10", "change": "-560.10 (-0.76%)", "pct": -0.76, "positive": False},
    "breadth": {"advances": 18, "declines": 30, "unchanged": 0},
}


def test_oct_12_after_close_is_a_negative_realized_session_not_a_bullish_opening():
    session = classify_session(at(2026, 10, 12, 17, 0))
    v = composer.realized_verdict(session, SNAPSHOT_OCT_12, "2026-10-12T11:30:00+00:00")
    assert v["kind"] == "realized" and v["direction"] == "Negative" and v["headline"] == "Lower close"
    assert v["ai_generated"] is False and v["confidence"] is None and v["forecast"] is None and v["target_date"] is None
    r = v["reasoning"]
    assert "0.70% lower" in r and "0.76% lower" in r and "30 declined and 18 advanced" in r
    for forbidden in ("bullish", "upside", "gap-up", "opening", "tomorrow"):
        assert forbidden not in r.lower()


def test_flat_and_positive_sessions_and_narrow_gain():
    s = classify_session(at(2026, 10, 12, 17, 0))
    flat = composer.realized_verdict(s, {"nifty": {"value": "22,000", "pct": 0.05}, "breadth": None}, None)
    assert flat["direction"] == "Neutral" and flat["headline"] == "Flat close" and "little changed" in flat["reasoning"]
    narrow = composer.realized_verdict(s, {"nifty": {"value": "22,000", "pct": 0.6}, "breadth": {"advances": 10, "declines": 36, "unchanged": 2}}, None)
    assert narrow["direction"] == "Positive" and "narrow" in narrow["reasoning"]


def test_weekend_and_holiday_say_which_session_they_describe():
    sat = classify_session(at(2026, 10, 10, 12, 0))
    v = composer.realized_verdict(sat, SNAPSHOT_OCT_12, None)
    assert "Fri 9 Oct 2026" in v["reasoning"] and v["session_state"] == WEEKEND
    block = composer.session_block(sat)
    assert block["label"] == "Weekend Review" and "Fri 9 Oct 2026" in block["subtitle"]
    assert composer.session_block(classify_session(at(2026, 10, 20, 12, 0)))["label"] == "Market Holiday"


def test_live_session_uses_present_tense():
    v = composer.realized_verdict(classify_session(at(2026, 10, 12, 11, 0)), SNAPSHOT_OCT_12, None)
    assert "is trading" in v["reasoning"] and v["headline"] == "Trading lower"


def test_missing_or_placeholder_index_data_is_unavailable_never_invented():
    s = classify_session(at(2026, 10, 12, 17, 0))
    for snap in ({}, {"nifty": None}, {"nifty": {"value": "—", "change": "—", "pct": 0.0, "positive": True}}):
        v = composer.realized_verdict(s, snap, None)
        assert v["kind"] == "unavailable" and v["direction"] is None and v["confidence"] is None
    # sensex and breadth missing: still a truthful Nifty-only sentence
    only = composer.realized_verdict(s, {"nifty": SNAPSHOT_OCT_12["nifty"]}, None)
    assert only["direction"] == "Negative" and "Sensex" not in only["reasoning"] and "declined" not in only["reasoning"]


def test_contradictory_benchmarks_are_called_out():
    s = classify_session(at(2026, 10, 12, 17, 0))
    v = composer.realized_verdict(s, {"nifty": {"value": "1", "pct": 0.4}, "sensex": {"value": "2", "pct": -0.4}}, None)
    assert "opposite directions" in v["reasoning"]


def test_parse_pct_handles_signs_and_unicode_minus():
    assert composer.parse_pct("-0.70%") == -0.70 and composer.parse_pct("−0.7%") == -0.7 and composer.parse_pct("+1.2%") == 1.2
    assert composer.parse_pct("▼ 0.7%") == -0.7 and composer.parse_pct("—") is None and composer.parse_pct(None) is None


# ── endpoint: after the close nothing generates a prediction ───────────────────────────────────────────────────────

@pytest.fixture
def stub_endpoint(monkeypatch):
    calls = {"forecast": 0}

    async def snapshot(session):
        return {**SNAPSHOT_OCT_12, "sectors": [], "market_status": brief._status_for(session), "vix": None, "banknifty": None,
                "sentiment_score": None, "movers": {"gainers": [], "losers": []}}

    async def events():
        return []

    async def facts(session):
        return []

    async def historical(events):
        return {"available": False, "message": "n/a"}

    async def watch():
        return []

    async def forecast(session):
        calls["forecast"] += 1
        raise AssertionError("opening prediction must not be generated outside the pre-open window")

    async def boom(*a, **k):
        raise AssertionError("build_opening_prediction was called")

    monkeypatch.setattr(brief, "_get_snapshot", snapshot)
    monkeypatch.setattr(brief, "_read_raw_events", events)
    monkeypatch.setattr(brief, "_get_facts", facts)
    monkeypatch.setattr(brief, "_get_historical_context", historical)
    monkeypatch.setattr(brief, "_get_watch_next", watch)
    monkeypatch.setattr(brief, "_get_forecast_verdict", forecast)
    monkeypatch.setattr(ops, "build_opening_prediction", boom)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("when", [at(2026, 10, 12, 17, 0), at(2026, 10, 10, 12, 0), at(2026, 10, 20, 12, 0), at(2026, 10, 12, 11, 0)])
async def test_non_preopen_rendering_never_invokes_the_opening_prediction(monkeypatch, stub_endpoint, when):
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(when))
    out = await brief.get_daily_brief_intelligence()
    assert stub_endpoint["forecast"] == 0
    assert out["market_verdict"]["kind"] == "realized" and out["market_verdict"]["direction"] == "Negative"
    assert out["session"]["state"] == classify_session(when).state
    assert out["market_verdict"]["target_date"] is None


@pytest.mark.asyncio
async def test_preopen_labels_the_forecast_with_its_target_date(monkeypatch, stub_endpoint):
    async def forecast(session):
        return {"kind": "forecast", "direction": "Neutral", "target_date": session.forecast_target_date.isoformat()}
    monkeypatch.setattr(brief, "_get_forecast_verdict", forecast)
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(at(2026, 10, 12, 8, 30)))
    out = await brief.get_daily_brief_intelligence()
    assert out["market_verdict"]["kind"] == "forecast" and out["market_verdict"]["target_date"] == "2026-10-12"
    assert out["session"]["label"] == "Pre-Market Outlook"


@pytest.mark.asyncio
async def test_fact_refresh_without_forecast_makes_no_ai_call(monkeypatch):
    written = []

    async def fake_upsert(db, fact_key, **fields):
        written.append((fact_key, fields))
        return fields

    async def overview():
        return {"indices": []}

    async def signals():
        return {"brent_crude": {"value": "71.3", "direction": "rising", "change": "+1.2%"}, "usd_inr": {"value": "88.1", "positive": True}}

    async def boom(*a, **k):
        raise AssertionError("build_opening_prediction was called")

    import app.api.market as market
    monkeypatch.setattr(fact_registry, "_upsert", fake_upsert)
    monkeypatch.setattr(market, "market_overview", overview)
    monkeypatch.setattr(ops, "build_opening_prediction", boom)
    monkeypatch.setattr(ops, "_gather_signals", signals)
    await fact_registry.refresh_market_facts(None, include_forecast=False)
    keys = [k for k, _ in written]
    assert any("BRENT_CRUDE" in k for k in keys) and any("USD_INR" in k for k in keys) and not any("VERDICT" in k for k in keys)


@pytest.fixture(autouse=True)
def _no_live_inputs(monkeypatch):
    """The brief's event-window query and overnight-signal gather are data reads; tests never touch the DB or network for them."""
    async def driver_inputs(session, now):
        return [], {}, {}

    async def scenario_inputs():
        return [], None

    monkeypatch.setattr(brief, "_get_driver_inputs", driver_inputs)
    monkeypatch.setattr(brief, "_get_scenario_inputs", scenario_inputs)

    async def company_sectors(symbols):
        return {}

    monkeypatch.setattr(brief, "_get_company_sectors", company_sectors)

"""Daily Brief V2 release-readiness checks: session boundaries (IST/UTC, holidays, weekends), suppressed-forecast containment across
cache, facts API and stored facts, and AI-call permission by session. No network, no LLM."""
from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import app.api.daily_brief_intelligence as brief
import app.api.facts as facts_api
import app.services.fact_registry as fact_registry
import app.services.opening_prediction_service as ops
from app.services.market_session_state import AFTER_CLOSE, HOLIDAY, OPEN, PRE_OPEN, WEEKEND, classify_session

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def at(y, m, d, hh, mm, tz=IST):
    return datetime(y, m, d, hh, mm, tzinfo=tz)


# ── session boundaries ─────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("when,state,ist_date", [
    (at(2026, 10, 12, 18, 29, UTC), PRE_OPEN, "2026-10-12"),        # 23:59 IST Monday, wait: 18:29 UTC = 23:59 IST same day -> after_close
] if False else [
    (at(2026, 10, 12, 3, 44, UTC), PRE_OPEN, "2026-10-12"),         # 09:14 IST
    (at(2026, 10, 12, 3, 45, UTC), OPEN, "2026-10-12"),             # 09:15 IST
    (at(2026, 10, 12, 10, 0, UTC), OPEN, "2026-10-12"),             # 15:30 IST
    (at(2026, 10, 12, 10, 1, UTC), AFTER_CLOSE, "2026-10-12"),      # 15:31 IST
    (at(2026, 10, 12, 18, 29, UTC), AFTER_CLOSE, "2026-10-12"),     # 23:59 IST
    (at(2026, 10, 12, 18, 30, UTC), PRE_OPEN, "2026-10-13"),        # 00:00 IST Tuesday: the IST date rolled, UTC date did not
    (at(2026, 10, 9, 18, 30, UTC), WEEKEND, "2026-10-10"),          # Friday 23:59 UTC-evening -> Saturday 00:00 IST
    (at(2026, 10, 11, 18, 30, UTC), PRE_OPEN, "2026-10-12"),        # Sunday evening UTC = Monday 00:00 IST
    (at(2026, 10, 1, 18, 30, UTC), HOLIDAY, "2026-10-02"),          # Gandhi Jayanti, a Friday
])
def test_ist_utc_boundaries(when, state, ist_date):
    s = classify_session(when)
    assert s.state == state and s.ist_date.isoformat() == ist_date


def test_holiday_and_weekend_chains_skip_to_real_trading_days():
    assert classify_session(at(2026, 10, 5, 8, 0)).reference_session_date == date(2026, 10, 1)       # Mon after Fri holiday + weekend -> Thursday
    assert classify_session(at(2026, 10, 2, 12, 0)).forecast_target_date == date(2026, 10, 5)        # holiday Friday's next opening is Monday
    assert classify_session(at(2026, 10, 3, 12, 0)).forecast_target_date == date(2026, 10, 5)        # Saturday -> Monday
    assert classify_session(at(2026, 12, 25, 12, 0)).state == HOLIDAY


def test_naive_datetime_is_treated_as_ist_not_utc():
    assert classify_session(datetime(2026, 10, 12, 16, 0)).state == AFTER_CLOSE


# ── AI calls by session ─────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def stubs(monkeypatch):
    calls = {"forecast": 0}

    async def snapshot(session):
        return {"nifty": {"value": "22,000", "pct": -0.7}, "sensex": None, "banknifty": None, "vix": None, "breadth": None, "sectors": [],
                "movers": {"gainers": [], "losers": []}, "market_status": brief._status_for(session)}

    async def none_list(*a, **k):
        return []

    async def facts(session):
        return []

    async def hist(events):
        return {"available": False, "message": ""}

    async def forecast(session):
        calls["forecast"] += 1
        return {"kind": "forecast", "headline": "Opening outlook", "direction": "Neutral", "reasoning": "r", "confidence": None, "primary_drivers": [], "risks": [],
                "target_date": session.forecast_target_date.isoformat(), "forecast": {"signals": []}}

    monkeypatch.setattr(brief, "_get_snapshot", snapshot)
    monkeypatch.setattr(brief, "_read_raw_events", none_list)
    monkeypatch.setattr(brief, "_get_facts", facts)
    monkeypatch.setattr(brief, "_get_historical_context", hist)
    monkeypatch.setattr(brief, "_get_watch_next", none_list)
    monkeypatch.setattr(brief, "_get_forecast_verdict", forecast)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("when,expected_calls", [
    (at(2026, 10, 12, 8, 59), 1), (at(2026, 10, 12, 9, 14), 1),                       # pre-open window: the only place a forecast is generated
    (at(2026, 10, 12, 9, 15), 0), (at(2026, 10, 12, 12, 0), 0), (at(2026, 10, 12, 15, 30), 0),
    (at(2026, 10, 12, 15, 31), 0), (at(2026, 10, 12, 23, 59), 0),
    (at(2026, 10, 10, 9, 0), 0), (at(2026, 10, 11, 9, 0), 0), (at(2026, 10, 2, 8, 0), 0),   # weekend, holiday at pre-open time
])
async def test_forecast_generated_only_in_the_preopen_window(monkeypatch, stubs, when, expected_calls):
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(when))
    await brief.get_daily_brief_intelligence()
    assert stubs["forecast"] == expected_calls


# ── suppressed forecast containment ───────────────────────────────────────────────────────────────────────────────

SIGNALS = {
    "gift_nifty": {"value": "22,400", "change": "-0.4%", "positive": False, "status": "live"},
    "india_vix": {"value": "15.2", "level": "MODERATE", "interpretation": "calm"},
    "bank_nifty": {"value": "48,000", "change": "-0.3%", "positive": False},
    "usd_inr": {"value": "88.1", "positive": True}, "brent_crude": {"value": "71", "change": "+1%", "direction": "rising"},
    "fii": {"available": True, "net": -1200.0, "buying": False},
    "us_futures": [{"name": "S&P 500 Fut", "value": "5,000", "pct": "-0.5%", "positive": False}], "asian_markets": [],
    "global_sentiment": {"positive_count": 4, "total": 10, "pct_positive": 40, "label": "Bearish"},
}


@pytest.mark.asyncio
async def test_cached_and_returned_withheld_forecast_carry_no_suppressed_content(monkeypatch):
    AI_PROSE = "SUPPRESSED-AI-PROSE upside bias gap-up"

    async def fake_ai(*a, **k):
        return {"direction": "Positive", "confidence": 62, "range_low": 20, "range_high": 55, "primary_drivers": [AI_PROSE], "risks": ["r"],
                "conflicting_signals": [AI_PROSE], "reasoning": AI_PROSE, "historical_note": AI_PROSE, "uncertainty_note": None, "ai_generated": True}

    async def sig():
        return SIGNALS

    async def ev(db):
        return {"today": [], "tomorrow": [], "mie_signals": []}

    async def hi(s, e):
        return {"similar_events": [], "count": 0, "avg_nifty_1d": None, "historical_accuracy_hint": None}

    async def zones(db):
        return {"sector_setup": [], "companies_in_focus": []}

    for name, fn in (("_run_ai", fake_ai), ("_gather_signals", sig), ("_gather_events", ev), ("_gather_historical", hi), ("_gather_impact_zones", zones)):
        monkeypatch.setattr(ops, name, fn)
    ops._CACHE.clear()
    monkeypatch.setattr("app.services.market_session_state.ist_now", lambda: datetime(2026, 10, 12, 8, 30, tzinfo=IST))
    first = await ops.build_opening_prediction(None)
    cached = await ops.build_opening_prediction(None)                         # served from the cache
    for result in (first, cached, list(ops._CACHE.values())[0][1]):
        blob = repr(result)
        assert AI_PROSE not in blob and "direction_ai" not in blob and "reasoning_ai" not in blob
        p = result["prediction"]
        assert p["direction"] is None and p["confidence"] is None and p["range_low"] is None and p["range_high"] is None
        assert p["primary_drivers"] == [] and result["strategy_note"] is None
        assert p["direction_check"]["withheld"] is True and p["direction_check"]["status"] == "conflict"


@pytest.mark.asyncio
async def test_withheld_forecast_removes_the_stored_forecast_fact(monkeypatch):
    executed = []

    class FakeDB:
        async def execute(self, stmt):
            executed.append(str(stmt))

        async def commit(self):
            executed.append("commit")

    async def overview():
        return {"indices": []}

    async def withheld_build(db):
        return {"signals": SIGNALS, "prediction": {"direction": None, "confidence": None, "ai_generated": True}}

    import app.api.market as market
    monkeypatch.setattr(market, "market_overview", overview)
    monkeypatch.setattr(ops, "build_opening_prediction", withheld_build)
    monkeypatch.setattr(fact_registry, "_upsert", lambda *a, **k: _async_none())
    await fact_registry.refresh_market_facts(FakeDB(), include_forecast=True)
    assert any("DELETE" in e.upper() for e in executed)


async def _async_none():
    return SimpleNamespace()


@pytest.mark.asyncio
@pytest.mark.parametrize("when,macro_kept", [(at(2026, 10, 12, 8, 30), True), (at(2026, 10, 12, 17, 0), False), (at(2026, 10, 10, 12, 0), False)])
async def test_facts_today_api_never_serves_the_forecast_fact_after_the_open(monkeypatch, when, macro_kept):
    seen = {}

    async def fake_get(db, refresh=True, include_forecast=True):
        seen["include_forecast"] = include_forecast
        mk = lambda t, k: SimpleNamespace(fact_key=k, entity_type=t, entity_key=k, name=k, claim="c", value=None, numeric_value=None, unit=None, direction=None,
                                          change_pct=None, confidence=None, source="s", evidence={}, affected_sectors=[], affected_companies=[],
                                          observed_at=None, generated_at=None)
        return [mk("macro", "market:VERDICT:2026-10-12"), mk("market_index", "market:NIFTY_50:2026-10-12")]

    import app.services.market_session_state as mss
    monkeypatch.setattr(fact_registry, "get_facts_for_today", fake_get)
    monkeypatch.setattr(mss, "classify_session", lambda now=None: classify_session(when) if now is None else classify_session(now))
    out = await facts_api.get_today_facts(db=None)
    kinds = [f["entity_type"] for f in out["facts"]]
    assert ("macro" in kinds) is macro_kept and "market_index" in kinds
    assert seen["include_forecast"] is macro_kept


def test_none_never_becomes_zero_or_neutral_in_the_brief_forecast_block():
    import asyncio
    pred = {"direction": None, "confidence": None, "range_low": None, "range_high": None, "primary_drivers": [], "risks": [], "reasoning": "m",
            "ai_generated": True, "direction_check": {"status": "conflict", "withheld": True, "message": "m"}}

    async def fake_build(db):
        return {"prediction": pred, "forecast": {"target_date": "2026-10-12"}, "generated_at": "t"}

    import app.services.opening_prediction_service as svc
    orig = svc.build_opening_prediction
    svc.build_opening_prediction = fake_build
    try:
        v = asyncio.new_event_loop().run_until_complete(brief._get_forecast_verdict(classify_session(at(2026, 10, 12, 8, 30))))
    finally:
        svc.build_opening_prediction = orig
    assert v["direction"] is None and v["confidence"] is None and v["expected_range"] == {"low": None, "high": None}
    assert v["headline"] == "Signals disagree"


@pytest.fixture(autouse=True)
def _no_live_inputs(monkeypatch):
    """The brief's event-window query and overnight-signal gather are data reads; tests never touch the DB or network for them."""
    async def driver_inputs(session, now):
        return [], {}, {}

    async def scenario_inputs():
        return [], None

    monkeypatch.setattr(brief, "_get_driver_inputs", driver_inputs)
    monkeypatch.setattr(brief, "_get_scenario_inputs", scenario_inputs)

"""Daily Brief V2, Phase 1: the opening forecast is validated against deterministic signals, carries its target date and provenance,
has no hardcoded index level or priming example, and never fabricates direction, confidence or range. No network, no LLM call."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app.services.ai_service as ai
import app.services.opening_prediction_service as ops
from app.services import opening_forecast_integrity as integ
from app.services.market_session_state import classify_session

IST = ZoneInfo("Asia/Kolkata")


def rows(*dirs):
    return [{"label": f"s{i}", "direction": d, "detail": ""} for i, d in enumerate(dirs)]


NEG3 = rows("negative", "negative", "negative", "neutral", "contextual")   # Oct 12 style: GIFT / FII / S&P futures all negative


def test_ai_positive_against_negative_signals_is_withheld_not_replaced():
    pred = {"direction": "Positive", "confidence": 62, "range_low": 20, "range_high": 55, "primary_drivers": ["x"],
            "reasoning": "Upside bias and a gap-up open on buying support.", "ai_generated": True}
    out = integ.apply_integrity(pred, "Neutral", NEG3)
    chk = out["direction_check"]
    assert chk["status"] == "conflict" and chk["withheld"] is True
    assert out["direction"] is None and out["confidence"] is None and out["range_low"] is None and out["range_high"] is None
    assert out["direction_ai"] == "Positive" and out["primary_drivers"] == []
    assert "disagree" in out["reasoning"].lower() and "positive" in out["reasoning"].lower()     # states the disagreement
    assert "upside" not in out["reasoning"].lower()                                              # the contradicted prose is not shown


def test_opposite_deterministic_direction_is_a_conflict_even_with_few_signals():
    out = integ.apply_integrity({"direction": "Negative", "confidence": 70, "reasoning": "", "ai_generated": True}, "Positive", rows("positive"))
    assert out["direction_check"]["status"] == "conflict" and out["direction"] is None


def test_aligned_forecast_is_untouched():
    pred = {"direction": "Negative", "confidence": 66, "range_low": -50, "range_high": -15, "primary_drivers": ["a"], "reasoning": "Weak global cues.", "ai_generated": True}
    out = integ.apply_integrity(pred, "Negative", NEG3)
    assert out["direction_check"]["status"] == "aligned" and out["direction"] == "Negative" and out["confidence"] == 66 and out["range_low"] == -50


def test_partial_disagreement_keeps_direction_but_says_so():
    out = integ.apply_integrity({"direction": "Positive", "confidence": 60, "reasoning": "x", "ai_generated": True}, "Neutral", rows("positive", "negative", "neutral"))
    chk = out["direction_check"]
    assert chk["status"] == "partial" and not chk["withheld"] and out["direction"] == "Positive" and "Mixed evidence" in chk["message"]


def test_explanation_that_argues_the_other_way_is_flagged():
    pred = {"direction": "Positive", "confidence": 60, "reasoning": "Selling pressure and a likely gap-down with downside risk.", "ai_generated": True}
    chk = integ.apply_integrity(pred, "Positive", rows("positive", "positive"))["direction_check"]
    assert chk["explanation_leans"] == "Negative" and chk["status"] == "partial"


def test_neutral_ai_is_never_withheld():
    assert not integ.apply_integrity({"direction": "Neutral", "reasoning": ""}, "Negative", NEG3)["direction_check"]["withheld"]


def test_non_directional_signals_are_ignored():
    assert integ.signal_counts(rows("contextual", "neutral", "positive")) == (1, 0)


# ── prompt and cache ───────────────────────────────────────────────────────────────────────────────────────────────

SIGNALS = {
    "gift_nifty": {"value": "22,400", "change": "-0.4%", "positive": False, "status": "live", "source_timestamp": "2026-10-13T02:50:00+00:00"},
    "india_vix": {"value": "15.2", "level": "MODERATE", "interpretation": "calm"},
    "bank_nifty": {"value": "48,000", "change": "-0.3%", "positive": False},
    "usd_inr": {"value": "88.1", "positive": True},
    "brent_crude": {"value": "71", "change": "+1%", "direction": "rising"},
    "fii": {"available": True, "net": -1200.0, "buying": False},
    "us_futures": [{"name": "S&P 500 Fut", "value": "5,000", "pct": "-0.5%", "positive": False}],
    "asian_markets": [],
    "global_sentiment": {"positive_count": 4, "total": 10, "pct_positive": 40, "label": "Bearish"},
}
EVENTS = {"today": [], "tomorrow": [], "mie_signals": []}
HIST = {"similar_events": [], "count": 0, "avg_nifty_1d": None, "historical_accuracy_hint": None}


@pytest.mark.asyncio
async def test_prompt_has_target_date_no_hardcoded_level_and_no_priming_example(monkeypatch):
    seen = {}

    async def fake(prompt, system, max_tokens=200, **kw):
        seen["prompt"] = prompt
        return ""

    monkeypatch.setattr(ai, "_call_with_fallback", fake)
    out = await ops._run_ai(SIGNALS, EVENTS, HIST, None, None, target_date="2026-10-13")
    p = seen["prompt"]
    assert "2026-10-13" in p and "tomorrow" not in p.lower().split("signal layer")[0]
    assert "24,300" not in p and "24300" not in p and "previous close: ~" not in p
    for primed in ('"direction": "Positive"', '"confidence": 68', '"range_low": 20', '"range_high": 55'):
        assert primed not in p
    assert "exactly one of: Positive, Negative, Neutral" in p
    assert out["ai_generated"] is False                      # empty model output -> deterministic fallback


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"direction": "Bullish", "confidence": 70},                  # not a valid direction
    {"confidence": 70},                                          # missing direction
    "not json at all",
])
async def test_invalid_model_output_falls_back_to_deterministic_never_a_default_direction(monkeypatch, payload):
    async def fake(*a, **k):
        return payload if isinstance(payload, str) else json.dumps(payload)

    monkeypatch.setattr(ai, "_call_with_fallback", fake)
    out = await ops._run_ai(SIGNALS, EVENTS, HIST, None, None, target_date="2026-10-13")
    assert out["ai_generated"] is False and out["direction"] in ("Positive", "Negative", "Neutral")


@pytest.mark.asyncio
async def test_missing_confidence_and_range_are_none_not_made_up(monkeypatch):
    async def fake(*a, **k):
        return json.dumps({"direction": "Negative", "primary_drivers": ["a"], "risks": ["b"], "reasoning": "r"})

    monkeypatch.setattr(ai, "_call_with_fallback", fake)
    out = await ops._run_ai(SIGNALS, EVENTS, HIST, None, None, target_date="2026-10-13")
    assert out["ai_generated"] is True and out["confidence"] is None and out["range_low"] is None and out["range_high"] is None


@pytest.mark.asyncio
async def test_inverted_range_is_dropped(monkeypatch):
    async def fake(*a, **k):
        return json.dumps({"direction": "Neutral", "confidence": 55, "range_low": 40, "range_high": 10, "reasoning": "r"})

    monkeypatch.setattr(ai, "_call_with_fallback", fake)
    out = await ops._run_ai(SIGNALS, EVENTS, HIST, None, None, target_date="2026-10-13")
    assert out["range_low"] is None and out["confidence"] == 55


def test_deterministic_fallback_gives_no_invented_point_range():
    out = ops._fallback_prediction(SIGNALS)
    assert out["range_low"] is None and out["range_high"] is None and out["confidence"] >= 45


@pytest.mark.asyncio
async def test_build_attaches_target_provenance_and_cache_is_keyed_by_target(monkeypatch):
    calls = []

    async def fake_ai(signals, events, hist, wctx, wadj, target_date=None):
        calls.append(target_date)
        return {"direction": "Positive", "confidence": 62, "range_low": 20, "range_high": 55, "primary_drivers": ["x"], "risks": [],
                "reasoning": "Upside bias.", "ai_generated": True}

    async def sig():
        return SIGNALS

    async def ev(db):
        return EVENTS

    async def hi(s, e):
        return HIST

    async def zones(db):
        return {"sector_setup": [], "companies_in_focus": []}

    monkeypatch.setattr(ops, "_run_ai", fake_ai)
    monkeypatch.setattr(ops, "_gather_signals", sig)
    monkeypatch.setattr(ops, "_gather_events", ev)
    monkeypatch.setattr(ops, "_gather_historical", hi)
    monkeypatch.setattr(ops, "_gather_impact_zones", zones)
    ops._CACHE.clear()

    monkeypatch.setattr("app.services.market_session_state.ist_now", lambda: datetime(2026, 10, 12, 8, 30, tzinfo=IST))
    pre = await ops.build_opening_prediction(None)
    monkeypatch.setattr("app.services.market_session_state.ist_now", lambda: datetime(2026, 10, 12, 17, 0, tzinfo=IST))
    post = await ops.build_opening_prediction(None)

    assert calls == ["2026-10-12", "2026-10-13"]                       # a different target is never served from the other's cache
    assert pre["forecast"]["target_date"] == "2026-10-12" and post["forecast"]["target_date"] == "2026-10-13"
    assert post["forecast"]["target_session"] == "opening" and post["forecast"]["generated_at"] == post["generated_at"]
    assert post["forecast"]["gift_nifty_source_timestamp"] == SIGNALS["gift_nifty"]["source_timestamp"]
    # Positive AI against negative signals (GIFT, FII, S&P futures all negative): withheld, and no strategy note for a direction not shown
    assert post["prediction"]["direction"] is None and post["prediction"]["direction_check"]["status"] == "conflict"
    assert post["strategy_note"] is None and post["prediction"]["confidence"] is None
    again = await ops.build_opening_prediction(None)
    assert again is post and calls == ["2026-10-12", "2026-10-13"]      # same target + state: cache hit


def test_forecast_session_uses_target_not_calendar_tomorrow_on_weekends():
    assert classify_session(datetime(2026, 10, 10, 12, 0, tzinfo=IST)).forecast_target_date.isoformat() == "2026-10-12"

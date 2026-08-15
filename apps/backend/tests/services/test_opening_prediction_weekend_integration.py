"""
Opening engine + weekend_context integration tests — brief §37/§38, the
most important tests in Phase 1C: prove Tuesday-Friday/no-context output
is byte-for-byte unchanged, prove precedence (Monday fresh data can
override weekend bias), and prove the double-count guard.

Pure unit tests over opening_prediction_service's private helpers —
these are the deterministic-formula functions, not the AI path (no
network/LLM calls here — see the "not live_e2e" marker convention).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import opening_prediction_service as ops
from app.services.weekend_intelligence.context import WeekendContext


def _signals(*, gift_positive=True, pct_positive=75) -> dict:
    return {
        "gift_nifty": {"value": "24500", "change": "+0.5%", "positive": gift_positive},
        "india_vix": {"value": "13.2", "float": 13.2, "level": "LOW", "interpretation": "calm"},
        "bank_nifty": {"value": "51000", "change": "+0.3%", "positive": True},
        "usd_inr": {"value": "83.1", "positive": False},
        "brent_crude": {"value": "78", "change": "-0.2%", "positive": False, "direction": "falling"},
        "fii": {"net": 500, "available": True, "buying": True},
        "us_futures": [], "asian_markets": [], "european_markets": [],
        "global_sentiment": {"positive_count": 3, "total": 4, "pct_positive": pct_positive, "label": "Bullish"},
        "crude_trend": "falling",
    }


def _weekend_context(*, status="ok", bias="positive", confidence=80.0, snapshot_id="s1", version=1,
                      event_ids=frozenset()) -> WeekendContext:
    return WeekendContext(
        target_trading_date="2099-09-07", generated_at=datetime.now(timezone.utc), status=status,
        overall_bias=bias, production_confidence=confidence,
        snapshot_id=snapshot_id, snapshot_version=version,
        meaningful_development_event_ids=event_ids,
    )


# ── Regression: no weekend context -> unchanged behavior ───────────────────

def test_weekend_adjustment_not_applied_when_context_is_none():
    signals = _signals()
    adj = ops._weekend_adjusted_score(signals, None)
    assert adj["applied"] is False
    assert adj["adjustment"] == 0.0
    assert adj["final_direction"] == adj["base_direction"]
    assert adj["final_score"] == adj["base_score"]


def test_fallback_prediction_identical_with_and_without_none_weekend_adjustment():
    """The regression guarantee, stated as a direct equality check:
    _fallback_prediction(signals) and _fallback_prediction(signals, None)
    must be identical, and both must match the pre-Phase-1C
    _base_fallback_score output exactly (minus the added
    weekend_adjustment=None key)."""
    signals = _signals()
    base = ops._base_fallback_score(signals)
    fb_no_arg = ops._fallback_prediction(signals)
    fb_none = ops._fallback_prediction(signals, None)

    for key in base:
        assert fb_no_arg[key] == base[key]
        assert fb_none[key] == base[key]
    assert fb_no_arg["weekend_adjustment"] is None
    assert fb_none["weekend_adjustment"] is None


def test_weekend_prompt_lines_empty_when_no_context():
    assert ops._weekend_prompt_lines({"mie_signals": []}, None) == []


# ── Precedence: Monday fresh data can override weekend bias ────────────────

def test_strongly_negative_monday_overrides_positive_weekend():
    """brief §15's explicit example: positive weekend + strongly negative
    Monday -> Monday must be able to override."""
    bearish_signals = _signals(gift_positive=False, pct_positive=10)  # strongly bearish Monday-fresh
    weekend = _weekend_context(bias="strong_positive", confidence=90.0)
    adj = ops._weekend_adjusted_score(bearish_signals, weekend)
    assert adj["applied"] is True
    assert adj["base_direction"] == "Negative"
    assert adj["final_direction"] == "Negative"  # weekend did NOT flip it
    assert adj["adjustment"] > 0  # weekend pulled toward positive...
    assert abs(adj["adjustment"]) < abs(adj["base_score"])  # ...but stayed bounded/smaller than base


def test_strongly_positive_monday_overrides_negative_weekend():
    bullish_signals = _signals(gift_positive=True, pct_positive=90)
    weekend = _weekend_context(bias="strong_negative", confidence=90.0)
    adj = ops._weekend_adjusted_score(bullish_signals, weekend)
    assert adj["base_direction"] == "Positive"
    assert adj["final_direction"] == "Positive"


def test_positive_weekend_reinforces_positive_monday():
    bullish_signals = _signals(gift_positive=True, pct_positive=70)
    weekend = _weekend_context(bias="positive", confidence=80.0)
    adj = ops._weekend_adjusted_score(bullish_signals, weekend)
    assert adj["base_direction"] == "Positive"
    assert adj["adjustment"] > 0
    assert adj["final_score"] > adj["base_score"]  # reinforced, not diminished


def test_low_confidence_weekend_has_small_or_no_effect():
    signals = _signals()
    weak_weekend = _weekend_context(bias="positive", confidence=5.0)  # below the floor
    adj = ops._weekend_adjusted_score(signals, weak_weekend)
    assert adj["applied"] is False
    assert adj["adjustment"] == 0.0


def test_insufficient_evidence_produces_zero_directional_effect():
    signals = _signals()
    weekend = _weekend_context(status="insufficient_evidence", bias="neutral", confidence=0.0)
    adj = ops._weekend_adjusted_score(signals, weekend)
    assert adj["applied"] is False
    assert adj["adjustment"] == 0.0


def test_degraded_context_has_bounded_nonzero_effect_when_confidence_present():
    signals = _signals()
    weekend = _weekend_context(status="degraded", bias="positive", confidence=45.0)
    adj = ops._weekend_adjusted_score(signals, weekend)
    assert adj["applied"] is True
    assert 0 < abs(adj["adjustment"]) <= 15.0  # bounded by _WEEKEND_BOUNDED_WEIGHT * 100


def test_neutral_bias_weekend_has_no_directional_effect():
    signals = _signals()
    weekend = _weekend_context(bias="neutral", confidence=90.0)
    adj = ops._weekend_adjusted_score(signals, weekend)
    assert adj["applied"] is False


def test_fallback_prediction_reflects_applied_weekend_adjustment():
    bearish_signals = _signals(gift_positive=False, pct_positive=10)
    weekend = _weekend_context(bias="strong_positive", confidence=90.0)
    adj = ops._weekend_adjusted_score(bearish_signals, weekend)
    fb = ops._fallback_prediction(bearish_signals, adj)
    assert fb["direction"] == adj["final_direction"]
    assert any("Weekend intelligence" in d for d in fb["primary_drivers"])
    assert fb["weekend_adjustment"] is adj


# ── Double-count guard (brief §14/§38, mandatory) ───────────────────────────

def test_double_count_note_added_when_mie_event_overlaps_weekend_development():
    events = {"mie_signals": [{"title": "RBI holds repo rate", "urgency": 80, "id": "evt-shared-1"}]}
    weekend = _weekend_context(event_ids=frozenset({"evt-shared-1"}))
    lines = ops._weekend_prompt_lines(events, weekend)
    assert any("SAME underlying event" in l for l in lines)


def test_no_double_count_note_when_no_overlap():
    events = {"mie_signals": [{"title": "Some other headline", "urgency": 80, "id": "evt-other"}]}
    weekend = _weekend_context(event_ids=frozenset({"evt-shared-1"}))
    lines = ops._weekend_prompt_lines(events, weekend)
    assert not any("SAME underlying event" in l for l in lines)


def test_no_double_count_note_when_mie_signal_has_no_id():
    """Defensive: an MIE signal missing its id (shouldn't happen post
    Phase 1C's _gather_events fix, but must not crash) must not be
    treated as a false-positive overlap."""
    events = {"mie_signals": [{"title": "Some headline", "urgency": 80}]}
    weekend = _weekend_context(event_ids=frozenset({"evt-shared-1"}))
    lines = ops._weekend_prompt_lines(events, weekend)
    assert not any("SAME underlying event" in l for l in lines)


# ── Cache key isolation (real bug caught during implementation) ────────────

def test_cache_key_varies_with_weekend_context_identity():
    ops._CACHE.clear()
    ops._cset("opening_prediction", {"marker": "no-context"})
    weekend = _weekend_context(snapshot_id="abc", version=3)
    key = f"opening_prediction:wi:{weekend.snapshot_id}:{weekend.snapshot_version}"
    assert ops._cget(key) is None  # must NOT collide with the no-context cache slot
    ops._CACHE.clear()

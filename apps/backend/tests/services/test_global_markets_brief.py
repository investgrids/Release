"""
Global Markets Intelligence Brief (Phase 1, deterministic) — 2026-10-20.
Pure-function fixtures for every mood boundary, exclusions, empty regions,
calendar states; plus endpoint flag-gating. No LLM, no network.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
import app.api.market as market

client = TestClient(app)

_ALL = ["Dow Jones", "S&P 500", "Nasdaq", "FTSE 100", "DAX", "CAC 40",
        "Nikkei 225", "Hang Seng", "Shanghai Composite", "KOSPI"]


def _idx(name, pct, freshness="live", session="REGULAR", value="100.00"):
    return {"name": name, "flag": "🏳", "value": value,
            "pct": (f"+{pct:.2f}%" if pct >= 0 else f"{pct:.2f}%"),
            "positive": pct >= 0, "source": "Yahoo Finance",
            "source_timestamp": "2026-10-20T07:00:00+00:00", "session": session,
            "timezone": "America/New_York", "freshness": freshness}


def _all(pcts: dict[str, float], **kw):
    return [_idx(n, pcts.get(n, 0.1), **kw) for n in _ALL]


@pytest.fixture(autouse=True)
def _clear_cache():
    market._cache.clear()
    yield
    market._cache.clear()


# ── mood boundaries ──────────────────────────────────────────────────────────

def test_mood_positive_at_70pct():
    pcts = {n: (1.0 if i < 7 else -1.0) for i, n in enumerate(_ALL)}  # 7 up / 3 down
    b = market._build_global_brief(_all(pcts), [])
    assert b["mood"]["label"] == "Positive" and b["mood"]["observed"] == 10 and b["mood"]["positive"] == 7


def test_mood_negative_at_70pct():
    pcts = {n: (-1.0 if i < 8 else 1.0) for i, n in enumerate(_ALL)}  # 8 down
    b = market._build_global_brief(_all(pcts), [])
    assert b["mood"]["label"] == "Negative"


def test_mood_mixed():
    pcts = {n: (1.0 if i < 5 else -1.0) for i, n in enumerate(_ALL)}  # 5/5
    b = market._build_global_brief(_all(pcts), [])
    assert b["mood"]["label"] == "Mixed"


def test_mood_uncertain_when_fewer_than_five_eligible():
    rows = [_idx(n, 1.0) for n in _ALL[:4]] + [_idx(n, 1.0, freshness="unavailable", value="—") for n in _ALL[4:]]
    b = market._build_global_brief(rows, [])
    assert b["mood"]["label"] == "Uncertain" and b["mood"]["observed"] == 4


# ── exclusions: stale/missing never silently influence ───────────────────────

def test_unavailable_and_unknown_excluded_from_mood():
    # 6 strong "up" but unavailable/unknown; 5 eligible down → should read Negative, not Positive.
    rows = ([_idx(n, 5.0, freshness="unavailable", value="—") for n in _ALL[:3]]
            + [_idx(n, 5.0, freshness="unknown") for n in _ALL[3:5]]
            + [_idx(n, -1.0) for n in _ALL[5:]])  # 5 eligible, all down
    b = market._build_global_brief(rows, [])
    assert b["mood"]["observed"] == 5 and b["mood"]["label"] == "Negative"


def test_closed_markets_are_eligible_but_session_preserved():
    rows = _all({n: 1.0 for n in _ALL}, freshness="closed", session="CLOSED")
    b = market._build_global_brief(rows, [])
    assert b["mood"]["observed"] == 10
    amer = next(r for r in b["regions"] if r["region"] == "Americas")
    assert amer["leader"]["session"] == "CLOSED"  # session kept so UI won't imply "live"


# ── regions ──────────────────────────────────────────────────────────────────

def test_regional_leader_and_laggard():
    pcts = {"Dow Jones": 2.0, "S&P 500": 0.5, "Nasdaq": -1.0}
    rows = [_idx("Dow Jones", 2.0), _idx("S&P 500", 0.5), _idx("Nasdaq", -1.0)] + \
           [_idx(n, 0.1) for n in _ALL[3:]]
    b = market._build_global_brief(rows, [])
    amer = next(r for r in b["regions"] if r["region"] == "Americas")
    assert amer["leader"]["name"] == "Dow Jones" and amer["laggard"]["name"] == "Nasdaq"


def test_empty_region_flagged():
    rows = [_idx(n, 1.0) for n in _ALL if n not in ("FTSE 100", "DAX", "CAC 40")]  # no Europe
    b = market._build_global_brief(rows, [])
    eur = next(r for r in b["regions"] if r["region"] == "Europe")
    assert eur["observed"] == 0 and eur["leader"] is None and eur.get("note")


# ── india implications + calendar ────────────────────────────────────────────

def test_india_implications_empty_in_phase1():
    b = market._build_global_brief(_all({n: 1.0 for n in _ALL}), [])
    assert b["india_implications"] == [] and b["india_implications_note"]


def test_what_to_watch_passthrough_and_empty_note():
    with_ev = market._build_global_brief(_all({n: 1.0 for n in _ALL}),
                                         [{"title": "India IIP", "date": "Oct 28, 2026", "category": "india_iip", "description": "High. Source: MOSPI."}])
    assert with_ev["what_to_watch"] and with_ev["what_to_watch_note"] is None
    empty = market._build_global_brief(_all({n: 1.0 for n in _ALL}), [])
    assert empty["what_to_watch"] == [] and "No verified events" in empty["what_to_watch_note"]


def test_cannot_conclude_always_present():
    b = market._build_global_brief(_all({n: 1.0 for n in _ALL}), [])
    assert "do not establish why" in b["cannot_conclude"]


def test_brief_regions_partition_all_ten_indices_exactly_once():
    """Regression: every configured global index belongs to exactly one brief
    region, and no region references an unknown index (the Shanghai-omission
    class of bug)."""
    from collections import Counter
    mapped = [name for names in market._BRIEF_REGIONS.values() for name in names]
    counts = Counter(mapped)
    assert set(mapped) == set(market._GLOBAL_INDICES), "regions must cover exactly the configured indices"
    assert all(c == 1 for c in counts.values()), f"each index appears exactly once: {counts}"
    assert "Shanghai Composite" in mapped


# ── endpoint flag-gating ─────────────────────────────────────────────────────

def test_brief_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "global_markets_freshness_enabled", False)
    resp = client.get("/api/market/global-brief")
    assert resp.status_code == 200 and resp.json() == {"enabled": False}


def test_brief_endpoint_enabled(monkeypatch):
    monkeypatch.setattr(settings, "global_markets_freshness_enabled", True)
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: {
        "price": 100.0, "change": 1.0, "pct": 1.0, "positive": True,
        "source_ts_epoch": __import__("time").time() - 60, "market_state": "REGULAR",
        "timezone": "America/New_York", "volume_24h": None, "quote_currency": "USD",
    })
    resp = client.get("/api/market/global-brief")
    assert resp.status_code == 200
    b = resp.json()
    assert b["enabled"] is True and b["mood"]["label"] == "Positive" and b["india_implications"] == []

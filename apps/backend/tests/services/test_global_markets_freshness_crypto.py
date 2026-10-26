"""
Global Markets enhancement (2026-10-20) — quote freshness + crypto, both
feature-flagged OFF by default. Yahoo calls are mocked; no live network.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
import app.api.market as market

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_market_cache():
    market._cache.clear()
    yield
    market._cache.clear()


# ── Pure freshness evaluator ─────────────────────────────────────────────────

def test_freshness_live_when_regular_and_recent():
    now = time.time()
    assert market._evaluate_freshness(now - 60, "REGULAR", now) == "live"


def test_freshness_delayed_when_regular_but_old():
    now = time.time()
    assert market._evaluate_freshness(now - 5000, "REGULAR", now) == "delayed"


def test_freshness_closed_for_closed_states():
    now = time.time()
    for st in ("CLOSED", "PRE", "PREPRE", "POST", "POSTPOST"):
        assert market._evaluate_freshness(now - 10, st, now) == "closed"


def test_freshness_unknown_when_no_timestamp():
    assert market._evaluate_freshness(None, "REGULAR", time.time()) == "unknown"


def test_freshness_crypto_is_never_closed():
    now = time.time()
    # Even if the (crypto) market_state were something odd, continuous=True means
    # fresh/delayed only — never a closed-session label.
    assert market._evaluate_freshness(now - 60, "REGULAR", now, continuous=True) == "live"
    assert market._evaluate_freshness(now - 5000, "CLOSED", now, continuous=True) == "delayed"


# ── _fetch_global_indices shapes ─────────────────────────────────────────────

def _rich(price=100.0, ts_age=60, state="REGULAR"):
    return {
        "price": price, "change": 1.0, "pct": 1.0, "positive": True,
        "source_ts_epoch": time.time() - ts_age, "market_state": state,
        "timezone": "America/New_York", "volume_24h": None, "quote_currency": "USD",
    }


def test_legacy_shape_has_no_new_fields(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote", lambda t: {"price": 100.0, "change": 1.0, "pct": 1.0, "positive": True})
    rows = market._fetch_global_indices(with_freshness=False)
    assert rows and all(set(r.keys()) == {"name", "flag", "value", "pct", "positive"} for r in rows)


def test_freshness_shape_adds_fields(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich())
    rows = market._fetch_global_indices(with_freshness=True)
    assert rows
    r = rows[0]
    for k in ("source", "source_timestamp", "session", "timezone", "freshness"):
        assert k in r
    assert r["source"] == "Yahoo Finance"
    assert r["freshness"] == "live"


def test_freshness_unavailable_on_failed_fetch(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: None)
    rows = market._fetch_global_indices(with_freshness=True)
    assert rows and all(r["freshness"] == "unavailable" and r["value"] == "—" for r in rows)


# ── crypto ───────────────────────────────────────────────────────────────────

def test_crypto_maps_symbols_and_pairs(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich(price=50000.0))
    rows = market._fetch_crypto()
    syms = {r["symbol"] for r in rows}
    assert syms == {"BTC", "ETH", "SOL", "XRP", "BNB"}
    btc = next(r for r in rows if r["symbol"] == "BTC")
    assert btc["pair"] == "BTC/USD" and btc["quote_currency"] == "USD"
    assert btc["change_window"] == "vs prior UTC-day close"
    assert btc["freshness"] == "live"


def test_crypto_no_fabrication_on_failure(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: None)
    rows = market._fetch_crypto()
    assert rows and all(r["value"] == "—" and r["freshness"] == "unavailable" and r["volume_24h"] is None for r in rows)


# ── endpoints with flags toggled ─────────────────────────────────────────────

def test_global_endpoint_backward_compatible_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "global_markets_freshness_enabled", False)
    monkeypatch.setattr(market, "_yf_quote", lambda t: {"price": 100.0, "change": 1.0, "pct": 1.0, "positive": True})
    resp = client.get("/api/market/global")
    assert resp.status_code == 200
    rows = resp.json()["indices"]
    assert rows and all("freshness" not in r for r in rows)


def test_global_endpoint_additive_when_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "global_markets_freshness_enabled", True)
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich())
    resp = client.get("/api/market/global")
    assert resp.status_code == 200
    rows = resp.json()["indices"]
    assert rows and all("freshness" in r and r["source"] == "Yahoo Finance" for r in rows)


def test_crypto_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "crypto_markets_enabled", False)
    resp = client.get("/api/market/crypto")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False and body["assets"] == []


def test_crypto_endpoint_serves_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "crypto_markets_enabled", True)
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich(price=50000.0))
    resp = client.get("/api/market/crypto")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True and len(body["assets"]) == 5

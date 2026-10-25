"""
US index futures endpoint (Global Markets selector, Phase C — 2026-10-25).
Flag-gated OFF by default; Yahoo calls mocked, no live network.
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


def _rich(price=5000.0, ts_age=60, state="REGULAR"):
    return {
        "price": price, "change": 12.5, "pct": 0.25, "positive": True,
        "source_ts_epoch": time.time() - ts_age, "market_state": state,
        "timezone": "America/New_York", "volume_24h": None, "quote_currency": "USD",
    }


# ── _fetch_us_futures shape ──────────────────────────────────────────────────

def test_us_futures_shape_and_provenance(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich())
    rows = market._fetch_us_futures()
    assert rows and len(rows) == len(market._US_FUTURES_TICKERS)
    for r in rows:
        assert r["instrument"] == "future"
        assert r["source"] == "Yahoo Finance"
        assert r["source_timestamp"] is not None
        assert r["freshness"] == "live"          # continuous + recent
        assert r["change"] != "—" and r["pct"].endswith("%")


def test_us_futures_never_closed_label(monkeypatch):
    # Futures are continuous — a stale quote is 'delayed', never 'closed'.
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich(ts_age=5000, state="CLOSED"))
    rows = market._fetch_us_futures()
    assert rows and all(r["freshness"] == "delayed" for r in rows)


def test_us_futures_no_fabrication_on_failure(monkeypatch):
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: None)
    rows = market._fetch_us_futures()
    assert rows and all(r["value"] == "—" and r["freshness"] == "unavailable" for r in rows)


# ── /api/market/futures gating ───────────────────────────────────────────────

def test_futures_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "global_markets_freshness_enabled", False)
    resp = client.get("/api/market/futures")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False and body["futures"] == []


def test_futures_endpoint_serves_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "global_markets_freshness_enabled", True)
    monkeypatch.setattr(market, "_yf_quote_rich", lambda t: _rich())
    resp = client.get("/api/market/futures")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True and body["market"] == "US"
    assert len(body["futures"]) == len(market._US_FUTURES_TICKERS)
    assert all(f["instrument"] == "future" for f in body["futures"])

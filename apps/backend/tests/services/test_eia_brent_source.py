"""
EIA Brent source tests — deterministic, fully mocked (no network, no real key).

Covers valid mapping, missing key, HTTP error, timeout, malformed JSON, empty
observations, stale data, unexpected units, and invalid values. A test key string
is used; it is not a real credential.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

import app.services.macro_rates.eia_brent_source as eia
from app.services.macro_rates.eia_brent_source import fetch_eia_brent

_NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
_KEY = "TEST_KEY_NOT_REAL"


class _FakeResp:
    def __init__(self, payload=None, *, raise_exc=None, json_exc=None):
        self._payload = payload
        self._raise = raise_exc
        self._json_exc = json_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._payload


class _FakeClient:
    def __init__(self, resp=None, get_exc=None):
        self._resp = resp
        self._get_exc = get_exc
        self.last_params = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        self.last_params = params
        if self._get_exc:
            raise self._get_exc
        return self._resp


def _install(monkeypatch, *, resp=None, get_exc=None):
    client = _FakeClient(resp=resp, get_exc=get_exc)
    monkeypatch.setattr(eia.httpx, "Client", lambda *a, **k: client)
    return client


def _payload(rows):
    return {"response": {"data": rows}}


def test_valid_response_maps_brent(monkeypatch):
    rows = [
        {"period": "2026-10-23", "series": "RBRTE", "value": 83.47, "units": "$/BBL"},
        {"period": "2026-10-22", "series": "RBRTE", "value": 81.13, "units": "$/BBL"},
    ]
    client = _install(monkeypatch, resp=_FakeResp(_payload(rows)))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "live"
    assert st.value == 83.47
    assert st.latest_date == date(2026, 10, 23)
    assert st.change == 2.34
    assert st.pct == 2.88
    assert st.unit == "USD / bbl"
    assert st.source == "U.S. Energy Information Administration"
    assert st.stale is False and st.age_days == 3
    # key is sent as a query param, not interpolated into a logged URL
    assert client.last_params["api_key"] == _KEY


def test_missing_key_no_http(monkeypatch):
    # if Client is constructed the test key check failed; make it explode if called
    monkeypatch.setattr(eia.httpx, "Client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP on missing key")))
    st = fetch_eia_brent("", now=_NOW)
    assert st.status == "unavailable" and st.reason == "missing_api_key"


def test_http_error(monkeypatch):
    err = httpx.HTTPStatusError("boom", request=httpx.Request("GET", eia._EIA_URL),
                                response=httpx.Response(503))
    _install(monkeypatch, resp=_FakeResp(raise_exc=err))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "http_503"


def test_timeout(monkeypatch):
    _install(monkeypatch, get_exc=httpx.TimeoutException("slow"))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "timeout"


def test_malformed_json(monkeypatch):
    _install(monkeypatch, resp=_FakeResp(json_exc=ValueError("not json")))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "request_error"


def test_empty_observations(monkeypatch):
    _install(monkeypatch, resp=_FakeResp(_payload([])))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "no_data_rows"


def test_stale_data_flagged(monkeypatch):
    rows = [
        {"period": "2026-10-01", "series": "RBRTE", "value": 80.0, "units": "$/BBL"},
        {"period": "2026-09-30", "series": "RBRTE", "value": 79.0, "units": "$/BBL"},
    ]
    _install(monkeypatch, resp=_FakeResp(_payload(rows)))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "live" and st.value == 80.0
    assert st.stale is True and st.age_days == 25   # > 10-day threshold


def test_unexpected_units_refused(monkeypatch):
    rows = [{"period": "2026-10-23", "series": "RBRTE", "value": 83.47, "units": "EUR/MWh"}]
    _install(monkeypatch, resp=_FakeResp(_payload(rows)))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "unexpected_units"


def test_wrong_series_refused(monkeypatch):
    rows = [{"period": "2026-10-23", "series": "WTISPLC", "value": 80.0, "units": "$/BBL"}]
    _install(monkeypatch, resp=_FakeResp(_payload(rows)))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "series_mismatch"


def test_invalid_value_skipped(monkeypatch):
    rows = [
        {"period": "2026-10-23", "series": "RBRTE", "value": None, "units": "$/BBL"},
        {"period": "2026-10-22", "series": "RBRTE", "value": "n/a", "units": "$/BBL"},
    ]
    _install(monkeypatch, resp=_FakeResp(_payload(rows)))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "unavailable" and st.reason == "no_valid_observations"


def test_single_observation_no_change(monkeypatch):
    rows = [{"period": "2026-10-23", "series": "RBRTE", "value": 83.47, "units": "$/BBL"}]
    _install(monkeypatch, resp=_FakeResp(_payload(rows)))
    st = fetch_eia_brent(_KEY, now=_NOW)
    assert st.status == "live" and st.value == 83.47
    assert st.change is None and st.pct is None

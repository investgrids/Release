"""app/services/frontend_revalidate.py -- the shared on-demand ISR
revalidation notifier (2026-09-20), extracted from image_worker.py's
original article-only version when opportunity-v2-canary-promote/-revert
gained the same need. Real production finding: reverting a canary left
its page publicly serving stale content past its own revalidate window
with no self-clearing observed. Covers: correct header (not body) auth,
correct kind/slug payload, silent no-op when unconfigured, and silent
failure on a network/HTTP error (this must never raise into or block the
caller's own database transaction).
"""
from __future__ import annotations

import pytest

import app.services.frontend_revalidate as revalidate_module
from app.services.frontend_revalidate import notify_frontend_revalidate


class _FakeSettings:
    frontend_url = "https://example.test"
    revalidate_secret = "real-secret-value"


class _UnconfiguredSettings:
    frontend_url = ""
    revalidate_secret = ""


@pytest.mark.asyncio
async def test_no_op_when_frontend_url_or_secret_missing(monkeypatch):
    monkeypatch.setattr(revalidate_module, "settings", _UnconfiguredSettings())
    calls = []

    class _ExplodingClient:
        def __init__(self, *a, **kw):
            calls.append("client_constructed")

    monkeypatch.setattr("httpx.AsyncClient", _ExplodingClient)
    await notify_frontend_revalidate("some-slug", kind="opportunity_v2")
    assert calls == [], "must not attempt any network call when unconfigured"


@pytest.mark.asyncio
async def test_sends_secret_as_header_never_in_body(monkeypatch):
    monkeypatch.setattr(revalidate_module, "settings", _FakeSettings())
    captured = {}

    class _FakeResponse:
        status_code = 200

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    await notify_frontend_revalidate("adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b", kind="opportunity_v2")

    assert captured["url"] == "https://example.test/api/revalidate"
    assert captured["json"] == {"slug": "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b", "kind": "opportunity_v2"}
    assert captured["headers"] == {"X-Revalidate-Secret": "real-secret-value"}
    assert "secret" not in captured["json"], "the secret must travel as a header, never inside the JSON body"


@pytest.mark.asyncio
async def test_network_failure_is_swallowed_never_raised(monkeypatch):
    monkeypatch.setattr(revalidate_module, "settings", _FakeSettings())

    class _FailingAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr("httpx.AsyncClient", _FailingAsyncClient)
    await notify_frontend_revalidate("some-slug", kind="article")  # must not raise

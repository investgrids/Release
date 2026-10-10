"""Railway cost follow-up: keep crawlers off the API host, bound the SSE stream, and cache the event detail endpoint. No provider, no network."""
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.testclient import TestClient

from app.core.robots_guard import ROBOTS_TXT, RobotsHeaderMiddleware


def _app():
    app = FastAPI()
    app.add_middleware(RobotsHeaderMiddleware)

    @app.get("/api/events/1")
    async def ev():
        return {"ok": True}

    @app.get("/api/media/x.jpg")
    async def media():
        return PlainTextResponse("img")

    @app.get("/api/stream")
    async def stream():
        async def gen():
            yield "data: 1\n\n"
            yield "data: 2\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def test_robots_txt_disallows_everything_except_media():
    assert "Disallow: /" in ROBOTS_TXT and "Allow: /api/media/" in ROBOTS_TXT
    assert ROBOTS_TXT.index("Allow: /api/media/") < ROBOTS_TXT.index("Disallow: /")


def test_api_responses_are_marked_noindex_but_media_is_not():
    c = TestClient(_app())
    assert "noindex" in c.get("/api/events/1").headers["x-robots-tag"]
    assert "x-robots-tag" not in c.get("/api/media/x.jpg").headers      # hero images and og:image must stay indexable and fetchable


def test_streaming_responses_pass_through_with_the_header_and_intact_body():
    r = TestClient(_app()).get("/api/stream")
    assert r.text == "data: 1\n\ndata: 2\n\n"
    assert "noindex" in r.headers["x-robots-tag"]


def test_the_real_app_serves_robots_txt():
    from app.main import app
    r = TestClient(app).get("/robots.txt")
    assert r.status_code == 200 and r.text == ROBOTS_TXT


# ── SSE lifetime ──────────────────────────────────────────────────────────────────────────────────────────────

def test_sse_stream_closes_itself_after_its_lifetime_and_tells_the_client_to_reconnect():
    from app.api import stream

    async def run():
        q: asyncio.Queue = asyncio.Queue()
        chunks = []
        t0 = time.monotonic()
        async for c in stream._generate(q, max_seconds=0.0):
            chunks.append(c)
        return chunks, time.monotonic() - t0

    chunks, took = asyncio.run(run())
    assert chunks[0].startswith(f"retry: {stream.SSE_RETRY_MS}")          # EventSource reconnect hint
    assert "event: connected" in chunks[0]
    assert chunks[-1].startswith("event: reconnect")
    assert took < 1.0                                                   # it ended instead of waiting for the next queue item


def test_sse_default_lifetime_is_bounded():
    from app.api import stream
    assert 0 < stream.SSE_MAX_SECONDS <= 600


# ── event detail cache ────────────────────────────────────────────────────────────────────────────────────────

class _Detail:
    def model_dump(self, mode="json"):
        return {"id": "e1", "title": "x"}


def test_event_detail_is_cached_and_a_hit_skips_the_database(monkeypatch):
    from app.api import events

    store: dict = {}
    calls = {"build": 0}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=0):
        store[key] = value
        store["_ttl"] = ttl

    class FakeService:
        def __init__(self, db):
            pass

        async def get_event_detail(self, event_id):
            calls["build"] += 1
            return _Detail()

    monkeypatch.setattr(events, "cache_get", fake_get)
    monkeypatch.setattr(events, "cache_set", fake_set)
    monkeypatch.setattr(events, "EventService", FakeService)

    first = asyncio.run(events.get_event_detail("e1", db=None))
    second = asyncio.run(events.get_event_detail("e1", db=None))
    assert calls["build"] == 1                                          # the second request never reached the service
    assert second == {"id": "e1", "title": "x"}
    assert store["_ttl"] == events.EVENT_DETAIL_CACHE_TTL == 120
    assert first is not None


def test_a_missing_event_is_a_404_and_is_never_cached(monkeypatch):
    from fastapi import HTTPException
    from app.api import events

    store: dict = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=0):
        store[key] = value

    class FakeService:
        def __init__(self, db):
            pass

        async def get_event_detail(self, event_id):
            return None

    monkeypatch.setattr(events, "cache_get", fake_get)
    monkeypatch.setattr(events, "cache_set", fake_set)
    monkeypatch.setattr(events, "EventService", FakeService)
    try:
        asyncio.run(events.get_event_detail("nope", db=None))
        raise AssertionError("expected a 404")
    except HTTPException as e:
        assert e.status_code == 404
    assert store == {}


def test_a_cache_write_failure_never_fails_the_request(monkeypatch):
    from app.api import events

    async def fake_get(key):
        return None

    async def broken_set(key, value, ttl=0):
        raise RuntimeError("redis down")

    class FakeService:
        def __init__(self, db):
            pass

        async def get_event_detail(self, event_id):
            return _Detail()

    monkeypatch.setattr(events, "cache_get", fake_get)
    monkeypatch.setattr(events, "cache_set", broken_set)
    monkeypatch.setattr(events, "EventService", FakeService)
    assert asyncio.run(events.get_event_detail("e1", db=None)) is not None

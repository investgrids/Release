"""
Provenance contract -- prompt-builder remediation, Path 3 (2026-10-19):
page_intelligence_service.py's get_company_intelligence() and
get_home_intelligence() must never admit a rule_based_fallback/unknown
event's one_liner into their cached, AI-generated context. (
get_event_intelligence() never queries EventTriage.one_liner directly --
confirmed during the read-only investigation -- so it needs no change
here; its only EventTriage-adjacent input is story_engine's narrative,
already filtered upstream by Path 2.)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.services import page_intelligence_service as svc


def _tag():
    return uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _clear_module_cache():
    svc._CACHE.clear()
    yield
    svc._CACHE.clear()


async def _cleanup(triage_ids: list[str]):
    async with AsyncSessionLocal() as db:
        if triage_ids:
            await db.execute(delete(EventTriage).where(EventTriage.id.in_(triage_ids)))
        await db.commit()


# ── get_company_intelligence() ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_company_all_fallback_coverage_never_reaches_the_ai_call(monkeypatch):
    """Zero eligible rows after provenance filtering must behave exactly
    like zero rows at all -- the pre-existing honest _fallback() path,
    never a company-specific AI call built from unverified headlines."""
    tag = _tag()
    target_symbol = f"FBCO{tag}"[:20].upper()

    fallback_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=fallback_id, event_id=f"ev-fb-{tag}", source="news",
            headline=f"{target_symbol} raw unprocessed headline", one_liner=f"{target_symbol} raw unprocessed headline",
            urgency=8, importance=8, confidence=4, sentiment="neutral", triage_source="rule_based_fallback",
            tickers=[target_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    called = {"ai": False}

    async def _fake_ai_call(*a, **kw):
        called["ai"] = True
        return {"market_story": "should not happen"}

    monkeypatch.setattr(svc, "_ai_call", _fake_ai_call)

    try:
        result = await svc.get_company_intelligence(target_symbol)
        assert called["ai"] is False, "a fallback-only company must never reach the AI call"
        assert result["market_story"] == ""
    finally:
        await _cleanup([fallback_id])


@pytest.mark.asyncio
async def test_company_mixed_provenance_only_passes_the_eligible_row(monkeypatch):
    tag = _tag()
    target_symbol = f"MIXCO{tag}"[:20].upper()

    fallback_id = str(uuid.uuid4())
    ai_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=fallback_id, event_id=f"ev-fb-{tag}", source="news",
            headline=f"{target_symbol} raw unprocessed headline", one_liner=f"{target_symbol} raw unprocessed headline",
            urgency=9, importance=8, confidence=4, sentiment="neutral", triage_source="rule_based_fallback",
            tickers=[target_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        db.add(EventTriage(
            id=ai_id, event_id=f"ev-ai-{tag}", source="news",
            headline=f"{target_symbol} announces real quarterly results", one_liner=f"{target_symbol} beats estimates on strong demand",
            urgency=6, importance=6, confidence=70, sentiment="bullish", triage_source="ai",
            tickers=[target_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    captured = {}

    async def _fake_ai_call(ctype, cid, context_data, source_count=0, similar=None):
        captured["context_data"] = context_data
        return {"market_story": "real", "confidence": {"level": "Low", "score": 30, "reasons": [], "breakdown": {}}}

    monkeypatch.setattr(svc, "_ai_call", _fake_ai_call)

    try:
        await svc.get_company_intelligence(target_symbol)
        assert "announces real quarterly results" in captured["context_data"]
        assert "beats estimates on strong demand" in captured["context_data"]
        assert "raw unprocessed headline" not in captured["context_data"]
    finally:
        await _cleanup([fallback_id, ai_id])


@pytest.mark.asyncio
async def test_fallback_row_headline_is_never_duplicated_as_a_second_evidence_line(monkeypatch):
    """Structural guarantee independent of the provenance filter: even if
    a row's one_liner equals its own headline text (always true for
    rule_based_fallback), it must never be printed twice."""
    tag = _tag()
    target_symbol = f"DUPCO{tag}"[:20].upper()
    headline = f"{target_symbol} raw unprocessed headline text"

    # AI-sourced row (so it survives the provenance filter) whose one_liner
    # happens to equal its own headline -- tests the dedup check itself,
    # independent of the provenance filter which already excludes the
    # fallback case this guards against.
    row_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=row_id, event_id=f"ev-dup-{tag}", source="news",
            headline=headline, one_liner=headline,
            urgency=6, importance=6, confidence=70, sentiment="neutral", triage_source="ai",
            tickers=[target_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    captured = {}

    async def _fake_ai_call(ctype, cid, context_data, source_count=0, similar=None):
        captured["context_data"] = context_data
        return {"market_story": "real", "confidence": {"level": "Low", "score": 30, "reasons": [], "breakdown": {}}}

    monkeypatch.setattr(svc, "_ai_call", _fake_ai_call)

    try:
        await svc.get_company_intelligence(target_symbol)
        assert captured["context_data"].count(headline) == 1, "identical headline/one_liner text must appear only once"
    finally:
        await _cleanup([row_id])


# ── get_home_intelligence() ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_home_intelligence_excludes_fallback_events_from_live_context(monkeypatch):
    tag = _tag()
    fallback_event = {
        "id": f"home-fb-{tag}", "urgency": 9, "one_liner": f"Raw fallback headline {tag}",
        "headline": f"Raw fallback headline {tag}", "triage_source": "rule_based_fallback",
    }
    ai_event = {
        "id": f"home-ai-{tag}", "urgency": 8, "one_liner": f"Genuine AI synthesis {tag}",
        "headline": f"Headline {tag}", "triage_source": "ai",
    }

    async def _fake_get_intelligence_state():
        return {"signals": {}, "top_events": [fallback_event, ai_event]}

    monkeypatch.setattr("app.services.intelligence.engine.get_intelligence_state", _fake_get_intelligence_state)

    # Hardening (2026-10-19): this test was found flaky under full-suite
    # ordering even though its 3 siblings (which exercise the identical
    # provenance-filter code path) were stable. The function also makes a
    # real Event/NewsArticle DB query and a real find_similar_events() call
    # that this test never needed and never asserted on -- full-suite state
    # from unrelated tests (leftover rows, a slow/erroring historical-memory
    # call) could plausibly perturb it. Isolating both removes every
    # dependency this test doesn't actually need, leaving only the
    # provenance-filter behavior under test.
    class _FakeScalars:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return _FakeScalars(self._rows)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *a, **kw):
            return _FakeResult([])

    monkeypatch.setattr("app.db.session.AsyncSessionLocal", lambda: _FakeSession())

    async def _fake_find_similar_events(*a, **kw):
        return []

    monkeypatch.setattr(
        "app.services.historical_memory_service.find_similar_events",
        _fake_find_similar_events,
    )

    captured = {}

    async def _fake_ai_call(ctype, cid, context_data, source_count=0, similar=None):
        captured["context_data"] = context_data
        return {"market_story": "real", "confidence": {"level": "Low", "score": 30, "reasons": [], "breakdown": {}}}

    monkeypatch.setattr(svc, "_ai_call", _fake_ai_call)

    try:
        await svc.get_home_intelligence()
        assert f"Genuine AI synthesis {tag}" in captured["context_data"]
        assert f"Raw fallback headline {tag}" not in captured["context_data"]
    finally:
        pass

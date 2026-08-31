"""
get_company_intelligence — real DB-backed tests for the 2026-08-25
wrong-entity-intelligence fix.

Real bug, exactly reproduced live before this fix: a company with zero
real EventTriage/NewsArticle rows mentioning it fell back to the most
recent rows for ANY company, labeled "RECENT MARKET EVENTS RELATED TO
THIS COMPANY" in the LLM prompt. Live-confirmed: 3IINFOLTD (no real
coverage) was fed IIFL Finance's real, unrelated Rs 963 crore tax-demand
story under that label, and the model wrote "3IINFOLTD (IIFL Finance)
faces headwinds..." — a real company's real content, wrongly attributed
to a different company. Systemic, not isolated: any company with zero
real recent coverage hit this same path.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.intelligence import EventTriage
from app.db.models_legacy import NewsArticle
from app.db.session import AsyncSessionLocal
from app.services import page_intelligence_service as svc


def _tag():
    return uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _clear_module_cache():
    """The service's own in-memory _CACHE dict persists across tests in
    the same process (it's module-level, not per-request) — clear it so
    one test's cached result can't leak into another's assertions."""
    svc._CACHE.clear()
    yield
    svc._CACHE.clear()


async def _cleanup(triage_ids: list[str], news_ids: list[int]):
    async with AsyncSessionLocal() as db:
        if triage_ids:
            await db.execute(delete(EventTriage).where(EventTriage.id.in_(triage_ids)))
        if news_ids:
            await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(news_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_company_with_zero_real_coverage_never_borrows_another_companys_content():
    """The real regression case: a real, distinct company symbol
    (matching neither headline nor tickers of any real row) must get the
    honest _fallback() response — never another company's real
    unrelated content, and never even reach the AI call."""
    tag = _tag()
    unrelated_symbol = f"UNRELATEDCO{tag}"[:20].upper()
    target_symbol = f"TARGETCO{tag}"[:20].upper()

    triage_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=triage_id, event_id=f"ev-{tag}", source="news", headline=f"{unrelated_symbol} faces a real unrelated crisis",
            urgency=8, importance=8, confidence=80, sentiment="bearish",
            tickers=[unrelated_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    try:
        result = await svc.get_company_intelligence(target_symbol)
        assert result["confidence"]["reasons"] == ["Insufficient data"]
        assert result["confidence"]["score"] == 20
        assert result["market_story"] == ""
        # The real regression assertion: the unrelated company's real
        # headline text must never appear anywhere in the response.
        assert unrelated_symbol not in str(result)
    finally:
        await _cleanup([triage_id], [])


@pytest.mark.asyncio
async def test_company_with_real_coverage_uses_only_its_own_real_matched_rows(monkeypatch):
    """When a company DOES have real matching rows, the AI call must be
    made with only that company's real matched data — proven by
    intercepting _ai_call's real context_data argument, not just
    checking the final (LLM-dependent) output."""
    tag = _tag()
    target_symbol = f"REALCO{tag}"[:20].upper()
    other_symbol = f"OTHERCO{tag}"[:20].upper()

    real_triage_id = str(uuid.uuid4())
    other_triage_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=real_triage_id, event_id=f"ev-real-{tag}", source="news",
            headline=f"{target_symbol} announces real quarterly results",
            urgency=6, importance=6, confidence=70, sentiment="neutral",
            tickers=[target_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        db.add(EventTriage(
            id=other_triage_id, event_id=f"ev-other-{tag}", source="news",
            headline=f"{other_symbol} unrelated real headline",
            urgency=9, importance=9, confidence=90, sentiment="bearish",
            tickers=[other_symbol], triaged_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    captured = {}

    async def _fake_ai_call(ctype, cid, context_data, source_count=0, similar=None):
        captured["context_data"] = context_data
        captured["source_count"] = source_count
        return {"market_story": "real", "confidence": {"level": "Low", "score": 30, "reasons": [], "breakdown": {}}}

    monkeypatch.setattr(svc, "_ai_call", _fake_ai_call)

    try:
        result = await svc.get_company_intelligence(target_symbol)
        assert "context_data" in captured, "the AI call must be reached when real matching data exists"
        assert target_symbol in captured["context_data"]
        assert f"{target_symbol} announces real quarterly results" in captured["context_data"]
        # The real regression assertion: the OTHER company's real
        # headline must never be included as this company's context.
        assert other_symbol not in captured["context_data"]
    finally:
        await _cleanup([real_triage_id, other_triage_id], [])

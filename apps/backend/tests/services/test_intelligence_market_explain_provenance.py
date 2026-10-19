"""
Provenance contract -- prompt-builder remediation, Path 1 (2026-10-19):
api/intelligence_market.py::explain_change() explicitly asks an LLM "what
caused this symbol to move" and returns the result directly to the user
with no downstream validation -- the highest-exposure of the three
prompt-builder paths found during the release audit. Fallback/unknown
provenance events must never enter the causal evidence set; with zero
eligible events, the endpoint must return an honest insufficient-evidence
response instead of asking the model to invent a cause.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage

client = TestClient(app)
_SYMBOL = "RELPROVTEST"
_IDS = [f"explain-prov-{i}" for i in range(2)]


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id.in_(_IDS)))
        await db.commit()


async def _seed(*rows: tuple[str, str]):
    """Each row: (event_id, triage_source)."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        for event_id, triage_source in rows:
            db.add(EventTriage(
                id=f"t-{event_id}", event_id=event_id, source="news",
                headline=f"{_SYMBOL} headline for {event_id}", urgency=8, importance=6, confidence=5,
                one_liner=f"{_SYMBOL} raw or AI one-liner for {event_id}", triage_source=triage_source,
                tickers=[_SYMBOL], triaged_at=now,
            ))
        await db.commit()


def test_all_fallback_evidence_returns_insufficient_evidence_without_calling_the_model():
    import asyncio
    asyncio.run(_cleanup())
    try:
        asyncio.run(_seed((_IDS[0], "rule_based_fallback")))
        with patch("app.services.ai_service._call_with_fallback", new=AsyncMock()) as mock_call:
            resp = client.get("/api/intelligence/market/explain", params={"symbol": _SYMBOL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["events_used"] == 0
        assert "Not enough verified" in data["explanation"]
        mock_call.assert_not_called()
    finally:
        asyncio.run(_cleanup())


def test_ai_sourced_evidence_is_used_and_model_is_called():
    import asyncio
    asyncio.run(_cleanup())
    try:
        asyncio.run(_seed((_IDS[0], "ai")))
        with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(return_value="Test explanation.")) as mock_call:
            resp = client.get("/api/intelligence/market/explain", params={"symbol": _SYMBOL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["events_used"] == 1
        assert data["explanation"] == "Test explanation."
        mock_call.assert_called_once()
        prompt = mock_call.call_args[0][0]
        assert "raw or AI one-liner" in prompt
        assert "not independently verified facts" in prompt
    finally:
        asyncio.run(_cleanup())


def test_mixed_provenance_only_uses_the_eligible_event():
    import asyncio
    asyncio.run(_cleanup())
    try:
        asyncio.run(_seed(
            (_IDS[0], "rule_based_fallback"), (_IDS[1], "ai"),
        ))
        with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(return_value="Test explanation.")) as mock_call:
            resp = client.get("/api/intelligence/market/explain", params={"symbol": _SYMBOL})
        data = resp.json()
        assert data["events_used"] == 1
        prompt = mock_call.call_args[0][0]
        assert _IDS[1] in prompt
        assert _IDS[0] not in prompt
    finally:
        asyncio.run(_cleanup())

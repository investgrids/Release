"""
CD3-D (D6) — deepseek_provider.py's _safe_json_call fallback dicts are now
tagged with integrity_status (see test_deepseek_provider_fallback_
integrity.py), and event_pipeline.py threads that tag through
merged_summary into Event.ai_summary at persistence time. This suite
confirms the tag survives the LAST hop -- event_service.py's response
construction and EventDetailResponse's Pydantic response_model
serialization -- through the real GET /api/events/{id} route via
TestClient, per the ecac930 lesson (a service-level test alone would not
have caught CD3-B's own schema-stripping bug, and would not catch one
here either).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.services.measurement_semantics import IntegrityStatus

client = TestClient(app)


async def _cleanup(event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()


@pytest.mark.asyncio
async def test_real_api_response_surfaces_fallback_integrity_status_on_all_three_surfaces():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-fallback-integrity-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event for D6 fallback-integrity survival check",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
                # Simulates exactly what event_pipeline.py persists when
                # summarize_event and generate_impact_analysis both hit
                # their fallback (real shape, real key names).
                ai_summary={
                    "summary": "Test event for D6 fallback-integrity survival check",
                    "why_it_matters": "This event may have market implications.",
                    "key_bullets": ["Test event for D6 fallback-integrity survival check"],
                    "immediate_impact": "neutral", "long_term_impact": "neutral",
                    "risk_factors": [], "opportunities": [],
                    "integrity_status": IntegrityStatus.FALLBACK.value,
                    "classification": {"category": "macro", "confidence": 0.7, "subcategory": "general",
                                        "integrity_status": IntegrityStatus.FALLBACK.value},
                    "market_reaction": {"short_term": "neutral", "medium_term": "neutral",
                                          "volatility": "medium", "sentiment": "neutral"},
                    "analysis": {"bull_case": "Positive fundamentals could drive upside.",
                                  "bear_case": "Macro headwinds may cap gains.",
                                  "base_case": "Neutral near-term outlook.",
                                  "key_risks": [], "catalysts": []},
                    "narrative_integrity_status": IntegrityStatus.FALLBACK.value,
                },
            ))
            await db.commit()

        resp = client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["summary"]["integrity_status"] == IntegrityStatus.FALLBACK.value
        assert body["marketReaction"]["integrity_status"] == IntegrityStatus.FALLBACK.value
        assert body["aiAnalysis"]["integrity_status"] == IntegrityStatus.FALLBACK.value
        assert body["aiAnalysis"]["classification"]["integrity_status"] == IntegrityStatus.FALLBACK.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_real_api_response_valid_generation_is_tagged_valid_not_fallback():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-valid-integrity-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event, real generation",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
                ai_summary={
                    "summary": "Real generated summary.", "why_it_matters": "Real reason.",
                    "key_bullets": ["Real bullet"], "immediate_impact": "positive",
                    "long_term_impact": "positive", "risk_factors": [], "opportunities": [],
                    "integrity_status": IntegrityStatus.VALID.value,
                    "classification": {"category": "corporate", "confidence": 0.9, "subcategory": "capex",
                                        "integrity_status": IntegrityStatus.VALID.value},
                    "market_reaction": {"short_term": "bullish", "medium_term": "neutral",
                                          "volatility": "low", "sentiment": "positive"},
                    "analysis": {"bull_case": "Real bull case.", "bear_case": "Real bear case.",
                                  "base_case": "Real base case.", "key_risks": [], "catalysts": []},
                    "narrative_integrity_status": IntegrityStatus.VALID.value,
                },
            ))
            await db.commit()

        resp = client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["summary"]["integrity_status"] == IntegrityStatus.VALID.value
        assert body["marketReaction"]["integrity_status"] == IntegrityStatus.VALID.value
        assert body["aiAnalysis"]["integrity_status"] == IntegrityStatus.VALID.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_legacy_event_with_no_integrity_status_at_all_fails_closed_to_unknown():
    """A real pre-D6 event (ai_summary exists but predates this tag
    entirely) must resolve to 'unknown', never silently upgraded to
    'valid' just because the field is absent -- same fail-safe reasoning
    CD3-B established for impact_provenance."""
    now = datetime.now(timezone.utc)
    event_id = f"pytest-legacy-integrity-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Legacy pre-D6 event",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
                ai_summary={
                    "summary": "Legacy summary with no integrity tagging at all.",
                    "why_it_matters": "Legacy reason.", "key_bullets": [],
                    "immediate_impact": "neutral", "long_term_impact": "neutral",
                    "risk_factors": [], "opportunities": [],
                    # Deliberately no integrity_status/classification/
                    # narrative_integrity_status keys -- simulates a row
                    # persisted before D6 shipped.
                },
            ))
            await db.commit()

        resp = client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["summary"]["integrity_status"] == "unknown"
        assert body["marketReaction"]["integrity_status"] == "unknown"
        assert body["aiAnalysis"]["integrity_status"] == "unknown"
    finally:
        await _cleanup(event_id)

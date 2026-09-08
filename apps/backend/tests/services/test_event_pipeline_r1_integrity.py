"""
Event Enrichment R1 — Integrity Propagation (2026-09-08 audit remediation).

Confirmed production defect: DeepSeekProvider.extract_companies()/
.extract_sectors() discarded the real integrity_status _safe_json_call()
already computes, so a provider failure at this specific stage (stage 4)
was indistinguishable from a genuine "zero companies/sectors" result --
invisible to the pipeline's only health check (stage 2's classify_event),
letting it silently resolve as an honestly-labeled-but-wrong
insufficient_data/done row that should have been retried instead.

Fix: extract_companies()/extract_sectors() now return
(list, integrity_status) tuples; event_pipeline.py checks both alongside
its existing stage-2 check and raises _AIUnavailable (the existing
retry/backoff path) on either FALLBACK. VALID + [] remains a legitimate
result and must never trigger a retry -- these tests specifically guard
that distinction end to end through the real pipeline, a real DB-backed
Event row, and a fully controlled fake AI provider (no network calls).

Tests E-I from the remediation task spec (A-D are pure provider-level
unit tests -- see test_deepseek_provider_fallback_integrity.py).
"""
from __future__ import annotations

import asyncio
import random
import string
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select

import app.pipeline.event_pipeline as event_pipeline_module
from app.db.models.event import Event
from app.db.session import AsyncSessionLocal
from app.pipeline.event_pipeline import run_event_pipeline
from app.services.measurement_semantics import IntegrityStatus


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


class _FakeAIProvider:
    """Full control over every stage's output, no network calls. Only
    extract_companies/extract_sectors' status is varied per test --
    every other stage is a real, valid, minimal-but-honest response."""

    def __init__(self, *, companies_status=IntegrityStatus.VALID.value, sectors_status=IntegrityStatus.VALID.value,
                 companies=None, sectors=None):
        self._companies_status = companies_status
        self._sectors_status = sectors_status
        self._companies = companies if companies is not None else []
        self._sectors = sectors if sectors is not None else []

    async def classify_event(self, text):
        return {"category": "corporate", "confidence": 0.9, "subcategory": "capex", "integrity_status": IntegrityStatus.VALID.value}

    async def summarize_event(self, title, text, source):
        return {
            "summary": "Test summary.", "why_it_matters": "Test reason.", "key_bullets": ["a"],
            "immediate_impact": "neutral", "long_term_impact": "neutral",
            "risk_factors": [], "opportunities": [], "integrity_status": IntegrityStatus.VALID.value,
        }

    async def extract_companies(self, title, text):
        return self._companies, self._companies_status

    async def extract_sectors(self, title, text):
        return self._sectors, self._sectors_status

    async def generate_impact_analysis(self, title, text, companies, sectors):
        return {
            "impact_score": 60, "confidence": 65,
            "market_reaction": {"short_term": "neutral", "medium_term": "neutral", "volatility": "medium", "sentiment": "neutral"},
            "analysis": {"bull_case": "x", "bear_case": "y", "base_case": "z", "key_risks": [], "catalysts": []},
            "integrity_status": IntegrityStatus.VALID.value,
        }

    async def generate_timeline(self, title, text, event_type):
        return []

    async def find_similar_events(self, title, sectors, candidates):
        return []

    async def generate_graph(self, title, companies, sectors):
        return {"nodes": [], "edges": []}


async def _seed_event(title: str) -> str:
    eid = f"test-r1-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        db.add(Event(
            id=eid, title=title, source="Test", enrichment_status="pending", retry_count=0,
            created_at=datetime.now(timezone.utc),
        ))
        await db.commit()
    return eid


async def _cleanup(event_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(event_ids)))
        await db.commit()


async def _run_with_fake_provider(event_id: str, fake_provider: _FakeAIProvider, monkeypatch) -> bool:
    monkeypatch.setattr(event_pipeline_module, "get_resilient_ai_provider", lambda: fake_provider)
    monkeypatch.setattr(event_pipeline_module, "find_similar_events", AsyncMock(return_value=[]))
    monkeypatch.setattr(event_pipeline_module.intelligence_orchestrator, "on_event_scored", AsyncMock(return_value=None))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))  # skip real _STAGE_DELAY/backoff waits
    async with AsyncSessionLocal() as db:
        event = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one()
        return await run_event_pipeline(event, db)


async def _fetch(event_id: str) -> Event:
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(Event).where(Event.id == event_id))).scalar_one()


@pytest.mark.asyncio
async def test_e_classification_valid_company_extraction_fallback_retries(monkeypatch):
    """Test E: classification VALID but company extraction FALLBACK -> retry."""
    eid = await _seed_event(f"{_tag()} real corporate event")
    try:
        provider = _FakeAIProvider(companies_status=IntegrityStatus.FALLBACK.value)
        ok = await _run_with_fake_provider(eid, provider, monkeypatch)
        assert ok is False
        event = await _fetch(eid)
        assert event.enrichment_status == "failed"
        assert event.last_failure_reason == "provider_unavailable"
        assert event.impact_score is None
    finally:
        await _cleanup([eid])


@pytest.mark.asyncio
async def test_f_classification_and_company_valid_sector_fallback_retries(monkeypatch):
    """Test F: classification VALID + company VALID + sector FALLBACK -> retry."""
    eid = await _seed_event(f"{_tag()} real corporate event")
    try:
        provider = _FakeAIProvider(sectors_status=IntegrityStatus.FALLBACK.value)
        ok = await _run_with_fake_provider(eid, provider, monkeypatch)
        assert ok is False
        event = await _fetch(eid)
        assert event.enrichment_status == "failed"
        assert event.last_failure_reason == "provider_unavailable"
    finally:
        await _cleanup([eid])


@pytest.mark.asyncio
async def test_g_all_stages_valid_low_coverage_still_honestly_done(monkeypatch):
    """Test G: all AI stages VALID (including a genuinely empty company/
    sector extraction) but real evidence coverage stays under 35% ->
    scoring_engine still legitimately returns insufficient_data/None,
    and this MUST still reach 'done', never retried. This is the
    critical regression guard: R1 must not turn every legitimate empty
    result into a false retry."""
    eid = await _seed_event(f"{_tag()} minor administrative filing")
    try:
        provider = _FakeAIProvider(companies=[], sectors=[])  # genuinely empty, both VALID
        ok = await _run_with_fake_provider(eid, provider, monkeypatch)
        assert ok is True
        event = await _fetch(eid)
        assert event.enrichment_status == "done"
        assert event.retry_count == 0
    finally:
        await _cleanup([eid])


@pytest.mark.asyncio
async def test_h_no_fabricated_impact_score_when_coverage_insufficient(monkeypatch):
    """Test H: impact_score must stay None, never a default/fabricated
    number, when real coverage is insufficient."""
    eid = await _seed_event(f"{_tag()} minor administrative filing")
    try:
        provider = _FakeAIProvider(companies=[], sectors=[])
        await _run_with_fake_provider(eid, provider, monkeypatch)
        event = await _fetch(eid)
        assert event.enrichment_status == "done"
        assert event.impact_score is None
        assert event.ai_summary["score_engine"]["status"] == "insufficient_data"
    finally:
        await _cleanup([eid])


@pytest.mark.asyncio
async def test_i_retry_backoff_state_unchanged_by_r1(monkeypatch):
    """Test I: existing retry/backoff behavior (retry_count increments,
    next_retry_at gets a real future backoff, status='failed' not
    'failed_permanent' on a first failure) is unaffected by R1 -- the
    same _AIUnavailable/mark_enrichment_failed path is reused, not a new
    one."""
    eid = await _seed_event(f"{_tag()} real corporate event")
    try:
        provider = _FakeAIProvider(companies_status=IntegrityStatus.FALLBACK.value)
        await _run_with_fake_provider(eid, provider, monkeypatch)
        event = await _fetch(eid)
        assert event.retry_count == 1
        assert event.enrichment_status == "failed"  # not failed_permanent -- only 1 of 5 retries used
        assert event.next_retry_at is not None
        next_retry_at = event.next_retry_at if event.next_retry_at.tzinfo else event.next_retry_at.replace(tzinfo=timezone.utc)
        assert next_retry_at > datetime.now(timezone.utc)
    finally:
        await _cleanup([eid])


@pytest.mark.asyncio
async def test_baseline_valid_real_companies_still_reaches_done(monkeypatch):
    """Sanity baseline: the tuple-unpacking refactor doesn't break the
    ordinary successful path when real company/sector data IS present."""
    eid = await _seed_event(f"{_tag()} real corporate acquisition event")
    try:
        provider = _FakeAIProvider(
            companies=[{"symbol": "RELIANCE", "name": "Reliance Industries", "impact_type": "beneficiary", "reason": "test", "impact_score": 7.0}],
            sectors=[{"sector": "Energy", "impact": "positive", "impact_score": 6.0, "reason": "test"}],
        )
        ok = await _run_with_fake_provider(eid, provider, monkeypatch)
        assert ok is True
        event = await _fetch(eid)
        assert event.enrichment_status == "done"
    finally:
        await _cleanup([eid])

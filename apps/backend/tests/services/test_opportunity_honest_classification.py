"""
Opportunity Radar honest-classification fix (2026-10-17).

Read-only audit confirmed two real defects in opportunity_generator.py:
  1. confidence = min(0.95, score / 110) is a pure deterministic rescaling
     of score, not an independent measure of evidence quality.
  2. When the AI call (_call_ai) returned empty or unparseable output,
     the heuristic fallback silently assigned trend="Positive" (changed
     here to "Neutral") and risk_level="Medium" -- indistinguishable from
     a real, successful AI verdict. Every one of 20 sampled production
     records had in fact hit this fallback path (confirmed: the heuristic
     summary template appeared verbatim in their persisted `summary`).

Fix: ai_summary_data["integrity_status"] ("valid"/"fallback", same
vocabulary as measurement_semantics.IntegrityStatus) is now always
persisted with the opportunity, no schema change (ai_summary is already
a nullable JSON column). opportunity_service.py reads it and nulls out
confidence/trend/risk_level/time_horizon plus sets a new
classification_status field ("classified"/"unclassified") in the API
response whenever the classification failed -- including for records
persisted before this fix shipped, which have no integrity_status key at
all and must resolve to "unclassified" too (never inferred as a stronger
claim than the code can prove, per measurement_semantics.py's own
documented rule).

The score formula itself (_score_opportunity) is explicitly NOT touched
by this fix -- see test_opportunity_scoring.py for its own coverage.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models.opportunity import Opportunity
from app.db.session import AsyncSessionLocal
from app.main import app
from app.pipeline import opportunity_generator as gen_mod
from app.services.measurement_semantics import IntegrityStatus
from app.services.opportunity_service import OpportunityService, _classification_status

client = TestClient(app)


def _ev(id_: str, title: str, summary: str = "", hours_ago: float = 0) -> dict:
    published = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"id": id_, "title": title, "summary": summary, "published_at": published.isoformat(), "category": "General"}


async def _cleanup(opportunity_id: int | None):
    if opportunity_id is None:
        return
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Opportunity).where(Opportunity.id == opportunity_id))
        await db.commit()


# ── _classification_status: pure unit tests, no DB ──────────────────────────

def test_classification_status_valid_integrity_status_is_classified():
    assert _classification_status({"integrity_status": "valid"}) == "classified"


def test_classification_status_fallback_integrity_status_is_unclassified():
    assert _classification_status({"integrity_status": "fallback"}) == "unclassified"


def test_classification_status_missing_integrity_status_key_is_unclassified():
    """A legacy record persisted before this fix has no integrity_status
    key at all -- must resolve to unclassified, never inferred as
    "classified" by default."""
    assert _classification_status({"matters": "x", "benefits": "y"}) == "unclassified"


def test_classification_status_none_ai_summary_is_unclassified():
    assert _classification_status(None) == "unclassified"


def test_classification_status_json_string_ai_summary_is_parsed_correctly():
    assert _classification_status('{"integrity_status": "valid"}') == "classified"


def test_classification_status_malformed_json_string_is_unclassified():
    assert _classification_status("not valid json {{{") == "unclassified"


# ── generate_opportunity_from_events: real end-to-end, _call_ai mocked ─────

@pytest.mark.asyncio
async def test_empty_ai_response_persists_fallback_integrity_status_and_neutral_trend(monkeypatch):
    monkeypatch.setattr(gen_mod, "_call_ai", lambda *a, **k: _noop_async(None))
    events = [_ev(f"e-{uuid.uuid4()}", "Real Corporate Event Title For Testing")]
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            opp = await gen_mod.generate_opportunity_from_events(db, events)
            assert opp is not None
            opp_id = opp.id
            assert opp.ai_summary["integrity_status"] == IntegrityStatus.FALLBACK.value
            # "Positive" would have misleadingly implied a real AI verdict;
            # "Neutral" is the Opportunity model's own documented default.
            assert opp.trend == "Neutral"
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_malformed_ai_response_also_persists_fallback_not_a_crash(monkeypatch):
    monkeypatch.setattr(gen_mod, "_call_ai", lambda *a, **k: _noop_async("not valid json at all {{{"))
    events = [_ev(f"e-{uuid.uuid4()}", "Another Real Corporate Event Title")]
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            opp = await gen_mod.generate_opportunity_from_events(db, events)
            assert opp is not None
            opp_id = opp.id
            assert opp.ai_summary["integrity_status"] == IntegrityStatus.FALLBACK.value
            assert opp.trend == "Neutral"
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_valid_ai_classification_persists_valid_integrity_status_and_real_trend(monkeypatch):
    valid_json = (
        '{"title": "Real AI Title", "summary": "Real AI summary.", '
        '"trend": "Negative", "risk_level": "High", "time_horizon": "1-3 Years", '
        '"matters": "m", "benefits": "b", "risks": ["r1"], "invalidate": "i", '
        '"why_bullets": ["w1"]}'
    )
    monkeypatch.setattr(gen_mod, "_call_ai", lambda *a, **k: _noop_async(valid_json))
    events = [_ev(f"e-{uuid.uuid4()}", "A Third Real Corporate Event Title")]
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            opp = await gen_mod.generate_opportunity_from_events(db, events)
            assert opp is not None
            opp_id = opp.id
            assert opp.ai_summary["integrity_status"] == IntegrityStatus.VALID.value
            # The real AI-returned trend must survive, not the fallback default.
            assert opp.trend == "Negative"
            assert opp.risk_level == "High"
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_score_formula_and_persisted_confidence_value_are_unchanged_by_this_fix(monkeypatch):
    """Explicit scope guard: this fix only changes what gets SERIALIZED
    (via classification_status) and the fallback trend default -- it must
    not touch _score_opportunity or the confidence = min(0.95, score/110)
    formula itself, even for a fallback record."""
    monkeypatch.setattr(gen_mod, "_call_ai", lambda *a, **k: _noop_async(None))
    events = [_ev(f"e-{uuid.uuid4()}", "A Fourth Real Corporate Event Title")]
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            opp = await gen_mod.generate_opportunity_from_events(db, events)
            assert opp is not None
            opp_id = opp.id
            assert opp.confidence == pytest.approx(round(min(0.95, opp.opportunity_score / 110), 2), abs=1e-6)
    finally:
        await _cleanup(opp_id)


async def _noop_async(value):
    return value


# ── OpportunityService: API-layer nulling + classification_status ─────────

async def _seed_opportunity(*, integrity_status: str | None, trend: str = "Neutral") -> int:
    ai_summary = {"matters": "m", "benefits": "b", "risks": [], "invalidate": "i", "why_bullets": []}
    if integrity_status is not None:
        ai_summary["integrity_status"] = integrity_status
    async with AsyncSessionLocal() as db:
        opp = Opportunity(
            slug=f"test-honest-classification-{uuid.uuid4()}",
            title="Test Opportunity", summary="Test summary.",
            opportunity_score=95.0, confidence=0.86,
            trend=trend, risk_level="Medium", time_horizon="3 – 5 Years",
            sectors=["Technology"], ai_summary=ai_summary,
        )
        db.add(opp)
        await db.commit()
        return opp.id


@pytest.mark.asyncio
async def test_unclassified_record_serializes_null_confidence_trend_risk_horizon_via_detail_api():
    opp_id = await _seed_opportunity(integrity_status=IntegrityStatus.FALLBACK.value)
    try:
        async with AsyncSessionLocal() as db:
            svc = OpportunityService(db)
            detail = await svc.get_opportunity_details(opp_id)
        assert detail is not None
        assert detail.classification_status == "unclassified"
        assert detail.confidence is None
        assert detail.trend is None
        assert detail.risk_level is None
        assert detail.time_horizon is None
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_classified_record_still_serializes_real_values_via_detail_api():
    opp_id = await _seed_opportunity(integrity_status=IntegrityStatus.VALID.value, trend="Negative")
    try:
        async with AsyncSessionLocal() as db:
            svc = OpportunityService(db)
            detail = await svc.get_opportunity_details(opp_id)
        assert detail is not None
        assert detail.classification_status == "classified"
        assert detail.confidence == pytest.approx(0.86)
        assert detail.trend == "Negative"
        assert detail.risk_level == "Medium"
        assert detail.time_horizon == "3 – 5 Years"
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_legacy_record_with_no_integrity_status_key_serializes_as_unclassified():
    """The exact state every one of the 20 sampled production records is
    in today -- must not keep rendering as if it were a real "Positive"
    classification just because no one has regenerated it."""
    opp_id = await _seed_opportunity(integrity_status=None)
    try:
        async with AsyncSessionLocal() as db:
            svc = OpportunityService(db)
            detail = await svc.get_opportunity_details(opp_id)
        assert detail is not None
        assert detail.classification_status == "unclassified"
        assert detail.trend is None
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_list_opportunities_also_nulls_fields_and_sets_classification_status():
    opp_id = await _seed_opportunity(integrity_status=IntegrityStatus.FALLBACK.value)
    try:
        async with AsyncSessionLocal() as db:
            svc = OpportunityService(db)
            page = await svc.list_opportunities(page=1, page_size=100)
        item = next((i for i in page.items if i.id == opp_id), None)
        assert item is not None
        assert item.classification_status == "unclassified"
        assert item.confidence is None
        assert item.trend is None
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_existing_record_id_slug_and_opportunity_score_unchanged_by_serialization():
    """The fix must not mutate persisted data -- confirmed by reading the
    same row back and checking identity/score survive byte-for-byte
    through the service layer, exactly as seeded."""
    opp_id = await _seed_opportunity(integrity_status=IntegrityStatus.FALLBACK.value)
    try:
        async with AsyncSessionLocal() as db:
            opp_before = await db.get(Opportunity, opp_id)
            slug_before, score_before = opp_before.slug, opp_before.opportunity_score

            svc = OpportunityService(db)
            detail = await svc.get_opportunity_details(opp_id)

            opp_after = await db.get(Opportunity, opp_id)
            assert opp_after.slug == slug_before
            assert opp_after.opportunity_score == score_before
            assert detail.id == opp_id
            assert detail.slug == slug_before
            assert detail.opportunity_score == score_before
    finally:
        await _cleanup(opp_id)


# ── radar.py's GET /{id}: investment_verdict must not fabricate from None ──

@pytest.mark.asyncio
async def test_detail_endpoint_skips_investment_verdict_cleanly_for_unclassified_record():
    """Found during final review: compute_investment_verdict does
    `confidence * 100 if confidence <= 1 else confidence`, a guaranteed
    TypeError now that confidence is None for an unclassified record.
    radar.py's try/except already prevented a 500, but logged a warning
    on every single fetch and left investment_verdict silently absent by
    accident rather than by design. Fixed by skipping the call outright
    for an unclassified record -- this test proves the real HTTP endpoint
    returns 200 with investment_verdict null and classification_status
    "unclassified", not a 500 and not a fabricated verdict."""
    opp_id = await _seed_opportunity(integrity_status=IntegrityStatus.FALLBACK.value)
    try:
        resp = client.get(f"/api/radar/{opp_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["classification_status"] == "unclassified"
        assert body["investment_verdict"] is None
        assert body["confidence"] is None
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_detail_endpoint_still_computes_a_real_investment_verdict_for_a_classified_record():
    opp_id = await _seed_opportunity(integrity_status=IntegrityStatus.VALID.value, trend="Positive")
    try:
        resp = client.get(f"/api/radar/{opp_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["classification_status"] == "classified"
        assert body["investment_verdict"] is not None
        assert body["investment_verdict"]["label"]
    finally:
        await _cleanup(opp_id)

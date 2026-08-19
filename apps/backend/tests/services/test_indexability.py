"""
Regression suite — coverage_engine.compute_indexable_batch/compute_indexable
(Phase 15, 2026-08 audit, revised v2 the same month after a Search Console
export showed real dividend/acquisition/financial-results pages sitting
noindex purely for not being Critical/High triage — an urgency signal, not
a page-quality signal).

v2 rule: indexable requires ALL of — a real slug, a content-quality floor
(real per-event analysis, not the AI pipeline's hardcoded fallback text),
AND (Critical/High triage OR a real MacroRelease OR a substantive filing
category by title). The quality floor applies to every branch, including
Critical/High — verified live against the 2026-08-19 Search Console
export that a category match alone is not enough (25 of 71 noindexed
event pages matched a substantive category by title, but all 25 still
carried the AI pipeline's literal fallback strings instead of real
analysis).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event, EventCompany
from app.db.models.event_coverage import EventCoverage
from app.db.models.macro_release import MacroRelease
from app.services import coverage_engine

_GENUINE_AI_SUMMARY = {
    "why_it_matters": "This directly affects working capital costs given the company's leverage profile.",
    "analysis": {"bull_case": "Refinancing at a lower rate should lift margins next quarter."},
}
_FALLBACK_AI_SUMMARY = {
    "why_it_matters": coverage_engine._GENERIC_FALLBACK_WHY,
    "analysis": {"bull_case": coverage_engine._GENERIC_FALLBACK_BULL},
}


def _make_event(event_id: str, *, title: str, slug: str | None, genuine: bool, description: str | None = None) -> Event:
    return Event(
        id=event_id,
        slug=slug,
        title=title,
        description=description if description is not None else (f"{title} — real expanded detail, not a restated headline." if genuine else title),
        ai_summary=_GENUINE_AI_SUMMARY if genuine else _FALLBACK_AI_SUMMARY,
        impact_score=6.5 if genuine else None,
        confidence=70.0 if genuine else None,
        source="NSE",
        event_type="corporate",
        enrichment_status="done",
    )


async def _cleanup(event_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventCompany).where(EventCompany.event_id.in_(event_ids)))
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(event_ids)))
        await db.execute(delete(MacroRelease).where(MacroRelease.id.in_(event_ids)))
        await db.execute(delete(Event).where(Event.id.in_(event_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_no_evidence_defaults_to_not_indexable():
    event_id = f"pytest-idx-none-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        result = await coverage_engine.compute_indexable(db, event_id)
    assert result is False


@pytest.mark.asyncio
async def test_critical_or_high_with_genuine_quality_is_indexable():
    critical_id = f"pytest-idx-critical-{uuid.uuid4().hex[:8]}"
    high_id = f"pytest-idx-high-{uuid.uuid4().hex[:8]}"
    medium_id = f"pytest-idx-medium-{uuid.uuid4().hex[:8]}"
    low_id = f"pytest-idx-low-{uuid.uuid4().hex[:8]}"
    ids = [critical_id, high_id, medium_id, low_id]
    await _cleanup(ids)
    try:
        async with AsyncSessionLocal() as db:
            for eid, tier in ((critical_id, "Critical"), (high_id, "High"), (medium_id, "Medium"), (low_id, "Low")):
                db.add(EventCoverage(event_id=eid, priority=tier, event_title="Test", detected_at=datetime.now(timezone.utc)))
                db.add(_make_event(eid, title="Some Company reported a material update", slug=f"slug-{eid}", genuine=True))
            await db.commit()

            flags = await coverage_engine.compute_indexable_batch(db, ids)
        assert flags[critical_id] is True
        assert flags[high_id] is True
        assert flags[medium_id] is False
        assert flags[low_id] is False
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_critical_tier_without_genuine_quality_stays_noindex():
    """The exact fix this revision makes: a Critical-tier event that still
    carries the AI pipeline's fallback text is exactly as thin as a
    routine filing with the same problem — tier alone must not bypass the
    quality floor."""
    event_id = f"pytest-idx-critical-thin-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(event_id=event_id, priority="Critical", event_title="Test", detected_at=datetime.now(timezone.utc)))
            db.add(_make_event(event_id, title="Some Company Limited has informed the Exchange about General Updates", slug=f"slug-{event_id}", genuine=False))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_real_macro_release_with_genuine_quality_is_indexable_regardless_of_coverage_priority():
    event_id = f"pytest-idx-macro-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(event_id=event_id, priority="Medium", event_title="Test", detected_at=datetime.now(timezone.utc)))
            db.add(MacroRelease(
                id=event_id, event_id=event_id, metric="CPI", release_value=4.2,
                affected_sectors=[], affected_companies=[], headline="Test macro headline",
            ))
            db.add(_make_event(event_id, title="CPI inflation print for July", slug=f"slug-{event_id}", genuine=True))
            await db.commit()

            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is True
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_macro_release_row_without_a_real_value_does_not_force_indexable():
    event_id = f"pytest-idx-macro-null-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(MacroRelease(
                id=event_id, event_id=event_id, metric="CPI", release_value=None,
                affected_sectors=[], affected_companies=[], headline="Test macro headline",
            ))
            db.add(_make_event(event_id, title="CPI inflation print for July", slug=f"slug-{event_id}", genuine=True))
            await db.commit()

            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_substantive_category_with_genuine_quality_is_indexable():
    """The new hybrid branch — no Critical/High tier, no macro release,
    but a real financial-results filing with actual per-event analysis."""
    event_id = f"pytest-idx-category-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(_make_event(
                event_id,
                title="Acme Industries Limited has submitted to the Exchange the financial results for the period ended Jun 30, 2026",
                slug=f"slug-{event_id}", genuine=True,
            ))
            db.add(EventCompany(event_id=event_id, symbol="ACME", name="Acme Industries", impact_type="beneficiary", impact_score=7, reason="Revenue grew 18% YoY driven by export orders."))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is True
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_substantive_category_without_genuine_quality_stays_noindex():
    """Verified live 2026-08-19: this is the actual, common case today —
    25 of 71 Search-Console-flagged event pages matched a substantive
    category by title but still carried only the AI pipeline's fallback
    text, not real analysis."""
    event_id = f"pytest-idx-category-thin-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(_make_event(
                event_id,
                title="Acme Industries Limited has informed the Exchange about Acquisition",
                slug=f"slug-{event_id}", genuine=False,
            ))
            db.add(EventCompany(event_id=event_id, symbol="ACME", name="Acme Industries", impact_type="neutral", impact_score=5, reason=""))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_routine_category_never_matches_even_with_genuine_content():
    """A routine filing (e.g. an AGM procedural notice) that happens to
    have real-looking text still shouldn't index — it never matches the
    substantive-category signal in the first place, and has no
    Critical/High tier or macro release either."""
    event_id = f"pytest-idx-routine-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(_make_event(
                event_id,
                title="Acme Industries Limited has informed the Exchange about Loss of Share Certificates",
                slug=f"slug-{event_id}", genuine=True,
            ))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_no_slug_stays_noindex_even_with_everything_else_passing():
    """Canonical URL requirement — an event with no real slug yet has no
    indexable address; this must fail even with Critical tier + genuine
    content, not just quietly fall through elsewhere in the pipeline."""
    event_id = f"pytest-idx-noslug-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(event_id=event_id, priority="Critical", event_title="Test", detected_at=datetime.now(timezone.utc)))
            db.add(_make_event(event_id, title="Some Company reported a material update", slug=None, genuine=True))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_company_with_empty_reason_fails_quality_floor():
    event_id = f"pytest-idx-emptyreason-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(event_id=event_id, priority="Critical", event_title="Test", detected_at=datetime.now(timezone.utc)))
            db.add(_make_event(event_id, title="Some Company reported a material update", slug=f"slug-{event_id}", genuine=True))
            db.add(EventCompany(event_id=event_id, symbol="X", name="X", impact_type="neutral", impact_score=5, reason=""))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is False
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_no_companies_at_all_does_not_block_indexability():
    """A pure macro/economy event with zero linked companies shouldn't be
    penalized for lacking a company reason it was never going to have."""
    event_id = f"pytest-idx-nocompanies-{uuid.uuid4().hex[:8]}"
    await _cleanup([event_id])
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(event_id=event_id, priority="High", event_title="Test", detected_at=datetime.now(timezone.utc)))
            db.add(_make_event(event_id, title="RBI holds repo rate steady", slug=f"slug-{event_id}", genuine=True))
            await db.commit()
            result = await coverage_engine.compute_indexable(db, event_id)
        assert result is True
    finally:
        await _cleanup([event_id])


@pytest.mark.asyncio
async def test_batch_handles_empty_list():
    async with AsyncSessionLocal() as db:
        result = await coverage_engine.compute_indexable_batch(db, [])
    assert result == {}

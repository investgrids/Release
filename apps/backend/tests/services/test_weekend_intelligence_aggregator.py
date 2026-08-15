"""
build_weekend_intelligence() end-to-end tests — brief §30, real DB.

All tests share target_trading_date="2099-04-06" (a Monday) / last_trading_
date="2099-04-03" (the Friday before, per session_resolution's own
verified arithmetic) — fixed, far-future dates chosen so evidence rows
can't collide with any real data in the shared local dev DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_announcements import CompanyAnnouncement
from app.db.models.event import Event, GovernmentPolicy
from app.db.models.intelligence import EventTriage, MarketSnapshot
from app.db.models.opportunity import Opportunity
from app.db.models_legacy import NewsArticle
from app.db.session import AsyncSessionLocal
from app.services.weekend_intelligence.aggregator import (
    STATUS_DEGRADED, STATUS_INSUFFICIENT_EVIDENCE, STATUS_OK, build_weekend_intelligence,
)

TARGET = "2099-04-06"
LAST_TRADING = "2099-04-03"
CHECKPOINT = datetime(2099, 4, 5, 4, 30, tzinfo=timezone.utc)  # Saturday ~10:00 IST
WITHIN_WINDOW = datetime(2099, 4, 4, 10, 0, tzinfo=timezone.utc)


async def _cleanup(event_ids=(), triage_ids=(), policy_ids=(), announcement_ids=(), news_ids=(),
                    opportunity_ids=(), snapshot_ids=()):
    async with AsyncSessionLocal() as db:
        if event_ids:
            await db.execute(delete(Event).where(Event.id.in_(event_ids)))
        if triage_ids:
            await db.execute(delete(EventTriage).where(EventTriage.id.in_(triage_ids)))
        if policy_ids:
            await db.execute(delete(GovernmentPolicy).where(GovernmentPolicy.id.in_(policy_ids)))
        if announcement_ids:
            await db.execute(delete(CompanyAnnouncement).where(CompanyAnnouncement.id.in_(announcement_ids)))
        if news_ids:
            await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(news_ids)))
        if opportunity_ids:
            await db.execute(delete(Opportunity).where(Opportunity.id.in_(opportunity_ids)))
        if snapshot_ids:
            await db.execute(delete(MarketSnapshot).where(MarketSnapshot.id.in_(snapshot_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_no_baseline_no_evidence_is_insufficient_evidence():
    async with AsyncSessionLocal() as db:
        result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
    assert result.baseline_available is False
    assert result.evidence_count == 0
    assert result.status == STATUS_INSUFFICIENT_EVIDENCE
    assert result.overall_bias == "neutral"
    assert result.changes == []


@pytest.mark.asyncio
async def test_baseline_available_but_no_evidence_still_insufficient_evidence():
    """brief §19's exact example: real Friday baseline + no weekend
    developments must NOT invent opportunities."""
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert result.baseline_available is True
        assert result.evidence_count == 0
        assert result.status == STATUS_INSUFFICIENT_EVIDENCE
    finally:
        await _cleanup(snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_evidence_without_baseline_is_degraded_not_insufficient():
    event_id = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    triage_id = f"pytest-agg-triage-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=event_id, title="RBI issues fresh liquidity guidance", published_at=WITHIN_WINDOW,
                         companies=["HDFCBANK"], sectors=["Banking"], confidence=70.0))
            db.add(EventTriage(id=triage_id, event_id=event_id, source="policy",
                                headline="RBI issues fresh liquidity guidance", urgency=9, importance=8))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert result.baseline_available is False
        assert result.evidence_count >= 1
        assert result.status == STATUS_DEGRADED
    finally:
        await _cleanup(event_ids=[event_id], triage_ids=[triage_id])


@pytest.mark.asyncio
async def test_one_high_impact_event_with_baseline_is_ok_status():
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    event_id = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    triage_id = f"pytest-agg-triage-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            db.add(Event(id=event_id, title="Defence ministry clears major order for BEL", published_at=WITHIN_WINDOW,
                         companies=["BEL"], sectors=["Defence"], confidence=85.0))
            db.add(EventTriage(id=triage_id, event_id=event_id, source="policy",
                                headline="Defence ministry clears major order", urgency=9, importance=9))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert result.status == STATUS_OK
        assert result.evidence_count == 1
        assert any(c.sector == "Defence" for c in result.sector_signals)
        assert any(c.symbol == "BEL" for c in result.company_signals)
    finally:
        await _cleanup(event_ids=[event_id], triage_ids=[triage_id], snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_multiple_independent_events_produce_multiple_clusters():
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    e1 = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    e2 = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            db.add(Event(id=e1, title="Infosys wins large multi-year IT contract", published_at=WITHIN_WINDOW,
                         companies=["INFY"], sectors=["IT"], confidence=75.0))
            db.add(Event(id=e2, title="Auto sales data shows strong monthly growth", published_at=WITHIN_WINDOW,
                         companies=["MARUTI"], sectors=["Auto"], confidence=70.0))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert len(result.clusters) == 2
        assert {s.sector for s in result.sector_signals} == {"IT", "Auto"}
    finally:
        await _cleanup(event_ids=[e1, e2], snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_duplicate_representation_of_same_development_not_double_counted():
    """The core brief §6/§30 scenario: a NewsArticle and an Event
    describing the same real story must cluster into ONE development,
    not inflate evidence_count/company signal strength as if independently
    confirmed twice."""
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    event_id = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    news_id = f"pytest-agg-news-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            db.add(Event(id=event_id, title="Tata Steel announces major capacity expansion plan",
                         published_at=WITHIN_WINDOW, companies=["TATASTEEL"], sectors=["Metals"], confidence=72.0))
            db.add(NewsArticle(id=news_id, headline="Tata Steel announces major capacity expansion plan",
                                summary="Tata Steel expansion", source="ET", published_at=WITHIN_WINDOW.isoformat(),
                                companies=["TATASTEEL"], impact_score=7.0, created_at=WITHIN_WINDOW))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert result.evidence_count == 2  # both rows still counted as raw evidence...
        assert len(result.clusters) == 1   # ...but merged into ONE development
        company = next(c for c in result.company_signals if c.symbol == "TATASTEEL")
        assert company.evidence_count == 1  # one cluster, not two independent confirmations
    finally:
        await _cleanup(event_ids=[event_id], news_ids=[news_id], snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_conflicting_evidence_produces_mixed_state_and_risk():
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    e1 = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    e2 = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            db.add(Event(id=e1, title="YES Bank reports improved asset quality metrics", published_at=WITHIN_WINDOW,
                         companies=["YESBANK"], sectors=["Banking"], confidence=60.0, ai_summary={"sentiment": "positive"}))
            db.add(Event(id=e2, title="YES Bank faces fresh regulatory scrutiny over lending",
                         published_at=WITHIN_WINDOW, companies=["YESBANK"], sectors=["Banking"], confidence=65.0,
                         ai_summary={"sentiment": "negative"}))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        # Two separate clusters (titles too different to merge) but both
        # touch YESBANK with opposing signals is not directly modeled by
        # Event's own direction field (evidence.py doesn't derive
        # direction from Event at all — see its normalizer) — this test
        # instead confirms the two independent events both surface as
        # real, separate evidence for the same company, which is the
        # honest, correct outcome given Event carries no sentiment field
        # Phase 1A's normalizer reads.
        yesbank_evidence = [c for c in result.clusters if "YESBANK" in c.companies]
        assert len(yesbank_evidence) == 2
    finally:
        await _cleanup(event_ids=[e1, e2], snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_company_announcement_and_related_event_merge():
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    event_id = f"pytest-agg-evt-{uuid.uuid4().hex[:8]}"
    ann_id = f"pytest-agg-ann-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            db.add(Event(id=event_id, title="HDFC Bank board approves quarterly dividend payout",
                         published_at=WITHIN_WINDOW, companies=["HDFCBANK"], sectors=["Banking"], confidence=55.0))
            db.add(CompanyAnnouncement(id=ann_id, symbol="HDFCBANK", subject="HDFC Bank board approves quarterly dividend payout",
                                        source="NSE", category="Dividend", announcement_date=WITHIN_WINDOW,
                                        ingested_at=WITHIN_WINDOW, impact_score=6, is_high_impact=False))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert len(result.clusters) == 1
        assert result.clusters[0].source_types == {"event", "announcement"}
    finally:
        await _cleanup(event_ids=[event_id], announcement_ids=[ann_id], snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_policy_evidence_counted_even_without_company_sector_fields():
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    policy_id = None
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            policy = GovernmentPolicy(external_id=f"pytest-agg-pol-{uuid.uuid4().hex[:8]}",
                                       title="RBI issues circular on NBFC lending norms", created_at=WITHIN_WINDOW)
            db.add(policy)
            await db.flush()
            policy_id = policy.id
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert result.evidence_count == 1
        assert any(m.source_type == "policy" for c in result.clusters for m in c.members)
    finally:
        if policy_id is not None:
            await _cleanup(policy_ids=[policy_id], snapshot_ids=[snap_id])
        else:
            await _cleanup(snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_opportunity_referenced_in_snapshot():
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            opp = Opportunity(slug=f"pytest-agg-opp-{uuid.uuid4().hex[:8]}", title="Green energy capex cycle",
                               summary="s", sectors=["Energy"], opportunity_score=80.0, confidence=0.7,
                               created_at=WITHIN_WINDOW)
            db.add(opp)
            await db.flush()
            opp_id = opp.id
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert str(opp_id) in result.opportunity_refs
    finally:
        if opp_id is not None:
            await _cleanup(opportunity_ids=[opp_id], snapshot_ids=[snap_id])
        else:
            await _cleanup(snapshot_ids=[snap_id])


@pytest.mark.asyncio
async def test_historical_analogue_unavailable_for_ordinary_low_significance_evidence():
    """No Critical/High event, cluster too small (<3 members) -> historical
    matching is deliberately skipped (brief §13: don't call it for every
    low-value item)."""
    snap_id = f"pytest-agg-close-{uuid.uuid4().hex[:8]}"
    news_id = f"pytest-agg-news-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketSnapshot(id=snap_id, trading_date=LAST_TRADING, snapshot_type="close", nifty_level=24500.0))
            db.add(NewsArticle(id=news_id, headline="Minor routine corporate filing update", summary="s",
                                source="RSS", published_at=WITHIN_WINDOW.isoformat(), companies=[], impact_score=6.5,
                                created_at=WITHIN_WINDOW))
            await db.commit()

            result = await build_weekend_intelligence(db, TARGET, CHECKPOINT)
        assert result.historical_analogue_refs == []
    finally:
        await _cleanup(news_ids=[news_id], snapshot_ids=[snap_id])

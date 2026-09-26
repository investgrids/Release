"""
Current Intelligence dedup — 2026-09-26 audit follow-up. IntelligenceArticle.
trigger_event_id and Opportunity's linked OpportunityEvent.event_id both
point into the same real `events` table, so one real event could
previously produce an article-sourced AND an opportunity-sourced
AICompanySignal for the same company, each weighted independently —
double-counting one real fact. These tests prove compute_company_score()
now dedupes by real event_id (never by title/text similarity), preserves
duplicates as supporting sources rather than discarding them, and reports
genuinely conflicting same-event signals separately instead of silently
picking a side.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_signal import AICompanySignal
from app.db.session import AsyncSessionLocal
from app.services.aipe import company_score_engine as engine


def _tag():
    return uuid.uuid4().hex[:8]


async def _cleanup(symbols: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol.in_(symbols)))
        await db.commit()


@pytest.mark.asyncio
async def test_same_event_article_and_opportunity_signal_counted_once():
    """The exact real shape this audit found: one event, one article-sourced
    signal, one opportunity-sourced signal, same company, both positive.
    Without dedup the weighted total would be double the real evidence."""
    tag = _tag()
    symbol = f"TESTDEDUP{tag}"[:20].upper()
    event_id = f"evt-{tag}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="article", source_id=f"art-{tag}", symbol=symbol,
            company_name="Test Dedup Co", sector="Energy", event_id=event_id,
            signed_magnitude=60.0, confidence=0.9, quality=0.9,
            reason="article coverage of the real event", signal_at=now,
        ))
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp-{tag}", symbol=symbol,
            company_name="Test Dedup Co", sector="Energy", event_id=event_id,
            signed_magnitude=60.0, confidence=0.7, quality=None,
            reason="opportunity built from the same real event", signal_at=now,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await engine.compute_company_score(db, symbol)
        assert result["signal_count"] == 2, "every real row still counts toward signal_count"
        assert result["contributing_signal_count"] == 1, "one real event must contribute once, not twice"
        assert result["contributing_event_count"] == 1
        assert result["contributing_no_lineage_count"] == 0
        assert result["supporting_source_count"] == 1, "the deduped duplicate must be preserved as a supporting source, not discarded"
        assert result["unresolved_lineage"] == []
    finally:
        await _cleanup([symbol])


@pytest.mark.asyncio
async def test_representative_pick_is_deterministic_by_confidence_then_source_type():
    """The higher confidence*quality row must win the representative slot —
    article (0.9*0.9=0.81) over opportunity (0.7*1.0=0.7) here — proven by
    checking which row's own reason text survives into top_contributors."""
    tag = _tag()
    symbol = f"TESTPRIORITY{tag}"[:20].upper()
    event_id = f"evt-priority-{tag}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="article", source_id=f"art-{tag}", symbol=symbol,
            company_name="Test Priority Co", sector="Energy", event_id=event_id,
            signed_magnitude=60.0, confidence=0.9, quality=0.9,
            reason="higher-confidence article reason", signal_at=now,
        ))
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp-{tag}", symbol=symbol,
            company_name="Test Priority Co", sector="Energy", event_id=event_id,
            signed_magnitude=60.0, confidence=0.7, quality=None,
            reason="lower-confidence opportunity reason", signal_at=now,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await engine.compute_company_score(db, symbol)
        reasons = [c["reason"] for c in result["top_contributors"]]
        assert "higher-confidence article reason" in reasons
        assert "lower-confidence opportunity reason" not in reasons
    finally:
        await _cleanup([symbol])


@pytest.mark.asyncio
async def test_conflicting_same_event_signals_excluded_and_reported():
    """Two real sources disagreeing on direction for the SAME real event —
    must never be averaged or silently resolved to one side; both are
    excluded from the weighted sum and the conflict is reported so a human
    can look at it."""
    tag = _tag()
    symbol = f"TESTCONFLICT{tag}"[:20].upper()
    event_id = f"evt-conflict-{tag}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="article", source_id=f"art-{tag}", symbol=symbol,
            company_name="Test Conflict Co", sector="Energy", event_id=event_id,
            signed_magnitude=60.0, confidence=0.8, quality=0.8,
            reason="article reads this positively", signal_at=now,
        ))
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp-{tag}", symbol=symbol,
            company_name="Test Conflict Co", sector="Energy", event_id=event_id,
            signed_magnitude=-50.0, confidence=0.8, quality=None,
            reason="opportunity reads the same event negatively", signal_at=now,
        ))
        # A real, unrelated, non-conflicting signal so score isn't None.
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp2-{tag}", symbol=symbol,
            company_name="Test Conflict Co", sector="Energy", event_id=None,
            signed_magnitude=40.0, confidence=0.8, quality=None,
            reason="unrelated real signal", signal_at=now,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await engine.compute_company_score(db, symbol)
        assert result["signal_count"] == 3
        # Only the unrelated no-lineage signal contributes; the conflicting
        # pair is excluded entirely, not picked-a-winner.
        assert result["contributing_signal_count"] == 1
        assert result["contributing_event_count"] == 0
        assert result["contributing_no_lineage_count"] == 1
        assert result["supporting_source_count"] == 0, "a genuine conflict is not a merged duplicate"
        assert len(result["unresolved_lineage"]) == 1
        conflict = result["unresolved_lineage"][0]
        assert conflict["event_id"] == event_id
        assert len(conflict["signals"]) == 2
        assert {s["source_type"] for s in conflict["signals"]} == {"article", "opportunity"}
    finally:
        await _cleanup([symbol])


@pytest.mark.asyncio
async def test_signals_without_event_id_are_never_deduped():
    """No known event lineage means nothing to dedupe against — every such
    row must still count independently, exactly as before this change."""
    tag = _tag()
    symbol = f"TESTNOLINEAGE{tag}"[:20].upper()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        for i in range(3):
            db.add(AICompanySignal(
                source_type="article", source_id=f"art-{tag}-{i}", symbol=symbol,
                company_name="Test No Lineage Co", sector="Energy", event_id=None,
                signed_magnitude=30.0, confidence=0.8, quality=0.8,
                reason=f"real signal {i}", signal_at=now,
            ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await engine.compute_company_score(db, symbol)
        assert result["signal_count"] == 3
        assert result["contributing_signal_count"] == 3
        assert result["contributing_event_count"] == 0
        assert result["contributing_no_lineage_count"] == 3
        assert result["supporting_source_count"] == 0
        assert result["unresolved_lineage"] == []
    finally:
        await _cleanup([symbol])


@pytest.mark.asyncio
async def test_current_intelligence_pillar_never_reports_complete():
    """2026-09-26 audit: the old '>=10 contributing signals = COMPLETE'
    threshold is retired as unvalidated. Even with far more than 10 real,
    independent, non-conflicting contributing signals, the pillar must
    report PARTIAL, never COMPLETE, until a real validated policy exists."""
    from app.services.marketripple_score.contracts import PillarStatus
    from app.services.marketripple_score.current_intelligence import score_current_intelligence

    tag = _tag()
    symbol = f"TESTNOCOMPLETE{tag}"[:20].upper()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        for i in range(15):  # far above the old threshold of 10
            db.add(AICompanySignal(
                source_type="article", source_id=f"art-{tag}-{i}", symbol=symbol,
                company_name="Test No Complete Co", sector="Energy", event_id=f"evt-{tag}-{i}",
                signed_magnitude=30.0, confidence=0.9, quality=0.9,
                reason=f"real independent signal {i}", signal_at=now,
            ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            pillar = await score_current_intelligence(db, symbol)
        assert pillar.detail["contributing_signal_count"] == 15
        assert pillar.status == PillarStatus.PARTIAL
        assert pillar.status != PillarStatus.COMPLETE
        assert "validated_completeness_policy" in pillar.metrics_missing
    finally:
        await _cleanup([symbol])

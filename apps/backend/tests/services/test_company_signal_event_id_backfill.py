"""
Existing-signal migration check (2026-09-26 audit follow-up): every
AICompanySignal row written before the event_id column existed has
event_id=NULL and is otherwise permanently un-deduplicatable. This proves
the real backfill derives the same real lineage new rows get automatically
(article.trigger_event_id / an opportunity's highest-importance
OpportunityEvent), is idempotent, and never guesses when no real source
lineage exists.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.company_signal import AICompanySignal
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.opportunity import Opportunity, OpportunityEvent
from app.db.session import AsyncSessionLocal
from app.services.aipe.company_signal_event_id_backfill import backfill_company_signal_event_ids


def _tag():
    return uuid.uuid4().hex[:8]


async def _cleanup(symbols, article_ids, opportunity_ids):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol.in_(symbols)))
        if article_ids:
            await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        if opportunity_ids:
            await db.execute(delete(OpportunityEvent).where(OpportunityEvent.opportunity_id.in_(opportunity_ids)))
            await db.execute(delete(Opportunity).where(Opportunity.id.in_(opportunity_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_backfill_derives_article_lineage_for_pre_existing_rows():
    tag = _tag()
    symbol = f"TESTBF{tag}"[:20].upper()
    article_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(
            id=article_id, headline="Test headline", slug=f"t-{tag}",
            trigger_event_id=f"evt-{tag}", published_at=now, created_at=now,
        ))
        db.add(AICompanySignal(
            source_type="article", source_id=article_id, symbol=symbol,
            sector="Energy", signed_magnitude=10.0, confidence=0.8, quality=0.8,
            signal_at=now, event_id=None,  # pre-existing row, predates the column
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await backfill_company_signal_event_ids(db)
        assert result["resolvable"] >= 1

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(AICompanySignal).where(AICompanySignal.symbol == symbol)
            )).scalar_one()
        assert row.event_id == f"evt-{tag}"

        # Idempotent: this row is no longer a candidate (event_id is no
        # longer NULL), so a second run must not touch it again.
        async with AsyncSessionLocal() as db:
            await backfill_company_signal_event_ids(db)
        async with AsyncSessionLocal() as db:
            row_again = (await db.execute(
                select(AICompanySignal).where(AICompanySignal.symbol == symbol)
            )).scalar_one()
        assert row_again.event_id == f"evt-{tag}", "re-running must not disturb an already-backfilled row"
    finally:
        await _cleanup([symbol], [article_id], [])


@pytest.mark.asyncio
async def test_backfill_derives_opportunity_lineage_via_highest_importance_event():
    tag = _tag()
    symbol = f"TESTBFOPP{tag}"[:20].upper()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        opp = Opportunity(slug=f"opp-{tag}", title="t", summary="s")
        db.add(opp)
        await db.flush()
        db.add(OpportunityEvent(opportunity_id=opp.id, event_id=f"evt-low-{tag}", importance=0.3))
        db.add(OpportunityEvent(opportunity_id=opp.id, event_id=f"evt-high-{tag}", importance=0.9))
        db.add(AICompanySignal(
            source_type="opportunity", source_id=str(opp.id), symbol=symbol,
            sector="Energy", signed_magnitude=10.0, confidence=0.8, quality=None,
            signal_at=now, event_id=None,
        ))
        await db.commit()
        opp_id = opp.id

    try:
        async with AsyncSessionLocal() as db:
            await backfill_company_signal_event_ids(db)
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(AICompanySignal).where(AICompanySignal.symbol == symbol)
            )).scalar_one()
        assert row.event_id == f"evt-high-{tag}", "must pick the highest-importance linked event, not just any"
    finally:
        await _cleanup([symbol], [], [opp_id])


@pytest.mark.asyncio
async def test_backfill_never_guesses_when_no_real_lineage_exists():
    tag = _tag()
    symbol = f"TESTBFNONE{tag}"[:20].upper()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="opportunity", source_id="999999999", symbol=symbol,
            sector="Energy", signed_magnitude=10.0, confidence=0.8, quality=None,
            signal_at=now, event_id=None,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await backfill_company_signal_event_ids(db)
        assert result["unresolved_no_real_lineage"] >= 1

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(AICompanySignal).where(AICompanySignal.symbol == symbol)
            )).scalar_one()
        assert row.event_id is None, "never fabricate lineage when no real source link exists"
    finally:
        await _cleanup([symbol], [], [])


@pytest.mark.asyncio
async def test_dry_run_reports_the_same_counts_but_writes_nothing():
    tag = _tag()
    symbol = f"TESTBFDRY{tag}"[:20].upper()
    article_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(
            id=article_id, headline="Test headline", slug=f"t-{tag}",
            trigger_event_id=f"evt-{tag}", published_at=now, created_at=now,
        ))
        db.add(AICompanySignal(
            source_type="article", source_id=article_id, symbol=symbol,
            sector="Energy", signed_magnitude=10.0, confidence=0.8, quality=0.8,
            signal_at=now, event_id=None,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            dry_result = await backfill_company_signal_event_ids(db, dry_run=True)
        assert dry_result["dry_run"] is True
        assert dry_result["resolvable"] >= 1

        # Nothing written — the row must still show event_id IS NULL.
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(AICompanySignal).where(AICompanySignal.symbol == symbol)
            )).scalar_one()
        assert row.event_id is None, "dry_run=True must never write anything"

        # The real run must then produce the same resolvable count.
        async with AsyncSessionLocal() as db:
            real_result = await backfill_company_signal_event_ids(db, dry_run=False)
        assert real_result["resolvable"] == dry_result["resolvable"]
        assert real_result["dry_run"] is False
    finally:
        await _cleanup([symbol], [article_id], [])


@pytest.mark.asyncio
async def test_dry_run_reports_a_newly_introduced_conflicting_group():
    """The real case this audit measured platform-wide: restoring lineage
    to two currently-independent (event_id=NULL) rows for the same symbol
    can reveal they actually disagree about the same real event — this
    must be reported as a NEW conflict, not silently absorbed."""
    tag = _tag()
    symbol = f"TESTBFCONFLICT{tag}"[:20].upper()
    article_a, article_b = str(uuid.uuid4()), str(uuid.uuid4())
    shared_event_id = f"evt-shared-{tag}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(
            id=article_a, headline="Positive take", slug=f"a-{tag}",
            trigger_event_id=shared_event_id, published_at=now, created_at=now,
        ))
        db.add(IntelligenceArticle(
            id=article_b, headline="Negative take", slug=f"b-{tag}",
            trigger_event_id=shared_event_id, published_at=now, created_at=now,
        ))
        db.add(AICompanySignal(
            source_type="article", source_id=article_a, symbol=symbol,
            sector="Energy", signed_magnitude=60.0, confidence=0.8, quality=0.8,
            signal_at=now, event_id=None,
        ))
        db.add(AICompanySignal(
            source_type="article", source_id=article_b, symbol=symbol,
            sector="Energy", signed_magnitude=-60.0, confidence=0.8, quality=0.8,
            signal_at=now, event_id=None,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await backfill_company_signal_event_ids(db, dry_run=True)
        assert symbol in result["symbols_with_new_conflicting_groups"]
        assert result["symbols_with_new_conflicting_groups_count"] >= 1
    finally:
        await _cleanup([symbol], [article_a, article_b], [])

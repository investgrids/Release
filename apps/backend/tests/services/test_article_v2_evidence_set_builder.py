"""
Article V2 Phase C2 — Evidence Set Builder tests. Real DB-backed, same
fixture convention as test_article_v2_candidate_gate.py. Covers: same-
company-different-development exclusion (the owner's own ₹800 crore
order example), primary selection preferring an authoritative NSE
filing over a higher-lexical-overlap RSS article, duplicate evidence
collapse, staleness exclusion, conflict detection, and the INSUFFICIENT/
COHERENT/PARTIAL status boundary.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.article_v2.evidence_set_builder import (
    COHERENT, DIFFERENT_DEVELOPMENT, DUPLICATE_EVIDENCE, INSUFFICIENT, PARTIAL,
    STALE_CONTEXT, build_evidence_set,
)


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


async def _seed_source(db, source_id: str, source_type: str = "nse"):
    db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type=source_type, collection_method="test"))
    await db.flush()


async def _seed_entity(db, symbol: str, entity_id: str):
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Industrials", source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))


async def _seed_evidence(db, *, entity_id: str, source_id: str, title: str, source_type: str = "nse", days_ago: int = 1) -> str:
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=doc_id, evidence_key=f"key-{doc_id}", payload_hash=f"hash-{doc_id}", source_id=source_id, source_type=source_type,
        title=title, published_at=now - timedelta(days=days_ago), observed_at=now,
    ))
    await db.flush()
    db.add(EvidenceEntityLink(entity_id=entity_id, raw_evidence_id=doc_id, relationship_type="subject", resolution_method="source_symbol"))
    return doc_id


async def _cleanup(entity_ids=(), evidence_ids=(), source_ids=()):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.execute(delete(Source).where(Source.id.in_(source_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_unresolved_entity_is_insufficient():
    async with AsyncSessionLocal() as db:
        result = await build_evidence_set(db, symbol=f"NOTAREAL{_tag()}", event_headline="Anything")
    assert result.status == INSUFFICIENT
    assert result.primary_evidence is None


@pytest.mark.asyncio
async def test_same_company_but_unrelated_development_is_excluded():
    """The owner's own real example: a genuine order-win development must
    not pull in this company's AGM notice, dividend record date, or an
    unrelated board appointment merely because they share an entity_id."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    order_headline = f"{symbol} wins real Rs 800 crore order from a real infrastructure client"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            order_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=0,
                title=f"{symbol} has informed the Exchange regarding a press release: real Rs 800 crore order win from infrastructure client",
            )
            agm_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=1,
                title=f"{symbol} has informed the Exchange regarding Notice of Annual General Meeting",
            )
            dividend_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=2,
                title=f"{symbol} has informed the Exchange that Record date for dividend has been fixed",
            )
            board_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=1,
                title=f"{symbol} has informed the Exchange regarding appointment of an Independent Director",
            )
            evidence_ids += [order_doc, agm_doc, dividend_doc, board_doc]
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await build_evidence_set(db, symbol=symbol, event_headline=order_headline)
        assert result.primary_evidence is not None
        assert result.primary_evidence.raw_evidence_id == order_doc
        excluded_ids = {e.evidence.raw_evidence_id: e.reason_code for e in result.excluded_evidence}
        assert excluded_ids.get(agm_doc) == DIFFERENT_DEVELOPMENT
        assert excluded_ids.get(dividend_doc) == DIFFERENT_DEVELOPMENT
        assert excluded_ids.get(board_doc) == DIFFERENT_DEVELOPMENT
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_primary_prefers_authoritative_source_over_higher_lexical_overlap():
    """The owner's explicit requirement: an NSE results filing must be
    primary even when an RSS article discussing those results has
    stronger raw lexical overlap with the query headline."""
    symbol, entity_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}"
    nse_source, rss_source = f"src_nse_{_tag()}", f"src_rss_{_tag()}"
    evidence_ids = []
    headline = f"{symbol} quarterly results beat estimates on strong real demand"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, nse_source, source_type="nse")
            await _seed_source(db, rss_source, source_type="rss")
            # The RSS article's title deliberately echoes the query
            # headline near-verbatim -- high lexical overlap.
            rss_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=rss_source, source_type="rss", days_ago=0,
                title=f"{symbol} quarterly results beat estimates on strong real demand, analysts say",
            )
            # The real NSE filing itself -- lower raw lexical overlap
            # with the paraphrased query headline, but the actual
            # authoritative source.
            nse_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=nse_source, source_type="nse", days_ago=0,
                title=f"{symbol} has informed the Exchange regarding financial results for the quarter ended real period",
            )
            evidence_ids += [rss_doc, nse_doc]
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await build_evidence_set(db, symbol=symbol, event_headline=headline)
        assert result.primary_evidence is not None
        assert result.primary_evidence.raw_evidence_id == nse_doc
        assert result.primary_evidence.source_type == "nse"
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[nse_source, rss_source])


@pytest.mark.asyncio
async def test_duplicate_evidence_collapses_to_one_representative():
    """3 near-identical copies of the same real filing must not count as
    3 independent pieces of evidence."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    base_title = f"{symbol} has informed the Exchange regarding a press release: real merger agreement signed"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            for i, variant in enumerate([base_title, base_title.upper(), base_title + "."]):
                doc_id = await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=variant, days_ago=i)
                evidence_ids.append(doc_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await build_evidence_set(db, symbol=symbol, event_headline="real merger agreement signed")
        assert result.primary_evidence is not None
        total_kept = 1 + len(result.supporting_evidence)
        assert total_kept == 1  # all 3 collapse to a single representative
        dup_reasons = [e.reason_code for e in result.excluded_evidence]
        assert dup_reasons.count(DUPLICATE_EVIDENCE) == 2
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_stale_evidence_is_excluded_from_the_live_development():
    """A topically-related item published long before the development's
    real live evidence is stale context, not current corroboration."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    headline = f"{symbol} real capacity expansion plan approved by board"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            live_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=0,
                title=f"{symbol} has informed the Exchange regarding a press release: real capacity expansion plan approved",
            )
            stale_doc = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=60,
                title=f"{symbol} has informed the Exchange regarding a press release: real capacity expansion plan under review",
            )
            evidence_ids += [live_doc, stale_doc]
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await build_evidence_set(db, symbol=symbol, event_headline=headline)
        assert result.primary_evidence is not None
        assert result.primary_evidence.raw_evidence_id == live_doc
        excluded_ids = {e.evidence.raw_evidence_id: e.reason_code for e in result.excluded_evidence}
        assert excluded_ids.get(stale_doc) == STALE_CONTEXT
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_conflicting_numeric_claims_are_preserved_not_resolved():
    """Two development-matched items disagreeing on a real material
    number must be recorded as a conflict, not silently averaged or
    forced into a false consensus -- and status must reflect it (PARTIAL,
    not COHERENT, even with real supporting evidence present)."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    headline = f"{symbol} real fundraising announcement"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc1 = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=0,
                title=f"{symbol} has informed the Exchange regarding a press release: real fundraising of Rs 500 crore approved",
            )
            doc2 = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=0,
                title=f"{symbol} has informed the Exchange regarding a press release: real fundraising of Rs 700 crore approved",
            )
            evidence_ids += [doc1, doc2]
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await build_evidence_set(db, symbol=symbol, event_headline=headline)
        assert result.status == PARTIAL
        assert len(result.conflicts) >= 1
        assert result.conflicts[0].kind == "currency_inr"
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_coherent_status_requires_primary_plus_real_supporting_no_conflicts():
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    headline = f"{symbol} real acquisition of a real target company"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc1 = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=0,
                title=f"{symbol} has informed the Exchange regarding a press release: real acquisition of a real target company completed",
            )
            doc2 = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id, days_ago=0,
                title=f"{symbol} has informed the Exchange regarding board approval for real acquisition of a real target company",
            )
            evidence_ids += [doc1, doc2]
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await build_evidence_set(db, symbol=symbol, event_headline=headline)
        assert result.status == COHERENT
        assert result.primary_evidence is not None
        assert len(result.supporting_evidence) >= 1
        assert result.conflicts == []
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])

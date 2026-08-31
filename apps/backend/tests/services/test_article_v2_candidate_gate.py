"""
Article V2 Phase C1 — Candidate Gate tests. Real DB-backed, matching this
codebase's established fixture convention (test_article_evidence_bundle.py).
Every required test category from the owner's C1 authorization is covered:
unresolved company, zero linked evidence, duplicated evidence, already-
covered development (both real-event-id and headline-similarity paths),
same company but a genuinely different development, a strong-evidence-but
-low-materiality administrative filing, and a material event with limited
but authoritative evidence.
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
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.article_v2.candidate_gate import (
    CANDIDATE, SKIP, UPDATE_CANDIDATE, evaluate_candidate,
)


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


async def _seed_source(db, source_id: str):
    db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type="nse", collection_method="test"))
    await db.flush()


async def _seed_entity(db, symbol: str, entity_id: str):
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Banking", source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))


async def _seed_evidence(db, *, entity_id: str, source_id: str, title: str, days_ago: int = 1) -> str:
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=doc_id, evidence_key=f"key-{doc_id}", payload_hash=f"hash-{doc_id}", source_id=source_id, source_type="nse",
        title=title, published_at=now - timedelta(days=days_ago), observed_at=now,
    ))
    await db.flush()
    db.add(EvidenceEntityLink(entity_id=entity_id, raw_evidence_id=doc_id, relationship_type="subject", resolution_method="source_symbol"))
    return doc_id


async def _cleanup(entity_ids=(), evidence_ids=(), source_ids=(), article_ids=()):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.execute(delete(Source).where(Source.id.in_(source_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_unresolved_company_is_skipped():
    async with AsyncSessionLocal() as db:
        result = await evaluate_candidate(db, symbol=f"NOTAREALSYMBOL{_tag()}", event_headline="Some real-sounding headline")
    assert result.outcome == SKIP
    assert result.reason_code == "ENTITY_UNRESOLVED"


@pytest.mark.asyncio
async def test_zero_linked_evidence_is_skipped():
    symbol, entity_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(db, symbol=symbol, event_headline="Anything")
        assert result.outcome == SKIP
        assert result.reason_code == "INSUFFICIENT_EVIDENCE"
        assert result.evidence_count == 0
    finally:
        await _cleanup(entity_ids=[entity_id])


@pytest.mark.asyncio
async def test_material_event_with_a_single_authoritative_filing_is_a_candidate():
    """A single HIGH-substantiveness filing (real NSE phrase, per
    evidence_ranking.py's own taxonomy) is enough on its own -- limited
    evidence count doesn't matter when what's there is genuinely
    material."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc_id = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id,
                title=f"{symbol} has informed the Exchange regarding a press release: real acquisition announcement",
            )
            evidence_ids.append(doc_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(db, symbol=symbol, event_headline="Acquisition announcement")
        assert result.outcome == CANDIDATE
        assert result.reason_code == "EVIDENCE_SUFFICIENT"
        assert result.evidence_count == 1
        assert result.top_evidence_score is not None and result.top_evidence_score >= 0.25
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_strong_evidence_count_but_administrative_filing_is_low_materiality():
    """Real evidence EXISTS (not the INSUFFICIENT_EVIDENCE case) but every
    item is a real, recognized LOW-substantiveness administrative filing
    -- must still be filtered out, evidence presence alone isn't enough."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            for i, title in enumerate([
                f"{symbol} has informed the Exchange regarding Allotment of Equity Shares under Employee Stock Option",
                f"{symbol} has informed the Exchange about Closure of Trading Window",
                f"{symbol} has informed the Exchange regarding Record Date for dividend",
            ]):
                doc_id = await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=title, days_ago=i)
                evidence_ids.append(doc_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(db, symbol=symbol, event_headline="Routine administrative filing")
        assert result.outcome == SKIP
        assert result.reason_code == "LOW_MATERIALITY"
        assert result.evidence_count == 3
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_already_covered_by_exact_trigger_event_id_becomes_update_candidate():
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    event_id = f"evt_{_tag()}"
    evidence_ids, article_ids = [], []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc_id = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id,
                title=f"{symbol} has informed the Exchange regarding a press release: real merger update",
            )
            evidence_ids.append(doc_id)
            article_id = str(uuid.uuid4())
            db.add(IntelligenceArticle(
                id=article_id, headline=f"{symbol} announces real merger", article_type="event_analysis",
                trigger_event_id=event_id, lifecycle_status="published", status="published",
                companies_affected=[{"symbol": symbol, "name": symbol}],
            ))
            article_ids.append(article_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(db, symbol=symbol, event_headline="Different phrasing entirely", event_id=event_id)
        assert result.outcome == UPDATE_CANDIDATE
        assert result.reason_code == "ALREADY_COVERED"
        assert result.matched_article_id == article_id
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id], article_ids=article_ids)


@pytest.mark.asyncio
async def test_already_covered_by_headline_similarity_becomes_update_candidate():
    """Same real development, re-filed/restated -- no real event_id match,
    but the headline text is near-identical and the article genuinely
    concerns this symbol. Must still be caught, not just the exact-id path."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids, article_ids = [], []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc_id = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id,
                title=f"{symbol} has informed the Exchange regarding a press release: real capital raise plan",
            )
            evidence_ids.append(doc_id)
            article_id = str(uuid.uuid4())
            db.add(IntelligenceArticle(
                id=article_id, headline=f"{symbol} unveils real capital raise plan for expansion",
                article_type="event_analysis", trigger_event_id=f"evt_{_tag()}",
                lifecycle_status="published", status="published",
                companies_affected=[{"symbol": symbol, "name": symbol}],
            ))
            article_ids.append(article_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(
                db, symbol=symbol, event_headline=f"{symbol} real capital raise plan for expansion",
                event_id=f"evt_{_tag()}",  # deliberately a DIFFERENT event_id -- only headline similarity should catch this
            )
        assert result.outcome == UPDATE_CANDIDATE
        assert result.reason_code == "ALREADY_COVERED"
        assert result.matched_article_id == article_id
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id], article_ids=article_ids)


@pytest.mark.asyncio
async def test_same_company_genuinely_different_development_is_still_a_candidate():
    """A real existing article about a DIFFERENT, unrelated development for
    the same company must NOT suppress a genuinely new, materially
    different story -- ALREADY_COVERED is about the same underlying
    development, not "this company was ever written about before"."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids, article_ids = [], []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc_id = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id,
                title=f"{symbol} has informed the Exchange regarding a press release: real new leadership appointment",
            )
            evidence_ids.append(doc_id)
            article_id = str(uuid.uuid4())
            db.add(IntelligenceArticle(
                id=article_id, headline=f"{symbol} reports real quarterly financial results beat",
                article_type="event_analysis", trigger_event_id=f"evt_{_tag()}",
                lifecycle_status="published", status="published",
                companies_affected=[{"symbol": symbol, "name": symbol}],
            ))
            article_ids.append(article_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(
                db, symbol=symbol, event_headline=f"{symbol} announces new leadership appointment",
                event_id=f"evt_{_tag()}",  # different real event
            )
        assert result.outcome == CANDIDATE
        assert result.reason_code == "EVIDENCE_SUFFICIENT"
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id], article_ids=article_ids)


@pytest.mark.asyncio
async def test_low_substantiveness_filing_is_not_rescued_by_query_relevance_alone():
    """C1.1 regression, 2026-08-31 -- the exact real shadow-run finding:
    TREJHARA's real 'Copy of Newspaper Publication' filing (explicitly a
    recognized LOW-substantiveness phrase) scored 0.32 -- above the
    unchanged 0.25 floor -- purely because the query context (the real
    event's own headline) closely echoes the filing's own title, giving
    a near-perfect Jaccard relevance score. Reproduced here with a
    near-identical real-shaped case: must now be SKIP/LOW_MATERIALITY,
    not CANDIDATE, with zero independent corroborating evidence."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    title = f"{symbol} SOLUTIONS LIMITED has informed the Exchange about Copy of Newspaper Publication regarding 09th Annual General Meeting"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            doc_id = await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=title)
            evidence_ids.append(doc_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            # Query context is the near-identical real event headline --
            # exactly the real-world condition that inflated the score.
            result = await evaluate_candidate(db, symbol=symbol, event_headline=title)
        assert result.outcome == SKIP
        assert result.reason_code == "LOW_MATERIALITY"
        assert "C1.1 hardening" in result.reason_detail
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_low_substantiveness_top_item_still_candidate_with_independent_high_corroboration():
    """The other half of C1.1: a low-substantiveness top-ranked item must
    NOT block a real candidate decision when genuine, independent
    corroborating evidence exists elsewhere in the bundle (a real,
    separate HIGH-substantiveness filing) -- the gate, not blanket
    suppression."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            # Top-ranked (most recent, day 0): low-substantiveness, will
            # score highest on query-relevance alone.
            low_title = f"{symbol} has informed the Exchange about Copy of Newspaper Publication regarding AGM"
            doc1 = await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=low_title, days_ago=0)
            evidence_ids.append(doc1)
            # Independent real corroboration: a genuinely separate
            # high-substantiveness filing (older, so it ranks below the
            # query-matching one, but its own real signal must still count).
            high_title = f"{symbol} has informed the Exchange regarding a press release: real board approval of merger"
            doc2 = await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=high_title, days_ago=2)
            evidence_ids.append(doc2)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(db, symbol=symbol, event_headline=low_title)
        assert result.outcome == CANDIDATE
        assert result.reason_code == "EVIDENCE_SUFFICIENT"
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])


@pytest.mark.asyncio
async def test_update_candidate_is_reachable_and_distinct_from_skip():
    """Owner instruction, 2026-08-31: prove UPDATE_CANDIDATE is an
    actually-reachable third state, not dead code, by exercising it with
    GENUINELY NEW evidence about an already-covered development (not
    just a re-surfaced identical headline) -- and prove in the SAME test
    that a real zero-evidence case lands on SKIP, not UPDATE_CANDIDATE,
    so the three outcomes are demonstrably distinct code paths, not one
    branch wearing two labels."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids, article_ids = [], []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            # The ALREADY-COVERED article represents an earlier real
            # development (a fundraising announcement).
            article_id = str(uuid.uuid4())
            db.add(IntelligenceArticle(
                id=article_id, headline=f"{symbol} announces real Rs 500 crore fundraising plan via QIP",
                article_type="event_analysis", trigger_event_id=f"evt_{_tag()}",
                lifecycle_status="published", status="published",
                companies_affected=[{"symbol": symbol, "name": symbol}],
            ))
            article_ids.append(article_id)
            # GENUINELY NEW evidence: a real follow-up filing with fresh
            # incremental information (the QIP price finalized) about the
            # SAME real development, not just a re-post of the same text.
            doc_id = await _seed_evidence(
                db, entity_id=entity_id, source_id=source_id,
                title=f"{symbol} has informed the Exchange regarding a press release: real Rs 500 crore fundraising plan via QIP priced at final issue price",
            )
            evidence_ids.append(doc_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            update_result = await evaluate_candidate(
                db, symbol=symbol,
                event_headline=f"{symbol} finalizes real Rs 500 crore fundraising plan via QIP at final issue price",
                event_id=f"evt_{_tag()}",  # a different real event_id -- caught via headline similarity, not identity
            )
        assert update_result.outcome == UPDATE_CANDIDATE
        assert update_result.reason_code == "ALREADY_COVERED"
        assert update_result.matched_article_id == article_id

        # Same symbol, but a genuinely separate, zero-evidence gate call
        # must land on SKIP -- proving UPDATE_CANDIDATE isn't just a
        # renamed SKIP path triggered by any old symbol match.
        other_symbol, other_entity_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}"
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, other_symbol, other_entity_id)
            await db.commit()
        try:
            async with AsyncSessionLocal() as db:
                skip_result = await evaluate_candidate(db, symbol=other_symbol, event_headline="Unrelated")
            assert skip_result.outcome == SKIP
            assert skip_result.reason_code == "INSUFFICIENT_EVIDENCE"
        finally:
            await _cleanup(entity_ids=[other_entity_id])

        assert update_result.outcome != skip_result.outcome
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id], article_ids=article_ids)


@pytest.mark.asyncio
async def test_duplicated_evidence_within_bundle_does_not_crash_and_still_gates_sensibly():
    """Within-bundle evidence dedup is explicitly Phase C2's job, not C1's
    (owner's own 7-stage design) -- but C1 must not crash or produce a
    nonsensical decision when the same real filing effectively appears
    twice (case-variant title / cross-feed restatement, the real GESHIP/
    COALINDIA pattern from the Phase B checkpoint). A genuinely
    substantive duplicated filing should still gate through."""
    symbol, entity_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", f"src_{_tag()}"
    evidence_ids = []
    try:
        async with AsyncSessionLocal() as db:
            await _seed_entity(db, symbol, entity_id)
            await _seed_source(db, source_id)
            base_title = f"{symbol} has informed the Exchange regarding a press release: real credit rating action"
            for variant in [base_title, base_title.upper()]:
                doc_id = await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=variant)
                evidence_ids.append(doc_id)
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await evaluate_candidate(db, symbol=symbol, event_headline="Credit rating action")
        assert result.outcome == CANDIDATE
        assert result.evidence_count == 2  # both duplicates counted -- real dedup is C2's job, not silently hidden here
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id])

"""
AI Article V2 Phase A — real tests for ArticleEvidenceBundle and the
code-composed grounded "What Happened". No network calls (price-move
fetch and historical-context are excluded per-test via the
include_price_move/include_historical flags), real DB-backed evidence.
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
from app.services.warehouse.article_evidence_bundle import build_article_evidence_bundle, compose_what_happened_from_evidence


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


async def _seed_source(db, source_id: str):
    db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type="nse", collection_method="test"))


async def _cleanup(symbols, entity_ids, evidence_ids, source_ids):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.execute(delete(Source).where(Source.id.in_(source_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_bundle_resolves_and_includes_real_linked_evidence():
    symbol, entity_id, doc_id, source_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}", str(uuid.uuid4()), f"src_{_tag()}"
    now = datetime.now(timezone.utc)
    try:
        async with AsyncSessionLocal() as db:
            await _seed_source(db, source_id)
            db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Banking", source="test"))
            await db.flush()
            db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))
            db.add(RawEvidence(
                id=doc_id, evidence_key=f"key-{doc_id}", payload_hash="x", source_id=source_id, source_type="nse",
                title=f"{symbol} has informed the Exchange about a real test disclosure",
                published_at=now - timedelta(days=1), observed_at=now,
            ))
            await db.flush()
            db.add(EvidenceEntityLink(raw_evidence_id=doc_id, entity_id=entity_id, relationship_type="subject", resolution_method="source_symbol", confidence=1.0))
            await db.commit()

        async with AsyncSessionLocal() as db:
            bundle = await build_article_evidence_bundle(db, symbol, include_price_move=False, include_historical=False)

        assert bundle.resolved is True
        assert bundle.entity_id == entity_id
        assert len(bundle.evidence) == 1
        assert bundle.evidence[0].title.startswith(symbol)
        assert bundle.marketripple_score is None  # Phase A: always None

        what_happened = compose_what_happened_from_evidence(bundle)
        assert what_happened is not None
        assert symbol not in what_happened or bundle.company_name in what_happened  # real company name used, not raw symbol
        assert "real test disclosure" in what_happened
    finally:
        await _cleanup([symbol], [entity_id], [doc_id], [source_id])


@pytest.mark.asyncio
async def test_bundle_unresolved_symbol_returns_honest_empty_bundle():
    async with AsyncSessionLocal() as db:
        bundle = await build_article_evidence_bundle(db, f"NOTAREALCOMPANY{_tag()}", include_price_move=False, include_historical=False)
    assert bundle.resolved is False
    assert bundle.evidence == []
    assert compose_what_happened_from_evidence(bundle) is None


@pytest.mark.asyncio
async def test_bundle_resolved_but_zero_linked_evidence_never_fabricates():
    symbol, entity_id = f"T{_tag()}", f"cmp_{uuid.uuid4().hex[:12]}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Banking", source="test"))
            await db.flush()
            db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))
            await db.commit()

        async with AsyncSessionLocal() as db:
            bundle = await build_article_evidence_bundle(db, symbol, include_price_move=False, include_historical=False)

        assert bundle.resolved is True
        assert bundle.evidence == []
        assert compose_what_happened_from_evidence(bundle) is None  # never a fabricated placeholder
    finally:
        await _cleanup([symbol], [entity_id], [], [])

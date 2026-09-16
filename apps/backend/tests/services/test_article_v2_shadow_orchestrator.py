"""
Article V2 Phase P5 — Shadow/canary orchestration tests. Real DB-backed,
matching this codebase's established fixture convention
(test_article_v2_candidate_gate.py). Covers: early stops (no tickers,
C1 SKIP) needing no LLM mocking; one real end-to-end run reaching
would_publish=True through the full C1-C8.5+P1+P2+P4 path with the LLM
mocked (headline_engine + composer's why_it_matters); and the central
structural guarantee -- shadow mode NEVER creates a public
`IntelligenceArticle` row, proven by querying the real table, not by
trusting the code's own claim.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

import app.services.article_v2.composer as composer_module
import app.services.article_v2.headline_engine as headline_engine_module
from app.db.models.article_v2_shadow_execution import ArticleV2ShadowExecution
from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.financial_fact import FinancialFact
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.article_v2.collision_gate import V1Decision
from app.services.article_v2.mode import ArticlePipelineMode
from app.services.article_v2.shadow_orchestrator import run_shadow_batch


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


async def _seed_source(db, source_id: str):
    db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type="nse", collection_method="test"))
    await db.flush()


async def _seed_entity(db, symbol: str, entity_id: str):
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Infrastructure", source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))


async def _seed_evidence(db, *, entity_id: str, source_id: str, title: str, days_ago: int = 0) -> str:
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=doc_id, evidence_key=f"key-{doc_id}", payload_hash=f"hash-{doc_id}", source_id=source_id, source_type="nse",
        title=title, published_at=now - timedelta(days=days_ago), observed_at=now,
    ))
    await db.flush()
    db.add(EvidenceEntityLink(entity_id=entity_id, raw_evidence_id=doc_id, relationship_type="subject", resolution_method="source_symbol"))
    return doc_id


async def _seed_fact(db, *, symbol: str, metric_code: str, metric_name: str, value: float, unit: str,
                      fiscal_year: int, fiscal_quarter: int | None, quality_status: str = "OK"):
    db.add(FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_name, value=value, unit=unit,
        fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter, period_type="Quarterly" if fiscal_quarter else "Annual",
        consolidation_scope="Non-Consolidated", source_provider="NSE",
        extraction_status="POPULATED", quality_status=quality_status,
    ))


async def _cleanup(entity_ids=(), evidence_ids=(), source_ids=(), shadow_ids=(), symbols=()):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.id.in_(shadow_ids)))
        await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.execute(delete(Source).where(Source.id.in_(source_ids)))
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol.in_(symbols)))
        await db.commit()


def _triage_event(event_id: str, headline: str, tickers: list[str]) -> dict:
    return {"event_id": event_id, "headline": headline, "urgency": 8, "importance": 7, "tickers": tickers, "sectors": [], "themes": []}


@pytest.mark.asyncio
async def test_no_tickers_stops_immediately_with_no_db_pipeline_calls():
    event_id = f"evt-{_tag()}"
    async with AsyncSessionLocal() as db:
        records = await run_shadow_batch(
            db, triage_events=[(_triage_event(event_id, "Some headline with no tickers", []), "approved")],
            v1_decisions={}, mode=ArticlePipelineMode.SHADOW_V2,
        )
    try:
        assert len(records) == 1
        assert records[0].stage_reached == "C1"
        assert records[0].would_publish is False
        assert "no tickers" in records[0].rejection_reason
        assert records[0].pipeline_mode == "shadow_v2"
    finally:
        await _cleanup(shadow_ids=[r.id for r in records])


@pytest.mark.asyncio
async def test_unresolved_entity_skips_at_c1_and_is_recorded():
    symbol = f"NOPE{_tag()}"
    event_id = f"evt-{_tag()}"
    async with AsyncSessionLocal() as db:
        records = await run_shadow_batch(
            db, triage_events=[(_triage_event(event_id, "Some real-sounding headline", [symbol]), "approved")],
            v1_decisions={event_id: V1Decision(decision="created")}, mode=ArticlePipelineMode.SHADOW_V2,
        )
    try:
        assert len(records) == 1
        r = records[0]
        assert r.c1_outcome == "SKIP"
        assert r.c1_reason_code == "ENTITY_UNRESOLVED"
        assert r.would_publish is False
        assert r.v1_publication_decision == "created"  # the caller's real V1 outcome, passed through untouched
    finally:
        await _cleanup(shadow_ids=[r.id for r in records])


@pytest.mark.asyncio
async def test_full_pipeline_reaches_would_publish_true_and_creates_no_public_article(monkeypatch):
    tag = _tag()
    symbol, entity_id, source_id = f"SHDW{tag}", f"cmp_shdw_{tag.lower()}", f"src-{tag}"
    event_id = f"evt-{tag}"
    title = f"{symbol} wins Rs 500 crore order from Ministry of Railways"

    async def fake_headline_call(prompt, system="", max_tokens=120, priority=None, **kwargs):
        return '{"headline": "Test Co Wins Rs 500 Crore Railway Order"}'

    async def fake_composer_call(prompt, system="", max_tokens=350, priority=None, **kwargs):
        return '{"why_it_matters": "This order strengthens the company revenue visibility.", "claims": []}'

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_headline_call)
    monkeypatch.setattr(composer_module, "_call_with_fallback", fake_composer_call)

    evidence_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        await _seed_source(db, source_id)
        await _seed_entity(db, symbol, entity_id)
        evidence_ids.append(await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=title))
        # Article V2-SG1 (2026-09-16): a real financial fact, so this
        # candidate has genuine structured grounding beyond the
        # triggering filing and legitimately reaches would_publish=True
        # under SG1 -- this test's own point is the shadow-mode
        # never-writes-a-public-row structural guarantee, not SG1 itself
        # (see test_article_v2_publisher_sg1.py for that).
        # "advances" is a real member of _FAMILY_METRIC_ALLOWLIST["ORDER_CONTRACT"]
        # (context_builder.py) -- financial_context is BANKING_V1-scoped
        # today, so an invented non-banking metric code would never match.
        await _seed_fact(db, symbol=symbol, metric_code="advances", metric_name="Advances", value=500.0, unit="inr", fiscal_year=2026, fiscal_quarter=2)
        await db.commit()

    try:
        # No public IntelligenceArticle exists for this entity before the run.
        async with AsyncSessionLocal() as db:
            before = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.headline.like(f"%{symbol}%")))).scalars().all()
        assert before == []

        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(event_id, title, [symbol]), "approved")],
                v1_decisions={event_id: V1Decision(decision="created")}, mode=ArticlePipelineMode.SHADOW_V2,
            )

        assert len(records) == 1
        r = records[0]
        assert r.c1_outcome in ("CANDIDATE", "UPDATE_CANDIDATE")
        assert r.canonical_entity_id == entity_id
        assert r.headline
        assert r.stage_reached == "P4"
        assert r.would_publish is True
        assert r.p4_validation_result == "would_publish"
        assert r.pipeline_version == "C1-C8.5+P1P2P4"

        # The central structural guarantee: shadow execution NEVER creates
        # a public IntelligenceArticle row, queried directly against the
        # real table -- not trusted from the code's own claim.
        async with AsyncSessionLocal() as db:
            after = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.headline.like(f"%{symbol}%")))).scalars().all()
        assert after == [], "shadow_v2 execution must never persist a public IntelligenceArticle row"

        # The shadow row itself IS durably persisted (P6 needs this).
        async with AsyncSessionLocal() as db:
            stored = (await db.execute(select(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.id == r.id))).scalar_one()
        assert stored.would_publish is True
    finally:
        await _cleanup(
            entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id],
            shadow_ids=[r.id for r in records], symbols=[symbol],
        )

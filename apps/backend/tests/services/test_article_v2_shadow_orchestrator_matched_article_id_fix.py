"""
Article V2 Phase P6 remediation (2026-09-08) — regression tests for the
real production defect the P6 cohort review found and root-caused:
`shadow_orchestrator.py` hardcoded `c4_matched_article_id=None` in its
call to `resolve_uniqueness()`, so every real C4 `UPDATE_EXISTING`
decision misreported as `NO_PUBLICATION` instead of correctly
propagating through to P1/P2/P4. Root cause: `CandidateDecision.
matched_article_id` (set by C1 whenever `reason_code == "ALREADY_COVERED"`)
was captured from `evaluate_candidate()` but never carried into
`_PendingCandidate` (which had no field for it) or forward into stage 2.

Real specimens that demonstrated the defect in production: CEIGALL,
AKSHAR, KOTYARK, SHIPROCKET (each: a real one-time CREATE/would_publish
execution, then mislabeled NO_PUBLICATION on every subsequent repeat
once C1 correctly reclassified them as UPDATE_CANDIDATE). These tests
reproduce that exact shape with a real seeded pre-existing
IntelligenceArticle rather than depending on the specific real symbols.

Also covers the P6 telemetry gap fixed in the same remediation:
`p2_authorization_summary` was never populated (existing schema column,
never written) -- `build_and_validate()` now also returns a
`BuildResult.authorization_summary`, and the shadow orchestrator
persists it.
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
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.article_v2.identity import CREATE_NEW, NO_PUBLICATION, UPDATE_EXISTING, resolve_uniqueness
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


async def _seed_existing_article(db, *, article_id: str, trigger_event_id: str, symbol: str, headline: str) -> None:
    """A real, already-published IntelligenceArticle -- the CEIGALL/
    AKSHAR/KOTYARK/SHIPROCKET shape: real existing coverage C1's own
    `_find_already_covered()` must find via trigger_event_id."""
    db.add(IntelligenceArticle(
        id=article_id, slug=article_id, article_type="company_intelligence",
        story_id=article_id, story_version=1, lifecycle_status="published",
        status="published", update_count=0, update_history=[],
        angle="primary", angle_entity=symbol,
        headline=headline, executive_summary="", key_takeaway="", why_it_matters="", what_happened="",
        companies_affected=[{"symbol": symbol}], sectors_affected=[],
        trigger_event_id=trigger_event_id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    ))


async def _cleanup(entity_ids=(), evidence_ids=(), source_ids=(), shadow_ids=(), article_ids=()):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.id.in_(shadow_ids)))
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.execute(delete(Source).where(Source.id.in_(source_ids)))
        await db.commit()


def _triage_event(event_id: str, headline: str, tickers: list[str]) -> dict:
    return {"event_id": event_id, "headline": headline, "urgency": 8, "importance": 7, "tickers": tickers, "sectors": [], "themes": []}


# ── 1. CREATE candidate: no matched_article_id required, unaffected ────────

@pytest.mark.asyncio
async def test_create_candidate_unaffected_by_the_fix(monkeypatch):
    tag = _tag()
    symbol, entity_id, source_id = f"CRT{tag}", f"cmp_crt_{tag.lower()}", f"src-{tag}"
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
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(event_id, title, [symbol]), "approved")],
                v1_decisions={event_id: "created"}, mode=ArticlePipelineMode.SHADOW_V2,
            )
        r = records[0]
        assert r.c1_outcome == "CANDIDATE"  # no existing coverage -- genuinely new
        assert r.c5_publication_action == CREATE_NEW
        assert r.would_publish is True
        assert r.p4_validation_result == "would_publish"
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id], shadow_ids=[r.id for r in records])


# ── 2. UPDATE_EXISTING + real matched_article_id: ID survives end to end ───

@pytest.mark.asyncio
async def test_update_existing_with_real_matched_article_id_reaches_p4(monkeypatch):
    """The CEIGALL/AKSHAR/KOTYARK/SHIPROCKET shape: a company with real
    EXISTING published coverage gets a new, materially substantive
    filing. Before the fix this always misreported as NO_PUBLICATION
    ("C4 did not authorize a new article for this development") even
    though C4 correctly decided UPDATE_EXISTING. After the fix, the
    real matched_article_id must survive to resolve_uniqueness() and
    the candidate must proceed all the way to P1/P2/P4."""
    tag = _tag()
    symbol, entity_id, source_id = f"UPD{tag}", f"cmp_upd_{tag.lower()}", f"src-{tag}"
    event_id = f"evt-{tag}"
    existing_article_id = f"existing-{tag}"
    title = f"{symbol} wins Rs 500 crore order from Ministry of Railways"

    async def fake_headline_call(prompt, system="", max_tokens=120, priority=None, **kwargs):
        return '{"headline": "Test Co Wins Rs 500 Crore Railway Order Update"}'

    async def fake_composer_call(prompt, system="", max_tokens=350, priority=None, **kwargs):
        return '{"why_it_matters": "This order strengthens the company revenue visibility.", "claims": []}'

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_headline_call)
    monkeypatch.setattr(composer_module, "_call_with_fallback", fake_composer_call)

    evidence_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        await _seed_source(db, source_id)
        await _seed_entity(db, symbol, entity_id)
        evidence_ids.append(await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=title))
        await _seed_existing_article(
            db, article_id=existing_article_id, trigger_event_id=event_id, symbol=symbol,
            headline=f"{symbol} announces railway order",
        )
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(event_id, title, [symbol]), "approved")],
                v1_decisions={event_id: "updated"}, mode=ArticlePipelineMode.SHADOW_V2,
            )
        r = records[0]
        # C1 must have found the real existing coverage via trigger_event_id.
        assert r.c1_outcome == "UPDATE_CANDIDATE"
        assert r.c1_reason_code == "ALREADY_COVERED"
        # The fix: C5 must now correctly report UPDATE_EXISTING, never the
        # old mislabeled NO_PUBLICATION.
        assert r.c5_publication_action == UPDATE_EXISTING
        # And it must actually reach P1/P2/P4, not stop at C5.
        assert r.stage_reached == "P4"
        assert r.p4_validation_result == "would_publish"
        assert r.would_publish is True
    finally:
        await _cleanup(
            entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id],
            shadow_ids=[r.id for r in records], article_ids=[existing_article_id],
        )


# ── 3. UPDATE_EXISTING + missing matched_article_id: fail closed ───────────

def test_update_existing_without_matched_article_id_fails_closed_never_create_new():
    """A direct, precise regression guard on resolve_uniqueness() itself
    -- the exact function shadow_orchestrator.py calls. A missing
    matched_article_id must NEVER be silently upgraded into CREATE_NEW;
    it must fail closed to NO_PUBLICATION, exactly as it already does
    today (this test guards that this invariant survives the fix, since
    the fix's whole point is to supply a REAL id when one exists -- it
    must never fabricate one when C1 didn't provide it)."""
    from app.services.article_v2.identity import ArticleIdentity

    identity = ArticleIdentity(
        entity_id="cmp_x", symbol="X", development_type="OTHER", anchor="topic:x", time_bucket="2026-W37",
        identity_key="cmp_x|OTHER|topic:x|2026-W37",
    )
    resolution = resolve_uniqueness(
        identity, c4_publication_action="UPDATE_EXISTING", c4_matched_article_id=None, known_identities={},
    )
    assert resolution.publication_action == NO_PUBLICATION
    assert resolution.publication_action != CREATE_NEW


# ── 4. P2 authorization summary is persisted ────────────────────────────────

@pytest.mark.asyncio
async def test_p2_authorization_summary_persisted_on_would_publish(monkeypatch):
    tag = _tag()
    symbol, entity_id, source_id = f"AUT{tag}", f"cmp_aut_{tag.lower()}", f"src-{tag}"
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
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(event_id, title, [symbol]), "approved")],
                v1_decisions={event_id: "created"}, mode=ArticlePipelineMode.SHADOW_V2,
            )
        r = records[0]
        assert r.would_publish is True
        assert r.p2_authorization_summary is not None
        summary = r.p2_authorization_summary
        assert summary["authorized_count"] >= 1
        assert summary["unavailable_count"] == 0
        assert "historical_description" in summary["capabilities_used"]

        # Re-read from a fresh session to prove it round-trips through the
        # real JSON column, not just held in the in-memory ORM object.
        async with AsyncSessionLocal() as db:
            stored = (await db.execute(select(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.id == r.id))).scalar_one()
        assert stored.p2_authorization_summary["authorized_count"] >= 1
    finally:
        await _cleanup(entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id], shadow_ids=[r.id for r in records])


# ── 5. Still zero public IntelligenceArticle writes, even for UPDATE_EXISTING ─

@pytest.mark.asyncio
async def test_update_existing_path_still_creates_no_public_article(monkeypatch):
    """The structural persistence boundary must hold for the newly-reachable
    UPDATE_EXISTING path too, not just the CREATE path already covered by
    test_article_v2_shadow_orchestrator.py."""
    tag = _tag()
    symbol, entity_id, source_id = f"NPB{tag}", f"cmp_npb_{tag.lower()}", f"src-{tag}"
    event_id = f"evt-{tag}"
    existing_article_id = f"existing-{tag}"
    title = f"{symbol} wins Rs 500 crore order from Ministry of Railways"

    async def fake_headline_call(prompt, system="", max_tokens=120, priority=None, **kwargs):
        return '{"headline": "Test Co Wins Rs 500 Crore Railway Order Update"}'

    async def fake_composer_call(prompt, system="", max_tokens=350, priority=None, **kwargs):
        return '{"why_it_matters": "This order strengthens the company revenue visibility.", "claims": []}'

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_headline_call)
    monkeypatch.setattr(composer_module, "_call_with_fallback", fake_composer_call)

    evidence_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        await _seed_source(db, source_id)
        await _seed_entity(db, symbol, entity_id)
        evidence_ids.append(await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=title))
        await _seed_existing_article(
            db, article_id=existing_article_id, trigger_event_id=event_id, symbol=symbol,
            headline=f"{symbol} announces railway order",
        )
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            before = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.headline.like(f"%{symbol}%")))).scalars().all()
        assert len(before) == 1  # only the seeded existing article

        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(event_id, title, [symbol]), "approved")],
                v1_decisions={event_id: "updated"}, mode=ArticlePipelineMode.SHADOW_V2,
            )
        r = records[0]
        assert r.c5_publication_action == UPDATE_EXISTING
        assert r.would_publish is True

        async with AsyncSessionLocal() as db:
            after = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.headline.like(f"%{symbol}%")))).scalars().all()
        assert len(after) == 1, "shadow_v2 must never persist a public IntelligenceArticle row, even for UPDATE_EXISTING"
        assert after[0].id == existing_article_id  # the seeded one, untouched
    finally:
        await _cleanup(
            entity_ids=[entity_id], evidence_ids=evidence_ids, source_ids=[source_id],
            shadow_ids=[r.id for r in records], article_ids=[existing_article_id],
        )

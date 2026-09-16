"""
Article V2 Phase P4 — Publisher + persistence layer tests. Real DB-backed
(AsyncSessionLocal), matching this codebase's established convention for
DB-touching Article V2 tests -- explicit insert, explicit cleanup, no
fixture-based transactional rollback wrapper. Flushes only (never
commits) inside publish_v2_article itself; these tests commit explicitly
so the row is visible to a fresh query, then delete it in cleanup --
proving persistence works without ever wiring a production entry point
(no route, no scheduler job, nothing outside this test calls it).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.article_v2.claim_translation import TranslationContext
from app.services.article_v2.composer import ComposedArticle, ComposedClaim, ComposedSection
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult, ValidationOutcome
from app.services.article_v2.identity import CREATE_NEW, ArticleIdentity, PublicationResolution
from app.services.article_v2.publisher import PublicationRefusal, publish_v2_article
from app.services.measurement_semantics import IntegrityStatus
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str, raw_id: str) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=raw_id, title=title, source_type="nse", published_at=datetime.now(timezone.utc),
        source_url=None, relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(ev1_id: str, symbol: str = "TESTPUB") -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt1", event_headline=f"{symbol} wins order",
        status=COHERENT, primary_evidence=_evidence(f"{symbol} wins Rs 500 crore order", ev1_id),
        supporting_evidence=[], company_name=f"{symbol} Industries Ltd",
    )


def _identity(symbol: str) -> ArticleIdentity:
    return ArticleIdentity(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, development_type="ORDER_CONTRACT",
        anchor="currency_inr:500", time_bucket="2026-W36",
        identity_key=f"cmp_{symbol.lower()}|ORDER_CONTRACT|currency_inr:500|2026-W36",
    )


def _resolution(identity: ArticleIdentity) -> PublicationResolution:
    return PublicationResolution(
        identity=identity, publication_action=CREATE_NEW, matched_identity_key=None,
        matched_article_id=None, reason="test",
    )


def _decision(evidence_set: ArticleEvidenceSet) -> ArticleDecision:
    return ArticleDecision(
        entity_id=evidence_set.entity_id, symbol=evidence_set.symbol, event_id=evidence_set.event_id,
        event_headline=evidence_set.event_headline, content_type=FACTUAL_UPDATE, publication_action=CREATE,
    )


def _headline(text: str) -> HeadlineResult:
    return HeadlineResult(h1=text, seo_title=text, social_title=text, status=ValidationOutcome.OK, attempts=1)


def _composed(*, what_happened_text: str, ev1_id: str, headline: str) -> ComposedArticle:
    claim = ComposedClaim(text=what_happened_text, claim_type="FACT", evidence_ids=[ev1_id])
    what_happened = ComposedSection(name="what_happened", text=what_happened_text, claims=[claim])
    # Article V2-SG1 (2026-09-16): a real structured fact, so these
    # persistence/field-override/json_ld tests satisfy the sufficiency
    # gate on their own merits and keep testing what they're actually
    # about -- not accidentally blocked by an orthogonal concern. SG1's
    # own tests (test_article_v2_publisher_sg1.py) cover the gate itself.
    fact_claim = ComposedClaim(
        text="Order value: Rs 500 crore.", claim_type="FACT", financial_fact_ids=["ORDER_VALUE"],
        structured_value={"kind": "financial_fact", "label": "Order value", "value": "Rs 500 crore", "period": "FY26 Q2", "metric_code": "ORDER_VALUE"},
    )
    key_details = ComposedSection(name="key_details", text=fact_claim.text, claims=[fact_claim])
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, key_details, source_updated]
    all_claims = [c for s in sections for c in s.claims]
    return ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=headline, sections=sections, all_claims=all_claims,
        llm_status="not_used", llm_attempts=0, word_count=sum(len(s.text.split()) for s in sections),
    )


async def _cleanup(article_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_publish_v2_article_persists_a_real_row_and_never_activates_anything():
    symbol = "TESTPUB1"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-v2-pub-{uuid.uuid4()}"
    evidence_set = _evidence_set(ev1_id, symbol=symbol)
    identity = _identity(symbol)
    composed = _composed(
        what_happened_text=f"On 5 September 2026, {symbol} Industries Ltd filed a Rs 500 crore order win.",
        ev1_id=ev1_id, headline=f"{symbol} Wins Rs 500 Crore Order",
    )
    try:
        async with AsyncSessionLocal() as db:
            article = await publish_v2_article(
                db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
                identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
                composed=composed,
            )
            assert article.id == article_id
            assert article.trigger_type == "article_v2_pipeline"
            assert article.confidence_score == 0.0
            assert article.ripple_effect == []
            await db.commit()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))).scalar_one()
            assert row.headline == f"{symbol} Wins Rs 500 Crore Order"
            assert row.slug.startswith(f"{symbol.lower()}-wins-rs-500-crore-order-")
            assert row.status == "draft"
            assert row.opportunities == []
            assert row.risks == []
    finally:
        await _cleanup([article_id])


@pytest.mark.asyncio
async def test_publish_v2_article_field_overrides_apply_on_top_of_p1_defaults():
    """P7 Real-Write (2026-09-14): the canary publisher must be able to
    explicitly override P1's status="draft"/lifecycle_status="generated"
    defaults -- every public read path filters status=="published", so
    a real canary write left at the P1 default would be persisted,
    collision-protected, and completely invisible to the public site.
    field_overrides is the mechanism; this proves it actually lands on
    the constructed row and leaves every other field untouched."""
    symbol = "TESTPUB1B"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-v2-pub-{uuid.uuid4()}"
    evidence_set = _evidence_set(ev1_id, symbol=symbol)
    identity = _identity(symbol)
    composed = _composed(
        what_happened_text=f"On 5 September 2026, {symbol} Industries Ltd filed a Rs 500 crore order win.",
        ev1_id=ev1_id, headline=f"{symbol} Wins Rs 500 Crore Order",
    )
    published_at = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    try:
        async with AsyncSessionLocal() as db:
            article = await publish_v2_article(
                db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
                identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
                composed=composed,
                field_overrides={"status": "published", "lifecycle_status": "published", "published_at": published_at},
            )
            assert article.status == "published"
            assert article.lifecycle_status == "published"
            assert article.published_at == published_at
            # Untouched by the override -- proves it's a merge, not a replace.
            assert article.trigger_type == "article_v2_pipeline"
            assert article.headline == f"{symbol} Wins Rs 500 Crore Order"
            await db.commit()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))).scalar_one()
            assert row.status == "published"
    finally:
        await _cleanup([article_id])


@pytest.mark.asyncio
async def test_publish_v2_article_syncs_json_ld_to_the_effective_published_at():
    """Article V2-F1 correction (owner review, 2026-09-14): the
    invariant belongs at the generic publication boundary, not in any
    one caller (canary_publisher.py originally special-cased this --
    moved here so no FUTURE caller of publish_v2_article() can forget
    it and persist a stale datePublished). Whenever field_overrides
    marks the effective status "published", json_ld must be rebuilt
    from the EFFECTIVE published_at, never P1's own translation-time
    placeholder."""
    symbol = "TESTPUB1C"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-v2-pub-{uuid.uuid4()}"
    evidence_set = _evidence_set(ev1_id, symbol=symbol)
    identity = _identity(symbol)
    composed = _composed(
        what_happened_text=f"On 5 September 2026, {symbol} Industries Ltd filed a Rs 500 crore order win.",
        ev1_id=ev1_id, headline=f"{symbol} Wins Rs 500 Crore Order",
    )
    effective_published_at = datetime(2026, 9, 20, 8, 30, tzinfo=timezone.utc)
    try:
        async with AsyncSessionLocal() as db:
            article = await publish_v2_article(
                db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
                identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
                composed=composed,
                field_overrides={"status": "published", "lifecycle_status": "published", "published_at": effective_published_at},
            )
            assert article.json_ld["datePublished"] == effective_published_at.isoformat()
            assert article.json_ld["dateModified"] == effective_published_at.isoformat()
            assert article.json_ld["headline"] == article.headline
            await db.commit()
    finally:
        await _cleanup([article_id])


@pytest.mark.asyncio
async def test_publish_v2_article_leaves_p1_placeholder_json_ld_when_not_published():
    """The other half of the same invariant: a caller that never sets
    status="published" (shadow's own validation-only build_and_validate
    path, or simply omitting field_overrides) must NOT have json_ld
    rewritten -- there is no real publication moment to synchronize
    against yet, so P1's own translation-time value stands."""
    symbol = "TESTPUB1D"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-v2-pub-{uuid.uuid4()}"
    evidence_set = _evidence_set(ev1_id, symbol=symbol)
    identity = _identity(symbol)
    composed = _composed(
        what_happened_text=f"On 5 September 2026, {symbol} Industries Ltd filed a Rs 500 crore order win.",
        ev1_id=ev1_id, headline=f"{symbol} Wins Rs 500 Crore Order",
    )
    try:
        async with AsyncSessionLocal() as db:
            article = await publish_v2_article(
                db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
                identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
                composed=composed,
            )
            assert article.status == "draft"
            assert article.json_ld is not None  # P1's own placeholder, still present
            await db.commit()
    finally:
        await _cleanup([article_id])


@pytest.mark.asyncio
async def test_publish_v2_article_refuses_closed_on_degraded_integrity_never_writes_a_row():
    symbol = "TESTPUB2"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-v2-pub-{uuid.uuid4()}"
    evidence_set = _evidence_set(ev1_id, symbol=symbol)
    identity = _identity(symbol)
    composed = _composed(
        what_happened_text=f"On 5 September 2026, {symbol} Industries Ltd filed a Rs 500 crore order win.",
        ev1_id=ev1_id, headline=f"{symbol} Wins Rs 500 Crore Order",
    )
    async with AsyncSessionLocal() as db:
        with pytest.raises(PublicationRefusal):
            await publish_v2_article(
                db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
                identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
                composed=composed, translation_ctx=TranslationContext(integrity_status=IntegrityStatus.DEGRADED),
            )
        await db.rollback()

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))).scalar_one_or_none()
        assert row is None, "PublicationRefusal must never leave a half-written row behind"


@pytest.mark.asyncio
async def test_publish_v2_article_refuses_closed_on_recommendation_language_never_writes_a_row():
    symbol = "TESTPUB3"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-v2-pub-{uuid.uuid4()}"
    evidence_set = _evidence_set(ev1_id, symbol=symbol)
    identity = _identity(symbol)
    unsafe_text = f"{symbol} is the preferred choice over its peers for a 12-month horizon."
    composed = _composed(what_happened_text=unsafe_text, ev1_id=ev1_id, headline=f"{symbol} Wins Rs 500 Crore Order")
    async with AsyncSessionLocal() as db:
        with pytest.raises(PublicationRefusal):
            await publish_v2_article(
                db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
                identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
                composed=composed,
            )
        await db.rollback()

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))).scalar_one_or_none()
        assert row is None

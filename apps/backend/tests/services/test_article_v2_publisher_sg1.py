"""
Article V2-SG1 — Public Article Sufficiency Gate (owner design, 2026-09-16).

Real DB-backed (AsyncSessionLocal), matching this codebase's established
convention. C3R traced two real, C8-ARTICLE, evidently-substantive
acquisitions (GLAND, JSWINFRA) end to end and found nothing beyond NSE's
own one-line filing subject anywhere in MarketRipple -- zero FinancialFact
rows, no deal-specific facts, real detail almost certainly locked inside
an unparsed PDF attachment. SG1 makes publication eligibility reflect the
evidence MarketRipple actually possesses: does at least one real,
authorized, structured fact (a verified financial fact or an authorized
market observation) survive to the translated payload, regardless of how
substantive C8 judged the underlying event or how much raw evidence
exists. C8's own tier judgment is never touched by this gate.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.article_v2.composer import ComposedArticle, ComposedClaim, ComposedSection
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult, ValidationOutcome
from app.services.article_v2.identity import CREATE_NEW, ArticleIdentity, PublicationResolution
from app.services.article_v2.publisher import PublicationRefusal, publish_v2_article
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str, raw_id: str) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=raw_id, title=title, source_type="nse", published_at=datetime.now(timezone.utc),
        source_url=None, relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(symbol: str, ev1_id: str) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt1", event_headline=f"{symbol} acquisition",
        status=COHERENT, primary_evidence=_evidence(f"{symbol} has informed the Exchange about an acquisition", ev1_id),
        supporting_evidence=[], company_name=f"{symbol} Limited",
    )


def _identity(symbol: str) -> ArticleIdentity:
    return ArticleIdentity(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, development_type="ACQUISITION",
        anchor="topic:acquisition", time_bucket="2026-W38",
        identity_key=f"cmp_{symbol.lower()}|ACQUISITION|topic:acquisition|2026-W38",
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


async def _cleanup(article_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()


@pytest.mark.asyncio
async def test_gland_shaped_restatement_with_no_structured_fact_is_refused():
    """The exact real pattern C3R found: a genuinely substantive
    acquisition, a real evidence_ids-backed what_happened claim, but
    nothing structured beyond it -- must now be refused, not published
    as a bare filing restatement."""
    symbol = "TESTSG1A"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-sg1-{uuid.uuid4()}"
    es = _evidence_set(symbol, ev1_id)
    identity = _identity(symbol)

    what_happened_text = f"{symbol} Limited has informed the Exchange about acquisition of 100% of the equity share capital of a subsidiary."
    claim = ComposedClaim(text=what_happened_text, claim_type="FACT", evidence_ids=[ev1_id])
    what_happened = ComposedSection(name="what_happened", text=what_happened_text, claims=[claim])
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, source_updated]
    composed = ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=f"{symbol} Completes Acquisition", sections=sections,
        all_claims=[c for s in sections for c in s.claims], llm_status="not_used", llm_attempts=0,
        word_count=sum(len(s.text.split()) for s in sections),
    )

    try:
        async with AsyncSessionLocal() as db:
            with pytest.raises(PublicationRefusal, match="SG1"):
                await publish_v2_article(
                    db, article_id=article_id, decision=_decision(es), evidence_set=es, identity=identity,
                    resolution=_resolution(identity), headline_result=_headline(composed.headline), composed=composed,
                )
    finally:
        await _cleanup(article_id)


@pytest.mark.asyncio
async def test_shiprocket_shaped_many_evidence_claims_with_no_structured_fact_still_refused():
    """Evidence COUNT alone must never satisfy SG1 -- the real SHIPROCKET
    specimen had 14 evidence items and zero differentiated content.
    Many plain FACT claims (each real, each evidence-backed, each would
    individually authorize as HISTORICAL_DESCRIPTION) still refuse
    without at least one STRUCTURED fact."""
    symbol = "TESTSG1B"
    ev_ids = [str(uuid.uuid4()) for _ in range(14)]
    article_id = f"test-sg1-{uuid.uuid4()}"
    es = _evidence_set(symbol, ev_ids[0])
    identity = _identity(symbol)

    what_happened_text = f"{symbol} Limited has informed the Exchange about a transcript of the earnings call."
    what_happened_claim = ComposedClaim(text=what_happened_text, claim_type="FACT", evidence_ids=[ev_ids[0]])
    what_happened = ComposedSection(name="what_happened", text=what_happened_text, claims=[what_happened_claim])

    related_claims = [
        ComposedClaim(text=f"Related filing #{i}: real supporting evidence.", claim_type="FACT", evidence_ids=[eid])
        for i, eid in enumerate(ev_ids[1:])
    ]
    key_details = ComposedSection(name="key_details", text=" ".join(c.text for c in related_claims), claims=related_claims)
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, key_details, source_updated]
    composed = ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=f"{symbol} Releases Earnings Call Transcript", sections=sections,
        all_claims=[c for s in sections for c in s.claims], llm_status="not_used", llm_attempts=0,
        word_count=sum(len(s.text.split()) for s in sections),
    )

    try:
        async with AsyncSessionLocal() as db:
            with pytest.raises(PublicationRefusal, match="SG1"):
                await publish_v2_article(
                    db, article_id=article_id, decision=_decision(es), evidence_set=es, identity=identity,
                    resolution=_resolution(identity), headline_result=_headline(composed.headline), composed=composed,
                )
    finally:
        await _cleanup(article_id)


@pytest.mark.asyncio
async def test_a_real_financial_fact_satisfies_sg1():
    symbol = "TESTSG1C"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-sg1-{uuid.uuid4()}"
    es = _evidence_set(symbol, ev1_id)
    identity = _identity(symbol)

    what_happened_text = f"{symbol} Limited reported quarterly results."
    what_happened = ComposedSection(
        name="what_happened", text=what_happened_text,
        claims=[ComposedClaim(text=what_happened_text, claim_type="FACT", evidence_ids=[ev1_id])],
    )
    fact_claim = ComposedClaim(
        text="Revenue: Rs 500 crore.", claim_type="FACT", financial_fact_ids=["REVENUE"],
        structured_value={"kind": "financial_fact", "label": "Revenue", "value": "Rs 500 crore", "period": "FY26 Q2", "metric_code": "REVENUE"},
    )
    key_details = ComposedSection(name="key_details", text=fact_claim.text, claims=[fact_claim])
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, key_details, source_updated]
    composed = ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=f"{symbol} Reports Rs 500 Crore Revenue", sections=sections,
        all_claims=[c for s in sections for c in s.claims], llm_status="not_used", llm_attempts=0,
        word_count=sum(len(s.text.split()) for s in sections),
    )

    try:
        async with AsyncSessionLocal() as db:
            article = await publish_v2_article(
                db, article_id=article_id, decision=_decision(es), evidence_set=es, identity=identity,
                resolution=_resolution(identity), headline_result=_headline(composed.headline), composed=composed,
            )
            assert article.key_facts == [
                {"kind": "financial_fact", "label": "Revenue", "value": "Rs 500 crore", "period": "FY26 Q2", "metric_code": "REVENUE"},
            ]
            await db.commit()
    finally:
        await _cleanup(article_id)


@pytest.mark.asyncio
async def test_sunshine_shaped_authorized_market_reaction_satisfies_sg1():
    """The real Sunshine/FUSION pattern (post-MR2): a real, authorized
    market observation alone is enough grounded depth to satisfy SG1,
    even with no financial_context fact."""
    symbol = "TESTSG1D"
    ev1_id = str(uuid.uuid4())
    article_id = f"test-sg1-{uuid.uuid4()}"
    es = _evidence_set(symbol, ev1_id)
    identity = _identity(symbol)

    what_happened_text = f"{symbol} Limited filed quarterly results."
    what_happened = ComposedSection(
        name="what_happened", text=what_happened_text,
        claims=[ComposedClaim(text=what_happened_text, claim_type="FACT", evidence_ids=[ev1_id])],
    )
    reaction_claim = ComposedClaim(
        text=f"{symbol} shares declined 18.11% on the day this was reported (temporal correlation only).",
        claim_type="FACT",
        structured_value={"kind": "market_reaction", "label": "Market reaction", "value": "-18.11%", "period": "observed"},
        market_observation={"instrument": symbol, "observed_at": datetime.now(timezone.utc).isoformat(), "change_pct": -18.11},
    )
    key_details = ComposedSection(name="key_details", text=reaction_claim.text, claims=[reaction_claim])
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, key_details, source_updated]
    composed = ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=f"{symbol} Files Quarterly Results", sections=sections,
        all_claims=[c for s in sections for c in s.claims], llm_status="not_used", llm_attempts=0,
        word_count=sum(len(s.text.split()) for s in sections),
    )

    try:
        async with AsyncSessionLocal() as db:
            article = await publish_v2_article(
                db, article_id=article_id, decision=_decision(es), evidence_set=es, identity=identity,
                resolution=_resolution(identity), headline_result=_headline(composed.headline), composed=composed,
            )
            assert article.key_facts == [{"kind": "market_reaction", "label": "Market reaction", "value": "-18.11%", "period": "observed"}]
            await db.commit()
    finally:
        await _cleanup(article_id)

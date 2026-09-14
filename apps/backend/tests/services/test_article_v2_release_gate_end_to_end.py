"""
Article V2-F3 — End-to-End Release Gate (owner's own contract, 2026-09-14).

This is deliberately NOT a new-behavior test suite -- F1 and F2 are
already closed. Its only job is to prove the finished path works as ONE
system: a real ComposedArticle goes through the actual P1 translator +
Publisher contract (translate_composed_article -> publish_v2_article,
the same pattern test_article_v2_publisher.py already establishes),
lands as a real IntelligenceArticle row, and is read back through the
REAL public route (GET /api/insights/{slug} via TestClient, matching
this codebase's own "test the real API serialization path, not just the
service object" convention -- see
test_event_lifecycle_provenance_survives_api.py).

Two specimens:
  - FULL_ARTICLE: two structured key_facts (financial_fact +
    market_reaction), a what_to_watch claim, two cited sources.
  - THIN (EVENT_ONLY-shaped): only what_happened + boilerplate
    source_updated -- no key_facts, no what_to_watch, one source. Proves
    a genuinely thinner V2 article still publishes and reads back clean
    rather than with fabricated placeholders.

While building this, the FULL_ARTICLE specimen surfaced a real gap:
insights.py's _detail_row() never serialized the `key_facts` column P1
added in F1 -- fixed alongside this test (see insights.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe.seo_metadata import build_canonical_url
from app.services.article_v2.composer import ComposedArticle, ComposedClaim, ComposedSection
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult, ValidationOutcome
from app.services.article_v2.identity import CREATE_NEW, ArticleIdentity, PublicationResolution
from app.services.article_v2.publisher import publish_v2_article
from app.services.warehouse.read_service import LinkedEvidence

client = TestClient(app)


def _evidence(title: str, raw_id: str, source_type: str = "nse") -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=raw_id, title=title, source_type=source_type, published_at=datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc),
        source_url=None, relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _identity(symbol: str) -> ArticleIdentity:
    return ArticleIdentity(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, development_type="ORDER_CONTRACT",
        anchor="currency_inr:500", time_bucket="2026-W37",
        identity_key=f"cmp_{symbol.lower()}|ORDER_CONTRACT|currency_inr:500|2026-W37",
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


async def _publish(*, composed: ComposedArticle, evidence_set: ArticleEvidenceSet, article_id: str, published_at: datetime) -> IntelligenceArticle:
    identity = _identity(evidence_set.symbol)
    async with AsyncSessionLocal() as db:
        article = await publish_v2_article(
            db, article_id=article_id, decision=_decision(evidence_set), evidence_set=evidence_set,
            identity=identity, resolution=_resolution(identity), headline_result=_headline(composed.headline),
            composed=composed,
            field_overrides={"status": "published", "lifecycle_status": "published", "published_at": published_at},
        )
        await db.commit()
        return article


@pytest.mark.asyncio
async def test_full_article_specimen_survives_backend_to_api_to_frontend_contract():
    symbol = "RGATE1"
    ev_primary = str(uuid.uuid4())
    ev_supporting = str(uuid.uuid4())
    article_id = f"test-v2-gate-{uuid.uuid4()}"
    published_at = datetime(2026, 9, 20, 8, 30, tzinfo=timezone.utc)

    evidence_set = ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt-gate-1",
        event_headline=f"{symbol} wins Rs 500 crore order",
        status=COHERENT,
        primary_evidence=_evidence(f"{symbol} wins Rs 500 crore order", ev_primary, source_type="nse"),
        supporting_evidence=[_evidence(f"{symbol} Q2 results filing", ev_supporting, source_type="nse")],
        company_name=f"{symbol} Industries Ltd",
    )

    what_happened = ComposedSection(
        name="what_happened",
        text=f"On 14 September 2026, {symbol} Industries Ltd won a Rs 500 crore order.",
        claims=[ComposedClaim(text=f"On 14 September 2026, {symbol} Industries Ltd won a Rs 500 crore order.", claim_type="FACT", evidence_ids=[ev_primary])],
    )
    why_it_matters = ComposedSection(
        name="why_it_matters",
        text=f"This order materially expands {symbol}'s order book.",
        claims=[ComposedClaim(text=f"This order materially expands {symbol}'s order book.", claim_type="FACT", evidence_ids=[ev_primary])],
    )
    financial_claim = ComposedClaim(
        text="Revenue for FY26 Q2 was Rs 500 crore.", claim_type="FACT", evidence_ids=[ev_supporting],
        structured_value={
            "kind": "financial_fact", "label": "Revenue", "value": "Rs 500 crore",
            "period": "FY26 Q2", "metric_code": "REVENUE", "prior_value": "Rs 420 crore", "prior_period": "FY25 Q2",
        },
    )
    market_claim = ComposedClaim(
        text="The stock moved +3.25% on the news.", claim_type="FACT", evidence_ids=[ev_supporting],
        structured_value={"kind": "market_reaction", "label": "Market reaction", "value": "+3.25%", "period": "observed"},
    )
    key_details = ComposedSection(
        name="key_details", text=f"{financial_claim.text} {market_claim.text}", claims=[financial_claim, market_claim],
    )
    what_to_watch = ComposedSection(
        name="what_to_watch",
        text="A board meeting is scheduled for 30 September 2026 to consider fund raising.",
        claims=[ComposedClaim(text="A board meeting is scheduled for 30 September 2026 to consider fund raising.", claim_type="FACT", evidence_ids=[ev_primary])],
    )
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])

    sections = [what_happened, why_it_matters, key_details, what_to_watch, source_updated]
    composed = ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=f"{symbol} Wins Rs 500 Crore Order",
        sections=sections, all_claims=[c for s in sections for c in s.claims],
        llm_status="not_used", llm_attempts=0, word_count=sum(len(s.text.split()) for s in sections),
    )

    try:
        article = await _publish(composed=composed, evidence_set=evidence_set, article_id=article_id, published_at=published_at)
        slug = article.slug

        resp = client.get(f"/api/insights/{slug}")
        assert resp.status_code == 200
        body = resp.json()

        # key_facts: F3 caught this NOT surviving the read path at all
        # before the insights.py fix landed alongside this test.
        assert len(body["key_facts"]) == 2
        kinds = {f["kind"] for f in body["key_facts"]}
        assert kinds == {"financial_fact", "market_reaction"}
        financial = next(f for f in body["key_facts"] if f["kind"] == "financial_fact")
        assert financial["label"] == "Revenue"
        assert financial["value"] == "Rs 500 crore"
        assert financial["metric_code"] == "REVENUE"
        assert financial["prior_value"] == "Rs 420 crore"
        market = next(f for f in body["key_facts"] if f["kind"] == "market_reaction")
        assert market["value"] == "+3.25%"

        # what_to_watch_next: string list, matching V1's own shape.
        assert body["what_to_watch_next"] == ["A board meeting is scheduled for 30 September 2026 to consider fund raising."]

        # sources: structured dicts, both cited evidence items present,
        # each carrying a real evidence_id -- never V1's bare string[].
        assert len(body["sources"]) == 2
        source_ids = {s["evidence_id"] for s in body["sources"]}
        assert source_ids == {ev_primary, ev_supporting}
        for s in body["sources"]:
            assert isinstance(s["title"], str) and s["title"]

        # risks stays empty -- F1's explicit lock, still true end-to-end.
        assert body["risks"] == []
        assert body["opportunities"] == []

        # canonical_url / json_ld survive the full path, synced to the
        # EFFECTIVE published_at (the publication-boundary fix from F1).
        assert body["canonical_url"] == build_canonical_url(slug)
        assert body["json_ld"]["datePublished"] == published_at.isoformat()
        assert body["json_ld"]["headline"] == composed.headline

        assert body["headline"] == composed.headline
        assert body["why_it_matters"]
        assert body["what_happened"]
    finally:
        await _cleanup(article_id)


@pytest.mark.asyncio
async def test_thin_specimen_publishes_and_reads_back_without_fabricated_placeholders():
    symbol = "RGATE2"
    ev_primary = str(uuid.uuid4())
    article_id = f"test-v2-gate-{uuid.uuid4()}"
    published_at = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)

    evidence_set = ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt-gate-2",
        event_headline=f"{symbol} board meeting notice",
        status=COHERENT,
        primary_evidence=_evidence(f"{symbol} board meeting notice", ev_primary, source_type="nse"),
        supporting_evidence=[], company_name=f"{symbol} Industries Ltd",
    )

    what_happened = ComposedSection(
        name="what_happened",
        text=f"On 14 September 2026, {symbol} Industries Ltd filed a board meeting notice.",
        claims=[ComposedClaim(text=f"On 14 September 2026, {symbol} Industries Ltd filed a board meeting notice.", claim_type="FACT", evidence_ids=[ev_primary])],
    )
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, source_updated]
    composed = ComposedArticle(
        content_type=FACTUAL_UPDATE, headline=f"{symbol} Files Board Meeting Notice",
        sections=sections, all_claims=[c for s in sections for c in s.claims],
        llm_status="not_used", llm_attempts=0, word_count=sum(len(s.text.split()) for s in sections),
    )

    try:
        article = await _publish(composed=composed, evidence_set=evidence_set, article_id=article_id, published_at=published_at)
        slug = article.slug

        resp = client.get(f"/api/insights/{slug}")
        assert resp.status_code == 200
        body = resp.json()

        # No fabrication for sections composer.py had nothing real to say
        # about -- empty lists, never a placeholder claim.
        assert body["key_facts"] == []
        assert body["what_to_watch_next"] == []
        assert body["risks"] == []
        assert body["opportunities"] == []
        assert body["historical_events"] == []

        assert len(body["sources"]) == 1
        assert body["sources"][0]["evidence_id"] == ev_primary

        assert body["headline"] == composed.headline
        assert body["what_happened"]
        # why_it_matters was never composed for this thin specimen.
        assert not body.get("why_it_matters")
    finally:
        await _cleanup(article_id)

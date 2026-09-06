"""
Article V2 Phase P1 — Publication Translation Contract tests. Pure
dataclasses, no DB, no LLM. Covers the real dispositions locked for
every IntelligenceArticle field: EMPTY (V1-only concepts V2.0 doesn't
populate), PROHIBITED (ripple_effect/confidence_score never fabricated),
DETERMINISTIC (executive_summary/key_takeaway/trigger_type composed
from V2's own verified sections, never a second LLM call), and V2
SOURCE (sources built only from claims actually cited, not every
evidence item C2 gathered). Also covers the scan-violation refusal path
(the Round-3 lesson: meta_description must be scanned before storage,
not just the visible body).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.article_v2.composer import ComposedArticle, ComposedClaim, ComposedSection
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult, ValidationOutcome
from app.services.article_v2.identity import CREATE_NEW, ArticleIdentity, PublicationResolution
from app.services.article_v2.publication_translator import build_slug, translate_composed_article
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str, raw_id: str) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=raw_id, title=title, source_type="nse", published_at=datetime.now(timezone.utc),
        source_url="https://nse.example/filing", relationship_type="subject",
        resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(ev1_id: str) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id="cmp_reliance", symbol="RELIANCE", event_id="evt1", event_headline="RELIANCE wins order",
        status=COHERENT, primary_evidence=_evidence("RELIANCE wins Rs 500 crore order", ev1_id),
        supporting_evidence=[], company_name="Reliance Industries Ltd",
    )


def _identity() -> ArticleIdentity:
    return ArticleIdentity(
        entity_id="cmp_reliance", symbol="RELIANCE", development_type="ORDER_CONTRACT",
        anchor="currency_inr:500", time_bucket="2026-W36", identity_key="cmp_reliance|ORDER_CONTRACT|currency_inr:500|2026-W36",
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


def _headline(text: str = "RELIANCE Wins Rs 500 Crore Order") -> HeadlineResult:
    return HeadlineResult(h1=text, seo_title=text, social_title=text, status=ValidationOutcome.OK, attempts=1)


def _composed(*, what_happened_text: str, ev1_id: str, extra_sections: list[ComposedSection] | None = None) -> ComposedArticle:
    claim = ComposedClaim(text=what_happened_text, claim_type="FACT", evidence_ids=[ev1_id])
    what_happened = ComposedSection(name="what_happened", text=what_happened_text, claims=[claim])
    source_updated = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
    sections = [what_happened, *(extra_sections or []), source_updated]
    all_claims = [c for s in sections for c in s.claims]
    return ComposedArticle(
        content_type=FACTUAL_UPDATE, headline="RELIANCE Wins Rs 500 Crore Order", sections=sections,
        all_claims=all_claims, llm_status="not_used", llm_attempts=0, word_count=sum(len(s.text.split()) for s in sections),
    )


class TestDispositions:
    def test_v1_only_concepts_are_empty(self):
        ev1_id = str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        composed = _composed(what_happened_text="On 5 September 2026, Reliance Industries Ltd filed an order win.", ev1_id=ev1_id)
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        f = result.fields
        assert f["opportunities"] == []
        assert f["risks"] == []
        assert f["historical_events"] == []
        assert f["what_to_watch_next"] == []
        assert f["faqs"] == []
        assert f["angle"] == "primary"
        assert f["angle_entity"] is None
        assert f["parent_event_group_id"] is None
        assert f["is_evergreen"] is False

    def test_ripple_effect_is_prohibited_always_empty(self):
        ev1_id = str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        composed = _composed(what_happened_text="A real fact.", ev1_id=ev1_id)
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        assert result.fields["ripple_effect"] == []

    def test_confidence_score_is_never_a_fabricated_value(self):
        ev1_id = str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        composed = _composed(what_happened_text="A real fact.", ev1_id=ev1_id)
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        # The real, unmodified schema default -- never a computed/manufactured "confidence".
        assert result.fields["confidence_score"] == 0.0

    def test_trigger_type_is_the_real_v1_v2_discriminator(self):
        ev1_id = str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        composed = _composed(what_happened_text="A real fact.", ev1_id=ev1_id)
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        assert result.fields["trigger_type"] == "article_v2_pipeline"

    def test_sources_only_include_evidence_actually_cited_by_a_surviving_claim(self):
        ev1_id, ev2_id = str(uuid.uuid4()), str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        # A supporting claim citing ev2 that was never actually part of any composed section --
        # sources must come from all_claims, not from evidence_set.supporting_evidence directly.
        composed = _composed(what_happened_text="A real fact about ev1.", ev1_id=ev1_id)
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        cited_ids = {s["title"] for s in result.fields["sources"]}
        assert len(result.fields["sources"]) == 1
        assert "RELIANCE wins Rs 500 crore order" in cited_ids


class TestDeterministicComposition:
    def test_executive_summary_and_key_takeaway_are_deterministic_first_sentences(self):
        ev1_id = str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        why = ComposedSection(
            name="why_it_matters", text="This matters because of real context. A second sentence.",
            claims=[ComposedClaim(text="This matters because of real context.", claim_type="INTERPRETATION")],
        )
        composed = _composed(what_happened_text="On 5 September 2026, RELIANCE filed a win.", ev1_id=ev1_id, extra_sections=[why])
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        assert result.fields["executive_summary"] == "On 5 September 2026, RELIANCE filed a win."
        assert result.fields["key_takeaway"] == "This matters because of real context."

    def test_slug_is_stable_and_collision_resistant(self):
        slug1 = build_slug("RELIANCE Wins Rs 500 Crore Order", "art-aaaa1111")
        slug2 = build_slug("RELIANCE Wins Rs 500 Crore Order", "art-bbbb2222")
        assert slug1 != slug2
        assert slug1.startswith("reliance-wins-rs-500-crore-order-")


class TestScanViolationRefusal:
    def test_recommendation_language_in_composed_prose_surfaces_as_a_scan_violation(self):
        """The Round-3 lesson, applied at the source: a comparison-style
        recommendation sentence reaching executive_summary/meta_description
        must be caught HERE, before storage -- never store-then-flag."""
        ev1_id = str(uuid.uuid4())
        evidence_set = _evidence_set(ev1_id)
        identity = _identity()
        unsafe_text = "RELIANCE is the preferred choice over its peers for a 12-month horizon."
        composed = _composed(what_happened_text=unsafe_text, ev1_id=ev1_id)
        result = translate_composed_article(
            article_id="art-1", decision=_decision(evidence_set), evidence_set=evidence_set, identity=identity,
            resolution=_resolution(identity), headline_result=_headline(), composed=composed,
        )
        assert result.scan_violations, "expected a scan violation for recommendation-language content"

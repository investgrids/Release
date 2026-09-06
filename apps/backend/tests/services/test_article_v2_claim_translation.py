"""
Article V2 Phase P2 — CD3 Claim Authorization Translator tests. Pure
dataclasses, no DB, no LLM -- covers the four locked corrections
directly: integrity-status-first ordering, DOCUMENTED_FACT (never
HISTORICAL_OUTCOME) for a verified FACT claim, PRICE_SIGN requiring
real structured proof (never inferred from evidence_ids alone), and
INTERPRETATION always QUALIFIED/never AUTHORIZED/never rejected. Also
covers section-level enforcement's split policy: per-claim excision for
concatenated sections, whole-section omission for holistic prose.
"""
from __future__ import annotations

from app.services.article_v2.claim_translation import (
    TranslationContext, authorize_composed_claim, enforce_section_authorization, is_real_market_observation,
)
from app.services.article_v2.composer import ComposedClaim, ComposedSection
from app.services.claim_authorization import Capability, Strength
from app.services.measurement_semantics import IntegrityStatus


def _fact_claim(evidence_ids=None, financial_fact_ids=None, validation_status="VERIFIED") -> ComposedClaim:
    return ComposedClaim(
        text="A real verified fact.", claim_type="FACT",
        evidence_ids=evidence_ids or [], financial_fact_ids=financial_fact_ids or [],
        validation_status=validation_status,
    )


def _interpretation_claim() -> ComposedClaim:
    return ComposedClaim(text="This may matter because of X.", claim_type="INTERPRETATION")


class TestIntegrityFirst:
    def test_non_valid_integrity_overrides_an_otherwise_authorizable_fact_claim(self):
        claim = _fact_claim(evidence_ids=["ev1"])
        result = authorize_composed_claim(claim, TranslationContext(integrity_status=IntegrityStatus.DEGRADED))
        assert result.strength == Strength.UNAVAILABLE
        assert result.capability == Capability.EVIDENCE_QUALITY
        assert "integrity_status=degraded" in (result.reason or "")

    def test_invalid_integrity_overrides_interpretation_too(self):
        result = authorize_composed_claim(_interpretation_claim(), TranslationContext(integrity_status=IntegrityStatus.INVALID))
        assert result.strength == Strength.UNAVAILABLE


class TestDocumentedFactNeverHistoricalOutcome:
    def test_fact_with_evidence_ids_authorizes_as_historical_description(self):
        result = authorize_composed_claim(_fact_claim(evidence_ids=["ev1"]), TranslationContext())
        assert result.strength == Strength.AUTHORIZED
        assert result.capability == Capability.HISTORICAL_DESCRIPTION

    def test_fact_with_financial_fact_ids_also_authorizes(self):
        result = authorize_composed_claim(_fact_claim(financial_fact_ids=["net_profit"]), TranslationContext())
        assert result.strength == Strength.AUTHORIZED
        assert result.capability == Capability.HISTORICAL_DESCRIPTION

    def test_fact_with_neither_evidence_nor_financial_fact_ids_fails_closed(self):
        result = authorize_composed_claim(_fact_claim(), TranslationContext())
        assert result.strength == Strength.UNAVAILABLE
        assert "no evidence_ids/financial_fact_ids" in (result.reason or "")

    def test_non_verified_claim_fails_closed_regardless_of_evidence(self):
        result = authorize_composed_claim(
            _fact_claim(evidence_ids=["ev1"], validation_status="REJECTED"), TranslationContext(),
        )
        assert result.strength == Strength.UNAVAILABLE


class TestPriceSignRequiresRealProof:
    def test_is_real_market_observation_is_never_satisfied_by_shape_alone(self):
        # A FACT claim with financial_fact_ids that LOOKS like it could be
        # a price signal must not be inferred as one -- is_real_market_
        # observation must stay independent of evidence_ids/section name.
        claim = _fact_claim(financial_fact_ids=["price_move_pct"])
        assert is_real_market_observation(claim) is False
        result = authorize_composed_claim(claim, TranslationContext())
        # Falls through to DOCUMENTED_FACT, never OBSERVED_DIRECTION.
        assert result.capability == Capability.HISTORICAL_DESCRIPTION


class TestInterpretationAlwaysQualified:
    def test_interpretation_is_qualified_never_authorized(self):
        result = authorize_composed_claim(_interpretation_claim(), TranslationContext())
        assert result.strength == Strength.QUALIFIED
        assert result.capability == Capability.ANALYTICAL_HYPOTHESIS

    def test_unclassified_claim_type_fails_closed(self):
        claim = ComposedClaim(text="odd", claim_type="SPECULATION")
        result = authorize_composed_claim(claim, TranslationContext())
        assert result.strength == Strength.UNAVAILABLE


class TestSectionEnforcement:
    def test_concatenated_section_drops_only_the_unauthorized_claim(self):
        good = _fact_claim(evidence_ids=["ev1"])
        bad = _fact_claim()  # no evidence -- fails closed
        section = ComposedSection(name="key_details", text=f"{good.text} {bad.text}", claims=[good, bad])
        result = enforce_section_authorization(section, TranslationContext())
        assert result.section is not None
        assert result.section.claims == [good]
        assert result.section.text == good.text
        assert result.dropped_claims == [bad]

    def test_concatenated_section_fully_omitted_when_every_claim_fails(self):
        bad = _fact_claim()
        section = ComposedSection(name="what_happened", text=bad.text, claims=[bad])
        result = enforce_section_authorization(section, TranslationContext())
        assert result.section is None
        assert result.dropped_claims == [bad]

    def test_why_it_matters_holistic_prose_is_wholly_omitted_on_any_failure(self):
        good = _fact_claim(evidence_ids=["ev1"])
        bad = _fact_claim()
        section = ComposedSection(
            name="why_it_matters", text="A holistic paragraph nobody may safely rewrite.", claims=[good, bad],
        )
        result = enforce_section_authorization(section, TranslationContext())
        assert result.section is None
        assert result.dropped_claims == [good, bad]  # both dropped -- whole-section omission, never a partial rewrite

    def test_section_with_no_claims_passes_through_unchanged(self):
        section = ComposedSection(name="source_updated", text="Source: an NSE regulatory filing.", claims=[])
        result = enforce_section_authorization(section, TranslationContext())
        assert result.section is section
        assert result.dropped_claims == []

    def test_all_claims_authorized_leaves_section_untouched(self):
        good1 = _fact_claim(evidence_ids=["ev1"])
        good2 = _fact_claim(financial_fact_ids=["net_profit"])
        section = ComposedSection(name="verified_context", text=f"{good1.text} {good2.text}", claims=[good1, good2])
        result = enforce_section_authorization(section, TranslationContext())
        assert result.section is section
        assert result.dropped_claims == []
        assert len(result.authorizations) == 2

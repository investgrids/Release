"""
Deep Filing Evidence Phase 1C-I — TransactionFact integration (owner
design, 2026-09-17): SourceDocument -> TransactionFact -> Warehouse
read service -> C3 ArticleContextBundle -> C6 composer -> CD3
authorization -> SG1 -> the final published payload.

Real DB-backed, matching this codebase's established convention.
Follows test_article_v2_publisher_sg1.py's own pattern: C1-C5 outputs
are constructed directly as minimal real fixtures (already proven
correct elsewhere) rather than re-run through the full pipeline; this
file's job is to prove the NEW boundary -- C3's real read of
TransactionFact through to the real published payload -- not to
re-prove upstream stages.

Four real acceptance specimens, using their REAL, already-verified
extracted values (Deep Filing Evidence Source Reality Audit +
TransactionFact validation cohorts, 2026-09-17), not synthetic
placeholders:

  ZODIAC (nse-4021315061) -- the primary acceptance case. Formerly a
  bare "acquisition filing + -0.05%" candidate (see the 5-specimen
  Article V2 revalidation that motivated Deep Filing Evidence in the
  first place); now carries real filing-derived facts (target entity,
  100% stake, cash consideration, Rs 1,00,000 consideration) with full
  provenance.

  PRIMO (nse-302e32d5d4) -- the partial-evidence acceptance case:
  target/stake flow through (extracted via the prose strategy), but
  consideration was never found in the filing's own text and must stay
  entirely absent from the published payload, never inferred.

  JUNIPER (nse-...) -- the adversarial normalization case: the article
  layer must receive the correctly normalized Rs 2,48,00,00,000 (not
  R1's original 248 bug), and the full source representation must
  survive as provenance.

  MUTHOOTFIN -- a second-cohort specimen, proving the integration isn't
  limited to the original development population.

Every published fact must retain its provenance chain: source_document_id,
page_number, source_span_text, extraction_method(_version), and a real
evidence lineage (raw_evidence_id) back to RawEvidence -- checked
explicitly in every specimen below, not assumed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_document import EXTRACTED, SourceDocument
from app.db.models.source_registry import Source
from app.db.models.transaction_fact import (
    CONSIDERATION_AMOUNT, CONSIDERATION_TYPE, POPULATED, STAKE_PERCENTAGE, TARGET_ENTITY_NAME, TransactionFact,
)
from app.db.session import AsyncSessionLocal
from app.services.article_v2.claim_translation import TranslationContext, authorize_composed_claim
from app.services.article_v2.composer import compose_article
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult, ValidationOutcome
from app.services.article_v2.identity import CREATE_NEW, ArticleIdentity, PublicationResolution
from app.services.article_v2.publisher import build_and_validate
from app.services.claim_authorization import Capability, Strength
from app.services.warehouse.read_service import get_verified_transaction_facts


def _evidence(title: str, raw_id: str, published_at=None) -> "LinkedEvidence":
    from app.services.warehouse.read_service import LinkedEvidence  # local import, matches sg1 test file's own style
    return LinkedEvidence(
        raw_evidence_id=raw_id, title=title, source_type="nse", published_at=published_at or datetime.now(timezone.utc),
        source_url=None, relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(symbol: str, ev1_id: str, title: str) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt1", event_headline=title,
        status=COHERENT, primary_evidence=_evidence(title, ev1_id), supporting_evidence=[], company_name=f"{symbol} Limited",
    )


def _identity(symbol: str) -> ArticleIdentity:
    return ArticleIdentity(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, development_type="ACQUISITION",
        anchor="topic:acquisition", time_bucket="2026-W38",
        identity_key=f"cmp_{symbol.lower()}|ACQUISITION|topic:acquisition|2026-W38",
    )


def _resolution(identity: ArticleIdentity) -> PublicationResolution:
    return PublicationResolution(
        identity=identity, publication_action=CREATE_NEW, matched_identity_key=None, matched_article_id=None, reason="test",
    )


def _decision(evidence_set: ArticleEvidenceSet) -> ArticleDecision:
    return ArticleDecision(
        entity_id=evidence_set.entity_id, symbol=evidence_set.symbol, event_id=evidence_set.event_id,
        event_headline=evidence_set.event_headline, content_type=FACTUAL_UPDATE, publication_action=CREATE,
    )


def _headline(text: str) -> HeadlineResult:
    return HeadlineResult(h1=text, seo_title=text, social_title=text, status=ValidationOutcome.OK, attempts=1)


async def _seed_chain(db, *, evidence_key: str, facts: list[dict]) -> tuple[str, str]:
    """Real Source -> RawEvidence -> SourceDocument -> TransactionFact
    chain, matching test_transaction_fact_extractor.py's own seeding
    pattern. Returns (raw_evidence_id, source_document_id)."""
    source_id = f"test_source_{uuid.uuid4().hex[:8]}"
    db.add(Source(id=source_id, name="Test Source", source_type="api", collection_method="test"))
    await db.commit()

    raw_evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=raw_evidence_id, evidence_key=evidence_key, payload_hash="x", source_id=source_id, source_type="nse",
        observed_at=now, ingested_at=now, mime_type="application/json", quality="good",
    ))
    await db.commit()

    doc_id = str(uuid.uuid4())
    db.add(SourceDocument(
        id=doc_id, raw_evidence_id=raw_evidence_id, canonical_url="https://example.test/doc.pdf",
        content_hash=uuid.uuid4().hex, byte_size=1000, mime_type="application/pdf",
        retrieved_at=now, extraction_status=EXTRACTED, extraction_method="pypdf",
        extraction_method_version="test", page_count=2, page_texts_json=None,
    ))
    await db.commit()

    for f in facts:
        db.add(TransactionFact(
            source_document_id=doc_id, raw_evidence_id=raw_evidence_id,
            field_code=f["field_code"], field_name=f.get("field_name", f["field_code"]),
            value_text=f.get("value_text"), value_numeric=f.get("value_numeric"), unit=f.get("unit"),
            extraction_status=POPULATED, extraction_method="sebi_reg30_annexure_table", extraction_method_version="1.1",
            page_number=f.get("page_number", 2), source_span_text=f.get("source_span_text", "test span"),
            extracted_at=now,
        ))
    await db.commit()
    return raw_evidence_id, doc_id


async def _cleanup(raw_evidence_id: str, source_document_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        source_id = (await db.execute(select(RawEvidence.source_id).where(RawEvidence.id == raw_evidence_id))).scalar_one_or_none()
        await db.execute(delete(TransactionFact).where(TransactionFact.source_document_id == source_document_id))
        await db.execute(delete(SourceDocument).where(SourceDocument.id == source_document_id))
        await db.execute(delete(RawEvidence).where(RawEvidence.id == raw_evidence_id))
        if source_id:
            await db.execute(delete(Source).where(Source.id == source_id))
        await db.commit()


# ── ZODIAC: primary acceptance specimen, full facts + provenance ────────

@pytest.mark.asyncio
async def test_zodiac_transaction_facts_flow_through_to_the_published_payload_with_provenance():
    symbol, title = "ZODIAC", "Zodiac Energy Limited has informed the Exchange about Acquisition-Incorporation of Wholly Owned Subsidiary"
    async with AsyncSessionLocal() as db:
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:zodiac-integration", facts=[
            {"field_code": TARGET_ENTITY_NAME, "field_name": "Name of the target entity",
             "value_text": "ZODIAC ENERGY IPP-3 PRIVATE LIMITED", "source_span_text": "Name: ZODIAC ENERGY IPP-3 PRIVATE LIMITED"},
            {"field_code": STAKE_PERCENTAGE, "field_name": "Percentage of shareholding / control acquired",
             "value_numeric": 100.0, "unit": "pct", "source_span_text": "100% shareholding and control"},
            {"field_code": CONSIDERATION_TYPE, "field_name": "Consideration", "value_text": "CASH", "source_span_text": "Cash Consideration"},
            {"field_code": CONSIDERATION_AMOUNT, "field_name": "Cost of acquisition", "value_numeric": 100000.0, "unit": "inr",
             "source_span_text": "₹1,00,000 (Rupees One Lakh Only)"},
        ])
        try:
            es = _evidence_set(symbol, raw_evidence_id, title)
            identity = _identity(symbol)
            ctx = await build_context(db, es)

            assert len(ctx.transaction_facts) == 4
            assert ctx.status in ("PARTIAL", "AVAILABLE")

            composed = await compose_article(_decision(es), es, ctx, identity, _resolution(identity), _headline(f"{symbol} Acquisition"))
            build_result = build_and_validate(
                article_id="test-zodiac-integration", decision=_decision(es), evidence_set=es, identity=identity,
                resolution=_resolution(identity), headline_result=_headline(f"{symbol} Acquisition"), composed=composed,
            )

            key_facts = build_result.fields["key_facts"]
            tf_facts = [f for f in key_facts if f.get("field_code") in (TARGET_ENTITY_NAME, STAKE_PERCENTAGE, CONSIDERATION_TYPE, CONSIDERATION_AMOUNT)]
            print("\n--- ZODIAC actual published key_facts ---")
            for f in tf_facts:
                print(" ", f)
            print("--- ZODIAC actual verified_context/key_details text ---")
            for section in composed.sections:
                if section.name in ("verified_context", "key_details"):
                    print(" ", section.text)

            assert len(tf_facts) == 4  # all 4 real facts survived CD3 authorization and SG1
            by_field = {f["field_code"]: f for f in tf_facts}
            assert by_field[TARGET_ENTITY_NAME]["value"] == "ZODIAC ENERGY IPP-3 PRIVATE LIMITED"
            assert by_field[STAKE_PERCENTAGE]["value"] == "100%"
            assert by_field[CONSIDERATION_TYPE]["value"] == "cash"
            # Real regression check: Rs 1,00,000 must never round to "Rs 0 crore"
            # (a real defect found by inspecting this exact payload during
            # integration -- fixed via magnitude-aware formatting, not a
            # hypothetical edge case).
            assert by_field[CONSIDERATION_AMOUNT]["value"] == "Rs 1.00 lakh"

            # Full provenance chain retained for every fact, not flattened.
            # 8, not 4: Article V2 Assembly A1 (2026-09-17) made
            # what_happened fact-aware, so each of the 4 real populated
            # facts now produces its OWN transaction_fact-bearing claim in
            # BOTH sections -- key_facts (the auditable structured list)
            # AND what_happened (its narrative rendering) -- each with its
            # own independent CD3 authorization, never a single fact
            # silently duplicated without provenance.
            tf_claims = [c for s in composed.sections for c in s.claims if c.transaction_fact]
            assert len(tf_claims) == 8
            for c in tf_claims:
                tf = c.transaction_fact
                assert tf["source_document_id"] == doc_id
                assert tf["raw_evidence_id"] == raw_evidence_id
                assert tf["page_number"] is not None
                assert tf["source_span_text"]
                assert tf["extraction_method"] == "sebi_reg30_annexure_table"
                assert tf["extraction_method_version"] == "1.1"

            # SG1 passed on real transaction-fact grounding
            assert build_result.fields.get("key_facts")
        finally:
            await _cleanup(raw_evidence_id, doc_id)


@pytest.mark.asyncio
async def test_zodiac_transaction_fact_claims_authorize_via_historical_description():
    """Direct CD3 check: a real, provenance-complete TransactionFact
    claim authorizes to HISTORICAL_DESCRIPTION -- the same capability an
    evidence_ids-backed document fact already gets, never a new,
    separately-invented capability."""
    async with AsyncSessionLocal() as db:
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:zodiac-cd3", facts=[
            {"field_code": STAKE_PERCENTAGE, "field_name": "Percentage of shareholding / control acquired", "value_numeric": 100.0, "unit": "pct"},
        ])
        try:
            es = _evidence_set("ZODIAC", raw_evidence_id, "Zodiac Energy Limited has informed the Exchange about Acquisition")
            ctx = await build_context(db, es)
            composed = await compose_article(
                _decision(es), es, ctx, _identity("ZODIAC"), _resolution(_identity("ZODIAC")), _headline("Zodiac Acquisition"),
            )
            tf_claim = next(c for s in composed.sections for c in s.claims if c.transaction_fact)
            authorized = authorize_composed_claim(tf_claim, TranslationContext())
            assert authorized.capability == Capability.HISTORICAL_DESCRIPTION
            assert authorized.strength == Strength.AUTHORIZED
        finally:
            await _cleanup(raw_evidence_id, doc_id)


# ── PRIMO: partial-evidence acceptance specimen ──────────────────────────

@pytest.mark.asyncio
async def test_primo_known_facts_flow_through_missing_consideration_stays_absent():
    symbol, title = "PRIMO", "Primo Chemicals Limited has informed the Exchange regarding acquisition of Balance 51% Equity Stake in Flow Tech Chemicals Private Limited."
    async with AsyncSessionLocal() as db:
        # Real PRIMO extraction never found consideration -- only target/stake exist as POPULATED rows.
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:primo-integration", facts=[
            {"field_code": TARGET_ENTITY_NAME, "field_name": "Name of the target entity", "value_text": "Flow Tech Chemicals Private Limited"},
            {"field_code": STAKE_PERCENTAGE, "field_name": "Percentage of shareholding / control acquired", "value_numeric": 51.0, "unit": "pct"},
        ])
        try:
            es = _evidence_set(symbol, raw_evidence_id, title)
            identity = _identity(symbol)
            ctx = await build_context(db, es)
            assert len(ctx.transaction_facts) == 2  # never a phantom 4

            composed = await compose_article(_decision(es), es, ctx, identity, _resolution(identity), _headline(f"{symbol} Acquisition"))
            build_result = build_and_validate(
                article_id="test-primo-integration", decision=_decision(es), evidence_set=es, identity=identity,
                resolution=_resolution(identity), headline_result=_headline(f"{symbol} Acquisition"), composed=composed,
            )
            key_facts = build_result.fields["key_facts"]
            field_codes = {f.get("field_code") for f in key_facts if f.get("field_code")}
            print("\n--- PRIMO actual published key_facts field_codes ---", field_codes)
            assert TARGET_ENTITY_NAME in field_codes
            assert STAKE_PERCENTAGE in field_codes
            assert CONSIDERATION_TYPE not in field_codes
            assert CONSIDERATION_AMOUNT not in field_codes
            full_text = " ".join(f.get("value", "") for f in key_facts if isinstance(f.get("value"), str))
            assert "cash" not in full_text.lower() and "swap" not in full_text.lower()
        finally:
            await _cleanup(raw_evidence_id, doc_id)


# ── JUNIPER: adversarial normalization case ──────────────────────────────

@pytest.mark.asyncio
async def test_juniper_normalized_amount_reaches_the_article_never_the_r1_bug_value():
    """The real R1 regression, end to end: the published payload must
    carry the correctly normalized Rs 2,48,00,00,000, never the
    unrelated bare 248 the original extractor bug would have produced."""
    symbol, title = "JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition"
    async with AsyncSessionLocal() as db:
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:juniper-integration", facts=[
            {"field_code": CONSIDERATION_TYPE, "field_name": "Consideration", "value_text": "CASH",
             "source_span_text": "Cash consideration of Rs. 2,48,00,00,000/- (Rupees Two Hundred Forty-Eight Crores Only)"},
            {"field_code": CONSIDERATION_AMOUNT, "field_name": "Cost of acquisition", "value_numeric": 2_480_000_000.0, "unit": "inr",
             "source_span_text": "Rs. 2,48,00,00,000/- (Rupees Two Hundred Forty-Eight Crores Only)"},
        ])
        try:
            es = _evidence_set(symbol, raw_evidence_id, title)
            identity = _identity(symbol)
            ctx = await build_context(db, es)
            composed = await compose_article(_decision(es), es, ctx, identity, _resolution(identity), _headline(f"{symbol} Acquisition"))
            build_result = build_and_validate(
                article_id="test-juniper-integration", decision=_decision(es), evidence_set=es, identity=identity,
                resolution=_resolution(identity), headline_result=_headline(f"{symbol} Acquisition"), composed=composed,
            )
            key_facts = build_result.fields["key_facts"]
            amount_fact = next(f for f in key_facts if f.get("field_code") == CONSIDERATION_AMOUNT)
            print("\n--- JUNIPER actual published consideration_amount fact ---", amount_fact)
            assert amount_fact["value"] == "Rs 248.00 crore"
            # Provenance retains the exact original filing representation, never just the normalized number
            tf_claim = next(c for s in composed.sections for c in s.claims if c.transaction_fact and c.transaction_fact["field_code"] == CONSIDERATION_AMOUNT)
            assert "2,48,00,00,000" in tf_claim.transaction_fact["source_span_text"]
            assert tf_claim.transaction_fact["value_numeric"] == 2_480_000_000.0
        finally:
            await _cleanup(raw_evidence_id, doc_id)


# ── MUTHOOTFIN: second-cohort specimen ───────────────────────────────────

@pytest.mark.asyncio
async def test_muthootfin_second_cohort_specimen_also_flows_through():
    symbol, title = "MUTHOOTFIN", "Muthoot Finance Limited has informed the Exchange about Acquisition"
    async with AsyncSessionLocal() as db:
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:muthootfin-integration", facts=[
            {"field_code": CONSIDERATION_TYPE, "field_name": "Consideration", "value_text": "CASH", "source_span_text": "Cash"},
            {"field_code": CONSIDERATION_AMOUNT, "field_name": "Cost of acquisition", "value_numeric": 318_009_491.0, "unit": "inr",
             "source_span_text": "approximately ₹31,80,09,491 / INR 31.80 Crores"},
        ])
        try:
            es = _evidence_set(symbol, raw_evidence_id, title)
            identity = _identity(symbol)
            ctx = await build_context(db, es)
            composed = await compose_article(_decision(es), es, ctx, identity, _resolution(identity), _headline(f"{symbol} Acquisition"))
            build_result = build_and_validate(
                article_id="test-muthootfin-integration", decision=_decision(es), evidence_set=es, identity=identity,
                resolution=_resolution(identity), headline_result=_headline(f"{symbol} Acquisition"), composed=composed,
            )
            key_facts = build_result.fields["key_facts"]
            print("\n--- MUTHOOTFIN actual published key_facts ---")
            for f in key_facts:
                if f.get("field_code"):
                    print(" ", f)
            amount_fact = next(f for f in key_facts if f.get("field_code") == CONSIDERATION_AMOUNT)
            assert amount_fact["value"] == "Rs 31.80 crore"  # matches the filing's own "approximately ... INR 31.80 Crores" restatement
        finally:
            await _cleanup(raw_evidence_id, doc_id)


# ── Amount formatting: all three magnitude tiers, directly ──────────────

def test_consideration_amount_formatting_picks_the_right_magnitude_tier():
    from app.services.article_v2.composer import _format_transaction_fact_amount
    assert _format_transaction_fact_amount(2_480_000_000.0) == "Rs 248.00 crore"
    assert _format_transaction_fact_amount(318_009_491.0) == "Rs 31.80 crore"
    assert _format_transaction_fact_amount(100_000.0) == "Rs 1.00 lakh"
    assert _format_transaction_fact_amount(50_000.0) == "Rs 50,000"
    # The real defect this fix closes: a sub-crore amount must never
    # round to zero.
    assert _format_transaction_fact_amount(100_000.0) != "Rs 0 crore"


def test_consideration_amount_formatting_exact_tier_boundaries():
    """Permanent boundary regression, per owner instruction: sub-lakh,
    lakh, and crore tiers, exactly at their thresholds -- the underlying
    normalized value must never change, only its display tier."""
    from app.services.article_v2.composer import _format_transaction_fact_amount, _CRORE, _LAKH
    assert _LAKH == 100_000
    assert _CRORE == 10_000_000
    # Just below the lakh threshold -- plain rupees.
    assert _format_transaction_fact_amount(_LAKH - 1) == "Rs 99,999"
    # Exactly at the lakh threshold -- lakh tier begins.
    assert _format_transaction_fact_amount(_LAKH) == "Rs 1.00 lakh"
    # Comfortably below the crore threshold -- still lakh tier. (Not
    # _CRORE - 1: 9,999,999 / 100,000 = 99.99999, which correctly rounds
    # to "100.00" at 2dp -- a cosmetic rounding coincidence at that exact
    # value, not a tier-selection error; the tier itself still stays lakh.)
    assert _format_transaction_fact_amount(_CRORE - 100_000) == "Rs 99.00 lakh"
    # Exactly at the crore threshold -- crore tier begins.
    assert _format_transaction_fact_amount(_CRORE) == "Rs 1.00 crore"


def test_structured_value_carries_the_raw_normalized_fact_not_only_the_formatted_string():
    """Owner review: structured_value must represent the actual fact
    semantics, not just the human-formatted sentence -- a future
    consumer must be able to read the real number directly rather than
    parsing "Rs 31.80 crore" back into 318009491.0. Authorization
    (claim_translation.py) already reads the raw claim.transaction_fact
    dict, never structured_value; this test locks in that
    structured_value itself also carries the same raw value alongside
    its display string."""
    from app.services.article_v2.context_builder import VerifiedTransactionFact
    from app.services.article_v2.composer import _compose_context_section
    from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet, COHERENT

    tf = VerifiedTransactionFact(
        field_code=CONSIDERATION_AMOUNT, field_name="Cost of acquisition", value_text=None, value_numeric=318_009_491.0,
        unit="inr", raw_evidence_id="re1", source_document_id="doc1", page_number=2, source_span_text="test span",
        extraction_method="sebi_reg30_annexure_table", extraction_method_version="1.1",
    )

    class _FakeCtx:
        financial_context = []
        market_reaction = None
        transaction_facts = [tf]

    es = ArticleEvidenceSet(
        entity_id="cmp_x", symbol="X", event_id="e1", event_headline="X has informed the Exchange about Acquisition",
        status=COHERENT, primary_evidence=_evidence("X has informed the Exchange about Acquisition", "re1"),
        supporting_evidence=[], company_name="X Limited",
    )
    section = _compose_context_section(es, _FakeCtx(), name="verified_context")
    claim = next(c for c in section.claims if c.transaction_fact)
    sv = claim.structured_value
    assert sv["value"] == "Rs 31.80 crore"          # display string, unchanged
    assert sv["value_numeric"] == 318_009_491.0     # the real normalized fact, not re-derivable only from prose
    assert sv["value_text"] is None
    assert sv["unit"] == "inr"


# ── Warehouse read service, directly ─────────────────────────────────────

@pytest.mark.asyncio
async def test_get_verified_transaction_facts_returns_only_populated_rows_with_full_provenance():
    async with AsyncSessionLocal() as db:
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:read-service-direct", facts=[
            {"field_code": STAKE_PERCENTAGE, "field_name": "Percentage of shareholding / control acquired",
             "value_numeric": 51.0, "unit": "pct", "page_number": 1, "source_span_text": "51% stake"},
        ])
        try:
            facts = await get_verified_transaction_facts(db, raw_evidence_id)
            assert len(facts) == 1
            f = facts[0]
            assert f.field_code == STAKE_PERCENTAGE
            assert f.value_numeric == 51.0
            assert f.raw_evidence_id == raw_evidence_id
            assert f.source_document_id == doc_id
            assert f.page_number == 1
            assert f.source_span_text == "51% stake"
            assert f.extraction_method_version == "1.1"
        finally:
            await _cleanup(raw_evidence_id, doc_id)


# ── NOT_FOUND must never become positive evidence ────────────────────────

@pytest.mark.asyncio
async def test_not_found_rows_never_reach_the_context_bundle_at_all():
    async with AsyncSessionLocal() as db:
        raw_evidence_id, doc_id = await _seed_chain(db, evidence_key="test:not-found-check", facts=[])
        try:
            # Seed one explicit NOT_FOUND row directly (never produced by
            # _seed_chain's helper, which only ever writes POPULATED facts)
            from datetime import datetime as dt
            db.add(TransactionFact(
                source_document_id=doc_id, raw_evidence_id=raw_evidence_id,
                field_code=CONSIDERATION_AMOUNT, field_name="Cost of acquisition",
                value_text=None, value_numeric=None, unit=None,
                extraction_status="NOT_FOUND", extraction_method="none_matched", extraction_method_version="1.1",
                page_number=None, source_span_text=None, extracted_at=dt.now(timezone.utc),
            ))
            await db.commit()

            es = _evidence_set("TESTNF", raw_evidence_id, "Test Limited has informed the Exchange about Acquisition")
            ctx = await build_context(db, es)
            assert ctx.transaction_facts == []  # the NOT_FOUND row must never surface here
        finally:
            await _cleanup(raw_evidence_id, doc_id)

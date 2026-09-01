"""
Article V2 Phase C8.1 -- Publication Tier tests. Real cases drawn
directly from the C7 500-event shadow run's manual classification, so
this classifier is validated against real data shapes, not invented
ones.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.article_v2.context_builder import AVAILABLE, ArticleContextBundle, ContextFinancialFact
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.publication_tier import ARTICLE, EVENT_ONLY, REJECT, classify_publication_tier
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=str(uuid.uuid4()), title=title, source_type="nse",
        published_at=datetime.now(timezone.utc), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _es(symbol: str, primary_title: str) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt", event_headline=primary_title,
        status=COHERENT, primary_evidence=_evidence(primary_title),
    )


def _decision(es: ArticleEvidenceSet, reason_codes: list[str] | None = None) -> ArticleDecision:
    return ArticleDecision(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        content_type=FACTUAL_UPDATE, publication_action=CREATE, reason_codes=reason_codes or [],
    )


def test_dabur_real_amalgamation_order_is_article():
    es = _es("DABUR", "Dabur India Limited has informed the Exchange about update related to Scheme of Amalgamation between Sesa Care Private Limited and Dabur India Limited- Order Reserved for the Second Motion Petition")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == ARTICLE
    assert "HIGH_SUBSTANTIVENESS_MATCH" in result.reason_codes


def test_supremeeng_real_results_and_fundraising_is_article():
    es = _es("SUPREMEENG", "SUPREMEENG : 31-Aug-2026 :  The Company has informed the Exchange that the Board Meeting scheduled for August 29, 2026, has been re-scheduled to August 31, 2026. The Board will consider and approve the financial results for the first quarter ended June 30, 2026, and the proposal for fund raising.")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == ARTICLE


def test_canbk_real_fundraising_with_financial_context_is_article():
    """Real bug found via the C8 500-event rerun: C4's own decide()
    never puts "SUFFICIENT_ANALYTICAL_CONTEXT" in reason_codes for a
    FACTUAL_UPDATE (only for FULL_ARTICLE), even when real financial
    context genuinely exists -- so this test deliberately passes NO
    reason_codes, matching what C4 actually returns for CANBK's real
    shape, to validate the fix (checking `context` directly) rather
    than mask it the way an artificial reason_codes value would."""
    es = _es("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to be held on 03-Sep-2026 to consider Fund raising.")
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[ContextFinancialFact(
            metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.1197, unit="pct",
            fiscal_year=2026, fiscal_quarter=3, quality_status="ok", source_document_url=None,
            matched_family="FUNDRAISING",
        )],
    )
    result = classify_publication_tier(_decision(es), es, context)
    assert result.tier == ARTICLE
    assert "ANALYTICAL_CONTEXT_PRESENT" in result.reason_codes


def test_routine_agm_notice_is_event_only():
    es = _es("MAHSEAMLES", "Maharashtra Seamless Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 15, 2026")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == EVENT_ONLY


def test_agm_notice_with_material_acquisition_approved_escalates_to_article():
    """The owner's own contrasting example, verbatim: an AGM announcement
    and an AGM where a material acquisition is approved are not
    equivalent."""
    es = _es("XYZ", "XYZ Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 15, 2026, at which the Board approved the acquisition of ABC Technologies Limited")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == ARTICLE


def test_brsr_disclosure_is_event_only():
    es = _es("FIRSTCRY", "Brainbees Solutions Limited has informed the Exchange regarding 'Business Responsibility & Sustainability Report for the FY 2025-26'.")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == EVENT_ONLY


def test_esop_grant_with_bare_integer_is_event_only():
    """A bare integer (option count) is not real numeric substance --
    extract_numeric_claims() correctly never matches it (no currency/%/
    ratio shape), so this must not falsely escalate."""
    es = _es("KPIGREEN", "KPI Green Energy Limited has informed the Exchange regarding Grant of 470104 Options.")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == EVENT_ONLY


def test_real_currency_figure_escalates_to_article():
    es = _es("SOMECO", "Some Company Limited has informed the Exchange regarding a real order worth Rs 5,000 crore from a client")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == ARTICLE
    assert "REAL_NUMERIC_SUBSTANCE" in result.reason_codes


def test_degenerate_undefined_subject_is_rejected():
    """SIGACHI's real case: the source filing's own subject field was
    malformed and C5 correctly refused to invent one -- honest, but not
    publishable."""
    es = _es("SIGACHI", "Sigachi Industries Limited has informed the Exchange regarding Notice of undefined to be held on September 15, 2026")
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == REJECT
    assert "DEGENERATE_SUBJECT" in result.reason_codes


def test_marketing_press_release_wrapper_does_not_falsely_escalate():
    """CYIENT's real case: EVERY press-release-forwarding filing shares
    the same 'press release' wrapper phrase regardless of whether the
    inner content is material. A pure rebrand/marketing announcement
    must not escalate just because it arrived via a press release."""
    es = _es("CYIENT", 'Cyient Limited has informed the Exchange regarding a press release dated August 24, 2026, titled "Cyient Unveils New Brand Positioning Nothing Less".')
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == EVENT_ONLY


def test_genuine_acquisition_press_release_still_escalates():
    """AXISCADES's real case: the inner quoted title itself carries the
    real substantiveness signal (an acquisition), so it must still
    escalate even though it arrives via the same wrapper phrase."""
    es = _es("AXISCADES", 'AXISCADES Technologies Limited has informed the Exchange regarding a press release dated August 30, 2026, titled "AXISCADES Technologies to Acquire Cloud Wave Technologies".')
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == ARTICLE


def test_material_market_move_alone_escalates_to_article():
    from app.services.article_v2.context_builder import MarketReaction
    es = _es("SOMECO", "Some Company Limited has informed the Exchange about General Updates")
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, market_reaction=MarketReaction(price_move_pct=5.5, note="temporal correlation only"),
    )
    result = classify_publication_tier(_decision(es), es, context)
    assert result.tier == ARTICLE
    assert "ANALYTICAL_CONTEXT_PRESENT" in result.reason_codes


def test_immaterial_market_move_does_not_escalate():
    from app.services.article_v2.context_builder import MarketReaction
    es = _es("SOMECO", "Some Company Limited has informed the Exchange about General Updates")
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, market_reaction=MarketReaction(price_move_pct=0.8, note="temporal correlation only"),
    )
    result = classify_publication_tier(_decision(es), es, context)
    assert result.tier == EVENT_ONLY


def test_no_primary_evidence_is_rejected():
    es = ArticleEvidenceSet(
        entity_id="cmp_x", symbol="X", event_id="evt", event_headline="test", status=COHERENT, primary_evidence=None,
    )
    result = classify_publication_tier(_decision(es), es, None)
    assert result.tier == REJECT

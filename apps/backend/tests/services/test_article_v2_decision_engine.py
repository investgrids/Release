"""
Article V2 Phase C4 — Article Decision Engine tests. `decide()` is a
pure, synchronous function over the three upstream dataclasses, so
these tests construct them directly rather than running the full real
pipeline (C1/C2/C3 are already independently tested). Covers every
required adversarial case from the owner's authorization.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.services.article_v2.candidate_gate import CANDIDATE, SKIP as C1_SKIP, UPDATE_CANDIDATE, CandidateDecision
from app.services.article_v2.context_builder import AVAILABLE, ArticleContextBundle, MarketReaction, NONE_STATUS, PARTIAL, ContextFinancialFact
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, FULL_ARTICLE, NONE_ACTION, SKIP, UPDATE_EXISTING, decide
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet, COHERENT, INSUFFICIENT, PARTIAL as C2_PARTIAL
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str, days_ago: int = 0, source_type: str = "nse") -> LinkedEvidence:
    now = datetime.now(timezone.utc)
    return LinkedEvidence(
        raw_evidence_id=str(uuid.uuid4()), title=title, source_type=source_type,
        published_at=now - timedelta(days=days_ago), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _candidate(*, outcome=CANDIDATE, score=0.7, symbol="TEST", matched_article_id=None, reason_code="EVIDENCE_SUFFICIENT") -> CandidateDecision:
    return CandidateDecision(
        outcome=outcome, reason_code=reason_code, reason_detail="test",
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, evidence_count=1,
        top_evidence_score=score, matched_article_id=matched_article_id,
    )


def _evidence_set(*, symbol="TEST", primary: LinkedEvidence | None, supporting: list[LinkedEvidence] | None = None, status=C2_PARTIAL) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt_1", event_headline=primary.title if primary else "headline",
        status=status, primary_evidence=primary, supporting_evidence=supporting or [],
        raw_evidence_count=1 + len(supporting or []),
    )


def test_detailed_results_single_source_becomes_full_article():
    """The owner's own explicit rule: a single authoritative source with
    real detailed results is not automatically insufficient."""
    primary = _evidence("Company has informed the Exchange regarding financial results: net profit grew 24% to Rs 512 crore for the quarter")
    candidate = _candidate(score=0.85)
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == FULL_ARTICLE
    assert result.publication_action == CREATE
    assert "STRONG_PRIMARY_EVIDENCE" in result.reason_codes


def test_major_order_single_source_becomes_full_article():
    primary = _evidence("Company has informed the Exchange regarding a press release: real order worth Rs 5,000 crore won from a real infrastructure client")
    candidate = _candidate(score=0.9)
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == FULL_ARTICLE
    assert result.publication_action == CREATE


def test_agm_newspaper_publication_is_skip():
    primary = _evidence("Company has informed the Exchange about Copy of Newspaper Publication regarding Annual General Meeting")
    candidate = _candidate(score=0.32)  # would already be filtered by C1.1 in the real pipeline; test C4's own independent judgment
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == SKIP
    assert result.publication_action == NONE_ACTION


def test_board_meeting_merely_proposing_is_factual_update_not_full_article():
    """The owner's own CANBK-shaped example, verbatim: a board meeting to
    CONSIDER fundraising, with real background financial context
    available, must still be FACTUAL_UPDATE, not FULL_ARTICLE -- the
    proposal framing caps it despite a strong score and real context."""
    primary = _evidence("CANARA BANK has informed the Exchange about Board Meeting to be held on 03-Sep-2026 to consider Fund raising")
    candidate = _candidate(score=0.7)
    es = _evidence_set(primary=primary, supporting=[_evidence("To consider Fund Raising")], status=COHERENT)
    ctx = ArticleContextBundle(
        entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=AVAILABLE,
        matched_event_families=["FUNDRAISING"],
        financial_context=[ContextFinancialFact(
            metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.1197, unit="pct",
            fiscal_year=2025, fiscal_quarter=3, quality_status="OK", source_document_url=None, matched_family="FUNDRAISING",
        )],
        market_reaction=MarketReaction(price_move_pct=-1.13, note="temporal"),
    )
    result = decide(candidate, es, ctx)
    assert result.content_type == FACTUAL_UPDATE
    assert result.publication_action == CREATE


def test_query_self_matched_administrative_cluster_is_not_full_article():
    """Real regression, found via the C4 120-event shadow run: BLS's and
    FIRSTCRY's real BRSR/ESG disclosure filings scored 0.7+ purely
    because the EventTriage headline was near-identical to the
    evidence's own title (a perfect self-match), and a cluster of
    equally-administrative supporting filings (Web Link Letter, Media
    Release, dividend record date) got counted as "independent
    corroboration." None of this is real analytical depth -- must be
    FACTUAL_UPDATE, not FULL_ARTICLE."""
    title = "BLS International Services Limited has informed the Exchange regarding 'Business Responsibility & Sustainability Report'."
    primary = _evidence(title)
    # Simulate the real self-matched inflated score (0.7, from a perfect
    # Jaccard self-match on an UNKNOWN-substantiveness item).
    candidate = _candidate(score=0.7, reason_code="EVIDENCE_SUFFICIENT")
    supporting = [
        _evidence("BLS International Services Limited has informed the Exchange about Web Link Letter"),
        _evidence("BLS International Services Limited has informed the Exchange regarding Media Release"),
        _evidence("BLS International Services Limited has informed the Exchange that Record date for the purpose of Dividend"),
    ]
    es = _evidence_set(primary=primary, supporting=supporting, status=COHERENT)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == FACTUAL_UPDATE
    assert result.publication_action == CREATE


def test_real_press_release_acquisition_still_becomes_full_article():
    """The genuine true positive from the same shadow run, for contrast:
    AXISCADES's real acquisition press release must still correctly
    reach FULL_ARTICLE after the fix -- the fix must not overcorrect
    into suppressing real strong single-source news."""
    title = 'AXISCADES Technologies Limited has informed the Exchange regarding a press release dated August 30, 2026, titled "AXISCADES Technologies to Acquire Cloud Wave Technologies"'
    primary = _evidence(title)
    candidate = _candidate(score=0.9238)
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(
        entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=title, status=PARTIAL,
        market_reaction=MarketReaction(price_move_pct=4.80, note="temporal"),
    )
    result = decide(candidate, es, ctx)
    assert result.content_type == FULL_ARTICLE
    assert result.publication_action == CREATE


def test_governance_change_with_no_extra_depth_is_factual_update():
    primary = _evidence("Company has informed the Exchange regarding resignation of an Independent Director")
    candidate = _candidate(score=0.5)
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == FACTUAL_UPDATE
    assert result.publication_action == CREATE


def test_existing_article_no_new_evidence_is_skip_none():
    candidate = _candidate(outcome=UPDATE_CANDIDATE, matched_article_id="art_123")
    es = _evidence_set(primary=None, status=INSUFFICIENT)
    result = decide(candidate, es, None)
    assert result.content_type == SKIP
    assert result.publication_action == NONE_ACTION


def test_existing_article_with_material_new_evidence_is_update_existing():
    candidate = _candidate(outcome=UPDATE_CANDIDATE, matched_article_id="art_123")
    primary = _evidence("Company has informed the Exchange regarding a press release: updated fundraising terms Rs 600 crore")
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == FACTUAL_UPDATE
    assert result.publication_action == UPDATE_EXISTING
    assert "EXISTING_COVERAGE" in result.reason_codes


def test_c2_insufficient_is_always_skip_even_for_strong_c1_candidate():
    candidate = _candidate(outcome=CANDIDATE, score=0.95)
    es = _evidence_set(primary=None, status=INSUFFICIENT)
    result = decide(candidate, es, None)
    assert result.content_type == SKIP
    assert result.publication_action == NONE_ACTION
    assert "EVIDENCE_INSUFFICIENT" in result.reason_codes


def test_c3_none_does_not_automatically_mean_skip_when_primary_has_real_substance():
    """Owner's explicit rule: C3 NONE (no event-aware financial context,
    no usable market window -- e.g. a non-Banking company or stale
    evidence) must not force SKIP when the primary evidence itself
    carries real, detailed substance."""
    primary = _evidence(
        "Company has informed the Exchange regarding a press release: revenue grew 32% to Rs 890 crore, "
        "net profit up 18% to Rs 145 crore for the quarter"
    )
    candidate = _candidate(score=0.9)
    es = _evidence_set(primary=primary, status=C2_PARTIAL)
    ctx = ArticleContextBundle(entity_id="cmp_test", symbol="TEST", event_id="evt_1", event_headline=primary.title, status=NONE_STATUS)
    result = decide(candidate, es, ctx)
    assert result.content_type == FULL_ARTICLE  # real numeric substance alone carries it
    assert result.publication_action == CREATE


def test_c1_skip_is_passed_through_unchanged():
    candidate = _candidate(outcome=C1_SKIP, reason_code="INSUFFICIENT_EVIDENCE", score=None)
    es = _evidence_set(primary=None, status=INSUFFICIENT)
    result = decide(candidate, es, None)
    assert result.content_type == SKIP
    assert result.publication_action == NONE_ACTION

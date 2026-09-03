"""
AI Article V2 Phase A.1 — real tests for evidence_ranking.py. Pure logic,
no DB, no network. Covers the real motivating case: a generic
administrative filing must not outrank a substantive one just because
it's marginally newer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.warehouse.evidence_ranking import rank_evidence
from app.services.warehouse.read_service import LinkedEvidence


def _ev(title, published_at, raw_evidence_id="x"):
    return LinkedEvidence(
        raw_evidence_id=raw_evidence_id, title=title, source_type="nse", published_at=published_at,
        source_url=None, relationship_type="subject", resolution_method="source_symbol", link_confidence=1.0,
    )


def test_real_tcs_case_press_release_outranks_generic_order_filing():
    # The real, observed Phase A case: a generic "Bagging/Receiving of
    # orders/contracts" filing landed one minute AFTER a real Porsche
    # press release -- must not win purely on recency.
    now = datetime.now(timezone.utc)
    generic = _ev("Tata Consultancy Services Limited has informed the Exchange about Bagging/Receiving of orders/contracts", now)
    press_release = _ev('Tata Consultancy Services Limited has informed the Exchange regarding a press release dated August 24, 2026, titled "TCS and Porsche AG Partner to Accelerate the Future of AI-Powered Mobility"', now - timedelta(minutes=1))

    ranked = rank_evidence([generic, press_release])
    assert ranked[0].evidence is press_release
    assert ranked[0].score > ranked[1].score


def test_low_substantiveness_esop_ranks_below_unknown():
    now = datetime.now(timezone.utc)
    esop = _ev("Company has informed the Exchange regarding Allotment of 181843 Equity Shares under Employee Stock Option", now)
    unknown = _ev("Company has informed the Exchange about a routine matter with no recognized phrase", now)
    ranked = rank_evidence([esop, unknown])
    assert ranked[0].evidence is unknown
    assert "low-substantiveness" in ranked[1].reasons[0]


def test_query_context_boosts_matching_title():
    now = datetime.now(timezone.utc)
    a = _ev("Company announces new factory in Gujarat", now)
    b = _ev("Company signs partnership deal with Porsche for AI mobility", now)
    ranked = rank_evidence([a, b], query_context="Porsche AI mobility partnership")
    assert ranked[0].evidence is b
    assert any("Jaccard" in r for r in ranked[0].reasons)


def test_no_query_context_falls_back_to_substantiveness_only():
    now = datetime.now(timezone.utc)
    ev = _ev("Company has informed the Exchange about Acquisition", now)
    ranked = rank_evidence([ev])
    assert "no query context" in ranked[0].reasons[-1]


def test_empty_evidence_list_returns_empty():
    assert rank_evidence([]) == []


def test_missing_title_never_crashes_and_scores_neutral():
    now = datetime.now(timezone.utc)
    ev = _ev(None, now)
    ranked = rank_evidence([ev])
    assert ranked[0].score == 0.5

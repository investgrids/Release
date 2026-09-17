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


def test_mixed_naive_and_aware_published_at_does_not_crash_the_sort():
    # MR-TZ1 real regression (ZODIAC, nse-4021315061, 2026-09-16): SQLite
    # round-trips a DateTime column as naive even when written aware, so
    # one linked evidence row's published_at can be naive while another's
    # (or the sort key's own datetime.min fallback) is aware. Before the
    # fix this raised "can't compare offset-naive and offset-aware
    # datetimes" and suppressed the entire market-reaction context for
    # the candidate, not just the one malformed row.
    naive_recent = datetime(2026, 9, 15, 14, 19, 3)  # no tzinfo, same shape as the real ZODIAC row
    aware_older = datetime(2026, 9, 14, 10, 0, 0, tzinfo=timezone.utc)

    naive_ev = _ev("Company has informed the Exchange about a routine matter with no recognized phrase", naive_recent, raw_evidence_id="naive")
    aware_ev = _ev("Company has informed the Exchange about a routine matter with no recognized phrase", aware_older, raw_evidence_id="aware")

    ranked = rank_evidence([aware_ev, naive_ev])  # order matters: aware item first exercises the tuple comparison both ways
    assert [r.evidence.raw_evidence_id for r in ranked] == ["naive", "aware"]


def test_missing_published_at_still_sorts_via_the_aware_min_fallback():
    now = datetime.now(timezone.utc)
    dated = _ev("Company has informed the Exchange about a routine matter with no recognized phrase", now, raw_evidence_id="dated")
    undated = _ev("Company has informed the Exchange about a routine matter with no recognized phrase", None, raw_evidence_id="undated")

    ranked = rank_evidence([undated, dated])
    assert [r.evidence.raw_evidence_id for r in ranked] == ["dated", "undated"]

"""Sector and company signal synthesis — pure functions over
in-memory EvidenceCluster objects, no DB."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.weekend_intelligence.company_synthesis import (
    HIGH_CONVICTION_WATCH, MIXED, MONITOR, POSITIVE_WATCH, RISK_WATCH, synthesize_companies,
)
from app.services.weekend_intelligence.dedup import EvidenceCluster
from app.services.weekend_intelligence.evidence import DETERMINISTIC, HEURISTIC, EvidenceItem
from app.services.weekend_intelligence.sector_synthesis import synthesize_sectors

_NOW = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)


def _cluster(*items: EvidenceItem) -> EvidenceCluster:
    return EvidenceCluster(members=list(items))


def _item(source_type, source_id, title, companies=None, sectors=None, direction=None, score_kind=HEURISTIC):
    return EvidenceItem(
        source_type=source_type, source_id=source_id, observed_at=_NOW, title=title,
        companies=companies or [], sectors=sectors or [], direction=direction, score_kind=score_kind,
    )


def test_sector_direction_positive_from_single_direction_clusters():
    clusters = [
        _cluster(_item("event", "e1", "Defence order win", sectors=["Defence"], direction="positive", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n1", "Defence budget boost", sectors=["Defence"], direction="positive")),
    ]
    signals = synthesize_sectors(clusters)
    assert len(signals) == 1
    assert signals[0].sector == "Defence"
    assert signals[0].direction == "positive"
    assert signals[0].evidence_count == 2


def test_sector_mixed_when_clusters_disagree():
    clusters = [
        _cluster(_item("event", "e1", "Banking rate cut helps margins", sectors=["Banking"], direction="positive", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n1", "Banking NPA concerns rise", sectors=["Banking"], direction="negative")),
    ]
    signals = synthesize_sectors(clusters)
    assert signals[0].direction == "mixed"
    assert signals[0].confidence < 0.5  # contradiction penalty applied


def test_sector_single_cluster_confidence_is_capped():
    clusters = [_cluster(_item("news", "n1", "One mention of IT sector", sectors=["IT"], direction="positive"))]
    signals = synthesize_sectors(clusters)
    assert signals[0].confidence <= 0.55


def test_sector_baseline_pct_attached_when_available():
    clusters = [_cluster(_item("event", "e1", "Auto news", sectors=["Auto"], direction="positive", score_kind=DETERMINISTIC))]
    signals = synthesize_sectors(clusters, baseline_sector_ranks=[{"name": "Auto", "pct": 1.2, "positive": True}])
    assert signals[0].baseline_pct == 1.2


def test_company_high_conviction_requires_multiple_sources_and_no_contradiction():
    clusters = [
        _cluster(_item("event", "e1", "Company win 1", companies=["BEL"], direction="positive", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n1", "Company win 2", companies=["BEL"], direction="positive")),
        _cluster(_item("opportunity", "o1", "Company win 3", companies=["BEL"], direction="positive")),
    ]
    signals = synthesize_companies(clusters)
    assert signals[0].symbol == "BEL"
    assert signals[0].state == HIGH_CONVICTION_WATCH


def test_company_positive_watch_when_single_source_type_despite_volume():
    """brief §7: don't reward duplicate-source-type ingestion as
    independent confirmation — 3 clusters, but all 'news', should not
    reach high_conviction_watch."""
    clusters = [
        _cluster(_item("news", "n1", "Story A", companies=["INFY"], direction="positive")),
        _cluster(_item("news", "n2", "Story B", companies=["INFY"], direction="positive")),
        _cluster(_item("news", "n3", "Story C", companies=["INFY"], direction="positive")),
    ]
    signals = synthesize_companies(clusters)
    assert signals[0].state == POSITIVE_WATCH
    assert "single_source_type" in signals[0].risk_flags


def test_company_mixed_state_on_contradiction():
    clusters = [
        _cluster(_item("event", "e1", "Good news", companies=["TCS"], direction="positive", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n1", "Bad news", companies=["TCS"], direction="negative")),
    ]
    signals = synthesize_companies(clusters)
    assert signals[0].state == MIXED
    assert "conflicting_evidence" in signals[0].risk_flags


def test_company_risk_watch_on_negative_only():
    clusters = [_cluster(_item("news", "n1", "Adverse development", companies=["YESBANK"], direction="negative"))]
    signals = synthesize_companies(clusters)
    assert signals[0].state == RISK_WATCH


def test_company_monitor_when_no_clear_direction():
    clusters = [_cluster(_item("announcement", "a1", "Routine update", companies=["ITC"], direction=None))]
    signals = synthesize_companies(clusters)
    assert signals[0].state == MONITOR


def test_company_refs_split_by_source_type():
    clusters = [
        _cluster(
            _item("event", "e1", "x", companies=["HDFCBANK"], direction="positive", score_kind=DETERMINISTIC),
            _item("opportunity", "o1", "x", companies=["HDFCBANK"], direction="positive"),
        ),
    ]
    signals = synthesize_companies(clusters)
    assert {r["source_id"] for r in signals[0].event_refs} == {"e1"}
    assert {r["source_id"] for r in signals[0].opportunity_refs} == {"o1"}


# ── Canonical tradable-symbol validation (Phase 1B refinement) ─────────────
# Real, live pollution this backstops: AICompanySignal.symbol has been seen
# holding "NSE_SEBI", "NSE:NIFTY50", "SENSEX" and similar regulator/index/
# exchange pseudo-tags from upstream article extraction — none of these are
# tradable companies and must never appear in the company ranking.

def test_non_tradable_pseudo_symbol_excluded_from_company_ranking():
    clusters = [_cluster(_item("company_signal", "cs1", "SEBI proposes new KYC norms", companies=["NSE_SEBI"],
                                direction="neutral"))]
    signals = synthesize_companies(clusters)
    assert signals == []


def test_index_and_exchange_pseudo_symbols_excluded():
    clusters = [
        _cluster(_item("news", "n1", "Sensex closes flat", companies=["SENSEX"], direction="neutral")),
        _cluster(_item("company_signal", "cs1", "Nifty 50 index update", companies=["NSE:NIFTY50"], direction="neutral")),
    ]
    signals = synthesize_companies(clusters)
    assert signals == []


def test_real_symbol_kept_alongside_excluded_pseudo_symbol_in_same_cluster():
    """A cluster can carry both a real company and a pseudo-tag together
    (e.g. an SEBI ruling that also names a company) — only the pseudo-tag
    is dropped from the ranking; the real company still appears."""
    clusters = [_cluster(_item("event", "e1", "SEBI ruling affects HDFC Bank", companies=["NSE_SEBI", "HDFCBANK"],
                                direction="neutral", score_kind=DETERMINISTIC))]
    signals = synthesize_companies(clusters)
    assert {s.symbol for s in signals} == {"HDFCBANK"}


def test_pseudo_symbol_cluster_evidence_not_lost_only_excluded_from_ranking():
    """The filter is a ranking-entry gate, not evidence deletion — the
    cluster itself (sectors, risks, new-since-close, evidence_refs) is
    untouched; only company_synthesis's own output excludes the symbol."""
    cluster = _cluster(_item("company_signal", "cs1", "SEBI proposes new KYC norms", companies=["NSE_SEBI"],
                              sectors=["Regulatory"], direction="neutral"))
    assert "NSE_SEBI" in cluster.companies  # still present on the cluster itself
    signals = synthesize_companies([cluster])
    assert signals == []  # just never entered the company ranking

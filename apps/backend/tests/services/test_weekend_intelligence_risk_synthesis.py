"""
Risk synthesis — brief §12, refined into market risks vs confidence
warnings (Phase 1B post-review refinement, pre-commit). See
risk_synthesis.py's module docstring for the rationale: a reader must be
able to tell "something about the market" apart from "a caveat on this
particular synthesis run" without cross-referencing risk_type.
"""
from __future__ import annotations

from app.services.weekend_intelligence.company_synthesis import CompanySignal
from app.services.weekend_intelligence.materiality import DEFAULT_EVIDENCE_COUNT_THRESHOLD
from app.services.weekend_intelligence.risk_synthesis import (
    CONFLICTING_EVIDENCE,
    INSUFFICIENT_EVIDENCE,
    SOURCE_CONCENTRATION,
    STALE_OR_MISSING_BASELINE,
    WEAK_HISTORICAL_ANALOGUE,
    _MARKET_RISK_LIMIT,
    synthesize_confidence_warnings,
    synthesize_market_risks,
)
from app.services.weekend_intelligence.sector_synthesis import SectorSignal


def _sector(sector, direction, evidence_count=1, confidence=0.5):
    return SectorSignal(sector=sector, direction=direction, strength="medium", confidence=confidence,
                         evidence_count=evidence_count, positive_evidence=0, negative_evidence=0)


def _company(symbol, state, evidence_count=1, risk_flags=None):
    return CompanySignal(symbol=symbol, state=state, signal_strength="medium", confidence=0.5,
                          evidence_count=evidence_count, risk_flags=risk_flags or [])


# ── Market risks ────────────────────────────────────────────────────────────

def test_mixed_sector_produces_conflicting_evidence_market_risk():
    risks = synthesize_market_risks([_sector("Banking", "mixed", evidence_count=3)], [])
    assert any(r.risk_type == CONFLICTING_EVIDENCE and "Banking" in r.related_sectors for r in risks)


def test_mixed_company_produces_conflicting_evidence_market_risk():
    risks = synthesize_market_risks([], [_company("TCS", "mixed", evidence_count=2)])
    assert any(r.risk_type == CONFLICTING_EVIDENCE and "TCS" in r.related_companies for r in risks)


def test_uncontested_positive_evidence_produces_no_market_risk():
    risks = synthesize_market_risks(
        [_sector("Defence", "positive", evidence_count=3)],
        [_company("BEL", "high_conviction_watch", evidence_count=3)],
    )
    assert not any(r.risk_type == CONFLICTING_EVIDENCE for r in risks)


def test_market_risks_contain_no_process_level_risk_types():
    """SOURCE_CONCENTRATION/STALE_OR_MISSING_BASELINE/WEAK_HISTORICAL_ANALOGUE/
    INSUFFICIENT_EVIDENCE must never appear in market_risks — they belong
    exclusively to confidence_warnings (that's the whole point of the split)."""
    risks = synthesize_market_risks(
        [_sector("Banking", "mixed", evidence_count=5)],
        [_company("INFY", "risk_watch", evidence_count=1, risk_flags=["single_source_type"])],
    )
    process_types = {SOURCE_CONCENTRATION, STALE_OR_MISSING_BASELINE, WEAK_HISTORICAL_ANALOGUE, INSUFFICIENT_EVIDENCE}
    assert all(r.risk_type not in process_types for r in risks)


def test_market_risks_ranked_high_severity_first_and_capped():
    sectors = [_sector(f"Sector{i}", "mixed", evidence_count=5) for i in range(_MARKET_RISK_LIMIT + 5)]
    risks = synthesize_market_risks(sectors, [])
    assert len(risks) == _MARKET_RISK_LIMIT
    assert all(r.severity == "high" for r in risks)  # evidence_count>=4 -> high, per the sector rule


# ── Confidence warnings ─────────────────────────────────────────────────────

def test_source_concentration_flagged_for_substantial_single_source_thesis():
    warnings = synthesize_confidence_warnings(
        [_company("INFY", "positive_watch", evidence_count=3, risk_flags=["single_source_type"])],
        baseline_available=True, historical_analogue_count=1, total_evidence_count=10,
        source_type_counts={"news": 5, "event": 5},
    )
    assert any(w.risk_type == SOURCE_CONCENTRATION and "INFY" in w.related_companies for w in warnings)


def test_source_concentration_not_flagged_for_thin_single_cluster():
    warnings = synthesize_confidence_warnings(
        [_company("INFY", "positive_watch", evidence_count=1, risk_flags=["single_source_type"])],
        baseline_available=True, historical_analogue_count=1, total_evidence_count=10,
        source_type_counts={"news": 5, "event": 5},
    )
    assert not any(w.risk_type == SOURCE_CONCENTRATION and "INFY" in w.related_companies for w in warnings)


def test_missing_baseline_produces_high_severity_confidence_warning():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=False, historical_analogue_count=0, total_evidence_count=0,
    )
    baseline_warnings = [w for w in warnings if w.risk_type == STALE_OR_MISSING_BASELINE]
    assert len(baseline_warnings) == 1
    assert baseline_warnings[0].severity == "high"


def test_no_historical_analogue_with_real_evidence_produces_weak_analogue_warning():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=0, total_evidence_count=6,
        source_type_counts={"news": 6},
    )
    assert any(w.risk_type == WEAK_HISTORICAL_ANALOGUE for w in warnings)


def test_no_weak_analogue_warning_when_no_evidence_at_all():
    """An empty weekend shouldn't get a 'weak historical analogue' warning
    on top of everything else — there was nothing to match against in
    the first place."""
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=0, total_evidence_count=0,
    )
    assert not any(w.risk_type == WEAK_HISTORICAL_ANALOGUE for w in warnings)


def test_whole_snapshot_source_concentration_fires_when_one_type_dominates():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=1, total_evidence_count=20,
        source_type_counts={"news": 18, "event": 2},
    )
    concentration = [w for w in warnings if w.risk_type == SOURCE_CONCENTRATION and not w.related_companies]
    assert len(concentration) == 1
    assert "news" in concentration[0].description


def test_whole_snapshot_source_concentration_not_flagged_when_balanced():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=1, total_evidence_count=20,
        source_type_counts={"news": 8, "event": 6, "announcement": 6},
    )
    assert not any(w.risk_type == SOURCE_CONCENTRATION and not w.related_companies for w in warnings)


def test_whole_snapshot_source_concentration_not_flagged_below_min_evidence():
    """A dominant share over a handful of items isn't meaningful — needs
    real volume before it's worth surfacing."""
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=1, total_evidence_count=3,
        source_type_counts={"news": 3},
    )
    assert not any(w.risk_type == SOURCE_CONCENTRATION and not w.related_companies for w in warnings)


def test_thin_evidence_produces_insufficient_evidence_warning():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=0,
        total_evidence_count=DEFAULT_EVIDENCE_COUNT_THRESHOLD - 1,
    )
    assert any(w.risk_type == INSUFFICIENT_EVIDENCE for w in warnings)


def test_insufficient_evidence_warning_not_fired_at_or_above_threshold():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=True, historical_analogue_count=1,
        total_evidence_count=DEFAULT_EVIDENCE_COUNT_THRESHOLD,
        source_type_counts={"news": DEFAULT_EVIDENCE_COUNT_THRESHOLD},
    )
    assert not any(w.risk_type == INSUFFICIENT_EVIDENCE for w in warnings)


def test_confidence_warnings_contain_no_market_risk_type():
    warnings = synthesize_confidence_warnings(
        [], baseline_available=False, historical_analogue_count=0, total_evidence_count=0,
    )
    assert all(w.risk_type != CONFLICTING_EVIDENCE for w in warnings)

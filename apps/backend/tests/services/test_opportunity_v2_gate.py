"""
opportunity_v2/gate.py::is_opportunity_evidence_worthy() — deliberately
separate from development_memory/graph_link.py's is_graph_worthy() (owner
correction, 2026-08-22: "does this deserve a graph node" and "can this
become an investable thesis" are different questions). Pure function, no
DB needed — constructs in-memory Development objects only, same
convention as test_development_memory_read.py's own _make_dev() helper.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.development import Development
from app.services.opportunity_v2.gate import is_opportunity_evidence_worthy


def _dev(
    *, evidence_count: int = 2, impact_tier: str | None = None,
    confidence: float | None = None, sectors: list[str] | None = None,
    companies: list[str] | None = None, primary_company: str | None = None,
) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id="test", canonical_title="Test development", status="open",
        primary_company=primary_company, companies=companies or [], sectors=sectors or [],
        themes=[], first_observed_at=now, last_observed_at=now,
        current_impact_tier=impact_tier, current_confidence=confidence,
        evidence_count=evidence_count, schema_version="test",
    )


def test_passes_with_meaningful_confidence_and_a_company_anchor():
    dev = _dev(primary_company="INFY", confidence=0.7, impact_tier=None)
    assert is_opportunity_evidence_worthy(dev) is True


def test_passes_with_meaningful_tier_alone_even_at_low_confidence():
    dev = _dev(sectors=["Banking"], impact_tier="High", confidence=0.2)
    assert is_opportunity_evidence_worthy(dev) is True


def test_fails_with_no_company_or_sector_anchor():
    dev = _dev(confidence=0.9, impact_tier="Critical")
    assert is_opportunity_evidence_worthy(dev) is False


def test_fails_on_low_tier_and_low_confidence_routine_filing():
    # The dominant real-data shape: routine NSE exchange filings —
    # Low tier, confidence in the 0.3-0.5 range, real sector/company tag.
    dev = _dev(companies=["SOMECO"], impact_tier="Low", confidence=0.4)
    assert is_opportunity_evidence_worthy(dev) is False


def test_tier_comparison_is_case_insensitive():
    # Confirmed live: real data has inconsistent casing ("High" vs "high").
    dev = _dev(sectors=["Banking"], impact_tier="high", confidence=0.1)
    assert is_opportunity_evidence_worthy(dev) is True


def test_fails_with_zero_evidence_count():
    dev = _dev(evidence_count=0, primary_company="INFY", confidence=0.9, impact_tier="Critical")
    assert is_opportunity_evidence_worthy(dev) is False


def test_falls_back_to_formation_fields_when_current_is_unset():
    dev = _dev(primary_company="INFY", confidence=None, impact_tier=None)
    dev.formation_confidence = 0.8
    dev.formation_impact_tier = None
    assert is_opportunity_evidence_worthy(dev) is True


def test_confidence_exactly_at_threshold_passes():
    dev = _dev(primary_company="INFY", confidence=0.5, impact_tier=None)
    assert is_opportunity_evidence_worthy(dev) is True


def test_medium_tier_counts_as_meaningful():
    dev = _dev(sectors=["Pharma"], impact_tier="Medium", confidence=0.1)
    assert is_opportunity_evidence_worthy(dev) is True

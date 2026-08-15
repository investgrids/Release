"""
Deterministic material-change detector tests — pure functions over
in-memory EvidenceItem lists, no DB access.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.weekend_intelligence.dedup import EvidenceCluster
from app.services.weekend_intelligence.evidence import DETERMINISTIC, HEURISTIC, EvidenceItem
from app.services.weekend_intelligence.materiality import (
    MEANINGFUL_OPPORTUNITY_CONFIDENCE,
    detect_material_change,
    is_meaningful_development,
    select_new_since_close,
)

_NOW = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)


def _event(source_id: str, tier: str | None) -> EvidenceItem:
    return EvidenceItem(
        source_type="event", source_id=source_id, observed_at=_NOW,
        title=f"Event {source_id}", impact_strength=tier, score_kind=DETERMINISTIC,
    )


def test_no_evidence_is_not_material():
    result = detect_material_change([])
    assert result.is_material is False
    assert result.new_evidence_count == 0
    assert result.reasons == []


def test_trivial_low_tier_evidence_is_not_material():
    items = [_event("e1", "Low"), _event("e2", "Medium")]
    result = detect_material_change(items, evidence_count_threshold=10)
    assert result.is_material is False


def test_critical_event_is_material():
    result = detect_material_change([_event("e1", "Critical")])
    assert result.is_material is True
    assert result.critical_event_count == 1
    assert any("Critical" in r for r in result.reasons)


def test_high_event_is_material():
    result = detect_material_change([_event("e1", "High")])
    assert result.is_material is True
    assert result.high_event_count == 1


def test_new_policy_evidence_is_material():
    item = EvidenceItem(source_type="policy", source_id="p1", observed_at=_NOW, title="RBI notice")
    result = detect_material_change([item])
    assert result.is_material is True
    assert result.new_policy_count == 1


def test_high_impact_announcement_is_material():
    item = EvidenceItem(source_type="announcement", source_id="a1", observed_at=_NOW,
                         title="Board decision", impact_strength="high")
    result = detect_material_change([item])
    assert result.is_material is True
    assert result.new_high_impact_announcement_count == 1


def test_low_impact_announcement_alone_is_not_material():
    item = EvidenceItem(source_type="announcement", source_id="a1", observed_at=_NOW,
                         title="Routine filing", impact_strength=None)
    result = detect_material_change([item], evidence_count_threshold=10)
    assert result.is_material is False


def test_meaningful_opportunity_is_material():
    item = EvidenceItem(source_type="opportunity", source_id="o1", observed_at=_NOW,
                         title="Strong opportunity", confidence=MEANINGFUL_OPPORTUNITY_CONFIDENCE)
    result = detect_material_change([item])
    assert result.is_material is True
    assert result.new_meaningful_opportunity_count == 1


def test_weak_opportunity_alone_is_not_material():
    item = EvidenceItem(source_type="opportunity", source_id="o1", observed_at=_NOW,
                         title="Weak opportunity", confidence=0.5)
    result = detect_material_change([item], evidence_count_threshold=10)
    assert result.is_material is False


def test_evidence_count_threshold_triggers_materiality():
    items = [_event(f"e{i}", "Low") for i in range(5)]
    result = detect_material_change(items, evidence_count_threshold=5)
    assert result.is_material is True
    assert any("total new evidence" in r for r in result.reasons)


def test_duplicate_evidence_does_not_inflate_count():
    dup = _event("e1", "Critical")
    result = detect_material_change([dup, dup, dup])
    assert result.new_evidence_count == 1
    assert result.critical_event_count == 1


def test_llm_confidence_does_not_override_deterministic_tier_absence():
    """An LLM-self-rated announcement with high confidence must not, by
    itself via raw confidence alone, be treated the same as a
    deterministic Critical event — only structural signals (tier,
    is_high_impact-derived impact_strength) drive materiality here."""
    item = EvidenceItem(source_type="announcement", source_id="a1", observed_at=_NOW,
                         title="High-confidence but not flagged high-impact",
                         confidence=0.95, impact_strength=None)
    result = detect_material_change([item], evidence_count_threshold=10)
    assert result.is_material is False


def test_new_company_and_sector_counts():
    item = EvidenceItem(source_type="event", source_id="e1", observed_at=_NOW, title="t",
                         companies=["TCS", "INFY"], sectors=["IT"])
    result = detect_material_change([item], previously_seen_companies={"TCS"}, evidence_count_threshold=10)
    assert result.new_company_count == 1  # only INFY is new
    assert result.new_sector_count == 1   # IT is new


# ── Cluster-level "new since market close" ─────────────────────────────────
# Phase 1B refinement: reuses the exact same per-item criteria above, at
# cluster granularity — a distinct concept from changes.py's "changed vs
# prior snapshot version" (see changes.py's module docstring).

def _cluster(*members: EvidenceItem) -> EvidenceCluster:
    return EvidenceCluster(members=list(members))


def test_critical_event_cluster_is_meaningful():
    assert is_meaningful_development(_cluster(_event("e1", "Critical"))) is True


def test_low_tier_event_cluster_is_not_meaningful():
    assert is_meaningful_development(_cluster(_event("e1", "Low"))) is False


def test_policy_cluster_is_always_meaningful():
    item = EvidenceItem(source_type="policy", source_id="p1", observed_at=_NOW, title="RBI notice")
    assert is_meaningful_development(_cluster(item)) is True


def test_high_impact_announcement_cluster_is_meaningful():
    item = EvidenceItem(source_type="announcement", source_id="a1", observed_at=_NOW,
                         title="Board decision", impact_strength="high")
    assert is_meaningful_development(_cluster(item)) is True


def test_meaningful_opportunity_cluster_is_meaningful():
    item = EvidenceItem(source_type="opportunity", source_id="o1", observed_at=_NOW,
                         title="Strong opportunity", confidence=MEANINGFUL_OPPORTUNITY_CONFIDENCE)
    assert is_meaningful_development(_cluster(item)) is True


def test_routine_news_only_cluster_is_not_meaningful():
    item = EvidenceItem(source_type="news", source_id="n1", observed_at=_NOW, title="Routine market wrap",
                         score_kind=HEURISTIC)
    assert is_meaningful_development(_cluster(item)) is False


def test_select_new_since_close_counts_clusters_not_raw_evidence():
    """5 outlets covering the same Critical event should count as ONE
    meaningful development, not 5 — this is why select_new_since_close
    operates on already-deduplicated clusters, and why the count it
    produces is meant to be much smaller than a raw evidence_count."""
    critical = _event("e1", "Critical")
    routine_news = [
        EvidenceItem(source_type="news", source_id=f"n{i}", observed_at=_NOW, title=f"wrap {i}", score_kind=HEURISTIC)
        for i in range(5)
    ]
    clusters = [_cluster(critical)] + [_cluster(n) for n in routine_news]
    selected = select_new_since_close(clusters)
    assert len(selected) == 1
    assert selected[0].members[0].source_id == "e1"


def test_select_new_since_close_empty_when_nothing_meaningful():
    routine = [_cluster(EvidenceItem(source_type="news", source_id="n1", observed_at=_NOW, title="wrap",
                                      score_kind=HEURISTIC))]
    assert select_new_since_close(routine) == []

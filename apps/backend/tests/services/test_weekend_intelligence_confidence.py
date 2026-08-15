"""
Production confidence tests — brief §31. These are the most important
tests in Phase 1B; each asserts a specific, meaningful behavior rather
than just `confidence > 0`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.weekend_intelligence.confidence import compute_production_confidence
from app.services.weekend_intelligence.dedup import EvidenceCluster
from app.services.weekend_intelligence.evidence import DETERMINISTIC, LLM_SELF_RATED, EvidenceItem

_NOW = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)


def _item(source_type, source_id, direction="positive", score_kind=LLM_SELF_RATED, confidence=0.5):
    return EvidenceItem(
        source_type=source_type, source_id=source_id, observed_at=_NOW, title=f"{source_type}-{source_id}",
        direction=direction, score_kind=score_kind, confidence=confidence,
    )


def _cluster(*items) -> EvidenceCluster:
    return EvidenceCluster(members=list(items))


def test_duplicate_evidence_merged_into_one_cluster_does_not_inflate_confidence():
    """3 EvidenceItems describing the same real development, already
    correctly merged (by dedup.py) into ONE cluster, must score as "one
    development" — not as strong as 3 genuinely independent ones."""
    merged = [_cluster(_item("news", "n1"), _item("event", "e1", score_kind=DETERMINISTIC), _item("opportunity", "o1"))]
    independent = [
        _cluster(_item("news", "n1")),
        _cluster(_item("event", "e2", score_kind=DETERMINISTIC)),
        _cluster(_item("opportunity", "o2")),
    ]
    merged_score, _ = compute_production_confidence(merged, baseline_available=True, historical_analogues=[])
    independent_score, _ = compute_production_confidence(independent, baseline_available=True, historical_analogues=[])
    assert independent_score > merged_score


def test_more_independent_clusters_increases_confidence():
    few = [_cluster(_item("news", "n1"))]
    many = [_cluster(_item("news", f"n{i}", score_kind=DETERMINISTIC)) for i in range(6)]
    few_score, _ = compute_production_confidence(few, baseline_available=True, historical_analogues=[])
    many_score, _ = compute_production_confidence(many, baseline_available=True, historical_analogues=[])
    assert many_score > few_score


def test_deterministic_evidence_outweighs_llm_self_rated():
    """Same cluster COUNT, same directions — only score_kind differs.
    The deterministic set must score higher, and this must hold even
    though the LLM-rated items could carry a much higher raw .confidence
    value (proving raw LLM confidence isn't what's driving the result)."""
    deterministic_clusters = [_cluster(_item("event", f"e{i}", score_kind=DETERMINISTIC, confidence=0.5)) for i in range(3)]
    llm_clusters = [_cluster(_item("news", f"n{i}", score_kind=LLM_SELF_RATED, confidence=0.99)) for i in range(3)]

    det_score, det_breakdown = compute_production_confidence(deterministic_clusters, baseline_available=True, historical_analogues=[])
    llm_score, llm_breakdown = compute_production_confidence(llm_clusters, baseline_available=True, historical_analogues=[])

    assert det_score > llm_score
    assert det_breakdown.evidence_strength > llm_breakdown.evidence_strength


def test_llm_confidence_95_does_not_produce_production_confidence_95():
    """The brief's own explicit example (§16): a single LLM-self-rated
    item claiming 95% confidence must not translate into
    production_confidence anywhere near 95."""
    clusters = [_cluster(_item("news", "n1", score_kind=LLM_SELF_RATED, confidence=0.95))]
    score, _ = compute_production_confidence(clusters, baseline_available=True, historical_analogues=[])
    assert score < 50


def test_contradiction_reduces_confidence_via_agreement_component():
    """Isolates agreement specifically: both groups have the same cluster
    count and the same score_kind mix (all DETERMINISTIC) — the only
    difference is direction, so evidence_strength/source_diversity are
    identical between them and any score difference is attributable to
    agreement alone."""
    uniform = [_cluster(_item("news", f"n{i}", direction="positive", score_kind=DETERMINISTIC)) for i in range(4)]
    contradictory = [
        _cluster(_item("news", "n0", direction="positive", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n1", direction="negative", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n2", direction="positive", score_kind=DETERMINISTIC)),
        _cluster(_item("news", "n3", direction="negative", score_kind=DETERMINISTIC)),
    ]

    uniform_score, uniform_bd = compute_production_confidence(uniform, baseline_available=True, historical_analogues=[])
    contra_score, contra_bd = compute_production_confidence(contradictory, baseline_available=True, historical_analogues=[])

    assert uniform_bd.evidence_strength == contra_bd.evidence_strength
    assert uniform_bd.source_diversity == contra_bd.source_diversity
    assert contra_bd.agreement < uniform_bd.agreement
    assert contra_score < uniform_score


def test_missing_baseline_caps_confidence_by_exactly_its_weight():
    clusters = [_cluster(_item("event", "e1", score_kind=DETERMINISTIC)) for _ in range(3)]
    with_baseline, _ = compute_production_confidence(clusters, baseline_available=True, historical_analogues=[])
    without_baseline, _ = compute_production_confidence(clusters, baseline_available=False, historical_analogues=[])
    # baseline_quality's weight is 0.15 -> exactly 15 points of difference,
    # deterministically, since it's the only input that changed.
    assert round(with_baseline - without_baseline, 2) == 15.0


def test_insufficient_evidence_cannot_produce_high_confidence():
    score, _ = compute_production_confidence([], baseline_available=True, historical_analogues=[])
    assert score < 40


def test_confidence_bounds_never_exceeded_even_at_maximum_input():
    clusters = [_cluster(_item("event", f"e{i}", score_kind=DETERMINISTIC), _item("policy", f"p{i}"),
                          _item("announcement", f"a{i}"), _item("news", f"n{i}"),
                          _item("company_signal", f"cs{i}"), _item("opportunity", f"o{i}"))
                for i in range(12)]
    score, breakdown = compute_production_confidence(
        clusters, baseline_available=True,
        historical_analogues=[{"id": i, "similarity": 100.0} for i in range(5)],
    )
    assert 0.0 <= score <= 100.0
    for v in breakdown.as_dict()["raw"].values():
        assert 0.0 <= v <= 1.0


def test_confidence_bounds_never_negative_at_minimum_input():
    score, _ = compute_production_confidence([], baseline_available=False, historical_analogues=[])
    assert score >= 0.0


def test_confidence_breakdown_reconciles_with_final_score():
    clusters = [_cluster(_item("event", "e1", score_kind=DETERMINISTIC)), _cluster(_item("news", "n1"))]
    score, breakdown = compute_production_confidence(clusters, baseline_available=True, historical_analogues=[{"id": 1, "similarity": 40.0}])
    reconciled = round(sum(breakdown.weighted_contributions().values()) * 100, 2)
    assert reconciled == score


def test_historical_support_increases_with_strong_analogues():
    clusters = [_cluster(_item("event", "e1", score_kind=DETERMINISTIC))]
    no_analogue, _ = compute_production_confidence(clusters, baseline_available=True, historical_analogues=[])
    strong_analogue, _ = compute_production_confidence(
        clusters, baseline_available=True,
        historical_analogues=[{"id": 1, "similarity": 90.0}, {"id": 2, "similarity": 85.0}, {"id": 3, "similarity": 80.0}],
    )
    assert strong_analogue > no_analogue

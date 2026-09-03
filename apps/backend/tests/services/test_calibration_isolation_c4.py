"""
CD3-C C4 — Phase 6C calibration isolation regression guard.

CD3-C's audit confirmed Phase 6C's real prediction contract is coarse
(no benchmark, no per-entity/horizon/type granularity -- calibration_factor
is pooled by confidence_level alone across every source/prediction_type/
horizon simultaneously). The CD3-C authorization explicitly said: keep
this isolated, expose "historical accuracy for this broad confidence
tier" at most, never a per-claim outcome probability. This suite pins
down the exact contract that makes that true today, so a future change
that quietly widens it (removes the sample-size guard, loosens the factor
bounds, or starts exposing calibration as a new "probability" field
rather than an adjustment to an existing confidence score) fails loudly.
"""
from __future__ import annotations

from app.services.ai_search.prediction_recording import apply_calibration
from app.services.confidence_service import ConfidenceResult


def _res(score: float = 60.0, level: str = "Medium") -> ConfidenceResult:
    return ConfidenceResult(
        total_score=score, level=level, reasons=["test reason"], explanation="", breakdown={},
    )


def test_calibration_requires_at_least_ten_verified_predictions():
    """The sample-size guard is the core isolation mechanism -- without
    it, a single lucky/unlucky verified prediction could swing a whole
    confidence tier's public-facing score."""
    res = _res()
    thin_data = {"Medium": {"calibration_factor": 1.5, "total": 9, "accuracy_rate": 0.9}}
    apply_calibration(res, thin_data)
    assert res.total_score == 60.0  # untouched -- guard held
    assert not any("Calibrated" in r for r in res.reasons)


def test_calibration_applies_only_at_exactly_ten_and_above():
    res = _res()
    exactly_ten = {"Medium": {"calibration_factor": 1.2, "total": 10, "accuracy_rate": 0.7}}
    apply_calibration(res, exactly_ten)
    assert res.total_score != 60.0  # guard passed at the boundary
    assert any("Calibrated" in r for r in res.reasons)


def test_calibration_factor_is_bounded_and_ignores_extreme_values():
    """Factor bounds (0.4-1.8) prevent a thin/noisy signal from producing
    an extreme swing even once the sample-size guard is satisfied."""
    res = _res()
    extreme = {"Medium": {"calibration_factor": 5.0, "total": 50, "accuracy_rate": 1.0}}
    apply_calibration(res, extreme)
    assert res.total_score == 60.0  # 5.0 is outside 0.4-1.8 -- no-op

    res2 = _res()
    extreme_low = {"Medium": {"calibration_factor": 0.1, "total": 50, "accuracy_rate": 0.1}}
    apply_calibration(res2, extreme_low)
    assert res2.total_score == 60.0  # 0.1 is outside 0.4-1.8 -- no-op


def test_calibration_never_introduces_a_new_probability_field():
    """CD3-C's explicit boundary: calibration may adjust an EXISTING
    confidence score (mutating total_score/level/reasons on the same
    ConfidenceResult), it must never manufacture a new "probability"
    attribute or field -- that would be exactly the "per-claim outcome
    probability" the authorization forbids."""
    res = _res()
    real_data = {"Medium": {"calibration_factor": 1.3, "total": 25, "accuracy_rate": 0.75}}
    apply_calibration(res, real_data)
    # ConfidenceResult is a dataclass with a fixed, known field set --
    # confirms apply_calibration only ever touches total_score/level/
    # reasons, never adds a new attribute.
    assert set(vars(res).keys()) == {"total_score", "level", "reasons", "explanation", "breakdown"}
    assert not hasattr(res, "probability")
    assert not hasattr(res, "calibrated_probability")


def test_calibration_reason_is_scoped_to_the_pooled_tier_not_a_specific_claim():
    """The disclosure text itself must describe a pooled tier-level
    statistic ("N verified predictions"), never phrase itself as a
    per-claim probability."""
    res = _res()
    real_data = {"Medium": {"calibration_factor": 1.3, "total": 25, "accuracy_rate": 0.75}}
    apply_calibration(res, real_data)
    calibration_reasons = [r for r in res.reasons if "Calibrated" in r]
    assert calibration_reasons
    reason = calibration_reasons[0]
    assert "25" in reason  # names the real sample size
    assert "will" not in reason.lower()  # never phrased as a forward claim
    assert "probability" not in reason.lower()


def test_calibration_no_op_on_missing_or_empty_data():
    res = _res()
    apply_calibration(res, {})
    assert res.total_score == 60.0
    apply_calibration(res, None)  # type: ignore[arg-type]
    assert res.total_score == 60.0

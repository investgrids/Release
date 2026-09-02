"""
CD3-A follow-up (isolated fix, not a semantic redesign): page_intelligence_
service._build_confidence() called prediction_service.get_calibration_data()
-- an async function -- without awaiting it, from a sync function, wrapped in
a bare `except Exception: pass`. The calibration adjustment on this call path
silently never applied since it was written; ai_search_service.py's call site
does this correctly and was the reference for the fix.

Fixed by making _build_confidence async, awaiting get_calibration_data(), and
routing the actual application through the same shared apply_calibration()
ai_search_service.py already uses (app.services.ai_search.prediction_recording)
-- not a second, independent calibration reimplementation. That shared
function carries its own >=10-verified-predictions guard, so these tests also
confirm the fix cannot make an old, uncalibrated confidence field look
"calibrated" off thin or absent data.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import app.services.page_intelligence_service as pis
from app.services.confidence_service import ConfidenceResult


def _res(score: float = 61.5, level: str = "Medium") -> ConfidenceResult:
    return ConfidenceResult(
        total_score=score,
        level=level,
        reasons=["12 independent developments, corroborated by 15 sources"],
        explanation="",
        breakdown={"evidence_quality": 60.0},
    )


@pytest.mark.asyncio
async def test_build_confidence_awaits_and_applies_real_calibration():
    """Sufficient sample size (>=10) and an in-bounds factor: calibration
    actually applies, proving get_calibration_data() is now awaited rather
    than silently returning an un-awaited coroutine that the bare except
    swallowed."""
    cal_data = {"Medium": {"calibration_factor": 1.2, "total": 25, "accuracy_rate": 0.7}}
    with patch("app.services.confidence_service.calculate_confidence", return_value=_res()), \
         patch("app.services.prediction_service.get_calibration_data", new=AsyncMock(return_value=cal_data)):
        conf = await pis._build_confidence({}, source_count=5, similar=[])

    assert conf["score"] == 74  # round(61.5 * 1.2, 1) = 73.8 -> round(73.8) = 74
    assert conf["level"] == "Very High"  # apply_calibration recomputes level from the calibrated score
    assert any("Calibrated" in r for r in conf["reasons"])


@pytest.mark.asyncio
async def test_build_confidence_never_calibrates_on_thin_data():
    """Fewer than 10 verified predictions for this confidence level: the
    shared apply_calibration() guard must leave the raw score untouched.
    This is the property the owner explicitly asked to be verified -- the
    fix must not make an old, unsafe confidence field suddenly look
    "calibrated" off near-zero evidence."""
    cal_data = {"Medium": {"calibration_factor": 1.4, "total": 3, "accuracy_rate": 0.9}}
    with patch("app.services.confidence_service.calculate_confidence", return_value=_res()), \
         patch("app.services.prediction_service.get_calibration_data", new=AsyncMock(return_value=cal_data)):
        conf = await pis._build_confidence({}, source_count=5, similar=[])

    assert conf["score"] == 62  # round(61.5) unchanged -- no calibration applied
    assert conf["level"] == "Medium"
    assert not any("Calibrated" in r for r in conf["reasons"])


@pytest.mark.asyncio
async def test_build_confidence_no_calibration_data_available():
    """get_calibration_data() returning {} (no predictions recorded yet at
    all) must be a clean no-op, same as production behaved before any
    calibration data existed."""
    with patch("app.services.confidence_service.calculate_confidence", return_value=_res()), \
         patch("app.services.prediction_service.get_calibration_data", new=AsyncMock(return_value={})):
        conf = await pis._build_confidence({}, source_count=5, similar=[])

    assert conf["score"] == 62
    assert conf["level"] == "Medium"


@pytest.mark.asyncio
async def test_build_confidence_survives_calibration_lookup_failure():
    """A raised exception from the calibration lookup (e.g. DB unavailable)
    must not break the whole confidence response -- the outer try/except is
    preserved."""
    with patch("app.services.confidence_service.calculate_confidence", return_value=_res()), \
         patch("app.services.prediction_service.get_calibration_data", new=AsyncMock(side_effect=RuntimeError("db down"))):
        conf = await pis._build_confidence({}, source_count=5, similar=[])

    assert conf["level"] == "Medium"
    assert conf["score"] == 62


@pytest.mark.asyncio
async def test_build_confidence_survives_scoring_engine_failure():
    """Outermost failure mode: calculate_confidence itself raises -- must
    still return the documented Medium/55 fallback, unchanged from before
    this fix."""
    with patch("app.services.confidence_service.calculate_confidence", side_effect=RuntimeError("boom")):
        conf = await pis._build_confidence({}, source_count=5, similar=[])

    assert conf == {"level": "Medium", "score": 55, "reasons": [], "breakdown": {}}

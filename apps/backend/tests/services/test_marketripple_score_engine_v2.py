"""
NONBANK_INDUSTRIAL_V2 engine composition — owner instruction 2026-09-27
(prioritize the 326 evidence-limited companies before Finance/Insurance).
Monkeypatches the four pillar-scoring functions with controlled PillarScore
objects (no live network) to verify the exact composition math: only
Financial Strength/Valuation/Market Behaviour ever enter the weighted
blend, Current Intelligence never gates or contributes to the headline
number even when present, and Banking's own 4-pillar rule is completely
unaffected by this addition.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.marketripple_score.contracts import PillarScore, PillarStatus
from app.services.marketripple_score.engine import (
    CANDIDATE_WEIGHTS, NONBANK_HEADLINE_REASON_INVALID_SCORE_RANGE, NONBANK_HEADLINE_REASON_MISSING_PILLAR,
    NONBANK_INDUSTRIAL_V2_WEIGHTS, compute_marketripple_score, compute_nonbank_headline,
)


def _pillar(name: str, score: float | None, coverage: float = 100.0) -> PillarScore:
    return PillarScore(
        name=name, score=score, coverage_pct=coverage,
        status=PillarStatus.COMPLETE if score is not None else PillarStatus.INSUFFICIENT,
        metrics_used=["x"] if score is not None else [], metrics_missing=[], sources=["test"],
        as_of=datetime.now(timezone.utc),
    )


def _patch_pillars(monkeypatch, *, fs, val, mkt, ci):
    async def fake_fs(db, symbol, sector, peer_group=None, prefetched=None):
        return fs

    async def fake_val(symbol, sector, peer_group=None, prefetched=None):
        return val

    async def fake_mkt(symbol, sector, prefetched_benchmarks=None):
        return mkt

    async def fake_ci(db, symbol):
        return ci

    monkeypatch.setattr("app.services.marketripple_score.engine.score_financial_strength", fake_fs)
    monkeypatch.setattr("app.services.marketripple_score.engine.score_valuation", fake_val)
    monkeypatch.setattr("app.services.marketripple_score.engine.score_market_behaviour", fake_mkt)
    monkeypatch.setattr("app.services.marketripple_score.engine.score_current_intelligence", fake_ci)


@pytest.mark.asyncio
async def test_v2_headline_score_uses_only_the_three_required_pillars(monkeypatch):
    """A real Technology symbol, all 4 pillars present INCLUDING current
    intelligence -- the headline score must come from ONLY fs/val/mkt at
    the fixed V2 weights, current_intelligence's real score must be
    visible in `pillars` but absent from `weights` and NOT used in the
    blend at all."""
    fs, val, mkt, ci = _pillar("financial_strength", 60.0), _pillar("valuation", 40.0), _pillar("market_behaviour", 80.0), _pillar("current_intelligence", 10.0)
    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=ci)

    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await compute_marketripple_score(db, "TCS")

    expected = round(
        60.0 * NONBANK_INDUSTRIAL_V2_WEIGHTS["financial_strength"]
        + 40.0 * NONBANK_INDUSTRIAL_V2_WEIGHTS["valuation"]
        + 80.0 * NONBANK_INDUSTRIAL_V2_WEIGHTS["market_behaviour"],
        1,
    )
    assert result.methodology_version == "NONBANK_INDUSTRIAL_V2"
    assert result.score == expected
    assert result.pillar_coverage_status == "complete"
    assert "current_intelligence" not in result.weights
    assert result.pillars["current_intelligence"].score == 10.0  # real, visible, just not weighted


@pytest.mark.asyncio
async def test_v2_headline_score_identical_whether_or_not_current_intelligence_is_present(monkeypatch):
    """The core guarantee of this redesign: Current Intelligence being
    None must produce the EXACT SAME headline score as it being present --
    proving it never gates or contributes to the number."""
    fs, val, mkt = _pillar("financial_strength", 55.0), _pillar("valuation", 65.0), _pillar("market_behaviour", 45.0)
    from app.db.session import AsyncSessionLocal

    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=_pillar("current_intelligence", None))
    async with AsyncSessionLocal() as db:
        without_ci = await compute_marketripple_score(db, "TCS")

    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=_pillar("current_intelligence", 77.0))
    async with AsyncSessionLocal() as db:
        with_ci = await compute_marketripple_score(db, "TCS")

    assert without_ci.score == with_ci.score
    assert without_ci.pillar_coverage_status == with_ci.pillar_coverage_status == "complete"


@pytest.mark.asyncio
async def test_v2_withholds_headline_score_when_fewer_than_three_required_pillars_are_usable(monkeypatch):
    fs, val = _pillar("financial_strength", 60.0), _pillar("valuation", 40.0)
    mkt_missing = _pillar("market_behaviour", None)
    from app.db.session import AsyncSessionLocal

    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt_missing, ci=_pillar("current_intelligence", 50.0))
    async with AsyncSessionLocal() as db:
        result = await compute_marketripple_score(db, "TCS")

    assert result.score is None
    assert result.label is None
    assert result.pillar_coverage_status == "partial"
    assert "2 of 3 required pillars" in result.pillar_coverage_message
    # The two real pillars that DID compute stay fully visible.
    assert result.pillars["financial_strength"].score == 60.0
    assert result.pillars["valuation"].score == 40.0


@pytest.mark.asyncio
async def test_banking_composition_completely_unaffected_by_v2(monkeypatch):
    """Regression guard: Banking must still use its own 4-pillar dynamic-
    renormalization rule against CANDIDATE_WEIGHTS, never the V2 3-pillar
    fixed-weight rule -- proven with a controlled case where a partial
    (3-of-4) Banking result would produce a DIFFERENT number under each
    rule if they were ever accidentally shared."""
    fs, val, mkt = _pillar("financial_strength", 60.0), _pillar("valuation", 40.0), _pillar("market_behaviour", 80.0)
    ci_missing = _pillar("current_intelligence", None)
    from app.db.session import AsyncSessionLocal

    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=ci_missing)
    async with AsyncSessionLocal() as db:
        result = await compute_marketripple_score(db, "ICICIBANK")

    assert result.methodology_version == "BANKING_V1"
    assert result.weights == CANDIDATE_WEIGHTS
    # Banking's own rule: 3-of-4 pillars usable < total_pillars (4) -> partial, headline withheld.
    # (Confirms Banking did NOT switch to V2's 3-required-pillar rule, which
    # would have called this "complete" and produced a real headline score.)
    assert result.score is None
    assert result.pillar_coverage_status == "partial"
    assert "3 of 4 pillars" in result.pillar_coverage_message


# ── compute_nonbank_headline() — the ONE dedicated function, unit-tested ────
# directly (no engine/db involved), per owner instruction 2026-09-27.
def test_compute_nonbank_headline_uses_exact_fraction_weights():
    """8/15 + 4/15 + 3/15 = 1 exactly -- verify the computed headline
    matches hand-computed exact rational arithmetic, not a decimal
    approximation that could drift for an unlucky input."""
    pillars = {
        "financial_strength": _pillar("financial_strength", 73.0),
        "valuation": _pillar("valuation", 41.0),
        "market_behaviour": _pillar("market_behaviour", 88.0),
        "current_intelligence": _pillar("current_intelligence", 12.0),
    }
    result = compute_nonbank_headline(pillars)
    from fractions import Fraction
    expected = round(float(Fraction(73, 1) * Fraction(8, 15) + Fraction(41, 1) * Fraction(4, 15) + Fraction(88, 1) * Fraction(3, 15)), 1)
    assert result.score == expected
    assert result.status == "complete"
    assert result.reason_code is None
    assert result.weights == NONBANK_INDUSTRIAL_V2_WEIGHTS


def test_compute_nonbank_headline_never_reads_current_intelligence():
    base = {
        "financial_strength": _pillar("financial_strength", 50.0),
        "valuation": _pillar("valuation", 50.0),
        "market_behaviour": _pillar("market_behaviour", 50.0),
    }
    without_ci = compute_nonbank_headline({**base, "current_intelligence": _pillar("current_intelligence", None)})
    with_ci = compute_nonbank_headline({**base, "current_intelligence": _pillar("current_intelligence", 99.0)})
    assert without_ci.score == with_ci.score == 50.0


def test_compute_nonbank_headline_missing_pillar_returns_structured_reason():
    pillars = {
        "financial_strength": _pillar("financial_strength", 60.0),
        "valuation": _pillar("valuation", None),
        "market_behaviour": _pillar("market_behaviour", 70.0),
        "current_intelligence": _pillar("current_intelligence", 40.0),
    }
    result = compute_nonbank_headline(pillars)
    assert result.score is None
    assert result.status == "partial"
    assert result.reason_code == NONBANK_HEADLINE_REASON_MISSING_PILLAR
    assert result.missing_pillars == ["valuation"]


def test_compute_nonbank_headline_all_missing_is_insufficient_not_partial():
    pillars = {name: _pillar(name, None) for name in ("financial_strength", "valuation", "market_behaviour", "current_intelligence")}
    result = compute_nonbank_headline(pillars)
    assert result.status == "insufficient"
    assert result.reason_code == NONBANK_HEADLINE_REASON_MISSING_PILLAR
    assert set(result.missing_pillars) == {"financial_strength", "valuation", "market_behaviour"}


def test_compute_nonbank_headline_rejects_out_of_range_score_as_invalid():
    """Real validation, not just presence-checking -- a pillar score
    outside [0, 100] indicates a real upstream bug and must never silently
    produce a nonsensical headline."""
    pillars = {
        "financial_strength": _pillar("financial_strength", 150.0),  # invalid
        "valuation": _pillar("valuation", 50.0),
        "market_behaviour": _pillar("market_behaviour", 50.0),
        "current_intelligence": _pillar("current_intelligence", 50.0),
    }
    result = compute_nonbank_headline(pillars)
    assert result.score is None
    assert result.status == "insufficient"
    assert result.reason_code == NONBANK_HEADLINE_REASON_INVALID_SCORE_RANGE


def test_compute_nonbank_headline_boundary_values_are_valid():
    pillars = {
        "financial_strength": _pillar("financial_strength", 0.0),
        "valuation": _pillar("valuation", 100.0),
        "market_behaviour": _pillar("market_behaviour", 50.0),
        "current_intelligence": _pillar("current_intelligence", None),
    }
    result = compute_nonbank_headline(pillars)
    assert result.status == "complete"
    assert result.reason_code is None

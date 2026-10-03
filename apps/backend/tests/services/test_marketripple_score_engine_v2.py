"""
MARKETRIPPLE_SCORE_V1 unified engine composition — owner instruction
2026-09-27 ("one score calculation": replace the separate Banking V1 and
Non-bank V2 headline rules with one shared function for every supported
company). Monkeypatches the four pillar-scoring functions with controlled
PillarScore objects (no live network) to verify the exact composition
math: only Financial Strength/Valuation/Market Behaviour ever enter the
weighted blend, Current Intelligence never gates or contributes to the
headline number even when present, and Banking now uses the EXACT SAME
rule as every non-bank sector (a real, deliberate change from the
engagement's earlier NONBANK_INDUSTRIAL_V2-only 3-pillar redesign).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.marketripple_score.contracts import (
    MARKETRIPPLE_SCORE_METHODOLOGY_VERSION, PillarScore, PillarStatus,
)
from app.services.marketripple_score.engine import (
    HEADLINE_REASON_INVALID_SCORE_RANGE, HEADLINE_REASON_MISSING_PILLAR,
    HEADLINE_WEIGHTS, compute_headline, compute_marketripple_score,
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

    async def fake_mkt(symbol, sector, prefetched_benchmarks=None, cutoff_date=None, benchmark_fetched_at=None):
        return mkt

    async def fake_ci(db, symbol):
        return ci

    monkeypatch.setattr("app.services.marketripple_score.engine.score_financial_strength", fake_fs)
    monkeypatch.setattr("app.services.marketripple_score.engine.score_valuation", fake_val)
    monkeypatch.setattr("app.services.marketripple_score.engine.score_market_behaviour", fake_mkt)
    monkeypatch.setattr("app.services.marketripple_score.engine.score_current_intelligence", fake_ci)


@pytest.mark.asyncio
async def test_headline_score_uses_only_the_three_required_pillars(monkeypatch):
    """A real Technology symbol, all 4 pillars present INCLUDING current
    intelligence -- the headline score must come from ONLY fs/val/mkt at
    the fixed weights, current_intelligence's real score must be visible
    in `pillars` but absent from `weights` and NOT used in the blend at
    all."""
    fs, val, mkt, ci = _pillar("financial_strength", 60.0), _pillar("valuation", 40.0), _pillar("market_behaviour", 80.0), _pillar("current_intelligence", 10.0)
    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=ci)

    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await compute_marketripple_score(db, "TCS")

    expected = round(
        60.0 * HEADLINE_WEIGHTS["financial_strength"]
        + 40.0 * HEADLINE_WEIGHTS["valuation"]
        + 80.0 * HEADLINE_WEIGHTS["market_behaviour"],
        1,
    )
    assert result.methodology_version == MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    assert result.score == expected
    assert result.pillar_coverage_status == "complete"
    assert "current_intelligence" not in result.weights
    assert result.pillars["current_intelligence"].score == 10.0  # real, visible, just not weighted


@pytest.mark.asyncio
async def test_headline_score_identical_whether_or_not_current_intelligence_is_present(monkeypatch):
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
async def test_withholds_headline_score_when_fewer_than_three_required_pillars_are_usable(monkeypatch):
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
async def test_banking_now_uses_the_identical_shared_headline_function_as_nonbank(monkeypatch):
    """The real, deliberate change this unification makes to Banking: a
    bank with Current Intelligence missing but all 3 required pillars
    present must now get a REAL headline number (Banking's old rule
    withheld any headline below 4-of-4) -- and that number must match
    hand-computed exact-fraction arithmetic at the SAME weights a non-bank
    company would use, proving one real shared function, not two rules
    that happen to agree by coincidence."""
    fs, val, mkt = _pillar("financial_strength", 60.0), _pillar("valuation", 40.0), _pillar("market_behaviour", 80.0)
    ci_missing = _pillar("current_intelligence", None)
    from app.db.session import AsyncSessionLocal

    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=ci_missing)
    async with AsyncSessionLocal() as db:
        result = await compute_marketripple_score(db, "ICICIBANK")

    expected = round(
        60.0 * HEADLINE_WEIGHTS["financial_strength"]
        + 40.0 * HEADLINE_WEIGHTS["valuation"]
        + 80.0 * HEADLINE_WEIGHTS["market_behaviour"],
        1,
    )
    assert result.methodology_version == MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    assert result.weights == HEADLINE_WEIGHTS
    assert result.score == expected
    assert result.label is not None
    assert result.pillar_coverage_status == "complete"
    assert "current_intelligence" not in result.weights


@pytest.mark.asyncio
async def test_banking_and_nonbank_peer_universes_stay_separate_under_the_shared_methodology(monkeypatch):
    """Sharing one methodology tag/headline function must never blur which
    real peer group a score was computed against -- ICICIBANK's peer
    universe must still be the real Banking universe, never a Technology
    sector list, even though both now report the same methodology_version."""
    fs, val, mkt = _pillar("financial_strength", 50.0), _pillar("valuation", 50.0), _pillar("market_behaviour", 50.0)
    from app.db.session import AsyncSessionLocal

    _patch_pillars(monkeypatch, fs=fs, val=val, mkt=mkt, ci=_pillar("current_intelligence", None))
    async with AsyncSessionLocal() as db:
        bank_result = await compute_marketripple_score(db, "ICICIBANK")
        tech_result = await compute_marketripple_score(db, "TCS")

    assert bank_result.methodology_version == tech_result.methodology_version == MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    assert "ICICIBANK" in bank_result.peer_universe
    assert "TCS" not in bank_result.peer_universe
    assert "TCS" in tech_result.peer_universe
    assert "ICICIBANK" not in tech_result.peer_universe


# ── compute_headline() — the ONE dedicated shared function, unit-tested ────
# directly (no engine/db involved), per owner instruction 2026-09-27.
def test_compute_headline_uses_exact_fraction_weights():
    """8/15 + 4/15 + 3/15 = 1 exactly -- verify the computed headline
    matches hand-computed exact rational arithmetic, not a decimal
    approximation that could drift for an unlucky input."""
    pillars = {
        "financial_strength": _pillar("financial_strength", 73.0),
        "valuation": _pillar("valuation", 41.0),
        "market_behaviour": _pillar("market_behaviour", 88.0),
        "current_intelligence": _pillar("current_intelligence", 12.0),
    }
    result = compute_headline(pillars)
    from fractions import Fraction
    expected = round(float(Fraction(73, 1) * Fraction(8, 15) + Fraction(41, 1) * Fraction(4, 15) + Fraction(88, 1) * Fraction(3, 15)), 1)
    assert result.score == expected
    assert result.status == "complete"
    assert result.reason_code is None
    assert result.weights == HEADLINE_WEIGHTS


def test_compute_headline_never_reads_current_intelligence():
    base = {
        "financial_strength": _pillar("financial_strength", 50.0),
        "valuation": _pillar("valuation", 50.0),
        "market_behaviour": _pillar("market_behaviour", 50.0),
    }
    without_ci = compute_headline({**base, "current_intelligence": _pillar("current_intelligence", None)})
    with_ci = compute_headline({**base, "current_intelligence": _pillar("current_intelligence", 99.0)})
    assert without_ci.score == with_ci.score == 50.0


def test_compute_headline_missing_pillar_returns_structured_reason():
    pillars = {
        "financial_strength": _pillar("financial_strength", 60.0),
        "valuation": _pillar("valuation", None),
        "market_behaviour": _pillar("market_behaviour", 70.0),
        "current_intelligence": _pillar("current_intelligence", 40.0),
    }
    result = compute_headline(pillars)
    assert result.score is None
    assert result.status == "partial"
    assert result.reason_code == HEADLINE_REASON_MISSING_PILLAR
    assert result.missing_pillars == ["valuation"]


def test_compute_headline_all_missing_is_insufficient_not_partial():
    pillars = {name: _pillar(name, None) for name in ("financial_strength", "valuation", "market_behaviour", "current_intelligence")}
    result = compute_headline(pillars)
    assert result.status == "insufficient"
    assert result.reason_code == HEADLINE_REASON_MISSING_PILLAR
    assert set(result.missing_pillars) == {"financial_strength", "valuation", "market_behaviour"}


def test_compute_headline_rejects_out_of_range_score_as_invalid():
    """Real validation, not just presence-checking -- a pillar score
    outside [0, 100] indicates a real upstream bug and must never silently
    produce a nonsensical headline."""
    pillars = {
        "financial_strength": _pillar("financial_strength", 150.0),  # invalid
        "valuation": _pillar("valuation", 50.0),
        "market_behaviour": _pillar("market_behaviour", 50.0),
        "current_intelligence": _pillar("current_intelligence", 50.0),
    }
    result = compute_headline(pillars)
    assert result.score is None
    assert result.status == "insufficient"
    assert result.reason_code == HEADLINE_REASON_INVALID_SCORE_RANGE


def test_compute_headline_boundary_values_are_valid():
    pillars = {
        "financial_strength": _pillar("financial_strength", 0.0),
        "valuation": _pillar("valuation", 100.0),
        "market_behaviour": _pillar("market_behaviour", 50.0),
        "current_intelligence": _pillar("current_intelligence", None),
    }
    result = compute_headline(pillars)
    assert result.status == "complete"
    assert result.reason_code is None

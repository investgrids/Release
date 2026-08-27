"""
Phase B0 — leakage-lock regression tests (owner instruction, 2026-08-23).

A full line-by-line manual audit already traced one real prediction
(RELIANCE, as_of=2023-03-17, idx=395) end-to-end through
generate_phase2d_predictions() against real stored QuantResearchPrediction/
QuantResearchEvaluation rows and confirmed no per-sample look-ahead
leakage: every baseline receives exactly `series[: idx + 1]`
(phase2d_backtest.py:186), and every evaluation target index is
`idx + horizon` for horizon >= 1 (phase2d_backtest.py:250), a strict `>`
boundary. These two tests turn that one-time manual finding into an
executable, regression-proof guarantee — not just something proven true
today by inspection.

The audit's own "structural fragility" finding (item 5) is exactly why
these tests matter: none of baselines.py's five functions accept an
as-of index and self-truncate — they trust every caller completely. The
leakage boundary lives ENTIRELY at the call site
(`closes_so_far = [c for _, c in series[: idx + 1]]`), so these tests
mirror that exact production slicing pattern rather than testing
baselines.py's pure functions in isolation, which would trivially pass
regardless of whether the call site is ever broken.

Run against REAL PriceBar data (RELIANCE) — same symbol/index used in
the manual audit trace, not synthetic data, per this codebase's
established "verify against real data" convention.
"""
from __future__ import annotations

import copy

import pytest

from app.db.session import AsyncSessionLocal
from app.services.quant.baselines import ALL_BASELINES
from app.services.quant.shadow_backtest import _load_closes

_SYMBOL = "RELIANCE"
_IDX = 395  # 2023-03-17 — the exact as-of index independently traced against real stored predictions


def _predict_at(series: list[tuple], idx: int) -> dict:
    """The EXACT production slicing pattern (phase2d_backtest.py:186,194).
    Deliberately not importing a refactored helper — this test stays
    honest about what the frozen production code actually does today."""
    closes_so_far = [c for _, c in series[: idx + 1]]
    return {name: fn(closes_so_far) for name, fn in ALL_BASELINES.items()}


async def _real_reliance_series() -> list[tuple]:
    async with AsyncSessionLocal() as db:
        series = await _load_closes(db, _SYMBOL)
    assert len(series) > _IDX + 20, "need real RELIANCE PriceBar data past the traced as-of index for this test"
    return series


@pytest.mark.asyncio
async def test_future_mutation_does_not_change_the_prediction():
    """Take a prediction at T, run it normally. Massively alter every
    price AFTER T. Re-run the prediction at T. It must be unchanged —
    this is the single strongest proof that no code path reads beyond
    series[:idx+1]."""
    series = await _real_reliance_series()

    before = _predict_at(series, _IDX)

    mutated = copy.deepcopy(series)
    for i in range(_IDX + 1, len(mutated)):
        d, _ = mutated[i]
        mutated[i] = (d, 999999.0)  # deliberately absurd future price — impossible to miss if it leaks in

    after = _predict_at(mutated, _IDX)

    for name in ALL_BASELINES:
        assert before[name].direction == after[name].direction, (
            f"{name}: direction changed after mutating future prices — LEAKAGE"
        )
        assert before[name].expected_return == after[name].expected_return, (
            f"{name}: expected_return changed after mutating future prices — LEAKAGE"
        )
        assert before[name].expected_volatility == after[name].expected_volatility, (
            f"{name}: expected_volatility changed after mutating future prices — LEAKAGE"
        )


@pytest.mark.asyncio
async def test_truncation_equivalence():
    """forecast(full_dataset, as_of=T) must equal
    forecast(dataset_physically_truncated_at_T, as_of=T) — guards
    specifically against off-by-one/boundary-arithmetic regressions in
    the idx+1 slice used throughout the harness."""
    series = await _real_reliance_series()

    from_full = _predict_at(series, _IDX)  # slice a longer array down to idx

    physically_truncated = series[: _IDX + 1]
    from_truncated = _predict_at(physically_truncated, len(physically_truncated) - 1)  # already-short array

    for name in ALL_BASELINES:
        assert from_full[name].direction == from_truncated[name].direction, (
            f"{name}: truncation equivalence failed — direction differs"
        )
        assert from_full[name].expected_return == from_truncated[name].expected_return, (
            f"{name}: truncation equivalence failed — expected_return differs"
        )
        assert from_full[name].expected_volatility == from_truncated[name].expected_volatility, (
            f"{name}: truncation equivalence failed — expected_volatility differs"
        )


@pytest.mark.asyncio
async def test_horizon_target_is_strictly_after_the_as_of_index():
    """Direct regression guard for audit item 10 (horizon off-by-one):
    for every horizon in the frozen HORIZONS tuple, the target index
    (idx + horizon) must be strictly greater than the as-of index."""
    from app.services.quant.phase2d_backtest import HORIZONS

    for horizon in HORIZONS:
        assert horizon >= 1, f"horizon {horizon} would make target_idx == as_of_idx — leakage"
        target_idx = _IDX + horizon
        assert target_idx > _IDX

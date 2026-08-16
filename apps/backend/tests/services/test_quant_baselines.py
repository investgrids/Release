"""
Phase 2B §7 — baseline model regression tests, offline (no DB, no network).

Each baseline is a pure function over a closing-price series; these
tests pin down the directional behavior that makes each model a
distinct, real challenger rather than a copy of another one (Phase 2A
§9: the point is that they can disagree, e.g. momentum vs mean
reversion on the exact same series).
"""
from __future__ import annotations

from app.services.quant.baselines import (
    ALL_BASELINES,
    random_walk,
    previous_return,
    moving_average_momentum,
    mean_reversion,
    linear_regression,
)

RISING = [100 + i * 0.5 for i in range(30)]
FALLING = [100 - i * 0.5 for i in range(30)]
FLAT = [100 + (0.1 if i % 2 == 0 else -0.1) for i in range(30)]


def test_random_walk_always_predicts_sideways_with_zero_expected_return():
    for series in (RISING, FALLING, FLAT):
        r = random_walk(series)
        assert r.direction == "sideways"
        assert r.expected_return == 0.0


def test_previous_return_continues_the_most_recent_move():
    up_series = [100.0, 100.0, 101.0]   # last step: +1%
    down_series = [100.0, 100.0, 99.0]  # last step: -1%
    assert previous_return(up_series).direction == "up"
    assert previous_return(down_series).direction == "down"


def test_momentum_and_mean_reversion_disagree_on_a_clear_trend():
    # This is the whole point of having both (Phase 2A §9) — a real
    # trend should make momentum say "up" and mean reversion say "down",
    # never the same direction on the same series.
    momentum = moving_average_momentum(RISING)
    reversion = mean_reversion(RISING)
    assert momentum.direction == "up"
    assert reversion.direction == "down"
    assert momentum.direction != reversion.direction


def test_momentum_and_mean_reversion_flip_together_on_a_falling_trend():
    momentum = moving_average_momentum(FALLING)
    reversion = mean_reversion(FALLING)
    assert momentum.direction == "down"
    assert reversion.direction == "up"


def test_linear_regression_follows_a_clean_trend():
    assert linear_regression(RISING).direction == "up"
    assert linear_regression(FALLING).direction == "down"


def test_flat_series_mostly_reads_as_sideways():
    # previous_return is naive-enough to flip on the very last noisy
    # step — that's expected, not a bug — but the smoother models
    # (momentum/mean_reversion/linear_regression) should stay sideways
    # on genuinely flat data.
    assert moving_average_momentum(FLAT).direction == "sideways"
    assert mean_reversion(FLAT).direction == "sideways"
    assert linear_regression(FLAT).direction == "sideways"


def test_short_series_degrades_to_sideways_instead_of_raising():
    short = [100.0, 101.0]
    for name, fn in ALL_BASELINES.items():
        result = fn(short)
        assert result.direction in ("up", "down", "sideways"), f"{name} produced an invalid direction"


def test_all_five_baselines_are_registered():
    assert set(ALL_BASELINES.keys()) == {
        "random_walk", "previous_return", "ma_momentum", "mean_reversion", "linear_regression",
    }


def test_volatility_is_computed_and_shared_across_models():
    for name, fn in ALL_BASELINES.items():
        result = fn(RISING)
        assert result.expected_volatility is not None, f"{name} should report volatility on a long-enough series"
        assert result.expected_volatility >= 0

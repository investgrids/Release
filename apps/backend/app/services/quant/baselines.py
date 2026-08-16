"""
Simple baseline/challenger models — Phase 2B §7.

Phase 2A §9: Kronos must not be evaluated in isolation — "does Kronos
beat a simple baseline" is the real question, not "does it look
plausible." These five are the baselines it will eventually have to
beat. All of them are interpretable one-liners deliberately — no new ML
dependency (no LightGBM/XGBoost — Phase 2A §9 noted neither is a
current dependency, and introducing one is a real decision left for
whenever a baseline this simple stops being enough).

Every model here is a pure function over an already-fetched, strictly
historical closing-price series (`closes`, chronological, oldest first,
last element = "today"/the as-of date). None of them read anything
future — the caller (shadow_backtest.py) is responsible for only ever
passing `closes` truncated at the real as-of date, which is what makes
the later backtest leakage-free (Phase 2A §18).

`expected_return` is populated only where the model genuinely computes
one (momentum, mean reversion, linear regression) — random walk and
previous-return continuation are purely categorical by construction
(Phase 2A §10's own rule: don't fabricate a number a model doesn't
produce). `expected_volatility` is a shared, real measurement (rolling
stdev of daily returns) attached to every model's output, since it's a
property of the underlying series, not a claim of model skill.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass
class BaselineResult:
    model_name: str
    direction: str            # "up" | "down" | "sideways"
    expected_return: float | None       # % — only when the model computes one
    expected_volatility: float | None   # % — rolling stdev of daily returns


_SIDEWAYS_BAND_PCT = 0.15   # a move smaller than this is called "sideways", not noise-fit as a direction


def _direction_from_return(pct: float) -> str:
    if pct >= _SIDEWAYS_BAND_PCT:
        return "up"
    if pct <= -_SIDEWAYS_BAND_PCT:
        return "down"
    return "sideways"


def _daily_returns_pct(closes: list[float]) -> list[float]:
    return [round((closes[i] / closes[i - 1] - 1) * 100, 4) for i in range(1, len(closes)) if closes[i - 1] > 0]


def _volatility(closes: list[float], window: int = 20) -> float | None:
    rets = _daily_returns_pct(closes[-(window + 1):])
    if len(rets) < 5:
        return None
    return round(statistics.pstdev(rets), 3)


def random_walk(closes: list[float]) -> BaselineResult:
    """The null hypothesis: tomorrow = today, zero expected change. Any
    model that can't beat this on directional accuracy has no edge."""
    return BaselineResult("random_walk", "sideways", 0.0, _volatility(closes))


def previous_return(closes: list[float]) -> BaselineResult:
    """Continuation: tomorrow repeats today's realized direction."""
    if len(closes) < 2:
        return BaselineResult("previous_return", "sideways", None, _volatility(closes))
    pct = round((closes[-1] / closes[-2] - 1) * 100, 4) if closes[-2] > 0 else 0.0
    return BaselineResult("previous_return", _direction_from_return(pct), pct, _volatility(closes))


def moving_average_momentum(closes: list[float], short: int = 5, long: int = 20) -> BaselineResult:
    """Short MA above long MA -> bullish momentum, below -> bearish."""
    if len(closes) < long:
        return BaselineResult("ma_momentum", "sideways", None, _volatility(closes))
    short_ma = statistics.fmean(closes[-short:])
    long_ma = statistics.fmean(closes[-long:])
    pct = round((short_ma / long_ma - 1) * 100, 4) if long_ma > 0 else 0.0
    return BaselineResult("ma_momentum", _direction_from_return(pct), pct, _volatility(closes))


def mean_reversion(closes: list[float], window: int = 20) -> BaselineResult:
    """Latest close far ABOVE its moving average -> predict pullback (down);
    far BELOW -> predict bounce (up). Opposite sign of the momentum model
    by construction — that's the point, they're meant to disagree."""
    if len(closes) < window:
        return BaselineResult("mean_reversion", "sideways", None, _volatility(closes))
    ma = statistics.fmean(closes[-window:])
    if ma <= 0:
        return BaselineResult("mean_reversion", "sideways", None, _volatility(closes))
    deviation_pct = round((closes[-1] / ma - 1) * 100, 4)
    # Reversion bets AGAINST the deviation, scaled down (a full reversion
    # to the mean in one session is not a defensible expectation).
    expected = round(-deviation_pct * 0.25, 4)
    return BaselineResult("mean_reversion", _direction_from_return(expected), expected, _volatility(closes))


def linear_regression(closes: list[float], window: int = 20) -> BaselineResult:
    """Ordinary least squares on the last `window` closes vs. day index,
    extrapolated one step forward. No external dependency — a 2-point
    sufficient-statistics OLS, exact and dependency-free."""
    series = closes[-window:]
    if len(series) < window:
        return BaselineResult("linear_regression", "sideways", None, _volatility(closes))
    n = len(series)
    xs = list(range(n))
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(series)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, series))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return BaselineResult("linear_regression", "sideways", None, _volatility(closes))
    slope = num / den
    intercept = y_mean - slope * x_mean
    predicted_next = intercept + slope * n   # one step past the window
    last_close = series[-1]
    pct = round((predicted_next / last_close - 1) * 100, 4) if last_close > 0 else 0.0
    if math.isnan(pct) or math.isinf(pct):
        return BaselineResult("linear_regression", "sideways", None, _volatility(closes))
    return BaselineResult("linear_regression", _direction_from_return(pct), pct, _volatility(closes))


# Registry — shadow_backtest.py iterates this rather than hardcoding the
# five names in two places.
ALL_BASELINES: dict[str, "callable"] = {
    "random_walk": random_walk,
    "previous_return": previous_return,
    "ma_momentum": moving_average_momentum,
    "mean_reversion": mean_reversion,
    "linear_regression": linear_regression,
}

MODEL_VERSION = "v1"   # Phase 2B §5/§27 — every shadow prediction from this module is tagged f"baseline-{name}-{MODEL_VERSION}"

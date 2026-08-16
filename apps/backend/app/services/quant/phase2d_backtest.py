"""
Phase 2D — Quant Validation Lab.

Large-scale walk-forward validation of the four cheap baseline models
(Kronos deliberately excluded — frozen at EXPERIMENTAL_NOT_PROMOTED per
Phase 2C, not spent on a run this large until the baselines themselves
prove a persistent signal) over the full available PriceBar history,
weekly cadence, graded against BOTH absolute (stock up/down/sideways)
and Nifty-relative (stock outperform/underperform/inline vs ^NSEI)
outcomes, at three horizons.

Leakage discipline unchanged from Phase 2B/2C (Phase 2A §18): every
model only ever sees closes[:idx+1] for its own as-of index idx.

Evaluation reads outcomes directly from the PriceBar warehouse — NOT
prediction_evaluator.py, which stays untouched (owner's explicit
instruction: "create a research-only evaluator over the warehouse").
This is the whole point of Phase 2D at this scale: ~51k predictions x 3
horizons would mean ~150k live yfinance re-fetches through the
production evaluator's own throttle-paced path, hours of runtime and
real Yahoo-throttling risk, for outcome data that is already durably
stored. Reading PriceBar directly turns that into an in-memory
dictionary lookup.

Storage: app.db.models.quant_research (QuantResearchPrediction /
QuantResearchEvaluation), not PredictionRecord/PredictionEvaluation —
see that module's docstring for why.
"""
from __future__ import annotations

import asyncio
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.price_bar import PriceBar
from app.db.models.quant_research import QuantResearchPrediction, QuantResearchEvaluation
from app.services.quant.baselines import ALL_BASELINES, _direction_from_return, _SIDEWAYS_BAND_PCT
from app.services.quant.universe import NIFTY_50, SECTOR
from app.services.quant.benchmark import NIFTY50_SYMBOL, NIFTYBEES_SYMBOL
from app.services.quant.shadow_backtest import _load_closes

log = structlog.get_logger(__name__)

RUN_TAG = "phase2d-v1"
HORIZONS = (1, 5, 20)   # trading sessions ahead — not calendar days
WARMUP = 25             # covers the longest baseline window (20-bar MA/regression) + margin
_MODELS = {name: fn for name, fn in ALL_BASELINES.items() if name != "random_walk"}   # 4 — owner: "four cheap baseline models"
_MAX_HORIZON = max(HORIZONS)

_DIRECTION_TO_RELATIVE_LABEL = {"up": "outperform", "down": "underperform", "sideways": "inline"}
_BENCHMARK_LOOKBACK_DAYS = 3   # nearest-prior-trading-day tolerance for aligning benchmark date to stock date


def _year_bucket(d: date) -> str:
    """2021 alone is a partial year (warehouse starts Aug 2021) and 2026
    is partial too (data ends Aug 2026) — merged/labeled per the owner's
    own example bucket set (2021/22, 2023, 2024, 2025, 2026 YTD)."""
    if d.year in (2021, 2022):
        return "2021/22"
    if d.year == 2026:
        return "2026 YTD"
    return str(d.year)


def _relative_label(pct: float) -> str:
    if pct >= _SIDEWAYS_BAND_PCT:
        return "outperform"
    if pct <= -_SIDEWAYS_BAND_PCT:
        return "underperform"
    return "inline"


def _weekly_as_of_indices(bar_dates: list[date]) -> list[int]:
    """Index of the LAST trading day in each ISO (year, week) — one
    eligible as-of per calendar week, per the approved scope."""
    last_idx_per_week: dict[tuple[int, int], int] = {}
    for idx, d in enumerate(bar_dates):
        iso = d.isocalendar()
        last_idx_per_week[(iso[0], iso[1])] = idx   # later idx overwrites — dates are ascending
    return sorted(last_idx_per_week.values())


async def _load_benchmark_dicts(db: AsyncSession) -> tuple[dict[date, float], dict[date, float]]:
    nifty_series = await _load_closes(db, NIFTY50_SYMBOL)
    beeps_series = await _load_closes(db, NIFTYBEES_SYMBOL)
    return {d: c for d, c in nifty_series}, {d: c for d, c in beeps_series}


def _nearest_close(bench: dict[date, float], target: date) -> float | None:
    if target in bench:
        return bench[target]
    for back in range(1, _BENCHMARK_LOOKBACK_DAYS + 1):
        cand = target - timedelta(days=back)
        if cand in bench:
            return bench[cand]
    return None


def _resolve_benchmark(nifty: dict, beeps: dict, as_of: date, target: date) -> tuple[float | None, float | None, str | None]:
    """Returns (price_as_of, price_at_horizon, symbol_used). Tries NIFTY50
    first (both dates must resolve), falls back to NIFTYBEES, records
    which one actually supplied the numbers — owner's explicit
    requirement, not a silent default."""
    n_as_of, n_target = _nearest_close(nifty, as_of), _nearest_close(nifty, target)
    if n_as_of is not None and n_target is not None:
        return n_as_of, n_target, NIFTY50_SYMBOL
    b_as_of, b_target = _nearest_close(beeps, as_of), _nearest_close(beeps, target)
    if b_as_of is not None and b_target is not None:
        return b_as_of, b_target, NIFTYBEES_SYMBOL
    return None, None, None


async def _eligible_indices_by_symbol(db: AsyncSession) -> dict[str, tuple[list[int], list[tuple[date, float]]]]:
    """For every usable symbol (>=30 bars — naturally excludes TATAMOTORS,
    which has zero PriceBar rows, same finding as Phase 2C), returns the
    list of (as_of_index, full_series) pairs that clear warmup AND have
    enough future bars for the longest horizon. Computed once, reused
    identically by the planner and the generator so the plan is never a
    stale estimate of what actually runs."""
    out: dict[str, tuple[list[int], list[tuple[date, float]]]] = {}
    for symbol in NIFTY_50:
        series = await _load_closes(db, symbol)
        n = len(series)
        if n < WARMUP + _MAX_HORIZON + 1:
            continue
        bar_dates = [d for d, _ in series]
        weekly = _weekly_as_of_indices(bar_dates)
        eligible = [idx for idx in weekly if WARMUP <= idx and idx + _MAX_HORIZON < n]
        if eligible:
            out[symbol] = (eligible, series)
    return out


async def plan_phase2d_run(db: AsyncSession) -> dict:
    """Exact planned counts, computed before anything is generated —
    owner's explicit requirement. No sampling anywhere in this module:
    every number here is what generate_phase2d_predictions() will
    actually produce."""
    by_symbol = await _eligible_indices_by_symbol(db)

    total_dates = 0
    by_year: dict[str, int] = {}
    per_symbol_counts = {}
    for symbol, (indices, series) in by_symbol.items():
        per_symbol_counts[symbol] = len(indices)
        total_dates += len(indices)
        for idx in indices:
            yb = _year_bucket(series[idx][0])
            by_year[yb] = by_year.get(yb, 0) + 1

    n_models = len(_MODELS)
    n_horizons = len(HORIZONS)
    predictions_planned = total_dates * n_models
    evaluations_planned = predictions_planned * n_horizons   # each row carries both absolute+relative

    plan = {
        "symbols_used": len(by_symbol),
        "symbols_skipped": [s for s in NIFTY_50 if s not in by_symbol],
        "total_eligible_as_of_dates": total_dates,
        "models": sorted(_MODELS.keys()),
        "n_models": n_models,
        "horizons": list(HORIZONS),
        "predictions_planned": predictions_planned,
        "evaluations_planned": evaluations_planned,
        "eligible_dates_by_year": dict(sorted(by_year.items())),
        "eligible_dates_by_symbol": per_symbol_counts,
    }
    log.info("phase2d.plan", **{k: v for k, v in plan.items() if k not in ("eligible_dates_by_symbol",)})
    return plan


async def generate_phase2d_predictions(db: AsyncSession) -> dict:
    by_symbol = await _eligible_indices_by_symbol(db)
    stored = 0

    for symbol, (indices, series) in by_symbol.items():
        sector = SECTOR.get(symbol)
        for idx in indices:
            as_of_date, as_of_close = series[idx]
            closes_so_far = [c for _, c in series[: idx + 1]]
            trailing_20 = closes_so_far[-21:]
            own_trend_regime = (
                "trending_up" if len(trailing_20) >= 21 and trailing_20[-1] > trailing_20[0]
                else "trending_down" if len(trailing_20) >= 21
                else "unknown"
            )
            for name, fn in _MODELS.items():
                result = fn(closes_so_far)
                db.add(QuantResearchPrediction(
                    id=str(uuid4()), run_tag=RUN_TAG, symbol=symbol, sector=sector, model_name=name,
                    as_of_date=as_of_date, direction=result.direction,
                    expected_return=result.expected_return, expected_volatility=result.expected_volatility,
                    stock_price_as_of=as_of_close, own_trend_regime=own_trend_regime, experimental=True,
                ))
                stored += 1
        await db.commit()   # per-symbol commit — one symbol's data never blocks another's
        log.info("phase2d.symbol_generated", symbol=symbol, dates=len(indices), stored_so_far=stored)

    log.info("phase2d.generated", stored=stored, symbols=len(by_symbol))
    return {"stored": stored, "symbols_used": len(by_symbol)}


async def _due_predictions(db: AsyncSession, horizon_days: int, limit: int) -> list[QuantResearchPrediction]:
    already_done = select(QuantResearchEvaluation.prediction_id).where(QuantResearchEvaluation.horizon_days == horizon_days)
    rows = (await db.execute(
        select(QuantResearchPrediction)
        .where(QuantResearchPrediction.run_tag == RUN_TAG, QuantResearchPrediction.id.not_in(already_done))
        .order_by(QuantResearchPrediction.symbol)
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def evaluate_phase2d_predictions(horizons: tuple[int, ...] = HORIZONS, batch_size: int = 5000) -> dict:
    """PriceBar-backed — no live fetches. Series and benchmark dicts are
    cached per symbol/globally across the whole run, not re-queried per
    prediction."""
    series_cache: dict[str, tuple[list[date], dict[date, float]]] = {}
    totals = {"evaluated": 0, "errors": 0, "no_outcome": 0}

    async with AsyncSessionLocal() as db:
        nifty_dict, beeps_dict = await _load_benchmark_dicts(db)

    for horizon in horizons:
        while True:
            async with AsyncSessionLocal() as db:
                due = await _due_predictions(db, horizon, batch_size)
                if not due:
                    break

                for pred in due:
                    if pred.symbol not in series_cache:
                        raw = await _load_closes(db, pred.symbol)
                        dates = [d for d, _ in raw]
                        closes_by_date = {d: c for d, c in raw}
                        series_cache[pred.symbol] = (dates, closes_by_date)
                    dates, closes_by_date = series_cache[pred.symbol]

                    idx = bisect_left(dates, pred.as_of_date)
                    if idx >= len(dates) or dates[idx] != pred.as_of_date or idx + horizon >= len(dates):
                        totals["no_outcome"] += 1
                        continue

                    target_date = dates[idx + horizon]
                    stock_price_horizon = closes_by_date[target_date]
                    stock_return = round((stock_price_horizon / pred.stock_price_as_of - 1) * 100, 4) if pred.stock_price_as_of > 0 else None

                    bench_as_of, bench_target, bench_used = _resolve_benchmark(nifty_dict, beeps_dict, pred.as_of_date, target_date)
                    bench_return = round((bench_target / bench_as_of - 1) * 100, 4) if bench_as_of and bench_target and bench_as_of > 0 else None
                    relative_return = round(stock_return - bench_return, 4) if stock_return is not None and bench_return is not None else None

                    actual_absolute = _direction_from_return(stock_return) if stock_return is not None else None
                    actual_relative = _relative_label(relative_return) if relative_return is not None else None

                    correct_absolute = (pred.direction == actual_absolute) if actual_absolute is not None else None
                    correct_relative = (
                        _DIRECTION_TO_RELATIVE_LABEL.get(pred.direction) == actual_relative
                        if actual_relative is not None else None
                    )

                    try:
                        db.add(QuantResearchEvaluation(
                            id=str(uuid4()), prediction_id=pred.id, horizon_days=horizon,
                            stock_price_at_horizon=stock_price_horizon, stock_return_pct=stock_return,
                            benchmark_symbol_used=bench_used, benchmark_price_as_of=bench_as_of,
                            benchmark_price_at_horizon=bench_target, benchmark_return_pct=bench_return,
                            relative_return_pct=relative_return,
                            actual_direction_absolute=actual_absolute, actual_direction_relative=actual_relative,
                            correct_absolute=correct_absolute, correct_relative=correct_relative,
                        ))
                        totals["evaluated"] += 1
                    except Exception as exc:
                        log.error("phase2d.eval_row_error", id=pred.id[:8], horizon=horizon, error=str(exc)[:120])
                        totals["errors"] += 1

                await db.commit()
                log.info("phase2d.batch_evaluated", horizon=horizon, batch=len(due), totals=dict(totals))

    log.info("phase2d.evaluated", **totals)
    return totals

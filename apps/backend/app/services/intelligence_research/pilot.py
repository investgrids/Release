"""
Phase 2E.2 — small, explicitly-labeled exploratory pilot.

Reuses exactly the outcome machinery Phase 2D validated (PriceBar,
absolute + Nifty-relative returns, session-counted horizons, same
_direction_from_return/_relative_label/_resolve_benchmark) — the same
naive-base-rate lesson from Phase 2D applies here: a "Strong Positive"
bucket only means something if it beats what the market was doing
anyway, not just whether the stock went up.

Leakage boundary: an observation's as-of date is the evidence trigger
date (see evidence.py — the day something new was actually observed).
Evidence is aggregated over (trigger_date - window_days, trigger_date]
only (evidence.py enforces this). The outcome is resolved from
PriceBar strictly AFTER the as-of trading day. No evidence with
occurred_at after the as-of date is ever included — enforced once, in
evidence.py, not re-implemented here.

EXPLORATORY — SMALL SAMPLE. This pilot's own output must always be read
with that label attached; see report formatting below. Not for
production weighting decisions.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_pilot import IntelligencePilotObservation, IntelligencePilotEvaluation
from app.services.intelligence_research.evidence import load_all_evidence, evidence_trigger_dates, build_evidence_state
from app.services.intelligence_research.safe_sources import RESEARCH_VERSION
from app.services.quant.universe import NIFTY_50, SECTOR
from app.services.quant.shadow_backtest import _load_closes
from app.services.quant.phase2d_backtest import _load_benchmark_dicts, _resolve_benchmark, HORIZONS as _PRICE_HORIZONS
from app.services.quant.baselines import _direction_from_return
from app.services.quant.phase2d_backtest import _relative_label

log = structlog.get_logger(__name__)

HORIZONS = _PRICE_HORIZONS   # (1, 5, 20) — identical to Phase 2D, deliberately
WINDOW_DAYS = 7
_MIN_BARS = 30
_MAX_HORIZON = max(HORIZONS)


async def _price_series_by_symbol(db: AsyncSession) -> dict[str, list[tuple[date, float]]]:
    out = {}
    for symbol in NIFTY_50:
        series = await _load_closes(db, symbol)
        if len(series) >= _MIN_BARS:
            out[symbol] = series
    return out


async def _eligible_observations(db: AsyncSession) -> dict[str, list[tuple[date, int]]]:
    """(symbol, trigger_date, as_of_bar_index) triples — the as_of bar is
    the most recent trading day on/before the trigger date (evidence
    observed on a non-trading day is attributed to the prior close),
    and must have >= 20 future trading sessions available so every
    horizon is resolvable."""
    by_symbol_evidence = await load_all_evidence(db)
    prices = await _price_series_by_symbol(db)

    out: dict[str, list[tuple[date, int]]] = {}
    for symbol, events in by_symbol_evidence.items():
        if not events or symbol not in prices:
            continue
        series = prices[symbol]
        bar_dates = [d for d, _ in series]
        n = len(bar_dates)
        eligible = []
        for trigger_date in evidence_trigger_dates(events):
            idx = bisect_right(bar_dates, trigger_date) - 1   # most recent bar <= trigger_date
            if idx < 0 or idx + _MAX_HORIZON >= n:
                continue
            eligible.append((trigger_date, idx))
        if eligible:
            out[symbol] = eligible
    return out


async def plan_pilot(db: AsyncSession) -> dict:
    """Exact planned counts before generating anything — same discipline
    as Phase 2D's plan_phase2d_run()."""
    eligible = await _eligible_observations(db)
    total = sum(len(v) for v in eligible.values())
    return {
        "symbols_used": len(eligible),
        "symbols_skipped": [s for s in NIFTY_50 if s not in eligible],
        "total_eligible_observations": total,
        "horizons": list(HORIZONS),
        "evaluations_planned": total * len(HORIZONS),
        "window_days": WINDOW_DAYS,
        "observations_by_symbol": {s: len(v) for s, v in eligible.items()},
    }


async def run_pilot(db: AsyncSession) -> dict:
    """Generates + evaluates in one pass (small scale — unlike Phase 2D,
    no need to split into separate batched jobs)."""
    by_symbol_evidence = await load_all_evidence(db)
    eligible = await _eligible_observations(db)
    prices = await _price_series_by_symbol(db)
    nifty_dict, beeps_dict = await _load_benchmark_dicts(db)

    stored_obs = stored_eval = 0
    for symbol, pairs in eligible.items():
        events = by_symbol_evidence[symbol]
        series = prices[symbol]
        bar_dates = [d for d, _ in series]
        closes_by_date = {d: c for d, c in series}
        sector = SECTOR.get(symbol)

        for trigger_date, idx in pairs:
            state = build_evidence_state(symbol, trigger_date, events, window_days=WINDOW_DAYS)
            as_of_bar_date = bar_dates[idx]
            as_of_close = closes_by_date[as_of_bar_date]

            obs_id = str(uuid4())
            db.add(IntelligencePilotObservation(
                id=obs_id, research_version=RESEARCH_VERSION, symbol=symbol, as_of_date=trigger_date,
                as_of_bar_date=as_of_bar_date, window_days=WINDOW_DAYS,
                event_positive_count=state.positive_count, event_negative_count=state.negative_count,
                event_neutral_count=state.neutral_count, highest_impact_0_100=state.highest_impact_0_100,
                aggregate_signed_magnitude=state.aggregate_signed_magnitude,
                aggregate_confidence_0_100=state.aggregate_confidence_0_100,
                signal_count=state.signal_count, triage_count=state.triage_count,
                announcement_count=state.announcement_count, conflict_bucket=state.conflict_bucket,
                sector_at_observation=sector, stock_price_as_of=as_of_close,
                evidence_refs=state.evidence_refs,
            ))
            await db.flush()   # force the observation INSERT before its evaluations are added — see FK ordering note below
            stored_obs += 1

            for horizon in HORIZONS:
                target_date = bar_dates[idx + horizon]
                stock_price_horizon = closes_by_date[target_date]
                stock_return = round((stock_price_horizon / as_of_close - 1) * 100, 4) if as_of_close > 0 else None

                bench_as_of, bench_target, bench_used = _resolve_benchmark(nifty_dict, beeps_dict, as_of_bar_date, target_date)
                bench_return = round((bench_target / bench_as_of - 1) * 100, 4) if bench_as_of and bench_target and bench_as_of > 0 else None
                relative_return = round(stock_return - bench_return, 4) if stock_return is not None and bench_return is not None else None

                db.add(IntelligencePilotEvaluation(
                    id=str(uuid4()), observation_id=obs_id, horizon_days=horizon,
                    stock_price_at_horizon=stock_price_horizon, stock_return_pct=stock_return,
                    benchmark_symbol_used=bench_used, benchmark_return_pct=bench_return,
                    relative_return_pct=relative_return,
                    actual_direction_absolute=_direction_from_return(stock_return) if stock_return is not None else None,
                    actual_direction_relative=_relative_label(relative_return) if relative_return is not None else None,
                    outcome_source="pricebar",
                ))
                stored_eval += 1
        await db.commit()

    log.info("phase2e_pilot.generated", observations=stored_obs, evaluations=stored_eval)
    return {"observations": stored_obs, "evaluations": stored_eval}

"""
Shadow backtest orchestration — Phase 2B §8/§9/§10.

Generates historical shadow predictions from the five baselines
(baselines.py) over real PriceBar history, stores them via the
EXISTING prediction_service.store_prediction() (source="quant_baseline",
experimental=True — Phase 2B §5/§11), then evaluates them through the
EXISTING prediction_evaluator.evaluate_prediction() (Phase 2A §26: reuse,
don't build a parallel evaluation framework).

Leakage discipline (Phase 2A §18): for a shadow prediction "as of" index
i in a symbol's chronological close series, every baseline only ever
sees `closes[: i + 1]` — nothing at or after i+1 is visible to the
model. The evaluator's own outcome check reads REAL future price data
via a fresh yfinance fetch bracketing `created_at + horizon_days`,
which is intentionally the SAME mechanism used for any live prediction
— no separate warehouse-reading evaluation path was built (Phase 2A
§26's instruction), so this exercises the exact evaluation code any
future Kronos prediction will also go through.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.price_bar import PriceBar
from app.db.models.predictions import PredictionRecord
from app.services.quant.baselines import ALL_BASELINES, MODEL_VERSION
from app.services.quant.symbols import to_yfinance
from app.services.quant.universe import NIFTY_50
from app.services.prediction_service import store_prediction

log = structlog.get_logger(__name__)

SOURCE = "quant_baseline"
HORIZON_DAYS = 1   # next-session direction — Phase 2A §8's primary use case, simplest to validate first


async def _load_closes(db: AsyncSession, symbol: str) -> list[tuple]:
    """(bar_date, close) ascending for one symbol."""
    rows = (await db.execute(
        select(PriceBar.bar_date, PriceBar.close)
        .where(PriceBar.symbol == symbol, PriceBar.timeframe == "1d")
        .order_by(PriceBar.bar_date.asc())
    )).all()
    return [(r.bar_date, r.close) for r in rows]


def _pick_as_of_indices(n_bars: int, count: int, warmup: int = 25, lookahead_buffer: int = 3) -> list[int]:
    """Evenly spaced indices in the eligible range [warmup, n_bars - lookahead_buffer).
    warmup=25 covers the longest baseline window (linear_regression/
    ma_momentum's 20-bar lookback + margin). lookahead_buffer=3 leaves
    real future bars for the evaluator's own 1-day-ahead price fetch to
    find (it fetches live from yfinance regardless, but the as-of date
    itself must not be the very last bar in our own series, or the
    "prediction" wouldn't be a real historical one)."""
    lo, hi = warmup, n_bars - lookahead_buffer
    if hi <= lo:
        return []
    if count >= (hi - lo):
        return list(range(lo, hi))
    step = (hi - lo) / count
    return sorted({lo + int(i * step) for i in range(count)})


async def generate_shadow_predictions(db: AsyncSession, symbols: list[str] = None, dates_per_symbol: int = 4) -> dict:
    """Phase 2B §8 — generate + store baseline shadow predictions for
    every (symbol, as-of date, baseline) combination. 50 symbols x 4
    dates x 5 baselines = 1,000 shadow predictions, matching the scale
    named in the approved Phase 2B scope."""
    symbols = symbols or list(NIFTY_50)
    stored = 0
    skipped_symbols: list[str] = []

    for symbol in symbols:
        series = await _load_closes(db, symbol)
        if len(series) < 30:
            skipped_symbols.append(symbol)
            continue

        indices = _pick_as_of_indices(len(series), dates_per_symbol)
        for idx in indices:
            as_of_date, as_of_close = series[idx]
            closes_so_far = [c for _, c in series[: idx + 1]]   # no lookahead — strictly <= as_of
            created_at = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=timezone.utc)

            for name, fn in ALL_BASELINES.items():
                result = fn(closes_so_far)
                pred_id = await store_prediction(
                    source=SOURCE,
                    prediction_text=f"{name} baseline: {result.direction} for {symbol} next session ({as_of_date.isoformat()})",
                    direction=result.direction,
                    prediction_type="company",
                    target_entities=[{
                        "type": "company", "symbol": symbol,
                        "baseline_price": as_of_close, "baseline_ticker": to_yfinance(symbol),
                    }],
                    confidence_score=50.0,
                    confidence_level="Medium",
                    confidence_factors={"as_of_date": as_of_date.isoformat(), "input_window": len(closes_so_far)},
                    horizon_days=HORIZON_DAYS,
                    query=f"quant_baseline:{name}:{symbol}:{as_of_date.isoformat()}",
                    experimental=True,
                    model_version=f"baseline-{name}-{MODEL_VERSION}",
                    expected_return=result.expected_return,
                    expected_volatility=result.expected_volatility,
                    created_at=created_at,
                )
                if pred_id:
                    stored += 1

    log.info("shadow_backtest.generated", stored=stored, symbols=len(symbols) - len(skipped_symbols),
              skipped=skipped_symbols)
    return {"stored": stored, "symbols_used": len(symbols) - len(skipped_symbols), "symbols_skipped": skipped_symbols}


async def _get_due_shadow_predictions(db: AsyncSession, limit: int) -> list[dict]:
    """Source-scoped equivalent of prediction_service.get_due_predictions()
    — same WHERE logic (not-yet-evaluated-at-this-horizon, pending/
    evaluating status, created_at past the horizon cutoff), but scoped to
    SOURCE up front. The shared helper has no source filter and no
    ordering; a real, pre-existing backlog of ~1,500 unevaluated
    production predictions (ai_search/aipe/triage — confirmed live in
    this dev DB while running this backtest) fills its `limit` before
    ever reaching these rows. Still calls the SAME evaluate_prediction()
    per row (Phase 2A §26) — only the collection query changes, not the
    evaluation logic itself."""
    from datetime import timedelta
    from sqlalchemy import and_
    from app.db.models.predictions import PredictionEvaluation

    cutoff = datetime.now(timezone.utc) - timedelta(days=HORIZON_DAYS - 0.25)
    already_done = select(PredictionEvaluation.prediction_id).where(PredictionEvaluation.horizon_days == HORIZON_DAYS)
    rows = (await db.execute(
        select(PredictionRecord)
        .where(and_(
            PredictionRecord.source == SOURCE,
            PredictionRecord.created_at <= cutoff,
            PredictionRecord.status.in_(["pending", "evaluating"]),
            PredictionRecord.id.not_in(already_done),
        ))
        .limit(limit)
    )).scalars().all()
    return [
        {"id": r.id, "source": r.source, "direction": r.direction, "prediction_type": r.prediction_type,
         "target_entities": r.target_entities or [], "confidence_score": r.confidence_score,
         "confidence_level": r.confidence_level, "horizon_days": HORIZON_DAYS,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]


async def evaluate_shadow_predictions(limit: int = 1500, delay_sec: float = 0.25) -> dict:
    """Phase 2B §9 — run every due quant_baseline prediction through the
    EXISTING evaluator (prediction_evaluator.evaluate_prediction), not a
    new evaluation path."""
    from app.services.prediction_evaluator import evaluate_prediction

    async with AsyncSessionLocal() as db:
        due = await _get_due_shadow_predictions(db, limit)

    evaluated = errors = 0
    for pred in due:
        try:
            await evaluate_prediction(pred, HORIZON_DAYS)
            evaluated += 1
        except Exception as exc:
            log.error("shadow_backtest.eval_error", id=pred["id"][:8], error=str(exc)[:120])
            errors += 1
        await asyncio.sleep(delay_sec)

    # Deliberately NOT calling recompute_calibration() here in a way that
    # would matter — recompute_calibration() already filters
    # experimental=False (Phase 2B §6), so these evaluations cannot
    # affect it even if it runs. Not calling it at all keeps this
    # function's side effects scoped to exactly what it evaluated.
    log.info("shadow_backtest.evaluated", evaluated=evaluated, errors=errors, due=len(due))
    return {"evaluated": evaluated, "errors": errors, "due": len(due)}


async def compute_baseline_report(db: AsyncSession) -> list[dict]:
    """Phase 2B §10 — real, computed per-model results, never a hand-
    typed table. Direction accuracy = fraction of evaluated predictions
    where the model's own predicted `direction` matches the evaluator's
    real `actual_direction` (up/down/sideways) — this is a stricter,
    more literal measure than PredictionEvaluation.verdict (which folds
    in a magnitude threshold via _CORRECT_THRESH/_PARTIAL_THRESH); both
    are reported so neither hides the other."""
    from sqlalchemy import func
    from app.db.models.predictions import PredictionEvaluation

    rows = (await db.execute(
        select(
            PredictionRecord.model_version,
            PredictionRecord.direction,
            PredictionEvaluation.actual_direction,
            PredictionEvaluation.verdict,
            PredictionEvaluation.actual_move_pct,
        )
        .join(PredictionEvaluation, PredictionEvaluation.prediction_id == PredictionRecord.id)
        .where(PredictionRecord.source == SOURCE, PredictionRecord.experimental.is_(True))
    )).all()

    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r.model_version, []).append(r)

    report = []
    for model_version, items in sorted(by_model.items()):
        conclusive = [r for r in items if r.actual_direction is not None]
        n = len(conclusive)
        direction_hits = sum(1 for r in conclusive if r.direction == r.actual_direction)
        verdict_correct = sum(1 for r in items if r.verdict == "correct")
        verdict_partial = sum(1 for r in items if r.verdict == "partial")
        conclusive_verdicts = sum(1 for r in items if r.verdict != "inconclusive")
        report.append({
            "model_version": model_version,
            "n_evaluated": len(items),
            "n_conclusive": n,
            "n_inconclusive": len(items) - n,
            "direction_accuracy_pct": round(100 * direction_hits / n, 1) if n else None,
            "verdict_weighted_accuracy_pct": (
                round(100 * (verdict_correct + 0.5 * verdict_partial) / conclusive_verdicts, 1)
                if conclusive_verdicts else None
            ),
            "avg_realized_move_pct": (
                round(sum(r.actual_move_pct for r in conclusive if r.actual_move_pct is not None)
                      / max(1, sum(1 for r in conclusive if r.actual_move_pct is not None)), 3)
                if conclusive else None
            ),
        })
    return report

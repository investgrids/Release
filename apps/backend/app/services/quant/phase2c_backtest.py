"""
Phase 2C — broader walk-forward evaluation: pretrained Kronos vs. the
five baselines, same price data, same information boundary, same
evaluator, multiple horizons.

Explicitly answers the owner's three critiques of Phase 2B's report:
  1. More than 4 dates per symbol (dates_per_symbol default: 6, up from
     4 — combined with keeping the FULL 49-symbol universe rather than
     narrowing it, this is a real, not cosmetic, increase in the walk-
     forward sample).
  2. Multiple horizons (1/7/30 trading-adjacent days), not just "did
     tomorrow go up" — each prediction is evaluated at all three via
     the SAME evaluate_prediction() call used for horizon=1, exactly
     mirroring how a real production prediction already accumulates
     evaluations at multiple horizons over its lifecycle (see
     prediction_evaluator.run_evaluation_cycle's own [1,3,7,30] loop) —
     not three independently-parameterized re-predictions.
  3. Kronos receives EXACTLY the same closes[:i+1] truncation as the
     baselines (same _load_closes/_pick_as_of_indices from
     shadow_backtest.py, same as-of index) — zero leakage difference
     between the two sides of the comparison.

Tagged distinctly from Phase 2B's original 980-prediction run
(model_version suffix "-p2c") so the two results never get silently
mixed — Phase 2B's own report stays reproducible and untouched.

Kronos is optional by construction (Phase 2A §29): if the model fails
to load or a single inference call fails, that one (symbol, date) is
skipped for Kronos only — baselines for the same pair are unaffected,
and nothing raises past this module.
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
from app.services.quant.baselines import ALL_BASELINES
from app.services.quant.symbols import to_yfinance
from app.services.quant.universe import NIFTY_50, SECTOR
from app.services.quant.shadow_backtest import _load_closes, _pick_as_of_indices, SOURCE as SOURCE_BASELINE
from app.services.prediction_service import store_prediction

log = structlog.get_logger(__name__)

SOURCE_KRONOS = "quant_kronos"
P2C_SUFFIX = "-p2c"
HORIZONS = (1, 7, 30)   # next-session / ~1-week / ~1-month, Phase 2A §12's own horizon set


async def _load_ohlcv(db: AsyncSession, symbol: str) -> dict[str, list]:
    """Full OHLCV series (ascending), for Kronos — baselines only ever
    needed close, but KronosPredictor.predict() wants open/high/low/
    close(/volume)."""
    rows = (await db.execute(
        select(PriceBar.bar_date, PriceBar.open, PriceBar.high, PriceBar.low, PriceBar.close, PriceBar.volume)
        .where(PriceBar.symbol == symbol, PriceBar.timeframe == "1d")
        .order_by(PriceBar.bar_date.asc())
    )).all()
    return {
        "dates": [r.bar_date for r in rows], "open": [r.open for r in rows], "high": [r.high for r in rows],
        "low": [r.low for r in rows], "close": [r.close for r in rows], "volume": [r.volume for r in rows],
    }


async def generate_phase2c_predictions(db: AsyncSession, symbols: list[str] | None = None, dates_per_symbol: int = 6) -> dict:
    from app.services.quant import kronos_model

    symbols = symbols or list(NIFTY_50)
    stored_baseline = stored_kronos = kronos_failed = 0
    skipped_symbols: list[str] = []

    kronos_ready = kronos_model.is_available()
    if not kronos_ready:
        log.warning("phase2c.kronos_unavailable_at_start", reason="torch not importable")

    for symbol in symbols:
        series = await _load_ohlcv(db, symbol)
        n = len(series["dates"])
        if n < 30:
            skipped_symbols.append(symbol)
            continue

        # warmup=35, not shadow_backtest's default 25 — Kronos's own
        # predict() requires >=30 bars of context; 25 was tuned only for
        # the baselines' shorter (20-bar) windows and left Kronos just
        # under its own minimum at the earliest as-of date (confirmed
        # live: deterministic "insufficient_history" at idx=25 with n=26
        # bars). 35 guarantees every selected date clears 30 for Kronos
        # too, with no change to which dates the baselines see relative
        # to each other (both still see the same as-of dates as Kronos —
        # the point is raising the floor, not diverging the two).
        indices = _pick_as_of_indices(n, dates_per_symbol, warmup=35)
        for idx in indices:
            as_of_date = series["dates"][idx]
            as_of_close = series["close"][idx]
            closes_so_far = series["close"][: idx + 1]
            created_at = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=timezone.utc)
            target_entities = [{
                "type": "company", "symbol": symbol,
                "baseline_price": as_of_close, "baseline_ticker": to_yfinance(symbol),
            }]
            # Regime proxy — Phase 2C's own "performance by regime" ask.
            # NOT the app's fragmented market_regime concept (Phase 2A §17
            # found that's inconsistent across MarketSnapshot/
            # HistoricalMarketEvent/engine.py) — a fresh, transparent,
            # symbol-own-trend proxy computed from the SAME no-lookahead
            # closes the model saw: trailing 20-bar return sign. Labeled
            # honestly as a proxy, not "the market regime".
            trailing_20 = closes_so_far[-21:]
            own_trend_regime = (
                "trending_up" if len(trailing_20) >= 21 and trailing_20[-1] > trailing_20[0]
                else "trending_down" if len(trailing_20) >= 21
                else "unknown"
            )
            common_factors = {
                "as_of_date": as_of_date.isoformat(), "input_window": len(closes_so_far),
                "sector": SECTOR.get(symbol), "own_trend_regime": own_trend_regime,
            }

            for name, fn in ALL_BASELINES.items():
                result = fn(closes_so_far)
                pred_id = await store_prediction(
                    source=SOURCE_BASELINE,
                    prediction_text=f"{name} baseline (p2c): {result.direction} for {symbol} ({as_of_date.isoformat()})",
                    direction=result.direction, prediction_type="company", target_entities=target_entities,
                    confidence_score=50.0, confidence_level="Medium", confidence_factors=common_factors,
                    horizon_days=1, query=f"quant_baseline_p2c:{name}:{symbol}:{as_of_date.isoformat()}",
                    experimental=True, model_version=f"baseline-{name}-v2{P2C_SUFFIX}",
                    expected_return=result.expected_return, expected_volatility=result.expected_volatility,
                    created_at=created_at,
                )
                if pred_id:
                    stored_baseline += 1

            if kronos_ready:
                kr = kronos_model.predict(
                    bar_dates=series["dates"][: idx + 1], closes=closes_so_far,
                    opens=series["open"][: idx + 1], highs=series["high"][: idx + 1], lows=series["low"][: idx + 1],
                    volumes=series["volume"][: idx + 1],
                    future_dates=[series["dates"][idx + 1]] if idx + 1 < n else None,
                )
                if kr.ok:
                    pred_id = await store_prediction(
                        source=SOURCE_KRONOS,
                        prediction_text=f"Kronos (pretrained): {kr.direction} for {symbol} ({as_of_date.isoformat()})",
                        direction=kr.direction, prediction_type="company", target_entities=target_entities,
                        confidence_score=50.0, confidence_level="Medium", confidence_factors=common_factors,
                        horizon_days=1, query=f"quant_kronos_p2c:{symbol}:{as_of_date.isoformat()}",
                        experimental=True, model_version=f"{kr.model_name}{P2C_SUFFIX}",
                        expected_return=kr.expected_return, expected_volatility=kr.expected_volatility,
                        created_at=created_at,
                    )
                    if pred_id:
                        stored_kronos += 1
                else:
                    kronos_failed += 1
                    log.debug("phase2c.kronos_skip", symbol=symbol, as_of=as_of_date.isoformat(), reason=kr.reason)

    log.info("phase2c.generated", stored_baseline=stored_baseline, stored_kronos=stored_kronos,
              kronos_failed=kronos_failed, symbols=len(symbols) - len(skipped_symbols), skipped=skipped_symbols)
    return {
        "stored_baseline": stored_baseline, "stored_kronos": stored_kronos, "kronos_failed": kronos_failed,
        "symbols_used": len(symbols) - len(skipped_symbols), "symbols_skipped": skipped_symbols,
    }


async def _due_p2c_predictions(db: AsyncSession, horizon_days: int, limit: int) -> list[dict]:
    """Deliberately NOT filtering on PredictionRecord.status here (unlike
    prediction_service.get_due_predictions, which correctly does for its
    own real use case). Every Phase 2C prediction is stored with a
    single nominal horizon_days=1 (Phase 2C's own multi-horizon design:
    one directional call, checked against realized outcomes at 1/7/30
    days — see this module's docstring), so record_evaluation() flips
    status to "complete" the moment the FIRST (horizon=1) evaluation
    lands, since 1 >= the stored horizon_days=1. That's correct,
    unmodified production behavior for a prediction whose own claimed
    horizon really is 1 — it just means status can't be used as a
    "still needs evaluating" signal for horizons 7/30 on these specific
    rows. The real gate is `not_in(already_done)` below (has THIS
    specific horizon been evaluated for THIS prediction yet), which is
    exactly right regardless of status."""
    from datetime import timedelta
    from sqlalchemy import and_
    from app.db.models.predictions import PredictionEvaluation

    cutoff = datetime.now(timezone.utc) - timedelta(days=horizon_days - 0.25)
    already_done = select(PredictionEvaluation.prediction_id).where(PredictionEvaluation.horizon_days == horizon_days)
    rows = (await db.execute(
        select(PredictionRecord)
        .where(and_(
            PredictionRecord.model_version.like(f"%{P2C_SUFFIX}"),
            PredictionRecord.created_at <= cutoff,
            PredictionRecord.id.not_in(already_done),
        ))
        .limit(limit)
    )).scalars().all()
    return [
        {"id": r.id, "source": r.source, "direction": r.direction, "prediction_type": r.prediction_type,
         "target_entities": r.target_entities or [], "confidence_score": r.confidence_score,
         "confidence_level": r.confidence_level, "horizon_days": horizon_days,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]


async def evaluate_phase2c_predictions(horizons: tuple[int, ...] = HORIZONS, limit: int = 5000, delay_sec: float = 0.2) -> dict:
    """Evaluates every Phase 2C prediction (baseline and Kronos alike)
    at each horizon in `horizons`, via the real evaluate_prediction()
    — same call Phase 2B used, same call production predictions go
    through. Sequential across horizons (not parallel) — same
    yfinance-throttling caution documented in backfill.py."""
    from app.services.prediction_evaluator import evaluate_prediction

    totals = {"evaluated": 0, "errors": 0, "due": 0}
    for horizon in horizons:
        async with AsyncSessionLocal() as db:
            due = await _due_p2c_predictions(db, horizon, limit)
        totals["due"] += len(due)
        for pred in due:
            try:
                await evaluate_prediction(pred, horizon)
                totals["evaluated"] += 1
            except Exception as exc:
                log.error("phase2c.eval_error", id=pred["id"][:8], horizon=horizon, error=str(exc)[:120])
                totals["errors"] += 1
            await asyncio.sleep(delay_sec)
        log.info("phase2c.horizon_done", horizon=horizon, due=len(due))

    log.info("phase2c.evaluated", **totals)
    return totals

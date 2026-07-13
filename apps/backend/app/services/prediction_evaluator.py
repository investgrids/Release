"""
Prediction Evaluator — compares stored predictions against actual market outcomes.

For each due prediction at each horizon (1d, 3d, 7d, 30d):
  1. Fetch price data from yfinance for the target entities
  2. Compare actual move direction & magnitude to the prediction
  3. Assign verdict: correct | partial | incorrect | inconclusive
  4. Persist result via prediction_service.record_evaluation()

Called by the daily scheduler task.
"""
from __future__ import annotations

import asyncio
import math
import structlog
from datetime import datetime, timedelta

log = structlog.get_logger(__name__)

# Thresholds for verdict classification
_CORRECT_THRESH  = 0.50   # ≥0.50% move in predicted direction → correct
_PARTIAL_THRESH  = 0.10   # ≥0.10% → partial


def _fetch_prices_sync(ticker: str, created_at_iso: str, horizon_days: int) -> dict:
    """
    Fetch (price_before, price_after) for a ticker around a prediction.
    price_before = close on or just after created_at
    price_after  = close on or just after (created_at + horizon_days)
    Returns {} on any failure.
    """
    try:
        import yfinance as yf

        created  = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00")).replace(tzinfo=None)
        start    = created - timedelta(days=7)    # buffer for weekends/holidays before
        end      = created + timedelta(days=horizon_days + 7)   # buffer after horizon

        hist = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if hist.empty or len(hist) < 2:
            return {}

        rows = []
        for ts, row in hist.iterrows():
            ts_naive = ts.replace(tzinfo=None) if hasattr(ts, "tzinfo") and ts.tzinfo else ts
            v = row["Close"]
            val = float(v.iloc[0] if hasattr(v, "iloc") else v)
            if val > 0 and not math.isnan(val):
                rows.append((ts_naive, val))

        if not rows:
            return {}

        # Price just before / at prediction time
        price_before = None
        for ts, val in rows:
            if ts >= created - timedelta(days=5):
                price_before = val
                break

        if price_before is None:
            price_before = rows[0][1]

        # Price at horizon
        target_date  = created + timedelta(days=horizon_days)
        price_after  = None
        for ts, val in rows:
            if ts >= target_date - timedelta(days=3):
                price_after = val
                break

        # Fall back to last available row
        if price_after is None and rows:
            price_after = rows[-1][1]

        if price_before is None or price_after is None:
            return {}

        move_pct = round((price_after / price_before - 1) * 100, 3)
        return {
            "price_before": round(price_before, 2),
            "price_after":  round(price_after, 2),
            "move_pct":     move_pct,
            "ticker":       ticker,
        }
    except Exception as exc:
        log.debug("evaluator.price_fail", ticker=ticker, error=str(exc)[:80])
        return {}


def _verdict(predicted_dir: str, move_pct: float) -> tuple[str, float]:
    """
    Returns (verdict, score).
    score: 1.0=correct, 0.5=partial, 0.0=incorrect
    """
    if predicted_dir == "up":
        if move_pct >=  _CORRECT_THRESH: return "correct",   1.0
        if move_pct >= -_PARTIAL_THRESH: return "partial",   0.5
        return "incorrect", 0.0

    if predicted_dir == "down":
        if move_pct <= -_CORRECT_THRESH: return "correct",   1.0
        if move_pct <=  _PARTIAL_THRESH: return "partial",   0.5
        return "incorrect", 0.0

    # sideways
    if abs(move_pct) <= 1.0: return "correct",  1.0
    if abs(move_pct) <= 2.5: return "partial",  0.5
    return "incorrect", 0.0


def _direction_label(move_pct: float) -> str:
    if move_pct >=  _CORRECT_THRESH: return "up"
    if move_pct <= -_CORRECT_THRESH: return "down"
    return "sideways"


def _resolve_ticker(entity: dict) -> str | None:
    """Resolve a yfinance ticker for an entity dict."""
    from app.services.prediction_service import SECTOR_TICKERS

    # Already has a resolved ticker
    ticker = entity.get("baseline_ticker") or entity.get("ticker") or entity.get("symbol")
    if ticker:
        return ticker

    etype = entity.get("type", "")
    name  = (entity.get("name") or "").lower()

    if etype == "sector":
        return next((v for k, v in SECTOR_TICKERS.items() if k in name), None)
    if etype == "index":
        return entity.get("ticker")  # indices already have proper tickers

    return None


async def evaluate_prediction(prediction: dict, horizon_days: int) -> None:
    """Evaluate a single prediction at a specific horizon."""
    from app.services.prediction_service import record_evaluation

    pred_id    = prediction["id"]
    direction  = prediction["direction"]
    entities   = prediction.get("target_entities", [])[:3]   # cap at 3 entities
    created_at = str(prediction["created_at"])
    loop       = asyncio.get_running_loop()

    entity_results = []
    for entity in entities:
        ticker = _resolve_ticker(entity)
        if not ticker:
            entity_results.append({"ticker": None, "verdict": "inconclusive", "score": None})
            continue

        price_data = await loop.run_in_executor(
            None, _fetch_prices_sync, ticker, created_at, horizon_days
        )
        if not price_data:
            entity_results.append({"ticker": ticker, "verdict": "inconclusive", "score": None})
            continue

        move_pct       = price_data["move_pct"]
        verd, score    = _verdict(direction, move_pct)
        entity_results.append({
            "ticker":       ticker,
            "verdict":      verd,
            "score":        score,
            "move_pct":     move_pct,
            "price_before": price_data["price_before"],
            "price_after":  price_data["price_after"],
        })

    # Aggregate across entities
    conclusive = [r for r in entity_results if r.get("score") is not None]

    if not conclusive:
        await record_evaluation(
            prediction_id=pred_id, horizon_days=horizon_days,
            verdict="inconclusive", actual_direction=None,
            actual_move_pct=None, score=0.5,
            evidence={"entities": entity_results},
            notes="No price data available",
        )
        return

    avg_score   = sum(r["score"] for r in conclusive) / len(conclusive)
    avg_move    = sum(r["move_pct"] for r in conclusive) / len(conclusive)
    final_verd  = "correct" if avg_score >= 0.75 else "partial" if avg_score >= 0.25 else "incorrect"

    await record_evaluation(
        prediction_id=pred_id,
        horizon_days=horizon_days,
        verdict=final_verd,
        actual_direction=_direction_label(avg_move),
        actual_move_pct=round(avg_move, 2),
        score=round(avg_score, 3),
        evidence={"entities": entity_results, "avg_move_pct": round(avg_move, 2)},
        notes=f"{len(conclusive)}/{len(entity_results)} entities evaluated",
    )


async def run_evaluation_cycle() -> dict:
    """
    Full evaluation cycle for all horizons (1d, 3d, 7d, 30d).
    Rate-limited to avoid hammering yfinance. Called by scheduler.
    """
    from app.services.prediction_service import get_due_predictions, recompute_calibration

    stats = {"horizon_counts": {}, "evaluated": 0, "inconclusive": 0, "errors": 0}

    for horizon in [1, 3, 7, 30]:
        due = await get_due_predictions(horizon_days=horizon, limit=50)
        stats["horizon_counts"][horizon] = len(due)

        for pred in due:
            try:
                await evaluate_prediction(pred, horizon)
                stats["evaluated"] += 1
                await asyncio.sleep(0.3)   # rate-limit yfinance
            except Exception as exc:
                log.error("evaluator.pred_error", id=pred["id"][:8], error=str(exc)[:80])
                stats["errors"] += 1

    if stats["evaluated"] > 0:
        await recompute_calibration()

    log.info("evaluator.cycle_done", **{k: v for k, v in stats.items() if k != "horizon_counts"},
             horizons=stats["horizon_counts"])
    return stats

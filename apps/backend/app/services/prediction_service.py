"""
Prediction persistence and calibration service.

Three responsibilities:
  1. store_prediction()       — persist a new prediction with baseline prices
  2. get_due_predictions()    — fetch predictions ready for evaluation at a horizon
  3. record_evaluation()      — persist an evaluation result + mark prediction status
  4. recompute_calibration()  — rebuild CalibrationStat from all completed evaluations
  5. get_calibration_data()   — return calibration factors (in-memory cached, 1h TTL)
"""
from __future__ import annotations

import asyncio
import time
import structlog
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.predictions import PredictionRecord, PredictionEvaluation, CalibrationStat

log = structlog.get_logger(__name__)

# Sector name fragments → yfinance tickers for evaluation
SECTOR_TICKERS: dict[str, str] = {
    "banking":        "^NSEBANK",
    "bank":           "^NSEBANK",
    "nbfc":           "^CNXFINANCE",
    "it":             "^CNXIT",
    "technology":     "^CNXIT",
    "software":       "^CNXIT",
    "pharma":         "^CNXPHARMA",
    "healthcare":     "^CNXPHARMA",
    "fmcg":           "^CNXFMCG",
    "consumer":       "^CNXFMCG",
    "staples":        "^CNXFMCG",
    "auto":           "^CNXAUTO",
    "automobile":     "^CNXAUTO",
    "metal":          "^CNXMETAL",
    "steel":          "^CNXMETAL",
    "realty":         "^CNXREALTY",
    "real estate":    "^CNXREALTY",
    "energy":         "^CNXENERGY",
    "oil":            "^CNXENERGY",
    "infra":          "^CNXINFRA",
    "infrastructure": "^CNXINFRA",
    "media":          "^CNXMEDIA",
    "finance":        "^CNXFINANCE",
    "financials":     "^CNXFINANCE",
    "psu":            "^CNXPSE",
    "defence":        "^CNXPSE",
    "midcap":         "^NSEMDCP50",
    "smallcap":       "^CNXSC",
}

# Expected accuracy per confidence level (used to compute calibration_factor)
_EXPECTED_ACCURACY: dict[str, float] = {
    "Low":       0.35,
    "Medium":    0.55,
    "High":      0.72,
    "Very High": 0.87,
}

# In-memory calibration cache (rebuilt by recompute_calibration)
_CAL_CACHE: dict[str, dict] = {}
_CAL_CACHE_AT: float        = 0.0
_CAL_CACHE_TTL: float       = 3600.0   # refresh from DB at most every 1 hour


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_price_sync(ticker: str) -> float | None:
    """Fetch latest close price via yfinance. Runs in executor."""
    try:
        import math
        import yfinance as yf
        hist = yf.download(ticker, period="3d", interval="1d", progress=False, auto_adjust=True, timeout=10)
        if hist.empty:
            return None
        close = hist["Close"].iloc[-1]
        v = float(close.iloc[0] if hasattr(close, "iloc") else close)
        return round(v, 2) if v > 0 and not math.isnan(v) else None
    except Exception:
        return None


async def _baseline_price(ticker: str) -> float | None:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _fetch_price_sync, ticker)
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

async def store_prediction(
    *,
    source: str,
    prediction_text: str,
    direction: str,
    prediction_type: str,
    target_entities: list[dict],
    confidence_score: float,
    confidence_level: str,
    confidence_factors: dict | None = None,
    horizon_days: int = 7,
    query: str | None = None,
    headline: str | None = None,
) -> str | None:
    """Persist a prediction. Fetches baseline prices for entities without one."""
    pred_id = str(uuid4())
    now     = datetime.now(timezone.utc)

    # Enrich entities with baseline prices in parallel
    enriched: list[dict] = []
    for ent in target_entities:
        e = dict(ent)
        if e.get("baseline_price") is None:
            raw_ticker = e.get("baseline_ticker") or e.get("ticker") or e.get("symbol") or ""
            if raw_ticker:
                # Add .NS suffix for plain company symbols
                if e.get("type") == "company" and not any(
                    raw_ticker.endswith(s) for s in [".NS", ".BO", "=X", "=F", "^"]
                ):
                    raw_ticker = f"{raw_ticker}.NS"
                price = await _baseline_price(raw_ticker)
                e["baseline_price"]  = price
                e["baseline_ticker"] = raw_ticker
        enriched.append(e)

    try:
        async with AsyncSessionLocal() as db:
            db.add(PredictionRecord(
                id=pred_id,
                source=source,
                query=(query or "")[:500] if query else None,
                headline=(headline or "")[:500] if headline else None,
                prediction_text=prediction_text[:1000],
                direction=direction,
                prediction_type=prediction_type,
                target_entities=enriched,
                confidence_score=round(float(confidence_score), 1),
                confidence_level=confidence_level,
                confidence_factors=confidence_factors,
                horizon_days=horizon_days,
                status="pending",
                evaluate_by=now + timedelta(days=horizon_days),
            ))
            await db.commit()
        log.info("prediction.stored", id=pred_id[:8], source=source,
                 type=prediction_type, dir=direction,
                 conf=confidence_score, horizon=horizon_days)
        return pred_id
    except Exception as exc:
        log.error("prediction.store_failed", error=str(exc))
        return None


async def get_due_predictions(horizon_days: int, limit: int = 100) -> list[dict]:
    """Return predictions due for evaluation at the given horizon (not yet evaluated there)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=horizon_days - 0.25)
    try:
        async with AsyncSessionLocal() as db:
            already_done = select(PredictionEvaluation.prediction_id).where(
                PredictionEvaluation.horizon_days == horizon_days
            )
            stmt = (
                select(PredictionRecord)
                .where(
                    and_(
                        PredictionRecord.created_at <= cutoff,
                        PredictionRecord.status.in_(["pending", "evaluating"]),
                        PredictionRecord.id.not_in(already_done),
                    )
                )
                .limit(limit)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [
                {
                    "id":               r.id,
                    "source":           r.source,
                    "direction":        r.direction,
                    "prediction_type":  r.prediction_type,
                    "target_entities":  r.target_entities or [],
                    "confidence_score": r.confidence_score,
                    "confidence_level": r.confidence_level,
                    "horizon_days":     horizon_days,
                    "created_at":       r.created_at.isoformat(),
                }
                for r in rows
            ]
    except Exception as exc:
        log.error("prediction.get_due_failed", horizon=horizon_days, error=str(exc))
        return []


async def record_evaluation(
    *,
    prediction_id: str,
    horizon_days: int,
    verdict: str,
    actual_direction: str | None,
    actual_move_pct: float | None,
    score: float,
    evidence: dict,
    notes: str,
) -> None:
    """Persist an evaluation result and update the prediction's status."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(PredictionEvaluation(
                id=str(uuid4()),
                prediction_id=prediction_id,
                horizon_days=horizon_days,
                verdict=verdict,
                actual_direction=actual_direction,
                actual_move_pct=actual_move_pct,
                score=round(float(score), 3),
                evidence=evidence,
                notes=notes,
            ))
            # Update prediction status
            pred = (await db.execute(
                select(PredictionRecord).where(PredictionRecord.id == prediction_id)
            )).scalar_one_or_none()
            if pred:
                if horizon_days >= pred.horizon_days:
                    pred.status     = "complete"
                    pred.completed_at = datetime.now(timezone.utc)
                else:
                    pred.status = "evaluating"
            await db.commit()
        log.info("prediction.eval_recorded", id=prediction_id[:8],
                 horizon=horizon_days, verdict=verdict, score=round(score, 2))
    except Exception as exc:
        log.error("prediction.eval_record_failed", error=str(exc))


async def recompute_calibration() -> None:
    """
    Rebuild CalibrationStat from all completed predictions.
    Uses the highest-horizon evaluation for each prediction as the ground truth.
    Called after each evaluation cycle.
    """
    global _CAL_CACHE, _CAL_CACHE_AT

    try:
        async with AsyncSessionLocal() as db:
            for level in ["Low", "Medium", "High", "Very High"]:
                preds = (await db.execute(
                    select(PredictionRecord).where(
                        and_(
                            PredictionRecord.confidence_level == level,
                            PredictionRecord.status == "complete",
                        )
                    )
                )).scalars().all()
                if not preds:
                    continue

                pred_ids = [p.id for p in preds]
                avg_conf = sum(p.confidence_score for p in preds) / len(preds)

                all_evals = (await db.execute(
                    select(PredictionEvaluation).where(
                        PredictionEvaluation.prediction_id.in_(pred_ids)
                    )
                )).scalars().all()

                # Take the highest-horizon evaluation per prediction
                best: dict[str, PredictionEvaluation] = {}
                for ev in all_evals:
                    prev = best.get(ev.prediction_id)
                    if prev is None or ev.horizon_days > prev.horizon_days:
                        best[ev.prediction_id] = ev

                evals = list(best.values())
                if not evals:
                    continue

                conclusive = [e for e in evals if e.verdict != "inconclusive"]
                if not conclusive:
                    continue

                correct  = sum(1 for e in conclusive if e.verdict == "correct")
                partial  = sum(1 for e in conclusive if e.verdict == "partial")
                wrong    = sum(1 for e in conclusive if e.verdict == "incorrect")
                inconc   = len(evals) - len(conclusive)
                accuracy = (correct + 0.5 * partial) / len(conclusive)

                expected = _EXPECTED_ACCURACY.get(level, 0.5)
                calib_f  = min(2.0, max(0.3, accuracy / expected)) if expected > 0 else 1.0

                existing = (await db.execute(
                    select(CalibrationStat).where(CalibrationStat.confidence_level == level)
                )).scalar_one_or_none()

                data = dict(
                    total_predictions    = len(evals),
                    correct_count        = correct,
                    partial_count        = partial,
                    incorrect_count      = wrong,
                    inconclusive_count   = inconc,
                    accuracy_rate        = round(accuracy, 4),
                    avg_confidence_score = round(avg_conf, 1),
                    calibration_factor   = round(calib_f, 4),
                    last_updated         = datetime.now(timezone.utc),
                )
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                else:
                    db.add(CalibrationStat(confidence_level=level, **data))

            await db.commit()

        # Invalidate in-memory cache so next call reloads from DB
        _CAL_CACHE    = {}
        _CAL_CACHE_AT = 0.0
        log.info("prediction.calibration_recomputed")
    except Exception as exc:
        log.error("prediction.calibration_failed", error=str(exc))


async def get_calibration_data() -> dict[str, dict]:
    """
    Return calibration stats by confidence level (memory-cached, 1-hour TTL).
    Returns {} if no data is available yet.
    """
    global _CAL_CACHE, _CAL_CACHE_AT
    if _CAL_CACHE and (time.time() - _CAL_CACHE_AT) < _CAL_CACHE_TTL:
        return _CAL_CACHE
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(CalibrationStat))).scalars().all()
        _CAL_CACHE = {
            r.confidence_level: {
                "total":              r.total_predictions,
                "correct":            r.correct_count,
                "partial":            r.partial_count,
                "incorrect":          r.incorrect_count,
                "inconclusive":       r.inconclusive_count,
                "accuracy_rate":      r.accuracy_rate,
                "calibration_factor": r.calibration_factor,
                "avg_score":          r.avg_confidence_score,
                "last_updated":       r.last_updated.isoformat() if r.last_updated else None,
            }
            for r in rows
        }
        _CAL_CACHE_AT = time.time()
        return _CAL_CACHE
    except Exception:
        return {}


async def get_stats() -> dict:
    """Overall accuracy statistics for the learning engine dashboard."""
    try:
        from sqlalchemy import func
        async with AsyncSessionLocal() as db:
            total    = (await db.execute(
                select(func.count()).select_from(PredictionRecord)
            )).scalar() or 0
            complete = (await db.execute(
                select(func.count()).select_from(PredictionRecord)
                .where(PredictionRecord.status == "complete")
            )).scalar() or 0

            verdict_rows = (await db.execute(
                select(PredictionEvaluation.verdict, func.count().label("n"))
                .group_by(PredictionEvaluation.verdict)
            )).all()
            verdicts = {r.verdict: r.n for r in verdict_rows}

            cal_rows = (await db.execute(select(CalibrationStat))).scalars().all()
            calibration = [
                {
                    "level":              r.confidence_level,
                    "total":              r.total_predictions,
                    "accuracy_rate":      round(r.accuracy_rate * 100, 1),
                    "calibration_factor": r.calibration_factor,
                    "last_updated":       r.last_updated.isoformat() if r.last_updated else None,
                }
                for r in sorted(cal_rows, key=lambda x: ["Low","Medium","High","Very High"].index(x.confidence_level) if x.confidence_level in ["Low","Medium","High","Very High"] else 99)
            ]

        conclusive = verdicts.get("correct", 0) + verdicts.get("partial", 0) + verdicts.get("incorrect", 0)
        accuracy   = (
            (verdicts.get("correct", 0) + 0.5 * verdicts.get("partial", 0)) / conclusive
            if conclusive > 0 else None
        )
        return {
            "total_predictions":    total,
            "complete_predictions": complete,
            "pending_predictions":  total - complete,
            "verdicts":             verdicts,
            "overall_accuracy":     round(accuracy * 100, 1) if accuracy is not None else None,
            "calibration":          calibration,
        }
    except Exception as exc:
        log.error("prediction.stats_failed", error=str(exc))
        return {"total_predictions": 0, "overall_accuracy": None, "calibration": []}

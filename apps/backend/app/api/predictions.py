"""
Predictions API — learning engine stats and prediction history.
"""
from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, BackgroundTasks

from app.db.session import get_db
from app.db.models.predictions import PredictionRecord, PredictionEvaluation
from app.services.prediction_service import get_stats

router = APIRouter()


@router.get("/stats")
async def prediction_stats():
    """Overall accuracy statistics for the learning engine."""
    return await get_stats()


@router.get("/recent")
async def recent_predictions(
    limit: int = 20,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Recent predictions with their evaluations, newest first."""
    stmt = select(PredictionRecord).order_by(desc(PredictionRecord.created_at))
    if source:
        stmt = stmt.where(PredictionRecord.source == source)
    stmt = stmt.limit(min(limit, 100))

    preds = (await db.execute(stmt)).scalars().all()
    result = []
    for p in preds:
        evals = (await db.execute(
            select(PredictionEvaluation)
            .where(PredictionEvaluation.prediction_id == p.id)
            .order_by(PredictionEvaluation.horizon_days)
        )).scalars().all()

        result.append({
            "id":               p.id,
            "source":           p.source,
            "prediction_text":  p.prediction_text,
            "direction":        p.direction,
            "prediction_type":  p.prediction_type,
            "confidence_score": p.confidence_score,
            "confidence_level": p.confidence_level,
            "horizon_days":     p.horizon_days,
            "status":           p.status,
            "created_at":       p.created_at.isoformat(),
            "target_entities":  [
                {k: v for k, v in e.items() if k not in ("baseline_price", "baseline_ticker")}
                for e in (p.target_entities or [])
            ],
            "evaluations": [
                {
                    "horizon_days":    e.horizon_days,
                    "verdict":         e.verdict,
                    "actual_move_pct": e.actual_move_pct,
                    "actual_direction":e.actual_direction,
                    "score":           e.score,
                    "evaluated_at":    e.evaluated_at.isoformat(),
                    "notes":           e.notes,
                }
                for e in evals
            ],
        })
    return result


@router.post("/evaluate")
async def trigger_evaluation(background_tasks: BackgroundTasks):
    """
    Manually trigger an evaluation cycle (admin / debug).
    Runs in the background so the request returns immediately.
    """
    from app.services.prediction_evaluator import run_evaluation_cycle
    background_tasks.add_task(run_evaluation_cycle)
    return {"status": "evaluation_triggered"}

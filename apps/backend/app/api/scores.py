"""
Score History + Audit API.

  GET /api/scores/{entity_type}/{entity_id}/history  -> Score History,
      Evidence Timeline, Confidence Evolution (all three are the same
      underlying data — a chronological list of ScoreUpdates — presented
      differently on the frontend: score deltas, discrete events, or a
      confidence line chart).

  GET /api/scores/formula/{model}  -> Intelligence Audit Panel ("how was
      this calculated" — the formula's weight distribution).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services import scoring_engine
from app.services.score_history_service import get_score_history

router = APIRouter()


@router.get("/formula/{model}")
async def formula_weights(model: str, version: Optional[str] = Query(None)):
    """The formula's intended weight distribution for one scoring model."""
    try:
        return scoring_engine.get_formula_weights(model, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{entity_type}/{entity_id}/history")
async def entity_score_history(
    entity_type: str,
    entity_id: str,
    model: Optional[str] = Query(None, description="Filter to one model, e.g. event_impact"),
    limit: int = Query(50, le=200),
):
    """Chronological score history for one entity."""
    history = await get_score_history(entity_type, entity_id, model=model, limit=limit)
    return {"entity_type": entity_type, "entity_id": entity_id, "count": len(history), "history": history}

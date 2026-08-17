"""
AI Search -> Prediction Memory / Calibration — shared by V2
(ai_search_service.py) and V3 (postprocess.py/pipeline.py).

Ported verbatim from V2's own `_map_horizon`/`_store_search_predictions`/
inline calibration block, which V2 already used on every completed
search. V3 (the primary user-facing pipeline) never called any of this —
confirmed live: it neither wrote a PredictionRecord nor applied the
historical calibration factor, meaning the pipeline actually receiving
real user traffic had been silently outside the
prediction->outcome->calibration->confidence feedback loop V2
participates in. This module is the fix, moved to one shared place so
V2 and V3 can never drift into two different calibration semantics
again — both call this, neither keeps a local copy.

Explicitly NOT a new algorithm: same thresholds, same horizon mapping,
same entity-extraction shape, same experimental/production semantics
(store_prediction's own `experimental` default of False is unchanged —
these are real production predictions, exactly as V2's always were).
"""
from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger(__name__)


def map_horizon(horizon_str: str) -> int:
    """Map investment_verdict.horizon text to calendar days."""
    h = (horizon_str or "").lower()
    if "intraday" in h or ("1" in h and "day" in h):    return 1
    if "week" in h or "3" in h and "day" in h:          return 3
    if "1 month" in h or "short" in h and "term" in h:  return 7
    return 30  # default: 30-day horizon for longer-term predictions


def apply_calibration(conf_result: Any, cal_data: dict) -> None:
    """Mutates conf_result.total_score/.level/.reasons in place — only
    when >= 10 verified predictions exist for that confidence level and
    the calibration factor is within the same sane bounds V2 always
    used (0.4-1.8). No-op (leaves conf_result untouched) otherwise —
    same "don't calibrate on thin data" guard V2 has always had."""
    from app.services.confidence_service import _THRESHOLDS

    if not cal_data or conf_result is None:
        return
    lvl_cal = cal_data.get(conf_result.level, {})
    cal_factor = float(lvl_cal.get("calibration_factor", 1.0))
    cal_n = int(lvl_cal.get("total", 0))
    if not (cal_n >= 10 and 0.4 <= cal_factor <= 1.8):
        return
    new_score = min(100.0, max(0.0, round(conf_result.total_score * cal_factor, 1)))
    new_level = next(lbl for thr, lbl in _THRESHOLDS if new_score >= thr)
    acc_pct = round(lvl_cal.get("accuracy_rate", 0.5) * 100)
    conf_result.total_score = new_score
    conf_result.level = new_level
    conf_result.reasons.append(
        f"Calibrated from {cal_n} verified predictions ({acc_pct}% historical accuracy)"
    )


async def get_search_calibration() -> dict:
    """One shared entry point for both pipelines to fetch calibration
    data — trivial passthrough today, but means a future change to how
    calibration is sourced only has one call site to update, not two."""
    try:
        from app.services.prediction_service import get_calibration_data
        return await get_calibration_data()
    except Exception:
        return {}


async def store_search_predictions(
    *, result: dict, confidence_score: float, confidence_level: str, confidence_breakdown: dict,
) -> None:
    """Extract and persist predictions from a completed AI Search result
    — verbatim V2 logic, decoupled from V2's specific ConfidenceResult
    object so V3 (which has its own differently-shaped confidence
    breakdown dict) can call this identically. Fire-and-forget by
    convention at the call site (asyncio.create_task), never awaited
    inline — a prediction-store failure must never affect the answer
    already being returned to the user."""
    try:
        from app.services.prediction_service import store_prediction

        query = result.get("query", "")
        verdict = result.get("investment_verdict") or {}
        answer = result.get("answer") or {}
        companies_list = result.get("companies") or []

        direction = (verdict.get("direction") or answer.get("sentiment") or "sideways").lower()
        if direction == "bullish":  direction = "up"
        if direction == "bearish":  direction = "down"
        if direction not in ("up", "down"): direction = "sideways"

        horizon = map_horizon(verdict.get("horizon", ""))

        # 1) Overall market direction prediction (top company as primary entity)
        top_cos = [c for c in companies_list[:2] if c.get("symbol")]
        if top_cos or verdict.get("direction"):
            entities = [
                {
                    "type":   "company",
                    "symbol": c.get("symbol", ""),
                    "name":   c.get("name", ""),
                    "ticker": c.get("symbol", ""),
                }
                for c in top_cos[:2]
            ]
            pred_text = (
                f"{direction.upper()} on {', '.join(c.get('symbol','') for c in top_cos) or 'market'} "
                f"— {answer.get('immediate_impact', '')[:120]}"
            )
            await store_prediction(
                source="ai_search",
                prediction_text=pred_text,
                direction=direction,
                prediction_type="overall",
                target_entities=entities,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                confidence_factors=confidence_breakdown,
                horizon_days=horizon,
                query=query[:400],
            )

        # 2) Individual company predictions (beneficiary = up, at_risk = down)
        for company in companies_list[:3]:
            sym = company.get("symbol", "").strip()
            if not sym:
                continue
            impact = (company.get("impact_type") or "neutral").lower()
            co_dir = "up" if impact == "beneficiary" else "down" if impact == "at_risk" else "sideways"
            co_conf = min(100, max(0, float(company.get("confidence", confidence_score) or confidence_score)))
            await store_prediction(
                source="ai_search",
                prediction_text=f"{co_dir.upper()} on {sym}: {company.get('reason', '')[:120]}",
                direction=co_dir,
                prediction_type="company",
                target_entities=[{
                    "type":   "company",
                    "symbol": sym,
                    "name":   company.get("name", sym),
                    "ticker": sym,
                }],
                confidence_score=co_conf,
                confidence_level=confidence_level,
                confidence_factors=confidence_breakdown,
                horizon_days=horizon,
                query=query[:400],
            )
    except Exception as exc:
        log.debug("prediction.store_search_fail", error=str(exc)[:80])

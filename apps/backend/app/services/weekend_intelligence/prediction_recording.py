"""
Weekend Intelligence prediction recording — brief §23-§26.

Fully reuses the existing prediction-tracking framework
(app.services.prediction_service.store_prediction, PredictionRecord) —
no new table, no new evaluation code. Once a record exists here with
source="weekend_intelligence", the ALREADY-SCHEDULED
job_evaluate_predictions / prediction_evaluator.run_evaluation_cycle()
picks it up automatically at horizon_days=1, using the exact same
yfinance-price-comparison logic every other prediction source already
goes through (brief §32/§33: "FULL REUSE").

WHEN this is called matters for evaluation correctness (see report §I):
called from the Monday pre-market flow (market.py's opening-prediction
route, when a target-session-matching WeekendContext is actually being
used), NOT from every Sat/Sun checkpoint. store_prediction() stamps
created_at as `now()` with no override — recording at checkpoint time
would stamp a Saturday/Sunday created_at, and the existing evaluator's
window logic (built assuming predictions are made on trading days)
would then resolve horizon_days=1 against the wrong close. Recording on
Monday morning, when the context is actually consumed, keeps created_at
a real weekday and the existing 1-day-horizon evaluation window correct
— unmodified, no new evaluator logic needed.

KNOWN V1 CONSEQUENCE, accepted deliberately, not fixed here (per
explicit review decision): recording is currently REQUEST-DRIVEN, not
scheduled. It only happens inside GET /api/market/opening-prediction,
triggered by a real caller consuming a target-session-matching
WeekendContext. If nobody requests that endpoint during the window a
snapshot's target_trading_date is live and valid, no
source="weekend_intelligence" PredictionRecord is ever created for that
weekend — Weekend Intelligence's own synthesis (the WeekendIntelligenceSnapshot
itself) is completely unaffected either way, only the downstream
learning-loop entry is missed. A scheduled "finalize Monday's Weekend
Intelligence predictions" job would remove this dependency on route
traffic; deliberately not built in Phase 1C (see final report — this is
a real product gap for later evaluation-pipeline work, not a Phase 1C
bug).

WHAT gets recorded (brief §24 — not every evidence item, not confidence
warnings, not neutral/mixed signals with no clear direction):
  MARKET:  overall_bias, if directional (brief §19: never for
           insufficient_evidence or a neutral/mixed bias)
  SECTOR:  top sector signals with a resolvable index ticker (brief §30
           — SECTOR_TICKERS, reused from prediction_service.py, never a
           fabricated single-stock proxy) AND a clear positive/negative
           direction
  COMPANY: top company signals in a clearly directional state
           (high_conviction_watch/positive_watch -> up,
           risk_watch -> down); mixed/monitor are skipped — no clear
           direction to evaluate

Idempotency (brief §39 "rerunning is idempotent"): no schema change —
reuses PredictionRecord.query (an existing free-text field) as a stable
dedup key (f"weekend_intelligence:{snapshot_id}:{type}:{target_id}"),
checked before every insert. This is what brief §45 means by "explain
why existing fields cannot carry X" — here they can, so no new column.

Snapshot versioning (brief §26): only ever call this with the CURRENT
snapshot's WeekendContext — superseded versions are never independently
recorded (get_weekend_context_for_session only ever returns the current
row, so this is enforced by construction, not a separate check here).
"""
from __future__ import annotations

from app.services.weekend_intelligence.company_synthesis import HIGH_CONVICTION_WATCH, POSITIVE_WATCH, RISK_WATCH
from app.services.weekend_intelligence.context import WeekendContext

_HORIZON_DAYS = 1

_BIAS_TO_UP_DOWN = {
    "strong_positive": "up", "positive": "up",
    "strong_negative": "down", "negative": "down",
}
_COMPANY_STATE_TO_UP_DOWN = {
    HIGH_CONVICTION_WATCH: "up", POSITIVE_WATCH: "up", RISK_WATCH: "down",
}
_SIGNAL_DIRECTION_TO_UP_DOWN = {"positive": "up", "negative": "down"}


def _confidence_level(score: float) -> str:
    """Named, explicit 4-bucket mapping (matching the existing
    Low/Medium/High/Very High vocabulary prediction_service.py already
    uses for _EXPECTED_ACCURACY/calibration) — not hidden, not a new
    5th bucket invented for this source."""
    if score < 40:
        return "Low"
    if score < 60:
        return "Medium"
    if score < 80:
        return "High"
    return "Very High"


async def _already_recorded(query_marker: str) -> bool:
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.predictions import PredictionRecord

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(PredictionRecord.id).where(PredictionRecord.query == query_marker).limit(1)
        )).scalar_one_or_none()
    return existing is not None


async def record_weekend_intelligence_predictions(weekend_context: WeekendContext) -> list[str]:
    """Returns the list of newly-created PredictionRecord ids (empty if
    nothing was recordable, or everything was already recorded for this
    snapshot — safe to call more than once per Monday, per brief §39)."""
    import structlog
    from app.services.prediction_service import SECTOR_TICKERS, store_prediction

    log = structlog.get_logger(__name__)

    if weekend_context.status == "insufficient_evidence":
        log.info("weekend_prediction.skipped", reason="insufficient_evidence",
                 target_trading_date=weekend_context.target_trading_date)
        return []

    created: list[str] = []
    snapshot_ref = f"{weekend_context.snapshot_id}:v{weekend_context.snapshot_version}"

    # ── MARKET ───────────────────────────────────────────────────────────
    market_direction = _BIAS_TO_UP_DOWN.get(weekend_context.overall_bias)
    if market_direction:
        marker = f"weekend_intelligence:{weekend_context.snapshot_id}:overall:NIFTY"
        if not await _already_recorded(marker):
            pred_id = await store_prediction(
                source="weekend_intelligence",
                prediction_text=(
                    f"Weekend Intelligence overall bias: {weekend_context.overall_bias} "
                    f"for {weekend_context.target_trading_date} (snapshot {snapshot_ref})"
                ),
                direction=market_direction,
                prediction_type="overall",
                target_entities=[{"type": "index", "ticker": "^NSEI", "name": "NIFTY"}],
                confidence_score=weekend_context.production_confidence,
                confidence_level=_confidence_level(weekend_context.production_confidence),
                confidence_factors={"source": "weekend_intelligence", "snapshot_ref": snapshot_ref,
                                     "status": weekend_context.status},
                horizon_days=_HORIZON_DAYS,
                query=marker,
                headline=f"Weekend Intelligence: {weekend_context.overall_bias} bias into {weekend_context.target_trading_date}",
            )
            if pred_id:
                created.append(pred_id)

    # ── SECTOR ───────────────────────────────────────────────────────────
    for sig in weekend_context.top_sector_signals:
        direction = _SIGNAL_DIRECTION_TO_UP_DOWN.get(sig.direction)
        if not direction:
            continue  # mixed/neutral — no clear direction to evaluate (brief §24)
        ticker = next((v for k, v in SECTOR_TICKERS.items() if k in sig.id.lower()), None)
        if not ticker:
            continue  # no reliable index proxy — do not fabricate (brief §30)
        marker = f"weekend_intelligence:{weekend_context.snapshot_id}:sector:{sig.id}"
        if await _already_recorded(marker):
            continue
        pred_id = await store_prediction(
            source="weekend_intelligence",
            prediction_text=f"Weekend Intelligence sector signal: {sig.id} ({sig.direction}, {sig.evidence_count} developments)",
            direction=direction,
            prediction_type="sector",
            target_entities=[{"type": "sector", "name": sig.id, "ticker": ticker}],
            confidence_score=sig.confidence * 100 if sig.confidence <= 1.0 else sig.confidence,
            confidence_level=_confidence_level(sig.confidence * 100 if sig.confidence <= 1.0 else sig.confidence),
            confidence_factors={"source": "weekend_intelligence", "snapshot_ref": snapshot_ref,
                                 "evidence_count": sig.evidence_count},
            horizon_days=_HORIZON_DAYS,
            query=marker,
            headline=f"Weekend Intelligence: {sig.id} sector {sig.direction}",
        )
        if pred_id:
            created.append(pred_id)

    # ── COMPANY ──────────────────────────────────────────────────────────
    # weekend_context.top_company_signals stores SectorSignal-shaped refs
    # (id/direction/confidence/evidence_count) built from
    # WeekendIntelligenceSnapshot.top_company_refs — `direction` there is
    # actually the company's canonical STATE string (high_conviction_watch
    # etc, see aggregator.py::_top_company_refs), not positive/negative.
    for sig in weekend_context.top_company_signals:
        direction = _COMPANY_STATE_TO_UP_DOWN.get(sig.direction)
        if not direction:
            continue  # mixed/monitor — no clear direction (brief §24)
        marker = f"weekend_intelligence:{weekend_context.snapshot_id}:company:{sig.id}"
        if await _already_recorded(marker):
            continue
        pred_id = await store_prediction(
            source="weekend_intelligence",
            prediction_text=f"Weekend Intelligence company signal: {sig.id} ({sig.direction}, {sig.evidence_count} developments)",
            direction=direction,
            prediction_type="company",
            target_entities=[{"type": "company", "symbol": sig.id, "name": sig.id}],
            confidence_score=sig.confidence * 100 if sig.confidence <= 1.0 else sig.confidence,
            confidence_level=_confidence_level(sig.confidence * 100 if sig.confidence <= 1.0 else sig.confidence),
            confidence_factors={"source": "weekend_intelligence", "snapshot_ref": snapshot_ref,
                                 "evidence_count": sig.evidence_count, "state": sig.direction},
            horizon_days=_HORIZON_DAYS,
            query=marker,
            headline=f"Weekend Intelligence: {sig.id} {sig.direction.replace('_', ' ')}",
        )
        if pred_id:
            created.append(pred_id)

    log.info(
        "weekend_prediction.recorded", target_trading_date=weekend_context.target_trading_date,
        snapshot_id=weekend_context.snapshot_id, created_count=len(created),
    )
    return created

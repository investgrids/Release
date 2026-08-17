"""
Development -> Prediction Memory — Phase 6C V1.

Fully reuses the existing prediction-tracking framework
(app.services.prediction_service.store_prediction, PredictionRecord,
the already-scheduled job_evaluate_predictions/prediction_evaluator) —
no new table, no new evaluator, no new scheduler. Once a record exists
here with source="development_memory", the existing evaluation cycle
picks it up automatically at horizon_days=7, using the exact same
yfinance-price-comparison logic every other prediction source already
goes through. Mirrors app/services/weekend_intelligence/prediction_recording.py's
shape closely — that module is the direct precedent for "a synthesis
system feeds this pipeline."

experimental=True (shadow mode) for this entire V1: turning
Development.current_direction into an "up/down in 7 trading days" claim
is a NEW predictive use of that interpretation — unlike Weekend
Intelligence's "next trading session" framing, which was already a
predictive contract from day one. Production CalibrationStat already
feeds back into real confidence scoring elsewhere in the app, so this
mapping earns that trust with evaluated shadow data first. Promotion to
experimental=False is a later, explicit decision — not automatic, and
not part of this module.

is_prediction_worthy() is deliberately STRICTER than 6B's
is_graph_worthy() (reused here as the floor, not duplicated): a graph
node means "worth remembering," a prediction means "we are making a
measurable directional claim." Requires ALL of: graph-worthy, a clear
positive/negative direction (never mixed/neutral), confidence above the
existing Low bucket (reuses weekend_intelligence's own _confidence_level
thresholds, not an invented cutoff), AND single-company only.

The single-company restriction is this module's one real simplification
of the "never apply a Development-level direction indiscriminately to
every linked company" rule: verifying genuine per-company agreement for
a multi-company Development (e.g. an import-duty Development where
Company A benefits and Company B is hurt) would need per-company
evidence attribution that DevelopmentEvidence doesn't currently store
(only the rolled-up Development.companies list does). Restricting to
single-company Developments satisfies the rule trivially — there is
only one target, so there is nothing to spray indiscriminately across —
rather than attempting the harder multi-company case now.

Idempotency: reuses PredictionRecord.query as a stable dedup key
(f"development:{id}:7d:v1:{target}"), exactly like weekend_intelligence's
own f"weekend_intelligence:{snapshot_id}:...". Deliberately does NOT
include current_direction in the key — a Development's direction
flipping later must not produce a second overlapping prediction; the
first qualified prediction is preserved as "what Market Ripple believed
when this Development became prediction-worthy." A revision concept is
an explicit later decision, not this module's job.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.db.models.predictions import PredictionRecord
from app.services.development_memory.graph_link import is_graph_worthy
from app.services.weekend_intelligence.prediction_recording import _confidence_level

HORIZON_DAYS = 7  # one of the evaluator's own cron'd horizons (1/3/7/30) — see prediction_evaluator.run_evaluation_cycle
_DIRECTION_TO_UP_DOWN = {"positive": "up", "negative": "down"}


async def is_prediction_worthy(db: AsyncSession, dev: Development) -> bool:
    if not await is_graph_worthy(db, dev):
        return False
    if dev.current_direction not in _DIRECTION_TO_UP_DOWN:
        return False
    if not dev.companies or len(dev.companies) != 1:
        return False  # V1: single-company only — see module docstring
    confidence_pct = (dev.current_confidence or 0.0) * 100
    return _confidence_level(confidence_pct) != "Low"


async def _already_recorded(db: AsyncSession, query_marker: str) -> bool:
    existing = (await db.execute(
        select(PredictionRecord.id).where(PredictionRecord.query == query_marker).limit(1)
    )).scalar_one_or_none()
    await db.commit()  # DO NOT REMOVE — store_prediction() opens its own AsyncSessionLocal()/commit; see graph_link.py's module docstring for why an open read transaction here causes "database is locked"
    return existing is not None


async def record_development_prediction(db: AsyncSession, dev: Development) -> str | None:
    """Returns the new PredictionRecord id, or None if not created (not
    prediction-worthy, or already recorded for this Development x
    target). Snapshots `dev` fields to locals up front — same
    expire_on_commit reasoning as graph_link.link_development_to_graph()."""
    dev_id = dev.id
    canonical_title = dev.canonical_title
    companies = list(dev.companies or [])
    direction_word = dev.current_direction
    confidence = dev.current_confidence
    evidence_count = dev.evidence_count
    impact_tier = dev.formation_impact_tier

    if not await is_prediction_worthy(db, dev):
        return None

    target = companies[0]
    marker = f"development:{dev_id}:7d:v1:{target}"
    if await _already_recorded(db, marker):
        return None

    from app.services.prediction_service import store_prediction

    up_down = _DIRECTION_TO_UP_DOWN[direction_word]
    confidence_pct = round((confidence or 0.0) * 100, 1)

    return await store_prediction(
        source="development_memory",
        prediction_text=f"Development memory: {canonical_title[:150]} -> {up_down} on {target}",
        direction=up_down,
        prediction_type="company",
        target_entities=[{"type": "company", "symbol": target, "name": target}],
        confidence_score=confidence_pct,
        confidence_level=_confidence_level(confidence_pct),
        confidence_factors={
            "source": "development_memory", "development_id": dev_id,
            "evidence_count": evidence_count, "formation_impact_tier": impact_tier,
        },
        horizon_days=HORIZON_DAYS,
        query=marker,
        headline=canonical_title[:200],
        experimental=True,  # shadow mode — see module docstring
    )

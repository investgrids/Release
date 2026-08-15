"""
Material-change gated checkpoint runner — brief §22-§25.

Each checkpoint:
  1. resolve target/last trading session
  2. find the current (prior) snapshot for that target_trading_date, if any
  3. if none exists yet -> ALWAYS build+persist (brief §22's explicit
     exception: "the first required weekend snapshot may be created even
     with low evidence so the system has an explicit state")
  4. else -> cheap materiality pre-check on evidence strictly since the
     PRIOR snapshot's own generated_at (not the full close-to-now window
     — that's what the full aggregator run uses if this gate passes)
  5. not material -> skip the expensive synthesis entirely, log, return
  6. material -> run the full aggregator, persist the next version, log

Idempotency (brief §25) falls out of this design for free: the
materiality gate always re-reads the LATEST persisted snapshot's
generated_at from the DB (never in-memory scheduler state), so a
scheduler restart re-evaluating the same checkpoint sees "no new
evidence since what's already the current version" and correctly skips
— no separate checkpoint-identity tracking needed. Snapshot versioning's
own DB-level is_current uniqueness (Phase 1A) is the second, independent
layer of protection against a genuine double-write race.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.weekend_intelligence.aggregator import (
    build_weekend_intelligence,
    persist_weekend_intelligence,
)
from app.services.weekend_intelligence.evidence_window import collect_evidence_since
from app.services.weekend_intelligence.materiality import detect_material_change
from app.services.weekend_intelligence.versioning import get_current_snapshot

log = structlog.get_logger(__name__)

_JOB_ID_MORNING = "weekend_intelligence_checkpoint_morning"
_JOB_ID_EVENING = "weekend_intelligence_checkpoint_evening"

SKIPPED_NO_MATERIAL_CHANGE = "skipped_no_material_change"
CREATED = "created"


@dataclass
class CheckpointResult:
    outcome: str  # "created" | "skipped_no_material_change"
    target_trading_date: str
    last_trading_date: str | None = None
    snapshot_version: int | None = None
    status: str | None = None
    production_confidence: float | None = None
    evidence_count: int | None = None


async def run_checkpoint(
    db: AsyncSession, target_trading_date: str, *, checkpoint_time: datetime | None = None,
    checkpoint_label: str | None = None,
) -> CheckpointResult:
    started = time.monotonic()
    checkpoint_time = checkpoint_time or datetime.now(timezone.utc)

    prior = await get_current_snapshot(db, target_trading_date)

    if prior is not None:
        since = prior.generated_at if prior.generated_at.tzinfo else prior.generated_at.replace(tzinfo=timezone.utc)
        delta_evidence = await collect_evidence_since(db, since, checkpoint_time)
        material = detect_material_change(delta_evidence)
        if not material.is_material:
            duration = round(time.monotonic() - started, 3)
            log.info(
                "weekend_intelligence.checkpoint_skipped",
                target_trading_date=target_trading_date, checkpoint=checkpoint_label,
                evidence_count=material.new_evidence_count, material=False, duration=duration,
            )
            return CheckpointResult(
                outcome=SKIPPED_NO_MATERIAL_CHANGE,
                target_trading_date=target_trading_date,
                evidence_count=material.new_evidence_count,
            )

    result = await build_weekend_intelligence(db, target_trading_date, checkpoint_time)
    snapshot = await persist_weekend_intelligence(db, result, checkpoint_label=checkpoint_label)
    await db.commit()

    duration = round(time.monotonic() - started, 3)
    log.info(
        "weekend_intelligence.checkpoint_created",
        target_trading_date=target_trading_date, last_trading_date=result.last_trading_date,
        checkpoint=checkpoint_label, evidence_count=result.evidence_count, material=True,
        snapshot_version=snapshot.version, status=result.status,
        production_confidence=result.production_confidence, duration=duration,
    )
    return CheckpointResult(
        outcome=CREATED,
        target_trading_date=target_trading_date,
        last_trading_date=result.last_trading_date,
        snapshot_version=snapshot.version,
        status=result.status,
        production_confidence=result.production_confidence,
        evidence_count=result.evidence_count,
    )


async def run_weekend_checkpoint_cycle() -> None:
    """
    Scheduler entry point (brief §23/§24) — called by APScheduler on the
    fixed Sat/Sun 09:00 & 18:00 IST cron (see scheduler.py's
    register_jobs, "weekend_intelligence_checkpoint_morning"/"_evening").
    The same function backs both jobs; the checkpoint_label is computed
    from the actual current IST time, not hardcoded per job, so one
    function correctly produces "Saturday 09:00 IST" / "Sunday 18:00
    IST" / etc. labels without four separate registrations.

    Weekday safety (brief §26): CronTrigger's own day_of_week="sat,sun"
    is what actually prevents this from firing on a normal weekday — this
    function does not additionally re-check the day itself, to avoid a
    second, possibly-inconsistent day-of-week implementation. If it is
    ever invoked outside a real weekend (e.g. a manual/test call),
    resolve_weekend_session's own generic date-arithmetic still resolves
    a sensible (though not weekend-specific) last/target trading date —
    it does not crash, it just does not represent a real weekend gap.

    Wrapped in try/except so a checkpoint failure cannot crash the
    scheduler (brief §33) — matches every other scheduled job in this
    codebase's own defensive pattern (see e.g. price_monitor.py's
    per-instrument try/except).
    """
    from app.db.session import AsyncSessionLocal
    from app.services.intelligence.engine import _IST
    from app.services.weekend_intelligence.session_resolution import resolve_weekend_session

    now_ist = datetime.now(_IST)
    checkpoint_label = now_ist.strftime("%A %H:%M IST")
    _, target_trading_date = resolve_weekend_session(now_ist.date())

    try:
        async with AsyncSessionLocal() as db:
            await run_checkpoint(
                db, target_trading_date,
                checkpoint_time=now_ist.astimezone(timezone.utc),
                checkpoint_label=checkpoint_label,
            )
    except Exception as exc:
        log.warning(
            "weekend_intelligence.checkpoint_cycle_error",
            target_trading_date=target_trading_date, checkpoint=checkpoint_label, error=str(exc)[:300],
        )

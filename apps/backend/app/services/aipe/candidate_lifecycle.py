"""
Real, durable lifecycle tracking for scheduled/synthetic article candidates
-- see app/db/models/candidate_run.py's module docstring for the incident
this closes. Two calls per candidate: start_candidate_run() right before
generation is attempted, complete_candidate_run() with whatever real
outcome actually happened. A candidate that never reaches generation (a
duplicate match, an already-covered slot, a thin historical sample) is
correctly not tracked here -- the current logic for those decisions
already runs before generation and isn't part of the gap this closes.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.candidate_run import CandidateRun

log = None  # set lazily to avoid import cost when unused; see _log()


def _log():
    global log
    if log is None:
        import structlog
        log = structlog.get_logger(__name__)
    return log


def _now():
    return datetime.now(timezone.utc)


async def start_candidate_run(
    db, candidate_id: str, candidate_type: str, trigger_type: str = "scheduled_cron",
) -> CandidateRun:
    """Called right before a generation attempt. Committed immediately (not
    batched with the eventual outcome) so a real candidate is provably
    recorded even if the process crashes mid-generation -- the exact
    INTERNAL_ERROR case this exists to catch."""
    run = CandidateRun(
        candidate_id=candidate_id, candidate_type=candidate_type,
        trigger_type=trigger_type, generation_started_at=_now(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def complete_candidate_run(
    db, run: CandidateRun, *, terminal_status: str,
    article_id: str | None = None, failure_reason: str | None = None,
    provider_attempts: list[dict] | None = None,
) -> None:
    run.terminal_status = terminal_status
    run.article_id = article_id
    run.failure_reason = failure_reason
    if provider_attempts is not None:
        run.provider_attempts = provider_attempts
    run.completed_at = _now()
    db.add(run)
    await db.commit()
    _log().info(
        "candidate_run.completed", candidate_id=run.candidate_id,
        candidate_type=run.candidate_type, terminal_status=terminal_status,
        failure_reason=failure_reason,
    )

"""
P7 Candidate Ownership Arbitration (owner design, 2026-09-13).

Under the locked execution model (V1 commits first, V2's shadow/canary
pass runs synchronously after, same AIPE cycle), a candidate V1
successfully creates is necessarily already owned by V1 before V2 gets
its turn. A real V2-creation canary therefore needs an explicit policy
deciding which candidates V1 should deliberately stand aside for, so V2
can legitimately attempt ownership -- otherwise canary only ever
exercises V2 updating/observing V1-owned rows, never real V2 creation.

Made safe by a real, verified fact from the read-only audit that led
here: `get_high_urgency_triage()` pulls from a 3-hour rolling
`EventTriage` window, recomputed every 5-minute AIPE cycle -- the same
event stays in V1's candidate pool for up to 36 cycles. Withholding a
candidate for ONE cycle is not "give it to V2 or lose it forever"; V1
gets another real chance ~5 minutes later. This module enforces exactly
one withheld cycle per event, ever (see ArticleV2CanaryWithhold's own
docstring for the DB-level invariant), giving a bounded, ~5-minute
worst-case delay rather than risking the full 3-hour window.

Explicit predicates only -- no invented "ownership confidence" score.
Reuses evidence_count>=3 as the fixed floor because that's the real
median already observed across P6-B's 664 would_publish=True executions
(range 1-12), not a newly chosen number.

Scope boundary: this module decides WHETHER to withhold and records
WHY. It never calls publish_v2_article() and never marks anything
"converted"/"published_v2" -- there is no real V2 public-write path yet
(see shadow_orchestrator.py's own structural persistence boundary).
`ARTICLE_V2_CANARY_OWNERSHIP_ENABLED` defaults False and must stay False
in production until a separate, later, explicitly-authorized patch adds
the real write path -- enabling this today would only make V1 skip a
High event for one cycle with zero product benefit.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.article_v2_canary_withhold import ArticleV2CanaryWithhold
from app.db.models.article_v2_shadow_execution import ArticleV2ShadowExecution
from app.db.models.event_coverage import EventCoverage

# P6-B's own observed evidence_count median across 664 real
# would_publish=True executions (range 1-12) -- the fixed floor the
# owner required, not an invented confidence number.
_MIN_EVIDENCE_COUNT = 3

# AIPE cycle interval is 300s (scheduler.py's aipe_publish_cycle
# IntervalTrigger). "Immediately preceding cycle" = one interval plus a
# small, explicit execution-jitter allowance -- NOT "whatever the latest
# row happens to be", which could authorize withholding off a stale
# (e.g. 40-minute-old) shadow result merely because nothing newer exists.
_FRESHNESS_WINDOW_SECONDS = 8 * 60  # 8 minutes: 5-min interval + 3-min jitter allowance

_ELIGIBLE_TIER = "High"  # never "Critical" -- locked, not configurable by this patch


@dataclass
class WithholdDecision:
    should_withhold: bool
    reason: str
    prior_shadow_execution_id: Optional[str] = None
    reason_predicates: dict = field(default_factory=dict)


async def should_withhold_for_v2_canary(
    db: AsyncSession, *, triage_event_id: Optional[str], ev_tier: str, cycle_start_time: datetime,
) -> WithholdDecision:
    """Called from publisher.py's run_aipe_cycle(), only inside the
    "no V1 duplicate found, about to create a new article" branch --
    arbitration never touches V1's own update path. Returns should_
    withhold=True only when every predicate passes AND a withhold row
    was successfully, uniquely inserted (fail-closed on any DB
    contention: if a duplicate insert is ever attempted, V1 retains
    ownership rather than risking a second arbitration record for the
    same event)."""
    if not triage_event_id:
        return WithholdDecision(False, "no triage_event_id")

    if ev_tier != _ELIGIBLE_TIER:
        return WithholdDecision(False, f"tier {ev_tier!r} not eligible (only {_ELIGIBLE_TIER!r} is, never Critical)")

    existing_withhold = (await db.execute(
        select(ArticleV2CanaryWithhold.id).where(ArticleV2CanaryWithhold.triage_event_id == triage_event_id)
    )).scalar_one_or_none()
    if existing_withhold is not None:
        return WithholdDecision(False, "already withheld once for this event -- at most one withhold, ever")

    coverage = (await db.execute(
        select(EventCoverage.coverage_status).where(EventCoverage.event_id == triage_event_id)
    )).scalar_one_or_none()
    if coverage in ("PUBLISHED", "COVERED_BY_EXISTING_ARTICLE"):
        return WithholdDecision(False, f"real coverage already exists (coverage_status={coverage!r})")

    prior = (await db.execute(
        select(ArticleV2ShadowExecution)
        .where(ArticleV2ShadowExecution.triage_event_id == triage_event_id)
        .order_by(ArticleV2ShadowExecution.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if prior is None:
        return WithholdDecision(False, "no prior shadow execution for this event")

    prior_created_at = prior.created_at
    if prior_created_at.tzinfo is None:
        prior_created_at = prior_created_at.replace(tzinfo=timezone.utc)
    age_seconds = (cycle_start_time - prior_created_at).total_seconds()
    if age_seconds < 0 or age_seconds > _FRESHNESS_WINDOW_SECONDS:
        return WithholdDecision(
            False,
            f"prior shadow execution is {age_seconds:.0f}s old, outside the {_FRESHNESS_WINDOW_SECONDS}s freshness window",
        )

    if not prior.would_publish:
        return WithholdDecision(False, "prior shadow execution did not reach would_publish=True")
    if prior.stage_reached != "P4":
        return WithholdDecision(False, f"prior shadow execution stopped at stage_reached={prior.stage_reached!r}, not P4")
    if prior.c8_tier != "ARTICLE":
        return WithholdDecision(False, f"prior shadow execution c8_tier={prior.c8_tier!r}, not ARTICLE")
    if prior.c5_publication_action != "CREATE_NEW":
        # The exact production-observed failure mode this predicate
        # guards against: a candidate C5 itself resolved as
        # UPDATE_EXISTING (real coverage already existed from V2's own
        # perspective) must never be withheld from V1 -- V2 didn't want
        # a NEW canonical article for it in the first place.
        return WithholdDecision(False, f"prior c5_publication_action={prior.c5_publication_action!r}, not CREATE_NEW")
    if prior.collision_gate_outcome != "no_collision":
        # Deliberately excludes NULL/not_evaluated -- historical/pre-gate
        # rows, or rows where C5 never reached CREATE_NEW at all, are
        # ineligible. Only post-gate "no_collision" evidence counts.
        return WithholdDecision(False, f"prior collision_gate_outcome={prior.collision_gate_outcome!r}, not no_collision")
    if (prior.evidence_count or 0) < _MIN_EVIDENCE_COUNT:
        return WithholdDecision(False, f"prior evidence_count={prior.evidence_count!r} < {_MIN_EVIDENCE_COUNT}")
    if not prior.canonical_entity_id:
        return WithholdDecision(False, "prior shadow execution has no resolved canonical_entity_id")

    reason_predicates = {
        "prior_shadow_execution_id": prior.id,
        "prior_shadow_age_seconds": round(age_seconds, 1),
        "would_publish": prior.would_publish,
        "stage_reached": prior.stage_reached,
        "c8_tier": prior.c8_tier,
        "c5_publication_action": prior.c5_publication_action,
        "collision_gate_outcome": prior.collision_gate_outcome,
        "evidence_count": prior.evidence_count,
        "canonical_entity_id": prior.canonical_entity_id,
        "ev_tier": ev_tier,
    }

    withhold_row = ArticleV2CanaryWithhold(
        id=f"withhold-{uuid.uuid4()}",
        triage_event_id=triage_event_id,
        prior_shadow_execution_id=prior.id,
        reason_predicates=reason_predicates,
        withheld_at=cycle_start_time,
    )
    db.add(withhold_row)
    try:
        await db.commit()
    except IntegrityError:
        # Fail closed: the unique index caught a race (two attempts to
        # withhold the same event). V1 retains ownership rather than a
        # second arbitration record ever existing for one event.
        await db.rollback()
        return WithholdDecision(False, "unique constraint prevented a duplicate withhold -- failing closed, V1 retains ownership")

    return WithholdDecision(True, "eligible: withholding for exactly this one cycle", prior.id, reason_predicates)

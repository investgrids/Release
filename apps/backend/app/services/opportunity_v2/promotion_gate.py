"""
V2 Promotion Eligibility Gate (2026-09-20, Item 7 enforcement) — the ONE
shared checkpoint every public_status shadow->public transition must go
through. app/api/admin.py's promote endpoint is the only real write path
to public_status="public" in this codebase (confirmed by a full grep
audit, 2026-09-20 -- orchestration.py only ever sets "shadow" at
creation); this module is called from there, before the guarded UPDATE,
so nothing can reach the write without first clearing this gate.

Two independent, additive rejection reasons:

  synthetic_exposure_development -- ANY linked Development matches the
    exact "Directly exposed to {X} opportunity through core operations"
    template. Defense against unsupported evidence (these don't read
    like real reported events at all), not a routine-filing judgment --
    a single synthetic-exposure Development is enough to reject,
    regardless of how material or routine the OTHER linked Developments
    are.

  routine_filing_only -- EVERY real (non-synthetic-exposure) linked
    Development independently classifies as a routine/procedural filing
    (routine_filing_classifier.py) with no material escape. A single
    genuinely material Development keeps the whole opportunity eligible
    (mixed clusters remain eligible by design).

A rejection NEVER mutates the row -- this function only decides; it
makes no database write of its own. No narrative rewrite/delete, no
score/identity/candidate_status/narrative_status change happens here or
as a side effect of a rejection. The existing 177 real rows this
dry-run identified stay exactly as they are (shadow) -- this gate only
ever prevents a FUTURE promotion attempt from succeeding, it does not
retroactively touch anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.event import Event
from app.db.models.opportunity_v2 import OpportunityV2Development
from app.services.opportunity_v2.routine_filing_classifier import (
    DevelopmentClassification,
    classify_development,
)

log = structlog.get_logger(__name__)

REASON_SYNTHETIC_EXPOSURE = "synthetic_exposure_development"
REASON_ROUTINE_FILING_ONLY = "routine_filing_only"


@dataclass
class PromotionEligibility:
    allowed: bool
    reason: str | None = None
    # Full per-Development classification detail, always populated
    # (allowed or not) -- for the caller to log/return regardless of
    # outcome, matching the "log the matched patterns and material
    # escapes evaluated" requirement even on an ALLOWED decision.
    evaluated: list[dict] = field(default_factory=list)


def _classification_to_dict(c: DevelopmentClassification) -> dict:
    return {
        "development_id": c.development_id,
        "is_routine": c.is_routine,
        "is_synthetic_exposure": c.is_synthetic_exposure,
        "matched_routine_patterns": c.matched_routine_patterns,
        "matched_escape_patterns": c.matched_escape_patterns,
        "reason": c.reason,
    }


async def evaluate_promotion_eligibility(db: AsyncSession, opportunity_id: str) -> PromotionEligibility:
    """Real DB reads only -- no write. Safe to call speculatively (e.g.
    a future "would this promote?" preview) without any promotion
    actually happening."""
    dev_ids = (await db.execute(
        select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opportunity_id)
    )).scalars().all()

    if not dev_ids:
        # No linked Development at all -- neither routine-filing nor
        # synthetic-exposure judgment applies to an opportunity with zero
        # real evidence structure; that's a separate (pre-existing)
        # concern this gate doesn't newly regulate.
        result = PromotionEligibility(allowed=True, evaluated=[])
        log.info("opportunity_v2.promotion_allowed", opportunity_id=opportunity_id, evaluated=[])
        return result

    developments = (await db.execute(select(Development).where(Development.id.in_(dev_ids)))).scalars().all()

    ev_rows = (await db.execute(
        select(DevelopmentEvidence.development_id, Event.event_type)
        .join(Event, Event.id == DevelopmentEvidence.source_id)
        .where(DevelopmentEvidence.development_id.in_(dev_ids), DevelopmentEvidence.source_type == "event")
    )).all()
    event_types_by_dev: dict[str, list[str | None]] = {}
    for dev_id, event_type in ev_rows:
        event_types_by_dev.setdefault(dev_id, []).append(event_type)

    classifications = [
        classify_development(d.id, d.canonical_title, event_types_by_dev.get(d.id, []))
        for d in developments
    ]
    evaluated = [_classification_to_dict(c) for c in classifications]

    synthetic_hits = [c for c in classifications if c.is_synthetic_exposure]
    if synthetic_hits:
        log.info(
            "opportunity_v2.promotion_rejected", opportunity_id=opportunity_id,
            reason=REASON_SYNTHETIC_EXPOSURE, evaluated=evaluated,
        )
        return PromotionEligibility(allowed=False, reason=REASON_SYNTHETIC_EXPOSURE, evaluated=evaluated)

    real_classifications = [c for c in classifications if not c.is_synthetic_exposure]
    if real_classifications and all(c.is_routine for c in real_classifications):
        log.info(
            "opportunity_v2.promotion_rejected", opportunity_id=opportunity_id,
            reason=REASON_ROUTINE_FILING_ONLY, evaluated=evaluated,
        )
        return PromotionEligibility(allowed=False, reason=REASON_ROUTINE_FILING_ONLY, evaluated=evaluated)

    log.info("opportunity_v2.promotion_allowed", opportunity_id=opportunity_id, evaluated=evaluated)
    return PromotionEligibility(allowed=True, evaluated=evaluated)

"""
Article V2 — V1<->V2 Collision Gate (owner design, 2026-09-13).

Prerequisite the owner locked before P7/canary_v2: prove V1 and V2 can
never independently allocate two public canonical articles for the same
real-world development. Root cause traced via a read-only audit: V1
(duplicate_detector.find_duplicate) and C1 (candidate_gate._find_already_
covered) implement two separately-scoped duplicate-detection queries --
sharing the same tokenizer/Jaccard/threshold, but different candidate
pools -- so they can and do disagree (the IKIO-shaped specimens: V1 says
"updated", C5 independently resolves CREATE_NEW). C5.2's own
resolve_uniqueness() collision check is purely in-memory and intra-batch;
it has zero visibility into anything persisted by a prior run or by V1.
There is also no database uniqueness constraint on trigger_event_id/
story_id -- deliberately not added here, since the identity model
legitimately allows multiple articles across different angles/events.

Execution model this gate assumes and requires (locked, not just
observed): V1 runs and commits first, then V2's shadow/canary pass runs
synchronously in the same process, same AIPE cycle -- never an
independently-scheduled V2 publisher. If that changes later, this gate's
design must be revisited.

## The rule that matters most

Under that execution model, a V1 `created` decision means V1 has JUST
committed a brand-new public IntelligenceArticle for this exact
candidate, moments before V2 runs. That is the strongest possible
ownership evidence -- stronger than "no collision found" if V2 were to
independently reconstruct identity. So `created` must resolve as
RESOLVED_EXISTING (V1 already owns it), not NO_COLLISION. Getting this
backwards would let V2 allocate a second canonical article for a
development V1 just published.

## Outcome semantics

- NO_COLLISION: no live article -- from V1's own decision or, when V1
  never reached ownership for this exact event, a fresh DB-backed
  fallback check -- claims this identity. C5's CREATE_NEW stands.
- RESOLVED_EXISTING: an unambiguous existing owner was found (via V1's
  own decision, or the fallback check). Caller must convert to
  UPDATE_EXISTING against `collision_owner_article_id` and must NEVER
  call publish_v2_article() (the create-only write path -- there is no
  V2 update-in-place implementation yet; that's separate, later scope,
  not solved by this gate).
- AMBIGUOUS: a concrete, narrow, observable DB state -- more than one
  live article already shares the exact (trigger_event_id, article_type,
  angle, angle_entity) tuple -- was found. This is a real data-integrity
  signal find_duplicate()'s own `.limit(1)` would silently paper over by
  picking whichever is most recent; the gate refuses to guess instead.
  Deliberately narrow: headline-similarity multi-match ambiguity is NOT
  implemented (would require exposing find_duplicate()'s internal steps,
  which it doesn't return today -- reusing it, not reinventing it, was
  the explicit design instruction).

## Explicitly NOT solved here (P7 prerequisite, recorded not implemented)

Under V1-commits-first, a V1 `created` candidate can never legitimately
become a V2 CREATE_NEW candidate at canary time -- V1 already owns it.
So an eventual canary_v2 needs its OWN separate policy deciding which
candidates V2 is allowed to attempt to OWN (create) before V1 does,
otherwise canary only ever exercises V2 updating/observing V1-owned
rows, never real V2 creation. That ownership-arbitration policy is a
named P7 prerequisite -- not implemented, not assumed, not started by
this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.duplicate_detector import find_duplicate

NOT_EVALUATED = "not_evaluated"
NO_COLLISION = "no_collision"
RESOLVED_EXISTING = "resolved_existing"
AMBIGUOUS = "ambiguous"

# match_basis values -- centralized here (not just documented in the
# CollisionResult docstring) so a schema-width regression test can
# assert every one of these actually fits the declared DB column
# without needing to duplicate the literal list.
BASIS_V1_DECISION = "v1_decision"
BASIS_DUPLICATE_LOOKUP = "duplicate_lookup"
BASIS_MULTIPLE_OWNERS = "multiple_owners"

_INFORMATIVE_V1_DECISIONS = {"created", "updated", "duplicate_no_update"}


@dataclass
class V1Decision:
    """Captured at the exact V1 call sites in aipe/publisher.py that
    already compute every one of these values -- never re-derived by V2.
    `story_id`/`article_type` come from content_planner.select_article_
    type() (the same function V1 itself calls); `matched_article_id` is
    duplicate_detector.find_duplicate()'s own return; `created_article_id`
    is the newly-committed article's own id when V1's decision was
    "created"."""
    decision: str
    story_id: Optional[str] = None
    article_type: Optional[str] = None
    matched_article_id: Optional[str] = None
    created_article_id: Optional[str] = None


@dataclass
class CollisionResult:
    outcome: str  # NO_COLLISION | RESOLVED_EXISTING | AMBIGUOUS
    match_basis: Optional[str]  # None | "v1_decision" | "duplicate_lookup" | "multiple_owners"
    collision_owner_article_id: Optional[str]


async def _count_exact_tuple_owners(
    db: AsyncSession, *, trigger_event_id: Optional[str], article_type: Optional[str],
    angle: str, angle_entity: Optional[str],
) -> int:
    """Narrow, explicit preflight find_duplicate() cannot express (it
    `.limit(1)`s). Deliberately excludes non-live lifecycle states via
    the same filter V1/C1 already apply, so this can only ever count
    genuinely live, competing owners -- not a stale/archived leftover."""
    if not trigger_event_id or not article_type:
        return 0
    result = await db.execute(
        select(func.count(func.distinct(IntelligenceArticle.id)))
        .where(IntelligenceArticle.trigger_event_id == trigger_event_id)
        .where(IntelligenceArticle.article_type == article_type)
        .where(IntelligenceArticle.angle == angle)
        .where(IntelligenceArticle.angle_entity == angle_entity)
        .where(IntelligenceArticle.lifecycle_status.notin_(("archived", "merged", "failed")))
    )
    return result.scalar() or 0


async def check_collision(
    db: AsyncSession, *, event_id: Optional[str], headline: str,
    v1_decision: Optional[V1Decision],
    fallback_story_id: Optional[str] = None, fallback_article_type: Optional[str] = None,
    angle: str = "primary", angle_entity: Optional[str] = None,
) -> CollisionResult:
    """The one real entry point. Called immediately before any V2
    CREATE_NEW becomes publishable.

    Priority:
      1. Trust V1's own decision for this exact event_id when it reached
         one (created/updated/duplicate_no_update) -- verified live via
         one cheap existence check, never re-derived.
      2. Otherwise (V1 never reached ownership for this event: skipped,
         generation_failed, validation_failed, or no entry at all), fall
         back to a fresh DB-backed check: a narrow multi-owner preflight,
         then duplicate_detector.find_duplicate() itself -- the same
         function V1 calls, not a reimplementation.
    """
    if v1_decision is not None and v1_decision.decision in _INFORMATIVE_V1_DECISIONS:
        owner_id = (
            v1_decision.created_article_id if v1_decision.decision == "created"
            else v1_decision.matched_article_id
        )
        if owner_id is not None:
            still_live = await db.get(IntelligenceArticle, owner_id)
            if still_live is not None and still_live.lifecycle_status not in ("archived", "merged", "failed"):
                return CollisionResult(RESOLVED_EXISTING, BASIS_V1_DECISION, owner_id)
            # The row V1 claimed no longer exists/is no longer live (e.g.
            # archived between V1's write and this check) -- V1's answer
            # is stale, fall through to the independent DB check below
            # rather than trusting a dangling id.

    owner_count = await _count_exact_tuple_owners(
        db, trigger_event_id=event_id, article_type=fallback_article_type,
        angle=angle, angle_entity=angle_entity,
    )
    if owner_count > 1:
        return CollisionResult(AMBIGUOUS, BASIS_MULTIPLE_OWNERS, None)

    match = await find_duplicate(
        db, story_id=fallback_story_id or "", article_type=fallback_article_type or "",
        headline=headline, trigger_event_id=event_id, angle=angle, angle_entity=angle_entity,
    )
    if match is not None:
        return CollisionResult(RESOLVED_EXISTING, BASIS_DUPLICATE_LOOKUP, match.id)

    return CollisionResult(NO_COLLISION, None, None)

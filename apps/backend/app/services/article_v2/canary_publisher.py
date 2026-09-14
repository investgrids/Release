"""
Article V2 — P7 Real-Write / Canary Activation (owner design, 2026-09-14).

The one module allowed to call `publish_v2_article()` for a real,
public-facing `IntelligenceArticle`. Everything before this point in the
pipeline (shadow_orchestrator.py, ownership_arbitration.py, the
collision gate) was deliberately built to never write one -- this module
is the separate, later boundary those modules' own docstrings named but
did not implement.

## Why this is a SEPARATE rerun, not a read of shadow telemetry

`run_shadow_batch()` (shadow_orchestrator.py) already reruns the entire
C1->C8.5->headline->compose->P1/P2/P4 sequence every cycle, including
for a candidate V1 just withheld -- but it structurally discards every
pipeline artifact except a durable `ArticleV2ShadowExecution` summary
row (see its own docstring: "not protected by a flag, structurally
absent"). Reading those artifacts back out of it, or adding a branch
inside it, would blur that structural boundary. Instead, this module
does its OWN minimal, independent rerun for exactly the one candidate
being considered for a real write -- duplicating ~8 lines of
orchestration/sequencing, never any pipeline stage's actual logic.
Given the lifetime budget is one article, ever, the cost of a second
rerun is irrelevant; freshness (re-deriving from current evidence at
the moment of the real write, not trusting a snapshot from moments
earlier) is worth more here than saving one rerun.

## The two-flag activation model

`article_v2_canary_ownership_enabled` (ownership_arbitration.py) decides
whether V1 may withhold a candidate at all. `article_v2_canary_public_
write_enabled` (this module) decides whether a withheld candidate may
result in a real write. BOTH must be True before `attempt_canary_
publish()` does anything beyond reconciliation. Both default False and
must stay False in production through this patch -- it ships the
real-write machinery DORMANT. Turning both on is a separate, later,
explicitly-authorized human checkpoint: "authorize exactly one
High-tier V2 canonical article in production?" Not a side effect of
deploying this file.

## Two independent budgets, not one (P7 Single Production Canary
   activation review, 2026-09-14)

A real gap in an earlier version of this module: the publish-budget
invariant below guarantees at most one ARTICLE ever commits, but it
does nothing to stop a SECOND CANDIDATE from being attempted in a later
cycle if the first one's fresh rerun simply declines pre-commit
(evidence changed, C5 stopped being CREATE_NEW, a collision appeared,
the Final Publication Validator refused). The lifetime budget stays
unused in that case, so both activation flags being left on would let
the system keep trying candidate after candidate until one finally
succeeds -- "one article ever" was enforced; "one attempt ever" was
not, and an operator racing a Railway redeploy to flip the write flag
off after observing a decline is a timing control, not a structural
guarantee.

Fixed with a SECOND, independent DB invariant: `attempted` (its own
partial unique index, `WHERE attempted=1`) is claimed atomically the
MOMENT a candidate enters this function -- before the tier re-check,
before the expensive rerun, before anything else. It is monotonic and
never un-set. The first candidate to claim it permanently closes the
real canary path for every other candidate, forever, regardless of
whether that first candidate goes on to publish, decline, or fail. The
two invariants are independently provable: attempt-budget (`attempted`)
bounds how many candidates may ever EXECUTE the real canary path;
publish-budget (`outcome='published_v2'`) bounds how many of those
executions may ever COMMIT an article. A correctly-functioning system
can never consume the second without having already consumed the
first.

## The publish budget: exactly one, DB-enforced, atomic WITH the article

The budget is not a counter -- it's "does any article_v2_canary_
withholds row already have outcome='published_v2'". A plain
check-then-write query has a real race between two workers each
observing zero. The invariant is enforced by a partial unique index on
`outcome` itself (see article_v2_canary_withhold.py's own
__table_args__) -- at most one row can ever hold that value, full stop,
enforced by the DB at commit time.

Critically, that budget claim is committed in the SAME transaction as
the article insert (see the corrected sequence below), not a separate,
later commit. An earlier draft of this module committed the article
first and only afterward tried to claim the budget via a second commit
-- that left a real window where two racing workers could each commit
a real article before either claimed the budget, and the partial index
would then only stop the second TELEMETRY row, too late to stop the
second ARTICLE. Folding the claim into the article's own transaction
means a losing worker's commit fails and rolls back BOTH the withhold
update and its article insert together -- it ends up with no article
at all, not a second one.

## Ownership transfer boundary

Ownership transfers at exactly one moment, and the article and its own
canary audit pointer become durable TOGETHER, in one transaction:

    article = await publish_v2_article(...)      # flush only, obtains article.id
    withhold_row.outcome = "published_v2"
    withhold_row.published_article_id = article.id
    await db.commit()                             # ONE commit -- ownership + budget claim

Everything before this commit (LLM/generation failure, changed
evidence, a second collision-gate check returning RESOLVED_EXISTING or
AMBIGUOUS, a PublicationRefusal from the Final Publication Validator,
or losing the budget race itself) is free -- a flush without commit, or
a rolled-back transaction, leaves zero durable trace, full stop, article
included. Only `coverage_mark_published()` happens after this commit,
and only it is best-effort bookkeeping -- exactly mirroring how V1's
own _publish_new_article -> coverage_mark_published sequence already
works in production today (article commit first, coverage a separate,
later commit merely logged on failure). This module does not invent
stricter atomicity than V1 has for coverage; it just refuses to split
the ONE thing that must never happen twice (the article + its budget
claim) across two commits.

## Reconciliation -- now a legacy/abnormal-state safety net, not the
   normal crash path

Because the article and published_article_id/outcome are now durable
together, a crash immediately after the ownership commit already
leaves the withhold row fully self-describing -- reconciliation is no
longer what recovers the NORMAL post-commit-crash case. It remains
useful for genuinely abnormal states: a crash between the ownership
commit and the coverage update (coverage alone would be stale, not
outcome/published_article_id), or a row left over from an earlier,
pre-fix version of this module. Every real V2-created article carries
an unconditional, deterministic producer marker --
`trigger_type="article_v2_pipeline"` (set by publication_translator.py
for every V2 build, not something this module adds) plus
`trigger_event_id`. Reconciliation never infers anything from
shadow-execution lineage or headline similarity: it looks for exactly
that (trigger_type, trigger_event_id) pair among live articles.
Zero matches -> nothing to reconcile. Exactly one match -> backfill
outcome/published_article_id/coverage from it. More than one match ->
fail closed and log at error level; never guess which one is
authoritative.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.article_v2_canary_withhold import ArticleV2CanaryWithhold
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.article_v2.candidate_gate import SKIP as C1_SKIP
from app.services.article_v2.candidate_gate import evaluate_candidate
from app.services.article_v2.collision_gate import NO_COLLISION, V1Decision, check_collision
from app.services.article_v2.composer import ComposerRefusal, compose_article
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, decide
from app.services.article_v2.evidence_set_builder import build_evidence_set
from app.services.article_v2.headline_engine import generate_headline
from app.services.article_v2.identity import CREATE_NEW, compute_identity, resolve_uniqueness
from app.services.article_v2.publication_tier import ARTICLE, classify_publication_tier
from app.services.article_v2.publisher import PublicationRefusal, publish_v2_article
from app.services.coverage_engine import mark_published as coverage_mark_published

log = structlog.get_logger(__name__)

# The producer marker every V2-built article already carries
# unconditionally (publication_translator.py's own "real V1/V2
# discriminator") -- reused here verbatim, never redefined, so
# reconciliation can never drift from what the write path itself sets.
_V2_TRIGGER_TYPE = "article_v2_pipeline"

_LIVE_LIFECYCLE_EXCLUDES = ("archived", "merged", "failed")


@dataclass
class CanaryPublishResult:
    published: bool
    reason: str
    article_id: Optional[str] = None


async def _lifetime_budget_consumed(db: AsyncSession) -> bool:
    """True once any withhold row has ever recorded a real publication.
    A plain existence check -- the actual race-proof invariant is the
    partial unique index on outcome itself; this is just the cheap
    early-exit that avoids attempting a rerun that would be refused
    anyway. Kept as a second, independent safety net alongside
    _attempt_budget_consumed below -- in a correctly-functioning system
    this can never fire without the attempt-budget claim having already
    fired first, but it costs nothing to check both."""
    row = (await db.execute(
        select(ArticleV2CanaryWithhold.id).where(ArticleV2CanaryWithhold.outcome == "published_v2")
    )).scalar_one_or_none()
    return row is not None


async def _attempt_budget_consumed(db: AsyncSession) -> bool:
    """True once any candidate has ever entered the real canary
    execution path, regardless of what happened to it. A plain
    existence check -- the actual race-proof invariant is the partial
    unique index on `attempted` itself; this is just the cheap
    early-exit that avoids even the ATTEMPT of a claim commit when the
    budget is obviously already gone."""
    row = (await db.execute(
        select(ArticleV2CanaryWithhold.id).where(ArticleV2CanaryWithhold.attempted.is_(True))
    )).scalar_one_or_none()
    return row is not None


async def _find_v2_produced_article(db: AsyncSession, *, event_id: str) -> list[IntelligenceArticle]:
    """Every live article this exact event could ever have produced via
    the real V2 write path -- the deterministic reconciliation lookup.
    Never matches a V1 article (V1 never sets trigger_type=
    "article_v2_pipeline") and never matches an archived/merged/failed
    leftover."""
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.trigger_type == _V2_TRIGGER_TYPE)
        .where(IntelligenceArticle.trigger_event_id == event_id)
        .where(IntelligenceArticle.lifecycle_status.notin_(_LIVE_LIFECYCLE_EXCLUDES))
    )
    return list(result.scalars().all())


async def reconcile_stale_canary_withholds(db: AsyncSession) -> None:
    """Called every cycle, unconditionally, whenever ownership
    arbitration is active -- cheap (at most a handful of NULL-outcome
    rows will ever exist for a one-shot canary) and self-contained.
    Never invents an outcome for a genuine zero-match row -- that's
    either a real pre-commit failure (which should already have
    recorded its own honest outcome at the point of failure) or a
    withhold not yet attempted this cycle; reconciliation only ever
    repairs a row whose article demonstrably already exists."""
    stale = (await db.execute(
        select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.outcome.is_(None))
    )).scalars().all()

    for row in stale:
        matches = await _find_v2_produced_article(db, event_id=row.triage_event_id)
        if not matches:
            continue
        if len(matches) > 1:
            log.error(
                "article_v2.canary_reconciliation_ambiguous",
                triage_event_id=row.triage_event_id,
                candidate_article_ids=[a.id for a in matches],
            )
            continue
        article = matches[0]
        log.warning(
            "article_v2.canary_reconciled_post_crash",
            triage_event_id=row.triage_event_id, article_id=article.id,
        )
        row.outcome = "published_v2"
        row.published_article_id = article.id
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            # Another row already legitimately holds outcome="published_v2"
            # (should be structurally impossible -- this row's own event
            # can only ever match the one real canary article -- but fail
            # closed rather than ever overwrite the invariant).
            await db.rollback()
            log.error("article_v2.canary_reconciliation_conflict", triage_event_id=row.triage_event_id)
            continue
        await coverage_mark_published(db, event_id=row.triage_event_id, article_id=article.id)


async def attempt_canary_publish(
    db: AsyncSession, *, triage_event: dict, ev_tier: str, mie_context: dict | None,
) -> CanaryPublishResult:
    """Called at most once per cycle, only for the one event V1 just
    withheld this same cycle. Re-verifies every eligibility predicate
    against fresh evidence rather than trusting anything computed
    earlier -- a withhold is permission to attempt, never permission to
    publish unconditionally."""
    event_id = triage_event.get("event_id")

    withhold_row = (await db.execute(
        select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id)
    )).scalar_one_or_none()
    if withhold_row is None or withhold_row.outcome is not None or withhold_row.attempted:
        # Re-verification of "was actually withheld this cycle, not yet
        # attempted" -- should be structurally impossible to reach this
        # function otherwise, but never trust the caller alone for the
        # one action that can create a real public article.
        return CanaryPublishResult(False, "no fresh, unattempted withhold row for this event")

    # ── Attempt-budget claim -- BEFORE the expensive rerun, and before
    # even the tier re-check below. This is the fix for a real gap: the
    # outcome='published_v2' index only stops a SECOND ARTICLE from
    # committing -- it does nothing if this candidate's rerun simply
    # declines pre-commit (evidence changed, collision appeared, the
    # validator refused). Without a separate claim here, a later cycle
    # could withhold and attempt a second candidate while both
    # activation flags stayed on, since the publish-budget was never
    # touched by the first candidate's decline. Claiming `attempted`
    # atomically, this early, means the FIRST candidate to reach this
    # function -- regardless of what happens to it next -- permanently
    # closes the real canary path for every other candidate, forever.
    if await _attempt_budget_consumed(db):
        return CanaryPublishResult(False, "global canary attempt budget already consumed by another candidate")
    withhold_row.attempted = True
    db.add(withhold_row)
    try:
        await db.commit()
    except IntegrityError:
        # Another candidate's commit won the race between our cheap
        # check above and this one. Fail closed: no second candidate
        # ever enters the real rerun, regardless of how the race
        # happened.
        await db.rollback()
        log.error("article_v2.canary_attempt_budget_race_lost", event_id=event_id)
        return CanaryPublishResult(False, "global canary attempt budget claimed by a concurrent commit")

    if ev_tier != "High":
        return await _fail(db, withhold_row, "ineligible: ev_tier is not High (never Critical)")

    if await _lifetime_budget_consumed(db):
        return await _fail(db, withhold_row, "lifetime V2 public-write budget already consumed")

    symbol = (triage_event.get("tickers") or [None])[0]
    headline = triage_event.get("headline") or ""
    if not symbol:
        return await _fail(db, withhold_row, "no ticker on this triage event")

    candidate = await evaluate_candidate(db, symbol=symbol, event_headline=headline, event_id=event_id)
    if candidate.outcome == C1_SKIP:
        return await _fail(db, withhold_row, f"fresh rerun: C1 SKIP ({candidate.reason_detail})")

    es = await build_evidence_set(db, symbol=symbol, event_headline=headline, event_id=event_id)
    if es.primary_evidence is None:
        return await _fail(db, withhold_row, "fresh rerun: C2 no usable primary evidence")

    ctx = await build_context(db, es)
    decision = decide(candidate, es, ctx)
    if decision.content_type not in (FULL_ARTICLE, FACTUAL_UPDATE):
        return await _fail(db, withhold_row, f"fresh rerun: C4 content_type={decision.content_type}")

    identity = compute_identity(es)
    resolution = resolve_uniqueness(
        identity, c4_publication_action=decision.publication_action,
        c4_matched_article_id=candidate.matched_article_id, known_identities={},
    )
    if resolution.publication_action != CREATE_NEW:
        return await _fail(db, withhold_row, f"fresh rerun: C5 resolved {resolution.publication_action}, not CREATE_NEW")

    from app.services.aipe.content_planner import select_article_type
    fallback_article_type, fallback_story_id, _ = select_article_type(
        {"event_id": event_id, "headline": headline}, mie_context,
    )
    collision = await check_collision(
        db, event_id=event_id, headline=headline,
        v1_decision=V1Decision(decision="withheld_for_v2_canary"),
        fallback_story_id=fallback_story_id, fallback_article_type=fallback_article_type,
    )
    if collision.outcome != NO_COLLISION:
        return await _fail(db, withhold_row, f"fresh rerun: collision gate returned {collision.outcome}, not no_collision")

    tier_result = classify_publication_tier(decision, es, ctx)
    if tier_result.tier != ARTICLE:
        return await _fail(db, withhold_row, f"fresh rerun: C8 tier={tier_result.tier}")

    headline_result = await generate_headline(es, ctx, identity, other_accepted_headlines={})

    try:
        composed = await compose_article(decision, es, ctx, identity, resolution, headline_result)
    except ComposerRefusal as exc:
        return await _fail(db, withhold_row, f"fresh rerun: ComposerRefusal: {exc}")

    article_id = str(uuid.uuid4())
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        article = await publish_v2_article(
            db, article_id=article_id, decision=decision, evidence_set=es, identity=identity,
            resolution=resolution, headline_result=headline_result, composed=composed,
            field_overrides={"status": "published", "published_at": now, "lifecycle_status": "published"},
        )
    except PublicationRefusal as exc:
        await db.rollback()
        return await _fail(db, withhold_row, f"fresh rerun: PublicationRefusal: {exc}")

    # ── Ownership transfer boundary ──────────────────────────────────────
    # The article insert (flushed, not yet committed) and the budget-
    # claiming withhold update are committed together, in ONE
    # transaction. This is the actual fix for a real gap in an earlier
    # draft: with the article commit and the withhold-outcome commit as
    # two separate steps, two racing workers could each commit their own
    # real article before either got to claim the budget -- the partial
    # unique index would then correctly stop a second telemetry row, but
    # too late, since two public articles would already exist. Folding
    # the budget claim into the SAME transaction as the article means
    # the partial unique index's IntegrityError rolls back the article
    # insert too -- a losing worker ends up with no article, not a
    # second one.
    withhold_row.outcome = "published_v2"
    withhold_row.published_article_id = article.id
    db.add(withhold_row)
    try:
        await db.commit()
    except IntegrityError:
        # The lifetime-budget partial unique index fired -- another
        # transaction already claimed outcome="published_v2" between our
        # budget check above and this commit. Rolling back here
        # discards the article insert too, in the SAME transaction --
        # no second public article, ever, regardless of how the race
        # happened.
        await db.rollback()
        log.error("article_v2.canary_budget_race_lost", event_id=event_id)
        return CanaryPublishResult(False, "lifetime budget consumed by a concurrent commit")

    log.info("article_v2.canary_published", event_id=event_id, article_id=article.id)

    # ── Everything below is best-effort bookkeeping, not ownership --
    # the article and its exact canary audit pointer (published_article_id)
    # are already durable together as of the commit above. A failure here
    # leaves coverage stale but never puts ownership itself in doubt, and
    # reconcile_stale_canary_withholds is no longer even the mechanism
    # that would notice it (the withhold row already has its outcome and
    # published_article_id set) -- this is purely EventCoverage's own
    # best-effort mirror, exactly like V1's own coverage_mark_published
    # call after _publish_new_article.
    await coverage_mark_published(db, event_id=event_id, article_id=article.id)

    return CanaryPublishResult(True, "published", article_id=article.id)


async def _fail(db: AsyncSession, withhold_row: ArticleV2CanaryWithhold, reason: str) -> CanaryPublishResult:
    """Every pre-commit failure path: record an honest outcome so this
    withhold row is never left ambiguously NULL, then let V1 resume
    ownership next cycle exactly as the non-canary withhold path already
    guarantees (the 3-hour rolling triage window)."""
    withhold_row.outcome = "shadow_not_qualified"
    db.add(withhold_row)
    await db.commit()
    log.info("article_v2.canary_publish_declined", triage_event_id=withhold_row.triage_event_id, reason=reason)
    return CanaryPublishResult(False, reason)

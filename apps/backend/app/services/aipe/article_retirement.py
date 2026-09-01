"""
Article Retirement (P0 content-integrity remediation, owner design,
2026-09-01). A reusable integrity primitive, not a one-off script that
knows specific IDs -- callers always supply the article ID(s) explicitly.
This module NEVER discovers what to retire on its own (no prose/
headline/keyword scanning) -- that decision was already made, by a
separate provenance audit, before this module is ever called.

Uses ONLY existing schema -- no migration needed:
  - status: already a free String(16) column every read path (insights.py's
    list/search/trending/company/detail routes) already filters on
    == "published" -- "retired" is simply a new valid value for a column
    that was already being checked. This is what makes retirement work
    at all: no new filtering logic needed anywhere, the existing gate
    already does the job.
  - archived_at: already declared on IntelligenceArticle, already
    nullable, confirmed (in the remediation audit) to be written by
    NOTHING today -- reused here as the retirement timestamp rather than
    adding a new column.
  - retirement audit trail (reason/who/when/prior state): stored inside
    the article's own existing market_context JSON column, additively --
    the article's original market_context is preserved alongside under
    the same key, nothing overwritten or lost. A brand new column would
    need a real ALTER TABLE migration this narrow fix doesn't need.

`status="retired"` (not a generic "unpublished"/"draft") is a deliberate
choice: these rows were withdrawn because their publication integrity
failed, not voluntarily unpublished drafts -- a real, distinct state
worth its own label for any future admin tooling/audit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle

RETIRED = "RETIRED"
WOULD_RETIRE = "WOULD_RETIRE"
SKIPPED_NOT_FOUND = "SKIPPED_NOT_FOUND"
SKIPPED_ALREADY_RETIRED = "SKIPPED_ALREADY_RETIRED"
SKIPPED_NOT_PUBLISHED = "SKIPPED_NOT_PUBLISHED"
SKIPPED_PROVENANCE_MISMATCH = "SKIPPED_PROVENANCE_MISMATCH"

RETIRED_STATUS = "retired"

# The exact real discriminator the provenance audit established and
# verified two independent ways (trigger_event_id prefix + slug suffix,
# 1:1 agreement across all 35 real market_wrap rows): only
# _build_scheduled_event() (publisher.py) ever produces a
# "scheduled-{article_type}-{date}" trigger_event_id. Anything else is a
# real provider-namespaced EventTriage id (nse-/rss-/...), i.e. came from
# the triage loop -- the P0-A bug's own contamination path.
_LEGITIMATE_SCHEDULED_PREFIX = "scheduled-"


@dataclass(frozen=True)
class RetirementDecision:
    outcome: str
    reason: str


def decide_retirement(
    *, found: bool, current_status: str | None, trigger_event_id: str | None, dry_run: bool,
) -> RetirementDecision:
    """The pure decision core -- given only an article's current real
    field values (never its headline/prose), decides what retire_article()
    should do. Deliberately separated from any DB/network access so the
    exact same decision logic can run two ways: (1) for real execution,
    fed by a live DB row inside retire_article() below; (2) for a
    read-only dry-run against real production data fetched over the API
    (scripts/retire_contaminated_market_wraps.py), which has no DB write
    access at all -- proving the same decision without ever being able to
    act on it."""
    if not found:
        return RetirementDecision(SKIPPED_NOT_FOUND, "no article exists with this id")
    if current_status == RETIRED_STATUS:
        return RetirementDecision(SKIPPED_ALREADY_RETIRED, "already retired -- idempotent no-op, not an error")
    if current_status != "published":
        return RetirementDecision(SKIPPED_NOT_PUBLISHED, f"current status is {current_status!r}, not 'published'")
    if not trigger_event_id or trigger_event_id.startswith(_LEGITIMATE_SCHEDULED_PREFIX):
        return RetirementDecision(
            SKIPPED_PROVENANCE_MISMATCH,
            f"trigger_event_id={trigger_event_id!r} matches the legitimate scheduled-wrap pattern (or is missing) "
            f"-- does NOT match confirmed contamination provenance; refusing to retire",
        )
    return RetirementDecision(
        WOULD_RETIRE if dry_run else RETIRED,
        f"published, trigger_event_id={trigger_event_id!r} confirms contamination provenance -- "
        f"{'would retire (dry run)' if dry_run else 'retiring'}",
    )


@dataclass(frozen=True)
class RetirementResult:
    article_id: str
    outcome: str
    reason: str
    prior_status: str | None = None
    prior_trigger_event_id: str | None = None


async def retire_article(
    db: AsyncSession, article_id: str, *, reason: str, retired_by: str, dry_run: bool = True,
) -> RetirementResult:
    """Real DB-session-based execution. Requires an explicit article_id
    (never discovers one). Idempotent: retiring an already-retired row is
    a clean no-op, not an error, and re-running with the same id/reason
    produces the same terminal state every time. Never deletes or
    rewrites article content -- only status/archived_at/market_context's
    additive "retirement" key change."""
    row = (await db.execute(
        select(IntelligenceArticle).where(IntelligenceArticle.id == article_id)
    )).scalar_one_or_none()

    decision = decide_retirement(
        found=row is not None,
        current_status=row.status if row else None,
        trigger_event_id=row.trigger_event_id if row else None,
        dry_run=dry_run,
    )

    if decision.outcome != RETIRED:
        return RetirementResult(
            article_id=article_id, outcome=decision.outcome, reason=decision.reason,
            prior_status=row.status if row else None,
            prior_trigger_event_id=row.trigger_event_id if row else None,
        )

    now = datetime.now(timezone.utc)
    prior_status = row.status
    prior_market_context = dict(row.market_context or {})
    prior_market_context["retirement"] = {
        "reason": reason,
        "retired_by": retired_by,
        "retired_at": now.isoformat(),
        "prior_status": prior_status,
        "prior_trigger_event_id": row.trigger_event_id,
    }

    row.status = RETIRED_STATUS
    row.archived_at = now
    row.market_context = prior_market_context
    await db.commit()

    return RetirementResult(
        article_id=article_id, outcome=RETIRED, reason=decision.reason,
        prior_status=prior_status, prior_trigger_event_id=row.trigger_event_id,
    )


async def retire_articles_batch(
    db: AsyncSession, article_ids: list[str], *, reason: str, retired_by: str, dry_run: bool = True,
) -> list[RetirementResult]:
    """Loops over an explicit, caller-supplied id list only -- never
    queries for candidates itself. One bad id's SKIPPED result never
    stops the rest of the batch."""
    return [
        await retire_article(db, aid, reason=reason, retired_by=retired_by, dry_run=dry_run)
        for aid in article_ids
    ]

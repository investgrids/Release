"""
Current Intelligence dedup follow-up (2026-09-26) — one-time backfill for
AICompanySignal rows created before the event_id column existed.

Not a migration framework, same convention as opportunity_v2/slug_backfill.py's
own "real backfill module, run once" pattern: every row with event_id IS NULL
gets one derived from its real source — article.trigger_event_id for
source_type="article", or the linked opportunity's highest-importance real
OpportunityEvent.event_id for source_type="opportunity" (same derivation
extract_company_signals()/extract_opportunity_signals() apply to new rows
going forward — see company_score_engine.py).

Without this, EVERY signal row written before this fix shipped keeps
event_id=NULL forever and is treated as "no known event lineage" — meaning
any duplicate-event double-counting that already exists in production data
today (confirmed real via a 2026-09-26 measurement: 128 real duplicate-
event groups in the local dev DB) continues uncorrected for those specific
rows until either (a) this backfill runs, or (b) the old rows' contribution
decays toward zero via the existing 21-day recency half-life — the displayed
signal_count/contributing_signal_count would still overstate evidence volume
indefinitely either way, only the weighted score itself fades.

Safe to re-run: only touches rows where event_id IS NULL, so a second run
against a mostly-backfilled table is a near no-op. A row whose real source
no longer exists (e.g. a since-deleted article) or whose source never had
a real event link (no trigger_event_id, no linked OpportunityEvent) is
left as NULL — never guessed.

Not wired into any endpoint, scheduler job, or CI step. This module exists
to be reviewed and run deliberately (a real, one-off maintenance script
invocation, per this project's own production-write-discipline precedent
— commit, review, then a captured/logged execution, never ad hoc), not as
part of this session's read-only verification pass.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_signal import AICompanySignal
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.opportunity import OpportunityEvent


async def backfill_company_signal_event_ids(db: AsyncSession, batch_size: int = 500) -> dict:
    rows = (await db.execute(
        select(AICompanySignal).where(AICompanySignal.event_id.is_(None))
    )).scalars().all()

    article_ids = {r.source_id for r in rows if r.source_type == "article"}
    opportunity_ids = {int(r.source_id) for r in rows if r.source_type == "opportunity" and r.source_id.isdigit()}

    trigger_by_article: dict[str, str | None] = {}
    if article_ids:
        trigger_by_article = dict((await db.execute(
            select(IntelligenceArticle.id, IntelligenceArticle.trigger_event_id)
            .where(IntelligenceArticle.id.in_(article_ids))
        )).all())

    # Same "highest-importance linked event, tie-broken by event_id" rule
    # extract_opportunity_signals() applies to new rows.
    primary_event_by_opportunity: dict[int, str] = {}
    if opportunity_ids:
        oe_rows = (await db.execute(
            select(OpportunityEvent.opportunity_id, OpportunityEvent.event_id, OpportunityEvent.importance)
            .where(OpportunityEvent.opportunity_id.in_(opportunity_ids))
        )).all()
        grouped: dict[int, list[tuple[float, str]]] = {}
        for opp_id, event_id, importance in oe_rows:
            grouped.setdefault(opp_id, []).append((importance or 0.0, event_id))
        for opp_id, candidates in grouped.items():
            candidates.sort(key=lambda t: (-t[0], t[1]))
            primary_event_by_opportunity[opp_id] = candidates[0][1]

    updated = 0
    skipped_no_real_lineage = 0
    for i, row in enumerate(rows):
        if row.source_type == "article":
            event_id = trigger_by_article.get(row.source_id)
        elif row.source_type == "opportunity" and row.source_id.isdigit():
            event_id = primary_event_by_opportunity.get(int(row.source_id))
        else:
            event_id = None

        if event_id:
            row.event_id = event_id
            updated += 1
        else:
            skipped_no_real_lineage += 1

        if (i + 1) % batch_size == 0:
            await db.commit()

    if updated:
        await db.commit()

    return {
        "candidates": len(rows),
        "updated": updated,
        "skipped_no_real_lineage": skipped_no_real_lineage,
    }

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


async def _derive_event_ids(db: AsyncSession, rows: list[AICompanySignal]) -> dict[int, str | None]:
    """Pure derivation, no writes — the same real lineage rule new rows get
    automatically. Returns {row.id: derived_event_id_or_None}."""
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

    derived: dict[int, str | None] = {}
    for row in rows:
        if row.source_type == "article":
            derived[row.id] = trigger_by_article.get(row.source_id)
        elif row.source_type == "opportunity" and row.source_id.isdigit():
            derived[row.id] = primary_event_by_opportunity.get(int(row.source_id))
        else:
            derived[row.id] = None
    return derived


class _Shadow:
    """A read-only stand-in carrying every field _dedupe_signals_by_event
    reads — including from its unresolved_lineage report branch — used so
    the conflict simulation below never mutates a real ORM row (which
    could otherwise get flushed by an unrelated autoflush)."""
    __slots__ = ("id", "source_type", "source_id", "event_id", "signed_magnitude", "confidence", "quality", "reason")

    def __init__(self, row: AICompanySignal, event_id_override: str | None = None):
        self.id = row.id
        self.source_type = row.source_type
        self.source_id = row.source_id
        self.event_id = event_id_override if event_id_override is not None else row.event_id
        self.signed_magnitude = row.signed_magnitude
        self.confidence = row.confidence
        self.quality = row.quality
        self.reason = row.reason


async def backfill_company_signal_event_ids(db: AsyncSession, batch_size: int = 500, dry_run: bool = False) -> dict:
    """dry_run=True computes and reports everything a real run would do —
    including which symbols would newly develop a conflicting-direction
    event group once lineage is restored (see _dedupe_signals_by_event) —
    without writing anything at all. dry_run=False (the real run) performs
    the exact same derivation and commits it."""
    from app.services.aipe.company_score_engine import _dedupe_signals_by_event

    rows = (await db.execute(
        select(AICompanySignal).where(AICompanySignal.event_id.is_(None))
    )).scalars().all()
    derived = await _derive_event_ids(db, rows)

    resolvable = sum(1 for r in rows if derived[r.id])
    unresolved = len(rows) - resolvable

    # Newly-introduced conflicting-direction groups: for every symbol with
    # at least one resolvable candidate row, simulate applying the derived
    # event_id (via read-only shadow copies, never the real ORM rows) and
    # compare against the conflicts that already exist today among rows
    # that already carry a real event_id — so this reports only what the
    # backfill itself would newly surface, not pre-existing conflicts.
    affected_symbols = {r.symbol for r in rows if derived[r.id]}
    newly_conflicting_symbols: list[str] = []
    if affected_symbols:
        all_rows = (await db.execute(
            select(AICompanySignal).where(AICompanySignal.symbol.in_(affected_symbols))
        )).scalars().all()
        by_symbol: dict[str, list[AICompanySignal]] = {}
        for r in all_rows:
            by_symbol.setdefault(r.symbol, []).append(r)

        for symbol, symbol_rows in by_symbol.items():
            before_shadows = [_Shadow(r) for r in symbol_rows if r.event_id]
            _, _, before_conflicts = _dedupe_signals_by_event(before_shadows)

            after_shadows = [_Shadow(r, derived.get(r.id)) for r in symbol_rows if r.event_id or derived.get(r.id)]
            _, _, after_conflicts = _dedupe_signals_by_event(after_shadows)

            if len(after_conflicts) > len(before_conflicts):
                newly_conflicting_symbols.append(symbol)

    result: dict = {
        "candidates": len(rows),
        "resolvable": resolvable,
        "unresolved_no_real_lineage": unresolved,
        "symbols_with_new_conflicting_groups": newly_conflicting_symbols,
        "symbols_with_new_conflicting_groups_count": len(newly_conflicting_symbols),
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    for i, row in enumerate(rows):
        if derived[row.id]:
            row.event_id = derived[row.id]
        if (i + 1) % batch_size == 0:
            await db.commit()
    if resolvable:
        await db.commit()

    return result

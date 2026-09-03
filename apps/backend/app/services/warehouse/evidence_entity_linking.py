"""
Evidence -> Entity linking (Warehouse Consumption Phase 2, "the major
unlock", owner decision 2026-08-25). See app/db/models/evidence_entity_
link.py's own docstring for the full architecture rationale.

Scope, deliberately narrow: NSE only, relationship_type="subject",
resolution_method="source_symbol". NSE's raw payload carries the filing's
own `symbol` (or `bm_symbol` for board meetings) directly, confirmed live
against real production data before this was built -- every NSE raw item
sampled had a real, present symbol field. This is the one real,
deterministic, no-AI-involved link available today; RSS/RBI/PIB/SEBI/Fed
evidence is left entirely unlinked, not guessed at, because none of those
producers currently expose anything a real resolver could use safely.

Resolution goes through app.services.company_identity.resolver.
resolve_identifier() -- the SAME resolver AI Search's entity_resolver.py
already uses, not a second, independent matching scheme. Only a real
ResolutionStatus.RESOLVED (unambiguous, sourced alias match) becomes a
link; UNRESOLVED and CONFLICT are both left unlinked rather than guessed
-- an evidence item with no entity is honest; a wrongly-linked one is
exactly the failure mode this whole effort exists to prevent.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.services.company_identity.resolver import ResolutionStatus, resolve_identifier

log = structlog.get_logger(__name__)


def extract_nse_symbol(raw: dict) -> str | None:
    """The real symbol field an NSE raw item carries, across its three
    real sub-kinds -- confirmed live against real production payloads:
    plain announcements and corporate actions both use `symbol`; board
    meetings use `bm_symbol` instead (same field-name split raw_evidence.
    py's own _extract_external_id/_extract_title already handle for this
    exact reason)."""
    kind = raw.get("_kind")
    if kind == "board_meeting":
        return raw.get("bm_symbol") or None
    return raw.get("symbol") or None


async def link_nse_evidence_to_entity(
    db: AsyncSession, raw_evidence_id: str, raw: dict,
) -> EvidenceEntityLink | None:
    """Resolve and persist the one real, deterministic link this source
    can support. Returns the created link, or None if nothing was linked
    (no symbol on this item, or the resolver couldn't unambiguously
    resolve it) -- never raises past a resolution failure, since an
    evidence item that can't be linked yet must not block being captured
    at all."""
    symbol = extract_nse_symbol(raw)
    if not symbol:
        return None

    try:
        result = await resolve_identifier(db, symbol)
    except Exception as exc:
        log.warning("warehouse.entity_link.resolve_failed", symbol=symbol, error=str(exc)[:160])
        return None

    if result.status != ResolutionStatus.RESOLVED:
        return None

    link = EvidenceEntityLink(
        raw_evidence_id=raw_evidence_id, entity_id=result.entity_id,
        relationship_type="subject", resolution_method="source_symbol",
        confidence=None,
    )
    db.add(link)
    return link


async def backfill_nse_entity_links(db: AsyncSession) -> dict:
    """One-time (re-runnable) pass over existing NSE raw_evidence rows
    that have no link yet. Deterministic only -- an item the resolver
    can't unambiguously resolve is left unlinked, not guessed, matching
    the owner's explicit instruction: 'if the entity cannot be established
    confidently, leave unlinked. That's better than contaminating the
    Warehouse.' Safe to re-run: the identity UniqueConstraint on
    EvidenceEntityLink means an already-linked item is simply skipped by
    the existing-ids check below, never double-linked."""
    import json

    from app.db.models.raw_evidence import RawEvidence

    already_linked = set((await db.execute(select(EvidenceEntityLink.raw_evidence_id))).scalars().all())

    rows = (await db.execute(
        select(RawEvidence.id, RawEvidence.raw_payload).where(RawEvidence.source_type == "nse")
    )).all()

    attempted = 0
    linked = 0
    skipped_already_linked = 0
    skipped_no_symbol = 0
    skipped_unresolved = 0
    skipped_conflict = 0
    skipped_parse_error = 0

    for row_id, raw_payload in rows:
        if row_id in already_linked:
            skipped_already_linked += 1
            continue
        attempted += 1
        try:
            raw = json.loads(raw_payload) if raw_payload else {}
        except (TypeError, ValueError):
            skipped_parse_error += 1
            continue

        symbol = extract_nse_symbol(raw)
        if not symbol:
            skipped_no_symbol += 1
            continue

        result = await resolve_identifier(db, symbol)
        if result.status == ResolutionStatus.RESOLVED:
            db.add(EvidenceEntityLink(
                raw_evidence_id=row_id, entity_id=result.entity_id,
                relationship_type="subject", resolution_method="source_symbol",
                confidence=None,
            ))
            linked += 1
        elif result.status == ResolutionStatus.CONFLICT:
            skipped_conflict += 1
        else:
            skipped_unresolved += 1

    if linked:
        await db.commit()

    summary = {
        "candidates": len(rows), "already_linked": skipped_already_linked,
        "attempted": attempted, "linked": linked,
        "skipped_no_symbol": skipped_no_symbol,
        "skipped_unresolved": skipped_unresolved,
        "skipped_conflict": skipped_conflict,
        "skipped_parse_error": skipped_parse_error,
    }
    log.info("warehouse.entity_link.backfill_complete", **summary)
    return summary

"""
Identifier resolver — turns a raw ticker-like string into a real
CompanyEntity, or explicitly refuses to.

This module only ever READS CompanyEntity/CompanyAlias. It never creates a
row. That split is deliberate and is the actual fix for the bug class C1
found: `IGNode` auto-creation (and anything else that meets an unfamiliar
ticker) used to just make a new node on the spot. Here, an identifier that
classifies as company-shaped but has no matching alias comes back
UNRESOLVED, not auto-created — only app.services.company_identity.importer,
fed by a real sourced universe file (NSE's EQUITY_L.csv / symbolchange.csv),
is allowed to create CompanyEntity rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity, CompanyAlias
from app.services.company_identity.classifier import (
    IdentifierType, classify_identifier, normalize_identifier,
)


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    NOT_A_COMPANY = "not_a_company"   # classified as index/commodity/fx/bond/unknown — never looked up
    UNRESOLVED = "unresolved"         # company-shaped, but no matching alias exists yet
    CONFLICT = "conflict"             # matched aliases point at more than one currently-valid entity


@dataclass
class ResolutionResult:
    status: ResolutionStatus
    identifier_type: IdentifierType
    entity_id: str | None = None
    matched_alias_type: str | None = None
    candidate_entity_ids: tuple[str, ...] = ()


async def resolve_identifier(db: AsyncSession, raw: str) -> ResolutionResult:
    itype = classify_identifier(raw)
    if itype != IdentifierType.COMPANY:
        return ResolutionResult(status=ResolutionStatus.NOT_A_COMPANY, identifier_type=itype)

    norm = normalize_identifier(raw)
    if not norm:
        return ResolutionResult(status=ResolutionStatus.UNRESOLVED, identifier_type=itype)

    rows = (await db.execute(
        select(CompanyAlias).where(func.upper(CompanyAlias.alias_value) == norm)
    )).scalars().all()

    if not rows:
        return ResolutionResult(status=ResolutionStatus.UNRESOLVED, identifier_type=itype)

    # Prefer a currently-valid alias (valid_to IS NULL). A symbol can be a
    # real historical alias of one entity AND, in principle, later reused
    # by an unrelated one — resolving to "whichever currently claims it"
    # is correct; resolving to a long-dead historical holder when a live
    # one also matches would be wrong.
    current = [r for r in rows if r.valid_to is None]
    pool = current if current else rows
    distinct_entities = {r.entity_id for r in pool}

    if len(distinct_entities) > 1:
        return ResolutionResult(
            status=ResolutionStatus.CONFLICT,
            identifier_type=itype,
            candidate_entity_ids=tuple(sorted(distinct_entities)),
        )

    match = pool[0]
    return ResolutionResult(
        status=ResolutionStatus.RESOLVED,
        identifier_type=itype,
        entity_id=match.entity_id,
        matched_alias_type=match.alias_type,
    )


async def get_entity(db: AsyncSession, entity_id: str) -> CompanyEntity | None:
    return await db.get(CompanyEntity, entity_id)

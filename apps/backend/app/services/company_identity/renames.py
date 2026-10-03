"""
Apply NSE symbol renames to the Company Master — narrowly, and only when the
identity is proven.

Why this exists (2026-10-03, HEG -> HEGAM): the Company Master is refreshed by
a manual bootstrap script, so a company renamed on NSE keeps its OLD symbol
until someone re-runs it. The page then asked the data providers for a ticker
that no longer exists and showed "HEG not found". A full re-import would also
create entities for every new listing (changing the directory and tiers), far
more than a rename fix should touch. This applies ONLY renames, through the
same upsert/alias code the full import uses, and only when:

  - an existing entity's CURRENT symbol is the old symbol of an NSE change,
  - NSE's equity master lists the (terminal) new symbol with the SAME ISIN as
    that entity — ISIN is the identity key, so a reused old symbol that now
    belongs to a different company is never renamed by mistake,
  - the new symbol isn't already another entity's.

Dry-run by default; the result lists every candidate with its action or the
reason it was skipped, so a run is its own audit record.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity
from app.services.company_identity.classifier import normalize_identifier
from app.services.company_identity.importer import (
    NseEqRow, SymbolChangeRow, apply_symbol_change_aliases, upsert_company_entities,
)


def _terminal_symbol(start: str, changes: list[SymbolChangeRow]) -> str:
    """Follow a rename chain (A->B, B->C) to its current symbol."""
    seen = {start}
    symbol = start
    while True:
        nxt = next((normalize_identifier(c.new_symbol) for c in changes if normalize_identifier(c.old_symbol) == symbol), None)
        if nxt is None or nxt in seen:
            return symbol
        seen.add(nxt)
        symbol = nxt


async def plan_verified_renames(
    db: AsyncSession, eq_rows: list[NseEqRow], change_rows: list[SymbolChangeRow],
) -> list[dict[str, Any]]:
    eq_by_symbol = {normalize_identifier(r.symbol): r for r in eq_rows}
    candidates: dict[str, SymbolChangeRow] = {}
    for c in change_rows:  # latest change per old symbol wins
        old = normalize_identifier(c.old_symbol)
        if old not in candidates or c.change_date > candidates[old].change_date:
            candidates[old] = c

    plan: list[dict[str, Any]] = []
    for old, change in sorted(candidates.items()):
        entity = (await db.execute(
            select(CompanyEntity).where(CompanyEntity.symbol == old, CompanyEntity.exchange == "NSE")
        )).scalars().first()
        if entity is None:
            continue  # not a company we hold under that symbol (never renamed, or already renamed)
        new = _terminal_symbol(normalize_identifier(change.new_symbol), change_rows)
        item: dict[str, Any] = {
            "old_symbol": old, "new_symbol": new, "isin": entity.isin,
            "change_date": change.change_date.isoformat(), "entity_id": entity.entity_id,
        }
        target = eq_by_symbol.get(new)
        if target is None:
            plan.append({**item, "action": "skip", "reason": "new symbol not in NSE's equity master"})
        elif not entity.isin or target.isin != entity.isin:
            plan.append({**item, "action": "skip", "reason": f"ISIN mismatch or missing (NSE lists {new} as {target.isin})"})
        elif (await db.execute(
            select(CompanyEntity.entity_id).where(CompanyEntity.symbol == new, CompanyEntity.exchange == "NSE")
        )).first() is not None:
            plan.append({**item, "action": "skip", "reason": "new symbol already belongs to another entity"})
        else:
            plan.append({**item, "action": "rename", "new_name": target.name, "_target": target, "_change": change})
    return plan


async def apply_verified_renames(
    db: AsyncSession, eq_rows: list[NseEqRow], change_rows: list[SymbolChangeRow], *, apply: bool = False,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """`only`: restrict what is APPLIED to these old symbols. The plan still
    lists every verified candidate, so a run shows what else is pending."""
    plan = await plan_verified_renames(db, eq_rows, change_rows)
    wanted = {normalize_identifier(s) for s in only} if only else None
    renames = [p for p in plan if p["action"] == "rename" and (wanted is None or p["old_symbol"] in wanted)]
    if apply and renames:
        await upsert_company_entities(db, [p["_target"] for p in renames])
        await apply_symbol_change_aliases(db, [p["_change"] for p in renames])
        await db.commit()
    public = [{k: v for k, v in p.items() if not k.startswith("_")} for p in plan]
    return {
        "applied": bool(apply and renames),
        "renames": len(renames),
        "pending_not_selected": sum(1 for p in plan if p["action"] == "rename") - len(renames),
        "skipped": sum(1 for p in plan if p["action"] == "skip"),
        "plan": public,
    }

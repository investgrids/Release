"""
V2 Promotion Blocker Remediation, Batch A — one-time backfill for
opportunities_v2 rows created before the slug column existed.

Not a migration framework, just an explicit, idempotent pass (same
convention as source_registry_seed.py/index_membership_seed.py's own
"real seed/backfill module, run once" pattern): every row with
slug IS NULL gets one computed via the same compute_opportunity_slug()
helper orchestration.py uses for new rows going forward, from whatever
real title info that row already has (current_title, else
formation_title, else thesis_anchor — never fabricated).

Safe to re-run: only touches rows where slug IS NULL, so a second run
against a mostly-backfilled table is a near no-op.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.opportunity_v2 import OpportunityV2
from app.services.opportunity_v2.slugs import compute_opportunity_slug


async def backfill_opportunity_v2_slugs(db: AsyncSession) -> dict:
    rows = (await db.execute(
        select(OpportunityV2).where(OpportunityV2.slug.is_(None))
    )).scalars().all()

    updated = 0
    for opp in rows:
        slug_base = opp.current_title or opp.formation_title or opp.thesis_anchor
        opp.slug = compute_opportunity_slug(opp.id, slug_base)
        updated += 1

    if updated:
        await db.commit()

    return {"candidates": len(rows), "updated": updated}

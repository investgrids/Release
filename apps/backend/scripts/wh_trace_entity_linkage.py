"""
Warehouse entity-linkage real-data demonstration — traces the full chain
Source -> RawEvidence -> EvidenceEntityLink -> Canonical CompanyEntity for
a named set of real companies, using only real, already-persisted data
(no synthetic rows, no re-running the backfill).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.raw_evidence import RawEvidence
from app.db.session import AsyncSessionLocal
from app.services.company_identity.resolver import resolve_identifier

SYMBOLS = ["ICICIBANK", "HDFCBANK", "TCS", "RELIANCE", "TMPV"]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for symbol in SYMBOLS:
            print(f"\n{'='*70}\n{symbol}\n{'='*70}")

            result = await resolve_identifier(db, symbol)
            print(f"Resolver: status={result.status.value} entity_id={result.entity_id} matched_alias_type={result.matched_alias_type}")

            if not result.entity_id:
                print("  -> No canonical entity resolved; cannot trace further.")
                continue

            entity = await db.get(CompanyEntity, result.entity_id)
            print(f"CompanyEntity: entity_id={entity.entity_id} name={entity.company_name!r} symbol={entity.symbol} isin={entity.isin}")

            aliases = (await db.execute(
                select(CompanyAlias).where(CompanyAlias.entity_id == entity.entity_id)
            )).scalars().all()
            print(f"Real aliases on this entity ({len(aliases)}): " + ", ".join(f"{a.alias_type}={a.alias_value}" for a in aliases[:8]))

            links = (await db.execute(
                select(EvidenceEntityLink).where(EvidenceEntityLink.entity_id == entity.entity_id)
            )).scalars().all()
            print(f"Real EvidenceEntityLink rows for this entity: {len(links)}")

            for link in links[:3]:
                ev = await db.get(RawEvidence, link.raw_evidence_id)
                if ev is None:
                    print(f"  link {link.id}: raw_evidence_id={link.raw_evidence_id} -> NOT FOUND (dangling)")
                    continue
                print(f"  link id={link.id} relationship={link.relationship_type} resolution={link.resolution_method}")
                print(f"    RawEvidence id={ev.id} source_type={ev.source_type} evidence_key={ev.evidence_key} external_id={ev.external_id}")
                print(f"    title: {ev.title}")
                print(f"    published_at={ev.published_at} observed_at={ev.observed_at}")

            if not links:
                # Real, honest reporting: is there ANY real_evidence for this
                # symbol at all that simply isn't linked (e.g. non-NSE source,
                # or NSE source without a resolvable symbol field)?
                raw_count = (await db.execute(
                    select(RawEvidence.id).where(RawEvidence.source_type == "nse")
                )).all()
                print(f"  (no links found; {len(raw_count)} total real NSE raw_evidence rows exist in this DB, unlinked to this symbol specifically)")


if __name__ == "__main__":
    asyncio.run(main())

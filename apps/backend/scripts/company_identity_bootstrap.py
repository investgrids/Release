"""
Production backfill tooling, prepared 2026-08-31 — the CompanyEntity/
CompanyAlias bootstrap has no existing standalone runner: `run_full_import()`
(app/services/company_identity/importer.py) has only ever been called from
tests. This is the missing, reusable script.

Fetches the two real, live NSE source files (EQUITY_L.csv,
symbolchange.csv) and calls run_full_import() with no series filter --
matching the real local dev DB this whole initiative (Company Identity
C1-C5, Company Page redesign, MarketRipple Score S1-S5E) has actually been
built and tested against: EQ + BE + BZ together, un-filtered
(`allowed_series=None`, the function's own default). The C1 reconciliation
audit measured 2,296 EQ-only rows; the real local dataset that resulted
from an unfiltered import is 2,557 entities / 3,053 aliases -- using a
narrower filter here would silently diverge from that already-validated
shape, not improve on it.

Idempotent by construction (see upsert_company_entities()'s own docstring)
-- safe to re-run against the same target DB; a rerun with unchanged NSE
source data creates zero new entities/aliases.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.company_identity.importer import run_full_import
from app.services.company_identity.live_source import fetch_nse_eq_csv, fetch_nse_symbolchange_csv


async def main() -> None:
    print("Fetching live NSE source files...")
    eq_csv = await fetch_nse_eq_csv()
    symbolchange_csv = await fetch_nse_symbolchange_csv()
    print(f"  EQUITY_L.csv: {len(eq_csv):,} bytes")
    print(f"  symbolchange.csv: {len(symbolchange_csv):,} bytes")

    async with AsyncSessionLocal() as db:
        result = await run_full_import(db, eq_csv, symbolchange_csv)
        await db.commit()

    print()
    print("=== Company Identity bootstrap result ===")
    for section, summary in result.items():
        print(f"{section}: {summary}")


if __name__ == "__main__":
    asyncio.run(main())

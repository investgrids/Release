"""
S4 — real backfill for the wider 27-bank universe (Quarterly only; Annual
skipped here since S3-B/C already found Advances/Deposits only 1 real year
deep even for the 5 reference banks — not needed for this experiment,
which is scoped to Gross NPA/Net NPA/CET1/ROA/ROE/NII growth/Profit
growth, matching S3-D's frozen metric set).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.financial_facts.ingest import ingest_period
from scripts.s4_bank_universe import ALL_BANKS, ORIGINAL_FIVE


async def main() -> None:
    to_backfill = [s for s in ALL_BANKS if s not in ORIGINAL_FIVE]  # the 5 are already real, backfilled in S3-C
    print(f"Backfilling {len(to_backfill)} real banks (the original 5 already have real S3-C data)")
    async with AsyncSessionLocal() as db:
        for symbol in to_backfill:
            try:
                result = await ingest_period(db, symbol, "Quarterly", real_quarters=4)
                print(f"{symbol:<12} {result}")
            except Exception as e:
                print(f"{symbol:<12} ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())

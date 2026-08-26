"""
S3-C — real, multi-period five-bank backfill. Run manually
(`python scripts/financial_facts_backfill.py`); writes real FinancialFact
rows for the 5 MarketRipple Score reference banks, both Quarterly (CET1/
NPA/ROA) and Annual (Advances/Deposits) periods. Not wired into any
scheduler — a manual, inspectable backfill tool, same phase-lock
discipline as the rest of this initiative.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.financial_facts.ingest import ingest_period

REFERENCE_BANKS = ["ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN"]


async def main() -> None:
    totals = {"populated": 0, "tag_missing": 0, "source_unavailable": 0, "parse_failed": 0, "anomaly": 0}
    async with AsyncSessionLocal() as db:
        for symbol in REFERENCE_BANKS:
            for period_type, real_quarters in [("Quarterly", 4), ("Annual", 3)]:
                result = await ingest_period(db, symbol, period_type, real_quarters=real_quarters)
                print(f"{symbol:<12} {period_type:<10} {result}")
                for k in totals:
                    totals[k] += result.get(k, 0)

    print()
    print("Totals across all 5 banks, both period types:", totals)


if __name__ == "__main__":
    asyncio.run(main())

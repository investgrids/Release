"""
S4.5 — retroactive plausibility backfill. The 27-bank real S4 dataset was
ingested before quality.assess_plausibility() existed, so it needs a
one-time pass to apply the same check the real ingestion pipeline now runs
automatically going forward. Updates ONLY quality_status/quality_reason on
existing rows that are currently OK (never touches a row already flagged
ANOMALY, never touches `value` — the real, as-filed number is never
altered). Real DB, real rows, no synthetic data.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.financial_fact import EXTRACTION_POPULATED, FinancialFact, QUALITY_OK
from app.services.financial_facts import quality


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(FinancialFact).where(
                FinancialFact.extraction_status == EXTRACTION_POPULATED,
                FinancialFact.quality_status == QUALITY_OK,
            )
        )).scalars().all()

        changed = []
        for row in rows:
            new_status, new_reason = quality.assess_plausibility(row.metric_code, row.value)
            if new_status != QUALITY_OK:
                changed.append((row.symbol, row.metric_code, row.fiscal_year, row.fiscal_quarter, row.value, new_status, new_reason))
                row.quality_status = new_status
                row.quality_reason = new_reason

        await db.commit()

        print(f"Scanned {len(rows)} real POPULATED+OK rows. Retroactively flagged {len(changed)}:\n")
        for symbol, code, fy, fq, value, status, reason in changed:
            print(f"  {symbol:<12} {code:<16} FY{fy}Q{fq or '-'}  value={value}  -> {status}")
            print(f"    reason: {reason}")


if __name__ == "__main__":
    asyncio.run(main())

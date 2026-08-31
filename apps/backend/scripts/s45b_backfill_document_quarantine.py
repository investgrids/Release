"""
S4.5-B — retroactive filing-level quarantine backfill. The 8 real YESBANK
cet1_ratio rows already flagged IMPLAUSIBLE_SCALE (S4.5 backfill) each
belong to a real source document; this propagates
QUALITY_SOURCE_DOCUMENT_QUARANTINED to every OTHER currently-OK metric
from those SAME real documents (gross_npa_pct, net_npa_pct, roa) — never
touching `value`, never touching rows from a different document/scope.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.financial_fact import FinancialFact, QUALITY_IMPLAUSIBLE_SCALE
from app.services.financial_facts import quality


async def main() -> None:
    async with AsyncSessionLocal() as db:
        triggers = (await db.execute(
            select(FinancialFact.symbol, FinancialFact.source_provider, FinancialFact.source_document_id, FinancialFact.consolidation_scope)
            .where(FinancialFact.quality_status == QUALITY_IMPLAUSIBLE_SCALE)
            .distinct()
        )).all()

        print(f"Found {len(triggers)} real document(s) with a structural-failure trigger:\n")
        total_quarantined = 0
        for symbol, provider, doc_id, scope in triggers:
            n = await quality.quarantine_document_if_needed(db, symbol, provider, doc_id, scope)
            print(f"  {symbol:<12} doc={provider}:{doc_id} scope={scope} -> {n} metric(s) newly quarantined")
            total_quarantined += n

        await db.commit()
        print(f"\nTotal newly quarantined: {total_quarantined}")

        # Real, itemized confirmation — never trust the count alone.
        print("\n=== Real rows now SOURCE_DOCUMENT_QUARANTINED ===\n")
        rows = (await db.execute(
            select(FinancialFact.symbol, FinancialFact.metric_code, FinancialFact.fiscal_year, FinancialFact.fiscal_quarter, FinancialFact.value, FinancialFact.quality_status)
            .where(FinancialFact.quality_status == "SOURCE_DOCUMENT_QUARANTINED")
        )).all()
        for symbol, code, fy, fq, value, status in rows:
            print(f"  {symbol:<12} {code:<16} FY{fy}Q{fq or '-'}  value={value}  status={status}")


if __name__ == "__main__":
    asyncio.run(main())

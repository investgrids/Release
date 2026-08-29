"""
S4.5 — real per-metric percentile check for YESBANK, post-plausibility-fix.
YESBANK's own FinStr score rose (52.8 -> 61.6) after excluding its
implausible CET1 — need to confirm whether that's because its OTHER real
FinancialFact-sourced metrics (gross_npa_pct, net_npa_pct, roa) are ALSO
implausibly favorable (same underlying scale-error filer) and are scoring
near the top of the peer percentile purely because "lower NPA / higher ROA
looks better" under the frozen percentile formula — a real, disclosed gap
in the current plausibility bounds (only CET1 has a hard regulatory floor
today), not a new bug.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.financial_strength import _FACT_METRICS, _latest_valid_fact_value
from app.services.marketripple_score.valuation import _percentile_rank


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for code, higher_is_better in _FACT_METRICS:
            values = {}
            for s in ALL_ELIGIBLE_NSE_BANKS:
                v = await _latest_valid_fact_value(db, s, code)
                if v is not None:
                    values[s] = v
            pctile = _percentile_rank(values, "YESBANK", cheaper_is_better=not higher_is_better)
            print(f"{code:<16} YESBANK real value={values.get('YESBANK')!r}  peer_pool_size={len(values)}  YESBANK_percentile={pctile}")
            ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=higher_is_better)
            print(f"  worst-3 real values in pool: {ordered[-3:]}")
            print(f"  best-3 real values in pool:  {ordered[:3]}")


if __name__ == "__main__":
    asyncio.run(main())

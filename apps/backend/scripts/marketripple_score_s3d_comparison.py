"""
S3-D — real five-bank rerun using the FinancialFact-sourced Financial
Strength pillar (Gross NPA/Net NPA/CET1/ROA real, anomaly-excluded) plus
the unchanged Valuation/Market Behaviour/Current Intelligence pillars.
Manual, local-only, publishable stays False. Prints the exact per-bank
decomposition and S2->S3-D comparison the owner asked for.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.engine import compute_marketripple_score

REFERENCE_BANKS = ["ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN"]

# Real S2 results (artifacts/marketripple_score_s2_five_bank_comparison.md),
# reproduced here only for the comparison table — not recomputed.
S2_SCORES = {"ICICIBANK": 65.4, "HDFCBANK": 51.0, "AXISBANK": 41.4, "KOTAKBANK": 42.3, "SBIN": 55.7}

_FACT_LABELS = [
    ("gross_npa_pct", "Gross NPA", 100),
    ("net_npa_pct", "Net NPA", 100),
    ("cet1_ratio", "CET1", 100),
    ("roa", "ROA", 100),
    ("roe", "ROE", 100),
    ("nii_growth_pct", "NII Growth", 1),
    ("profit_growth_pct", "Profit Growth", 1),
]


async def main() -> None:
    results = {}
    async with AsyncSessionLocal() as db:
        for symbol in REFERENCE_BANKS:
            results[symbol] = await compute_marketripple_score(db, symbol)

    for symbol in REFERENCE_BANKS:
        r = results[symbol]
        fs = r.pillars["financial_strength"]
        print(f"\n{symbol}")
        print("Financial Strength")
        d = fs.detail
        for key, label, mult in _FACT_LABELS:
            raw = d.get(key)
            if raw is None:
                print(f"  {label:<15} n/a")
                continue
            shown = raw * 100 if mult == 100 else raw
            unit = "%" if mult == 100 or key.endswith("_pct") else ""
            print(f"  {label:<15} {shown:.2f}{unit}")
        print("                  " + "-" * 6)
        print(f"Financial Score   {fs.score}")
        print(f"  (coverage {fs.coverage_pct}%)")
        print()
        print(f"Valuation         {r.pillars['valuation'].score}")
        print(f"Market Behaviour  {r.pillars['market_behaviour'].score}")
        print(f"Current Intel     {r.pillars['current_intelligence'].score}")
        print()
        print(f"MarketRipple      {r.score}")
        print(f"Coverage          {r.overall_coverage_pct}%")
        print(f"Publishable       {r.publishable}")

    print("\n\n=== S2 -> S3-D comparison ===")
    print(f"{'Symbol':<12}{'S2':>8}{'S3-D':>8}{'Change':>9}")
    for symbol in REFERENCE_BANKS:
        s2 = S2_SCORES[symbol]
        s3d = results[symbol].score
        change = round(s3d - s2, 1) if s3d is not None else None
        sign = "+" if change is not None and change >= 0 else ""
        print(f"{symbol:<12}{s2:>8}{s3d:>8}{sign}{change:>8}")


if __name__ == "__main__":
    asyncio.run(main())

"""
S2-D — private five-bank candidate-score evaluation. Run manually
(`python scripts/marketripple_score_five_bank_comparison.py`), reads real
data only, writes nothing. Produces the exact breakdown table the owner
asked for so the candidate weights/normalization can be sanity-checked
against real outputs before any Company-page change is considered.

Not wired into any API route or scheduler — this stays a manual, local
inspection tool until S2 is reviewed.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.engine import compute_marketripple_score

REFERENCE_BANKS = ["ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN"]


async def main() -> None:
    results = []
    async with AsyncSessionLocal() as db:
        for symbol in REFERENCE_BANKS:
            result = await compute_marketripple_score(db, symbol)
            results.append(result)

    print()
    header = f"{'Symbol':<12}{'Fin.Str':>9}{'Valuation':>11}{'Market':>9}{'Intel.':>9}{'MRScore':>10}  Label"
    print(header)
    print("-" * len(header))
    for r in results:
        fs = r.pillars["financial_strength"].score
        val = r.pillars["valuation"].score
        mkt = r.pillars["market_behaviour"].score
        ci = r.pillars["current_intelligence"].score
        print(
            f"{r.symbol:<12}"
            f"{fs if fs is not None else '—':>9}"
            f"{val if val is not None else '—':>11}"
            f"{mkt if mkt is not None else '—':>9}"
            f"{ci if ci is not None else '—':>9}"
            f"{r.score if r.score is not None else '—':>10}  {r.label}"
        )

    print()
    print("Coverage (%) per pillar, per symbol:")
    header2 = f"{'Symbol':<12}{'Fin.Str':>9}{'Valuation':>11}{'Market':>9}{'Intel.':>9}{'Overall':>10}"
    print(header2)
    print("-" * len(header2))
    for r in results:
        print(
            f"{r.symbol:<12}"
            f"{r.pillars['financial_strength'].coverage_pct:>9}"
            f"{r.pillars['valuation'].coverage_pct:>11}"
            f"{r.pillars['market_behaviour'].coverage_pct:>9}"
            f"{r.pillars['current_intelligence'].coverage_pct:>9}"
            f"{r.overall_coverage_pct:>10}"
        )

    print()
    print("Financial Strength real detail (ROE / ROA / NII growth / Profit growth / NIM-proxy-not-scored):")
    for r in results:
        d = r.pillars["financial_strength"].detail
        print(f"  {r.symbol:<12} ROE={d.get('roe')} ROA={d.get('roa')} "
              f"NII_growth={d.get('nii_growth_pct')}% Profit_growth={d.get('profit_growth_pct')}% "
              f"NIM_proxy={d.get('nim_proxy_pct')}%")

    print()
    print("Valuation real detail (PE / PB / peer percentiles / own historical range):")
    for r in results:
        d = r.pillars["valuation"].detail
        print(f"  {r.symbol:<12} PE={d.get('pe')} (pctile {d.get('pe_peer_percentile')}) "
              f"PB={d.get('pb')} (pctile {d.get('pb_peer_percentile')}) "
              f"own_hist_pctile: see historical_annual_pe={d.get('historical_annual_pe')}")

    print()
    print("Market Behaviour real detail (200DMA / 3m return / sector 3m / RSI):")
    for r in results:
        d = r.pillars["market_behaviour"].detail
        print(f"  {r.symbol:<12} price_vs_200dma={d.get('price_vs_200dma_pct')}% "
              f"own_3m={d.get('own_3m_return_pct')}% nifty_3m={d.get('nifty_3m_return_pct')}% "
              f"sector_3m={d.get('sector_3m_return_pct')}% RSI14={d.get('rsi_14')}")

    print()
    print(f"publishable for all 5: {[r.publishable for r in results]}")
    print()
    print("publish_reason (ICICIBANK, representative — identical phase-lock reason for all 5):")
    print(" ", results[0].publish_reason)


if __name__ == "__main__":
    asyncio.run(main())

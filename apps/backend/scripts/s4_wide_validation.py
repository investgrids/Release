"""
S4 — wider Banking validation. Frozen algorithm (S3-D), frozen weights —
this script only varies the real peer universe and reports on real
output, never tunes anything. Manual, local-only, publishable stays False
on every real computation.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.financial_fact import FinancialFact
from app.services.marketripple_score.engine import compute_marketripple_score
from app.services.marketripple_score.financial_strength import _FACT_METRICS
from scripts.s4_bank_universe import ALL_BANKS, BANK_TYPE, ORIGINAL_FIVE


async def _evidence_range(db, symbol: str) -> tuple[str | None, str | None, int]:
    rows = (await db.execute(
        select(FinancialFact.fiscal_year, FinancialFact.fiscal_quarter, FinancialFact.quality_status)
        .where(FinancialFact.symbol == symbol, FinancialFact.metric_code.in_([c for c, _ in _FACT_METRICS]))
    )).all()
    if not rows:
        return None, None, 0
    periods = sorted({(fy, fq or 0) for fy, fq, _ in rows})
    oldest = f"FY{periods[0][0]}Q{periods[0][1]}"
    newest = f"FY{periods[-1][0]}Q{periods[-1][1]}"
    anomalies = sum(1 for _, _, qs in rows if qs == "ANOMALY")
    return oldest, newest, anomalies


async def main() -> None:
    results_wide = {}
    async with AsyncSessionLocal() as db:
        for symbol in ALL_BANKS:
            try:
                results_wide[symbol] = await compute_marketripple_score(db, symbol, peer_group=ALL_BANKS)
            except Exception as e:
                print(f"{symbol} FAILED: {e}")

    print("\n=== S4 full table, 27-bank peer universe ===\n")
    header = f"{'Symbol':<12}{'Type':<18}{'FinStr':>7}{'Val':>6}{'Mkt':>6}{'Intel':>6}{'MRScore':>9}  {'Coverage':>9}  Publishable"
    print(header)
    print("-" * len(header))
    async with AsyncSessionLocal() as db:
        for symbol in ALL_BANKS:
            r = results_wide.get(symbol)
            if not r:
                continue
            fs = r.pillars["financial_strength"].score
            val = r.pillars["valuation"].score
            mkt = r.pillars["market_behaviour"].score
            ci = r.pillars["current_intelligence"].score
            print(
                f"{symbol:<12}{BANK_TYPE[symbol]:<18}"
                f"{fs if fs is not None else '—':>7}{val if val is not None else '—':>6}"
                f"{mkt if mkt is not None else '—':>6}{ci if ci is not None else '—':>6}"
                f"{r.score if r.score is not None else '—':>9}  {r.overall_coverage_pct:>8}%  {r.publishable}"
            )

    print("\n=== Real fact evidence per bank (oldest/newest scored period, anomalies) ===\n")
    async with AsyncSessionLocal() as db:
        for symbol in ALL_BANKS:
            oldest, newest, anomalies = await _evidence_range(db, symbol)
            ci_detail = results_wide[symbol].pillars["current_intelligence"].detail if symbol in results_wide else {}
            contributing = ci_detail.get("contributing_signal_count", "n/a")
            print(f"{symbol:<12} oldest={oldest} newest={newest} anomalies_in_window={anomalies} contributing_signals={contributing}")

    # Peer-universe sensitivity — original 5 under 5-bank vs 27-bank peer group
    print("\n=== Peer-universe sensitivity: original 5 banks, 5-bank vs 27-bank peer group ===\n")
    results_narrow = {}
    async with AsyncSessionLocal() as db:
        for symbol in ORIGINAL_FIVE:
            results_narrow[symbol] = await compute_marketripple_score(db, symbol, peer_group=None)  # production default = 5-bank

    print(f"{'Symbol':<12}{'FinStr(5)':>11}{'FinStr(27)':>12}{'Delta':>8}   {'MRScore(5)':>11}{'MRScore(27)':>13}{'Delta':>8}")
    for symbol in ORIGINAL_FIVE:
        n = results_narrow[symbol]
        w = results_wide[symbol]
        fs_n = n.pillars["financial_strength"].score
        fs_w = w.pillars["financial_strength"].score
        fs_delta = round(fs_w - fs_n, 1) if fs_n is not None and fs_w is not None else None
        mr_delta = round(w.score - n.score, 1) if n.score is not None and w.score is not None else None
        print(f"{symbol:<12}{fs_n:>11}{fs_w:>12}{fs_delta:>+8}   {n.score:>11}{w.score:>13}{mr_delta:>+8}")

    print("\nDone. publishable=False on every real computation above.")


if __name__ == "__main__":
    asyncio.run(main())

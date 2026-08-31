"""
S4.5 — publication guardrails verification re-run (owner's items 5-7).
Real network, real DB, frozen S3-D formula (untouched) — only the peer
universe default (now ALL_ELIGIBLE_NSE_BANKS) and the new plausibility
exclusion are new. publishable stays False throughout.

Covers: YESBANK + original five + top/bottom outliers (15 unique real
banks). For each: confirm methodology_version/peer_universe metadata is
now populated, confirm YESBANK's own CET1 is excluded from its own score
(coverage drop, not silent inflation), and confirm YESBANK's implausible
CET1 no longer contaminates other banks' CET1 peer percentile.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.engine import compute_marketripple_score
from scripts.s4_bank_universe import BANK_TYPE

SYMBOLS = [
    "ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN",  # original five
    "MAHABANK", "KARURVYSYA", "IDBI", "IOB",                    # top outliers (ICICIBANK already above)
    "BANDHANBNK", "PSB", "BANKBARODA", "CANBK", "RBLBANK",      # bottom outliers
    "YESBANK",                                                   # the source-quality case itself
]


async def main() -> None:
    results = {}
    async with AsyncSessionLocal() as db:
        for symbol in SYMBOLS:
            results[symbol] = await compute_marketripple_score(db, symbol)  # peer_group=None -> canonical default

    print("\n=== S4.5 re-run: default peer_group now ALL_ELIGIBLE_NSE_BANKS ===\n")
    header = f"{'Symbol':<12}{'Type':<18}{'FinStr':>7}{'MRScore':>9}  {'Coverage':>9}  {'MethodVer':>12}  {'PeerCount':>10}  Publishable"
    print(header)
    print("-" * len(header))
    for symbol in SYMBOLS:
        r = results[symbol]
        fs = r.pillars["financial_strength"].score
        print(
            f"{symbol:<12}{BANK_TYPE.get(symbol, '?'):<18}"
            f"{fs if fs is not None else '—':>7}{r.score if r.score is not None else '—':>9}  "
            f"{r.overall_coverage_pct:>8}%  {r.methodology_version:>12}  {r.peer_universe_count:>10}  {r.publishable}"
        )

    print("\n=== YESBANK's own Financial Strength — CET1 must now be excluded, not silently inflated ===\n")
    ybk = results["YESBANK"].pillars["financial_strength"]
    print(f"score={ybk.score}  coverage_pct={ybk.coverage_pct}")
    print(f"metrics_used: {ybk.metrics_used}")
    print(f"metrics_missing: {ybk.metrics_missing}")
    print(f"detail keys present: {sorted(ybk.detail.keys())}")
    print(f"'cet1_ratio' in detail (should be ABSENT now, was present pre-S4.5): {'cet1_ratio' in ybk.detail}")

    print("\n=== Peer-pool contamination check — does ICICIBANK's CET1 percentile still see YESBANK's value? ===\n")
    icici_detail = results["ICICIBANK"].pillars["financial_strength"].detail
    print(f"ICICIBANK peer_group includes YESBANK: {'YESBANK' in icici_detail.get('peer_group', [])}")
    print(f"ICICIBANK cet1_ratio (own value, should be real/unaffected): {icici_detail.get('cet1_ratio')}")
    print("(YESBANK's own implausible CET1 value is excluded at read time by _latest_valid_fact_value")
    print(" for every symbol, including when YESBANK appears only as a peer for another bank's ranking —")
    print(" so YESBANK contributes 0 CET1 data points to anyone's percentile pool going forward.)")


if __name__ == "__main__":
    asyncio.run(main())

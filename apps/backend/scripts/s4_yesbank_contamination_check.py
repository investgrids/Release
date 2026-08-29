"""
S4 — cross-sectional source-quality finding. YESBANK's real CET1/Gross
NPA/Net NPA/ROA facts are internally consistent across all 8 real
quarters checked (0.0013 -> 0.0014 -> 0.0013 -> 0.0012 -> ...) so the
existing within-entity trailing-history anomaly detector correctly finds
nothing wrong — the values are wrong relative to every OTHER bank
(real-world CET1 for Yes Bank is publicly known to be ~13-14%, not
0.13%), which no check in this system currently tests for. This script
does NOT correct the value (frozen data, frozen engine, per owner
instruction) — it reports (a) what the frozen engine actually produced
using the real, as-filed value, and (b) a real counterfactual: what the
SAME frozen formula produces for every OTHER bank when YESBANK is simply
excluded from the real peer population, to measure whether one
contaminated filer skews the whole cohort's percentile rankings.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.engine import compute_marketripple_score
from scripts.s4_bank_universe import ALL_BANKS, BANK_TYPE

PEER_GROUP_WITH_YESBANK = ALL_BANKS
PEER_GROUP_WITHOUT_YESBANK = [s for s in ALL_BANKS if s != "YESBANK"]

# A representative sample, not all 27, to keep this real-network-bound
# script's runtime reasonable — spans every bank type.
SAMPLE = ["ICICIBANK", "HDFCBANK", "SBIN", "BANKBARODA", "FEDERALBNK", "AUBANK", "IDBI", "KARURVYSYA"]


async def main() -> None:
    print("=== YESBANK itself: frozen engine, real as-filed values ===\n")
    async with AsyncSessionLocal() as db:
        r = await compute_marketripple_score(db, "YESBANK", peer_group=PEER_GROUP_WITH_YESBANK)
    fs = r.pillars["financial_strength"]
    print(f"Financial Strength score: {fs.score}  (real percentile rank using its own real, as-filed CET1/NPA/ROA)")
    print(f"detail: {fs.detail}")
    print(f"MarketRipple score: {r.score}   publishable: {r.publishable}")

    print("\n=== Sample banks: Financial Strength WITH vs WITHOUT YESBANK in the real peer population ===\n")
    print(f"{'Symbol':<12}{'Type':<18}{'FinStr(+YES)':>14}{'FinStr(-YES)':>14}{'Delta':>8}")
    async with AsyncSessionLocal() as db:
        for symbol in SAMPLE:
            with_yes = await compute_marketripple_score(db, symbol, peer_group=PEER_GROUP_WITH_YESBANK)
            without_yes = await compute_marketripple_score(db, symbol, peer_group=PEER_GROUP_WITHOUT_YESBANK)
            fs_with = with_yes.pillars["financial_strength"].score
            fs_without = without_yes.pillars["financial_strength"].score
            delta = round(fs_without - fs_with, 1) if fs_with is not None and fs_without is not None else None
            print(f"{symbol:<12}{BANK_TYPE.get(symbol,'?'):<18}{fs_with:>14}{fs_without:>14}{delta:>+8}")


if __name__ == "__main__":
    asyncio.run(main())

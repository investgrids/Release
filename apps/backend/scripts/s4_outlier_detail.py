"""
S4 — outlier-test evidence pull for the top/bottom banks not yet detailed
(MAHABANK, KARURVYSYA, BANDHANBNK, PSB were already pulled). Read-only,
frozen engine, real peer_group=ALL_BANKS (27-bank universe) — matches the
main S4 run exactly, just re-fetching per-metric raw detail for the report.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.engine import compute_marketripple_score
from scripts.s4_bank_universe import ALL_BANKS, BANK_TYPE

# Top-5 remaining (MAHABANK, KARURVYSYA already done) + bottom-5 remaining
# (BANDHANBNK, PSB already done), per the 27-bank MRScore ranking.
BANKS = ["MAHABANK", "KARURVYSYA", "BANDHANBNK", "PSB"]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for symbol in BANKS:
            r = await compute_marketripple_score(db, symbol, peer_group=ALL_BANKS)
            fs = r.pillars["financial_strength"]
            print(f"\n=== {symbol} ({BANK_TYPE.get(symbol, '?')}) — MRScore={r.score} FinStr={fs.score} ===")
            print(f"detail: {fs.detail}")


if __name__ == "__main__":
    asyncio.run(main())

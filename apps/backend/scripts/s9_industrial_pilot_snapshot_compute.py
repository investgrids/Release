"""
S9 — compute + persist real MarketRippleScoreSnapshot rows for a small,
cross-sector pilot set of the NS1 Non-Banking Industrial cohort (owner
instruction 2026-09-27): one company each from Technology, FMCG,
Automotive, Pharmaceuticals, Chemicals, Consumer, Metals — the 7 measured,
supported sectors. Calls the real, unmodified compute_and_persist_snapshot()
verbatim, same as the Banking pilot's own s8 script. publishable stays
exactly what engine.py's S2 phase lock decides (False) for every sector —
this script makes zero publication decisions.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot

# One real, well-known, currently-listed company per NS1 sector.
PILOT_SYMBOLS: dict[str, str] = {
    "Technology": "TCS",
    "FMCG": "HINDUNILVR",
    "Automotive": "MARUTI",
    "Pharmaceuticals": "SUNPHARMA",
    "Chemicals": "PIDILITIND",
    "Consumer": "TITAN",
    "Metals": "TATASTEEL",
}


async def main() -> None:
    for sector, symbol in PILOT_SYMBOLS.items():
        print(f"=== {sector}: {symbol} (fetches live yfinance data for {symbol} + its real sector peers) ===")
        try:
            async with AsyncSessionLocal() as db:
                snap = await compute_and_persist_snapshot(db, symbol)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            continue
        print(f"  id={snap.id} score={snap.score} rating={snap.rating} publishable={snap.publishable} "
              f"methodology={snap.methodology_version} peer_count={snap.peer_universe_count}")
        print(f"  financial_strength={snap.financial_strength} valuation={snap.valuation} "
              f"market_behaviour={snap.market_behaviour} current_intelligence={snap.current_intelligence}")
        print(f"  coverage_pct={snap.coverage_pct} financial_coverage_pct={snap.financial_coverage_pct}")
        print(f"  financial_metrics_used_count={snap.financial_metrics_used_count}/{snap.financial_metrics_total_count}")
        print(f"  financial_data_as_of={snap.financial_data_as_of}")
        print(f"  publication_policy_version={snap.publication_policy_version} "
              f"publication_block_reasons={snap.publication_block_reasons}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

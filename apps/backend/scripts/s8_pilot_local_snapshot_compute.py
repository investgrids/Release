"""
S8 — compute + persist real MarketRippleScoreSnapshot rows for the two
pilot banks (ICICIBANK, KOTAKBANK), against whatever database this script
is run against (the local ig_dev.db when run locally, per this session's
own confirmed DATABASE_URL). Calls the real, frozen compute_and_persist_snapshot()
verbatim -- no new scoring logic, no peer_group override (default
ALL_ELIGIBLE_NSE_BANKS, matching the real S4.5 methodology), no fixtures.

publishable stays exactly what engine.py's S2 phase lock decides
(hardcoded False) -- this script makes zero publication decisions.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot

SYMBOLS = ["ICICIBANK", "KOTAKBANK"]


async def main() -> None:
    for symbol in SYMBOLS:
        print(f"=== Computing {symbol} (this fetches live yfinance data for {symbol} + 26 real peers -- may take a while) ===")
        async with AsyncSessionLocal() as db:
            snap = await compute_and_persist_snapshot(db, symbol)
        print(f"  id={snap.id} score={snap.score} rating={snap.rating} publishable={snap.publishable}")
        print(f"  financial_strength={snap.financial_strength} valuation={snap.valuation} "
              f"market_behaviour={snap.market_behaviour} current_intelligence={snap.current_intelligence}")
        print(f"  coverage_pct={snap.coverage_pct} financial_coverage_pct={snap.financial_coverage_pct}")
        print(f"  financial_metrics_used_count={snap.financial_metrics_used_count}/{snap.financial_metrics_total_count}")
        print(f"  financial_data_as_of={snap.financial_data_as_of}")
        print(f"  pillar_coverage_status={snap.pillar_coverage_status} ({snap.pillar_coverage_message})")
        print(f"  publication_policy_version={snap.publication_policy_version} "
              f"publication_block_reasons={snap.publication_block_reasons}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

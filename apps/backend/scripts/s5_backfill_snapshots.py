"""
S5-A — real backfill run: compute_and_persist_snapshot() for every real
bank in ALL_ELIGIBLE_NSE_BANKS, proving the snapshot persistence path
works end-to-end against real network + real DB, not just unit tests.
publishable stays False throughout (the frozen S2 phase lock, unchanged
by S5-A — S5-A only adds persistence, not a publication decision).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot, get_latest_snapshot


async def main() -> None:
    print(f"=== S5-A real snapshot backfill: {len(ALL_ELIGIBLE_NSE_BANKS)} real banks ===\n")
    header = f"{'Symbol':<12}{'EntityID':<14}{'Score':>7}{'FinData':>10}  {'MethodVer':>12}  {'Publishable'}"
    print(header)
    print("-" * len(header))
    for symbol in ALL_ELIGIBLE_NSE_BANKS:
        async with AsyncSessionLocal() as db:
            snap = await compute_and_persist_snapshot(db, symbol)
        print(
            f"{snap.symbol:<12}{(snap.entity_id or '—'):<14}{snap.score if snap.score is not None else '—':>7}"
            f"{(snap.financial_data_as_of or '—'):>10}  {snap.methodology_version:>12}  {snap.publishable}"
        )

    # Real read-path proof: get_latest_snapshot must return exactly what
    # was just persisted, with zero additional network calls.
    print("\n=== Real read-path check (no network, DB only) ===\n")
    async with AsyncSessionLocal() as db:
        latest = await get_latest_snapshot(db, "ICICIBANK")
    print(f"ICICIBANK latest snapshot: score={latest.score} calculated_at={latest.calculated_at} id={latest.id}")


if __name__ == "__main__":
    asyncio.run(main())

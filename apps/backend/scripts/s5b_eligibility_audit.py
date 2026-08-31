"""
S5-B — real 27-bank publication verification, post-BANKING_V1_P1
decision. Reads the real, already-persisted snapshots (zero new network
calls) and confirms the real per-bank publication_block_reasons match
what the policy should produce -- verified, not just asserted.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS


async def main() -> None:
    async with AsyncSessionLocal() as db:
        snapshots = {}
        for symbol in ALL_ELIGIBLE_NSE_BANKS:
            row = (await db.execute(
                select(MarketRippleScoreSnapshot)
                .where(MarketRippleScoreSnapshot.symbol == symbol)
                .order_by(MarketRippleScoreSnapshot.calculated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if row:
                snapshots[symbol] = row

    print(f"=== S5-B real verification: BANKING_V1_P1, {len(snapshots)} real banks ===\n")
    header = (
        f"{'Symbol':<12}{'FinMetrics':>12}{'Overall%':>10}  {'FinDataAsOf':>12}  "
        f"{'PolicyVer':>14}  {'Eligible':>9}  Reasons"
    )
    print(header)
    print("-" * len(header))

    eligible_count = 0
    blocked = []
    for symbol in ALL_ELIGIBLE_NSE_BANKS:
        s = snapshots.get(symbol)
        if not s:
            print(f"{symbol:<12} NO SNAPSHOT")
            continue
        reasons = s.publication_block_reasons or []
        eligible = len(reasons) == 0
        if eligible:
            eligible_count += 1
        else:
            blocked.append(symbol)
        print(
            f"{symbol:<12}{s.financial_metrics_used_count!s:>7}/{s.financial_metrics_total_count!s:<4}"
            f"{s.coverage_pct:>10.1f}  {(s.financial_data_as_of or '—'):>12}  "
            f"{(s.publication_policy_version or '—'):>14}  {'Y' if eligible else 'N':>9}  {reasons}"
        )

    print(f"\nReal result: {eligible_count}/{len(snapshots)} eligible under BANKING_V1_P1. Blocked: {blocked}")
    print("Expected (owner): 25 eligible, 2 blocked (YESBANK, INDUSINDBK).")
    print(f"Match: {eligible_count == 25 and set(blocked) == {'YESBANK', 'INDUSINDBK'}}")

    print(f"\npublishable (standing phase lock) on every row: {set(s.publishable for s in snapshots.values())}")


if __name__ == "__main__":
    asyncio.run(main())

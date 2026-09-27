"""
S8-b — detail-only report: calls compute_marketripple_score() directly
(NOT compute_and_persist_snapshot) so it does not add another snapshot
row -- purely to surface the full per-metric metrics_used/metrics_missing
breakdown for the Financial Strength pillar, which the persisted
MarketRippleScoreSnapshot row does not retain (only aggregate counts).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.engine import compute_marketripple_score

SYMBOLS = ["ICICIBANK", "KOTAKBANK"]


async def main() -> None:
    for symbol in SYMBOLS:
        print(f"=== {symbol} — Financial Strength pillar detail ===")
        async with AsyncSessionLocal() as db:
            result = await compute_marketripple_score(db, symbol)
        fs = result.pillars["financial_strength"]
        print(f"  score={fs.score}  coverage_pct={fs.coverage_pct}  status={fs.status}")
        print(f"  metrics_used ({len(fs.metrics_used)}):")
        for m in fs.metrics_used:
            print(f"    - {m}")
        print(f"  metrics_missing ({len(fs.metrics_missing)}):")
        for m in fs.metrics_missing:
            print(f"    - {m}")
        print(f"  per-metric provenance: {fs.detail.get('metrics')}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

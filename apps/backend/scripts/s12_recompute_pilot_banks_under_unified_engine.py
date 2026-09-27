"""
S12 — recompute the two real pilot banks (ICICIBANK, KOTAKBANK) under the
unified MARKETRIPPLE_SCORE_V1 engine (owner instruction, 2026-09-27, "one
score calculation"). Real, deliberate consequence: both banks previously
had Current Intelligence data too thin to reach Banking's old 4-of-4
requirement, so neither ever got a headline number under BANKING_V1 --
under the new shared 3-required-pillar rule they should now get a real
one. No live yfinance disambiguation needed for 2 symbols, so this is a
plain per-symbol compute_and_persist_snapshot() call, not a shared-fetch
batch like s11.

Usage: python scripts/s12_recompute_pilot_banks_under_unified_engine.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot

PILOT_BANKS = ["ICICIBANK", "KOTAKBANK"]


async def main() -> None:
    for symbol in PILOT_BANKS:
        async with AsyncSessionLocal() as db:
            snap = await compute_and_persist_snapshot(db, symbol)
        print(
            f"{symbol}: methodology={snap.methodology_version} score={snap.score} rating={snap.rating} "
            f"pillar_status={snap.pillar_coverage_status} pillars="
            f"fs={snap.financial_strength} val={snap.valuation} mkt={snap.market_behaviour} ci={snap.current_intelligence} "
            f"fs_metrics={snap.financial_metrics_used_count}/{snap.financial_metrics_total_count} "
            f"coverage={snap.coverage_pct} eligible_reasons={snap.publication_block_reasons}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())

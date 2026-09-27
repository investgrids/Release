"""
S13 — recompute every real NONBANK_INDUSTRIAL_SECTORS company under the
unified MARKETRIPPLE_SCORE_V1 engine (owner instruction, 2026-09-27, "one
score calculation"). The per-company Financial Strength/Valuation/Market
Behaviour formulas and weights are UNCHANGED for non-bank sectors (V2's
3-pillar/8:4:3 rule is exactly what the unified engine now uses for
everyone) -- this run exists purely so every company's LATEST snapshot
carries the new single methodology tag get_latest_snapshot() now requires,
not because the non-bank numbers themselves should change. Loops
s11_shared_fetch_sector_backfill.py's own real per-sector shared-fetch
batch across every sector in one run, sector by sector, so it can be
kicked off once and left running rather than invoked 19 separate times.

Usage: python scripts/s13_recompute_all_sectors_under_unified_engine.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS
from scripts.s11_shared_fetch_sector_backfill import main as run_sector


async def main() -> None:
    for i, sector in enumerate(NONBANK_INDUSTRIAL_SECTORS, 1):
        print(f"\n########## SECTOR {i}/{len(NONBANK_INDUSTRIAL_SECTORS)}: {sector} ##########", flush=True)
        try:
            await run_sector(sector, set())
        except Exception as e:
            print(f"SECTOR {sector} FAILED: {type(e).__name__}: {e}", flush=True)
    print("\n=== ALL SECTORS COMPLETE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

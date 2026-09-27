"""
S10 — real, full local backfill of the Technology sector (NS1 cohort),
skipping TCS (already computed via s9's pilot run). Same per-symbol error-
handling pattern as marketripple_score_production_backfill.py's own
hardened Banking backfill: one symbol failing (yfinance timeout, a
genuinely delisted/renamed ticker, etc.) logs the error and continues,
never aborts the whole run. Local DB only, publishable stays False for
every row (S2 phase lock, untouched) -- this script makes zero publication
decisions.

Prints progress after EVERY symbol (not just at the end) so a long-running
background execution can be monitored via its own output file.
"""
from __future__ import annotations

import asyncio
import sys
import time

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.sector_universe import sector_peer_universe
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot

ALREADY_DONE = {"TCS"}  # s9's pilot run


async def main() -> None:
    universe = sector_peer_universe("Technology")
    todo = [s for s in universe if s not in ALREADY_DONE]
    print(f"=== Technology sector full backfill: {len(todo)} companies to go "
          f"(skipping {sorted(ALREADY_DONE)}, already computed) ===\n")

    succeeded, failed = 0, []
    for i, symbol in enumerate(todo, 1):
        t0 = time.monotonic()
        try:
            async with AsyncSessionLocal() as db:
                snap = await compute_and_persist_snapshot(db, symbol)
            elapsed = time.monotonic() - t0
            print(f"[{i}/{len(todo)}] {symbol}: score={snap.score} rating={snap.rating} "
                  f"fs_metrics={snap.financial_metrics_used_count}/{snap.financial_metrics_total_count} "
                  f"coverage={snap.coverage_pct} eligible_reasons={snap.publication_block_reasons} "
                  f"({elapsed:.0f}s)", flush=True)
            succeeded += 1
        except Exception as e:
            elapsed = time.monotonic() - t0
            print(f"[{i}/{len(todo)}] {symbol}: ERROR {type(e).__name__}: {e} ({elapsed:.0f}s)", flush=True)
            failed.append((symbol, str(e)))

    print(f"\n=== Done: {succeeded}/{len(todo)} succeeded ===")
    if failed:
        print(f"{len(failed)} failed (real errors, not silently skipped):")
        for symbol, err in failed:
            print(f"  {symbol}: {err}")


if __name__ == "__main__":
    asyncio.run(main())

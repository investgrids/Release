"""
S11 — shared-fetch sector backfill (NS1 round 2, owner instruction
2026-09-27). Replaces s10's per-company-independent-fetch approach, which
had every company in a sector re-fetch that sector's ENTIRE peer
population from scratch (O(N) real network calls per company, O(N^2) per
sector) -- a real, found-live inefficiency that made a 32-company sector
take ~34 minutes at ~64s/company and meaningfully raised the odds of
yfinance throttling along the way.

This script fetches each sector's real peer/benchmark data ONCE:
  - financial_strength_industrial.py's real financials/balance_sheet
    inputs for every company in the sector,
  - valuation.py's real PE/PB/ROE snapshot for every company,
  - the real NIFTY and (if mapped) sector-ETF daily closes, once each,

then computes and persists a real snapshot for every company using that
one shared cache via compute_and_persist_snapshot's own industrial_cache
parameter -- same real yfinance data, fetched once instead of once per
company. Each company's own daily price history (market_behaviour) and
own historical EPS series (valuation) are still fetched per-company,
since those were never redundant across companies to begin with.

Per-symbol failures are logged and do not abort the run (same discipline
as marketripple_score_production_backfill.py's own hardened Banking
backfill). Reports how many companies end with a real numeric score, a
partial (no headline number but real per-pillar data), or no usable data
at all -- per the owner's explicit reporting requirement.

Usage: python scripts/s11_shared_fetch_sector_backfill.py <Sector> [--skip SYM1,SYM2]
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.financial_strength_industrial import prefetch_industrial_inputs
from app.services.marketripple_score.market_behaviour import (
    _NIFTY_TICKER, _SECTOR_ETFS, _SECTOR_LABEL_TO_ETF_KEY, _fetch_daily_closes_sync,
)
from app.services.marketripple_score.sector_universe import sector_peer_universe
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot
from app.services.marketripple_score.valuation import prefetch_valuation_snapshots


async def _prefetch_benchmarks(sector: str) -> dict[str, list[float]]:
    loop = asyncio.get_event_loop()
    sector_ticker = _SECTOR_ETFS.get(_SECTOR_LABEL_TO_ETF_KEY.get(sector, sector))
    tickers = [_NIFTY_TICKER] + ([sector_ticker] if sector_ticker else [])
    fetched = await asyncio.gather(*[loop.run_in_executor(None, _fetch_daily_closes_sync, t) for t in tickers])
    return dict(zip(tickers, fetched))


async def main(sector: str, skip: set[str]) -> None:
    universe = sector_peer_universe(sector)
    todo = [s for s in universe if s not in skip]
    print(f"=== {sector}: shared-fetch backfill, {len(todo)} companies "
          f"(real universe size {len(universe)}, skipping {sorted(skip) or 'none'}) ===\n")

    print("Step 1/4: prefetching real financial_strength_industrial inputs for the whole sector once...")
    financial_inputs = await prefetch_industrial_inputs(universe)
    print(f"  done — {sum(1 for v in financial_inputs.values() if v)} of {len(universe)} symbols returned real data\n")

    print("Step 2/4: prefetching real valuation (PE/PB/ROE) snapshots for the whole sector once...")
    valuation_snapshots = await prefetch_valuation_snapshots(universe)
    print(f"  done — {sum(1 for v in valuation_snapshots.values() if v.get('pe') or v.get('pb'))} of {len(universe)} symbols have a real PE/PB\n")

    print("Step 3/4: prefetching real NIFTY + sector-ETF benchmarks once...")
    benchmarks = await _prefetch_benchmarks(sector)
    for ticker, closes in benchmarks.items():
        print(f"  {ticker}: {len(closes)} real daily closes")
    print()

    industrial_cache = {
        "financial_inputs": financial_inputs,
        "valuation_snapshots": valuation_snapshots,
        "benchmarks": benchmarks,
    }

    print(f"Step 4/4: computing + persisting {len(todo)} real snapshots using the shared cache...\n")
    numeric, partial, unusable, errors = [], [], [], []
    for i, symbol in enumerate(todo, 1):
        try:
            async with AsyncSessionLocal() as db:
                snap = await compute_and_persist_snapshot(db, symbol, industrial_cache=industrial_cache)
        except Exception as e:
            print(f"[{i}/{len(todo)}] {symbol}: ERROR {type(e).__name__}: {e}", flush=True)
            errors.append((symbol, str(e)))
            continue

        if snap.score is not None:
            numeric.append(symbol)
            bucket = "NUMERIC"
        elif snap.financial_strength is not None or snap.valuation is not None or snap.market_behaviour is not None or snap.current_intelligence is not None:
            partial.append(symbol)
            bucket = "PARTIAL (real per-pillar data, no headline number)"
        else:
            unusable.append(symbol)
            bucket = "NO USABLE DATA"

        print(f"[{i}/{len(todo)}] {symbol}: {bucket} — score={snap.score} "
              f"fs_metrics={snap.financial_metrics_used_count}/{snap.financial_metrics_total_count} "
              f"coverage={snap.coverage_pct} eligible_reasons={snap.publication_block_reasons}", flush=True)

    print(f"\n=== {sector} backfill complete ===")
    print(f"  numeric score:     {len(numeric)}  {numeric}")
    print(f"  partial (no headline number): {len(partial)}  {partial}")
    print(f"  no usable data:    {len(unusable)}  {unusable}")
    print(f"  errors:            {len(errors)}  {[s for s, _ in errors]}")
    for s, err in errors:
        print(f"    {s}: {err}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/s11_shared_fetch_sector_backfill.py <Sector> [--skip SYM1,SYM2]")
        sys.exit(1)
    sector_arg = sys.argv[1]
    skip_arg: set[str] = set()
    if "--skip" in sys.argv:
        idx = sys.argv.index("--skip")
        skip_arg = set(sys.argv[idx + 1].split(","))
    asyncio.run(main(sector_arg, skip_arg))

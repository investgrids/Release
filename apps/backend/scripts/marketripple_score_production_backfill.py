"""
Production backfill tooling, prepared 2026-08-31 — a hardened variant of
S5-A's `s5_backfill_snapshots.py` for unattended production use.

The original S5-A script (left untouched -- it already did its real job,
proving the persistence path works end-to-end, and is part of the closed
S5-A/S5-E validation lineage) has no per-bank error handling: one bank
throwing (e.g. a yfinance timeout -- valuation/market_behaviour are "pure
yfinance" per engine.py's own comment) aborts the whole loop and leaves
every subsequent bank in ALL_ELIGIBLE_NSE_BANKS unattempted for that run.
`scripts/s4_backfill_wide_universe.py` already established the right
pattern for this class of problem (wrap each symbol, log the error, keep
going) -- this script applies that same pattern here, matching the
production-backfill readiness audit's finding.

publishable stays exactly what compute_marketripple_score() /
evaluate_eligibility() decide -- this script makes zero publication
decisions and does not touch the S2 phase lock.

Idempotency note: compute_and_persist_snapshot() is INSERT-ONLY by design
(a new row per call, history is kept -- see snapshot.py's own docstring).
Re-running this script is safe for correctness (get_latest_snapshot()
always reads the newest row) but not free -- each run adds one row per
bank rather than overwriting. Don't loop this unattended; run it once per
intended backfill/refresh, the same discipline S5-A itself already used.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot


async def main() -> None:
    print(f"=== MarketRipple Score production backfill: {len(ALL_ELIGIBLE_NSE_BANKS)} real banks ===\n")
    header = f"{'Symbol':<12}{'EntityID':<14}{'Score':>7}{'FinData':>10}  {'MethodVer':>12}  {'Publishable'}"
    print(header)
    print("-" * len(header))

    succeeded = 0
    failed: list[tuple[str, str]] = []

    for symbol in ALL_ELIGIBLE_NSE_BANKS:
        try:
            async with AsyncSessionLocal() as db:
                snap = await compute_and_persist_snapshot(db, symbol)
            print(
                f"{snap.symbol:<12}{(snap.entity_id or '—'):<14}{snap.score if snap.score is not None else '—':>7}"
                f"{(snap.financial_data_as_of or '—'):>10}  {snap.methodology_version:>12}  {snap.publishable}"
            )
            succeeded += 1
        except Exception as e:
            print(f"{symbol:<12} ERROR: {e}")
            failed.append((symbol, str(e)))

    print()
    print(f"=== {succeeded}/{len(ALL_ELIGIBLE_NSE_BANKS)} banks succeeded ===")
    if failed:
        print(f"{len(failed)} bank(s) failed and were skipped (rerun this script to retry just these, or all):")
        for symbol, err in failed:
            print(f"  {symbol}: {err}")


if __name__ == "__main__":
    asyncio.run(main())

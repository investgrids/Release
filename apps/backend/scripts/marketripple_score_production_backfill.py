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

2026-08-31 addition -- fail-closed publication-lock preflight: before
writing anything, this script computes one real score (no persistence)
and asserts publishable is False, straight from the same
compute_marketripple_score() code path every real snapshot write goes
through -- not a second, independently-hardcoded flag that could drift
out of sync with the real one. engine.py hardcodes publishable=False
unconditionally in both its return paths today (S2 phase lock, owner
decision 2026-08-25), so this should always pass; if it doesn't, that
means the lock itself has changed since this tooling was written, which
is exactly the moment an unattended backfill must refuse to proceed
rather than assume nothing changed.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.engine import compute_marketripple_score
from app.services.marketripple_score.snapshot import compute_and_persist_snapshot


class PublicationLockViolation(RuntimeError):
    pass


async def _preflight_publication_lock() -> None:
    """Real, no-persistence check against the actual scoring code path.
    Uses the first bank in ALL_ELIGIBLE_NSE_BANKS -- any real symbol works,
    since engine.py's publishable=False is unconditional, not
    symbol-dependent."""
    probe_symbol = ALL_ELIGIBLE_NSE_BANKS[0]
    print(f"Preflight: verifying the S2 publication lock is still in place (probe symbol: {probe_symbol})...")
    async with AsyncSessionLocal() as db:
        result = await compute_marketripple_score(db, probe_symbol)
    if result.publishable is not False:
        raise PublicationLockViolation(
            f"REFUSING TO RUN: compute_marketripple_score({probe_symbol}) returned "
            f"publishable={result.publishable!r}, not the expected False. The S2 phase "
            "lock (engine.py) appears to have changed since this backfill tooling was "
            "written -- this script makes zero publication decisions of its own and will "
            "not write any snapshot until a human confirms this is an intended, deliberate "
            "unlock, not a regression."
        )
    print("Preflight OK: publication lock confirmed in place (publishable=False). Proceeding.\n")


async def main() -> None:
    await _preflight_publication_lock()

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

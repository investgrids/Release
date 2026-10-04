"""
Run one filing-backed score refresh as its own process (never inside the web worker):

    python -m app.tasks.filing_score_refresh [--activate] [--symbols A,B,C] [--no-behaviour]

Writes one immutable run (filing_score_runs / filing_score_snapshots). Activation is guarded (see runner.MIN_RATIO_OF_ACTIVE). Not scheduled anywhere, and no page
reads the result unless the reader flag is on.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from app.db.session import AsyncSessionLocal
from app.services.filing_score import runner
from app.services.filing_score.live_collector import LiveCollector


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--activate", action="store_true")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--no-behaviour", action="store_true", help="skip the market-behaviour pillar (those companies are then withheld)")
    ap.add_argument("--raw-dir", default=None, help="optional folder to cache raw filings (not the database)")
    args = ap.parse_args(argv)
    if hasattr(os, "nice"):
        try:
            os.nice(10)   # background work must not starve the web worker
        except OSError:
            pass
    if not runner.acquire_lock():
        print(json.dumps({"status": "skipped", "reason": "another filing_score_refresh is running"}))
        return 2
    try:
        async with AsyncSessionLocal() as db:
            universe = await runner.load_universe(db)
            if args.symbols:
                want = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
                universe = [c for c in universe if c.symbol in want]
            out = await runner.run_refresh(db, LiveCollector(raw_dir=args.raw_dir, market_behaviour=not args.no_behaviour), trigger="manual", universe=universe,
                                           activate=args.activate)
            await db.commit()
        print(json.dumps(out, default=str))
        return 0 if out["status"] == "complete" else 1
    finally:
        runner.release_lock()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""
Entry point for one MarketRipple Score refresh, run as its own process
(started by app.services.marketripple_score.refresh.start_refresh_process —
the admin endpoint and the weekly scheduler job). See refresh.py for why this
must never run inside a web worker.

Usage: python scripts/run_marketripple_score_refresh.py [--no-banks] [--sectors Technology,FMCG]
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, ".")

from app.services.marketripple_score.refresh import _lock_path, refresh_all_scores  # noqa: E402


def main() -> None:
    print(f"refresh process {os.getpid()} starting", flush=True)
    if hasattr(os, "nice"):
        os.nice(10)  # web workers keep CPU priority
    lock = _lock_path()
    lock.write_text(str(os.getpid()))  # also covers a manual CLI run
    try:
        sectors = sys.argv[sys.argv.index("--sectors") + 1].split(",") if "--sectors" in sys.argv else None
        asyncio.run(refresh_all_scores(include_banks="--no-banks" not in sys.argv, sectors=sectors))
    finally:
        try:
            if lock.read_text().strip() == str(os.getpid()):
                lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()

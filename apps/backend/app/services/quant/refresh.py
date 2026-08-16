"""
Incremental daily refresh — Phase 2B §4/§20.

Same backfill_symbol()/upsert_price_bars() path as the historical
backfill (app/services/quant/backfill.py) — a daily refresh is not a
different mechanism, just a short `period`. Reusing `period="5d"`
(rather than `period="1d"`) so a missed run (weekend/holiday/scheduler
downtime) self-heals on the next run instead of leaving a permanent
gap — the upsert is idempotent, so re-fetching a few already-stored
days is cheap and safe (Phase 2B §3's own idempotency guarantee).

Scheduling (Phase 2A §20 decision): post-close, in the open window
after 16:00 IST where only job_evaluate_predictions runs today (Phase
2A §20's own finding) — registered in app/scheduler/scheduler.py as
`quant_price_refresh`, 16:30 IST, i.e. after evaluate_predictions
(16:00) so a same-day price bar is available for tomorrow's baseline
generation without competing with that job for yfinance calls at the
same instant.
"""
from __future__ import annotations

import structlog

from app.db.session import AsyncSessionLocal
from app.services.quant.backfill import backfill_universe
from app.services.quant.universe import NIFTY_50

log = structlog.get_logger(__name__)


async def run_daily_refresh() -> dict:
    async with AsyncSessionLocal() as db:
        result = await backfill_universe(db, list(NIFTY_50), period="5d", delay_sec=0.4)
    log.info(
        "quant.daily_refresh.done",
        succeeded=result["succeeded"], failed=result["failed"],
        bars_inserted=result["total_bars_inserted"], bars_updated=result["total_bars_updated"],
    )
    return result

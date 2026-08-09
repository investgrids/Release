"""Protected operational endpoints — admin-key gated, not for end users.

Distinct from /api/publishing (ops dashboard, its own admin-gated endpoints
for content review) — this is infra/db status, for spotting misconfigurations
like an unmounted volume before they cause data loss.
"""
from __future__ import annotations

import pathlib

from fastapi import APIRouter, Depends

from app.core.security import require_admin_key

router = APIRouter()


@router.get("/db-status", dependencies=[Depends(require_admin_key)])
async def db_status_endpoint():
    from app.db.session import engine
    from app.db.health import db_status
    return await db_status(engine)


# ── TEMPORARY — one-off 429 backlog reset ──────────────────────────────────
# Trigger for scripts/reset_429_backlog.py: that script can't run via
# `railway run` (it executes locally; production is SQLite on a Railway
# volume, /data/ig.db, unreachable except from inside the container), so
# this route runs the identical scoped-reset logic in-process instead. Not
# meant to outlive the backfill — remove this block and the script together
# once the AFTER snapshot confirms the reset landed.
_RESET_IDS_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "reset_429_backlog_ids.txt"


async def _reset_429_snapshot(db, event_ids: list[str], label: str) -> dict:
    from sqlalchemy import select
    from app.db.models.event import Event

    result = await db.execute(
        select(Event.id, Event.enrichment_status, Event.impact_score)
        .where(Event.id.in_(event_ids))
    )
    found = {r.id: (r.enrichment_status, r.impact_score) for r in result.all()}

    by_status: dict[str, int] = {}
    for status, score in found.values():
        key = f"{status} (scored)" if score is not None else f"{status} (null)"
        by_status[key] = by_status.get(key, 0) + 1

    return {
        "label": label,
        "requested": len(event_ids),
        "found_in_db": len(found),
        "missing": len(event_ids) - len(found),
        "by_status": by_status,
    }, found


@router.post("/reset-429-backlog", dependencies=[Depends(require_admin_key)])
async def reset_429_backlog_endpoint():
    from app.db.session import AsyncSessionLocal
    from app.db.models.event import Event

    event_ids = [
        line.strip() for line in _RESET_IDS_PATH.read_text().splitlines() if line.strip()
    ]

    async with AsyncSessionLocal() as db:
        before, before_found = await _reset_429_snapshot(db, event_ids, "before")

        not_null_score = [eid for eid, (_, score) in before_found.items() if score is not None]
        to_reset = [eid for eid, (status, score) in before_found.items() if score is None and status != "pending"]

        updated = 0
        if to_reset:
            await db.execute(
                Event.__table__.update()
                .where(Event.id.in_(to_reset))
                .values(enrichment_status="pending")
            )
            await db.commit()
            updated = len(to_reset)

        after, _ = await _reset_429_snapshot(db, event_ids, "after")

    return {
        "before": before,
        "updated_done_to_pending": updated,
        "already_scored_skipped": len(not_null_score),
        "after": after,
    }

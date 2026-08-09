"""
One-off, scoped backfill: reset enrichment_status to "pending" for exactly the
event IDs confirmed via Railway log cross-reference to have failed enrichment
solely because of OpenRouter 429 rate-limiting (2026-08-08 10:30 UTC through
2026-08-09 08:08 UTC), now that AI_PROVIDER has been switched to Gemini.

Deliberately NOT a blanket `WHERE impact_score IS NULL` reset: the same
insufficient_data/score=None shape can also come from a genuinely low-evidence
event (no companies/sectors/historical match, even with AI working) or a
different bug entirely (one event in this same window failed with an
unrelated AttributeError, not a 429 — excluded from this list). Only event
IDs whose pipeline run had an immediately-preceding 429 in the logs, and
nothing else, are included.

Run once via: railway run -s backend -- python scripts/reset_429_backlog.py
Safe to re-run: only touches enrichment_status, and only for IDs already
sitting at "done" with a null score (skips anything already reprocessed).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

EVENT_IDS = [
    line.strip()
    for line in (pathlib.Path(__file__).parent / "reset_429_backlog_ids.txt").read_text().splitlines()
    if line.strip()
]


async def _snapshot(db, label: str) -> dict[str, tuple[str, float | None]]:
    from sqlalchemy import select
    from app.db.models.event import Event

    result = await db.execute(
        select(Event.id, Event.enrichment_status, Event.impact_score)
        .where(Event.id.in_(EVENT_IDS))
    )
    found = {r.id: (r.enrichment_status, r.impact_score) for r in result.all()}

    by_status: dict[str, int] = {}
    for status, score in found.values():
        key = f"{status} (scored)" if score is not None else f"{status} (null)"
        by_status[key] = by_status.get(key, 0) + 1

    print(f"--- {label} --- requested={len(EVENT_IDS)} found_in_db={len(found)} missing={len(EVENT_IDS) - len(found)}")
    for key, count in sorted(by_status.items()):
        print(f"  {key}: {count}")
    return found


async def main():
    from app.db.session import AsyncSessionLocal
    from app.db.models.event import Event

    async with AsyncSessionLocal() as db:
        before = await _snapshot(db, "BEFORE")

        not_null_score = [eid for eid, (_, score) in before.items() if score is not None]
        to_reset = [eid for eid, (status, score) in before.items() if score is None and status != "pending"]

        if not_null_score:
            print(f"NOTE - {len(not_null_score)} already have a real score, left untouched:", not_null_score[:10])

        if to_reset:
            await db.execute(
                Event.__table__.update()
                .where(Event.id.in_(to_reset))
                .values(enrichment_status="pending")
            )
            await db.commit()
            print(f"Updated {len(to_reset)} rows: enrichment_status done/failed -> pending")
        else:
            print("Nothing to reset (all targets already pending or already scored).")

        await _snapshot(db, "AFTER")


if __name__ == "__main__":
    asyncio.run(main())

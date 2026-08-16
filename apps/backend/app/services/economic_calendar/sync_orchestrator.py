"""
Phase 5A.6 — shared sync hardening: one orchestration path every source
runs through, plus source-health/staleness visibility. Nothing here
duplicates sync_engine.py's per-row upsert logic (identity, tier
precedence, versioning stay there) — this module is about the RUN as a
whole: counting outcomes, logging a health summary, and answering
"which sources are trustworthy right now" for a future scheduler or
API to read, without either of those existing yet (Phase 5A.7/5A.8).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.economic_calendar.sync_engine import CalendarCandidate, upsert_calendar_event

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SourceRegistration:
    run_name: str                       # distinct per scheduled run, for logging/health clarity
    categories: tuple[str, ...]         # EconomicCalendarEvent.category values this fetch produces
    fetch_fn: Callable[[], Awaitable[list[CalendarCandidate]]]


def _build_registry() -> tuple[SourceRegistration, ...]:
    """Deferred import — avoids importing every source module (and their
    own httpx/pypdf/zoneinfo setup) just for anything that only needs
    is_stale()/get_source_health(), and sidesteps any import-order
    fragility between this module and the source modules (which import
    CalendarCandidate from sync_engine.py, not from here)."""
    from app.services.economic_calendar.rbi_source import fetch_rbi_mpc_candidates
    from app.services.economic_calendar.mospi_source import fetch_mospi_candidates
    from app.services.economic_calendar.fed_source import fetch_fomc_candidates
    from app.services.economic_calendar.bls_source import fetch_us_cpi_candidates, fetch_us_jobs_candidates

    return (
        SourceRegistration("rbi", ("rbi_mpc",), fetch_rbi_mpc_candidates),
        SourceRegistration("mospi", ("india_cpi", "india_iip"), fetch_mospi_candidates),
        SourceRegistration("fed", ("fomc",), fetch_fomc_candidates),
        SourceRegistration("bls_cpi", ("us_cpi",), fetch_us_cpi_candidates),
        SourceRegistration("bls_jobs", ("us_jobs",), fetch_us_jobs_candidates),
    )

# The only source tags any real ingestion module is allowed to write.
# A consumer-facing read (Phase 5A.8's API) filters on this allowlist —
# not because anything currently writes an unlisted tag (nothing does),
# but so a future test fixture or seed script can use an out-of-list
# tag (e.g. "test") and know by construction it can never surface
# through a production read path, the same isolation guarantee this
# session's Phase 2 quant tables already rely on via `experimental`.
REAL_SOURCES = frozenset({"rbi", "mospi", "fed", "bls"})   # eurostat/ecb: see deferred_sources.py

# A source normally syncs once daily (Phase 5A §20's own recommendation,
# not yet scheduled — 5A.7). Missing one day is a blip; missing several
# in a row is worth surfacing as degraded rather than staying silent.
_STALE_AFTER_DAYS = 4


def _aware(dt: datetime) -> datetime:
    """Same SQLite naive-read-back normalization used throughout this
    package — see sync_engine.py's _aware for the full explanation."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_stale(last_verified_at: datetime, now: datetime | None = None, threshold_days: int = _STALE_AFTER_DAYS) -> bool:
    now = now or datetime.now(timezone.utc)
    return (now - _aware(last_verified_at)) > timedelta(days=threshold_days)


async def run_source_sync(source_name: str, fetch_fn: Callable[[], Awaitable[list[CalendarCandidate]]]) -> dict:
    """The one path every source's ingestion runs through. A fetch
    failure (fetch_fn returns []) is NOT treated as "nothing to do" —
    it's logged as its own outcome so a health check can tell "the
    source had zero real changes today" apart from "the source
    couldn't be reached today," which existing rows staying untouched
    (sync_engine's own guarantee, proven in the live test suite)
    doesn't by itself make visible to anything watching."""
    t0 = time.perf_counter()
    candidates = await fetch_fn()

    if not candidates:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        log.warning("economic_calendar.sync_run_empty", source=source_name, elapsed_ms=elapsed_ms)
        return {
            "source": source_name, "fetched": 0, "created": 0, "updated": 0,
            "unchanged": 0, "skipped_lower_tier": 0, "ok": False, "elapsed_ms": elapsed_ms,
        }

    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped_lower_tier": 0}
    async with AsyncSessionLocal() as db:
        for candidate in candidates:
            result = await upsert_calendar_event(db, candidate)
            counts[result["action"]] = counts.get(result["action"], 0) + 1

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    summary = {
        "source": source_name, "fetched": len(candidates), "ok": True,
        "elapsed_ms": elapsed_ms, **counts,
    }
    log.info("economic_calendar.sync_run_complete", **summary)
    return summary


async def get_source_health(db: AsyncSession) -> list[dict]:
    """Per-source visibility: how many current rows, how recently
    verified, is it stale. Answers exactly the "Source data valid /
    Last verification / Automatic discovery" view requested after
    5A.4 — computed from data that already exists (last_verified_at),
    not a new tracking table, since the row-level field already IS the
    per-source signal once aggregated."""
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(
            EconomicCalendarEvent.source,
            func.count(EconomicCalendarEvent.id).label("current_rows"),
            func.max(EconomicCalendarEvent.last_verified_at).label("last_verified_at"),
            func.min(EconomicCalendarEvent.scheduled_at).filter(EconomicCalendarEvent.scheduled_at > now).label("next_scheduled_at"),
        )
        .where(EconomicCalendarEvent.is_current.is_(True))
        .group_by(EconomicCalendarEvent.source)
    )).all()

    out = []
    for r in rows:
        last_verified = _aware(r.last_verified_at) if r.last_verified_at else None
        out.append({
            "source": r.source,
            "is_real_source": r.source in REAL_SOURCES,
            "current_rows": r.current_rows,
            "last_verified_at": last_verified.isoformat() if last_verified else None,
            "is_stale": is_stale(last_verified, now) if last_verified else True,
            "next_scheduled_at": _aware(r.next_scheduled_at).isoformat() if r.next_scheduled_at else None,
        })
    return out


async def run_full_sync() -> dict:
    """Phase 5A.7's daily job — every registered source, in sequence
    (not parallel: same yfinance-throttling-caution convention this
    codebase already applies elsewhere to sequential external fetches).
    One source's exception never aborts the run for the others — each
    registration is wrapped individually, matching the scheduler rule
    "source failure must not fail the whole scheduler cycle."""
    registry = _build_registry()
    results = []
    for reg in registry:
        try:
            result = await run_source_sync(reg.run_name, reg.fetch_fn)
        except Exception as exc:
            log.error("economic_calendar.full_sync.source_exception", source=reg.run_name, error=str(exc)[:200])
            result = {"source": reg.run_name, "fetched": 0, "ok": False, "elapsed_ms": 0}
        results.append(result)

    total_fetched = sum(r.get("fetched", 0) for r in results)
    if total_fetched == 0:
        # Owner's explicit operational safeguard: every real source
        # returning zero on the SAME run is much more likely a shared
        # parsing/site-change/network problem than a genuinely empty
        # calendar across RBI+MOSPI+Fed+BLS simultaneously — loud, not
        # a routine warning.
        log.error(
            "economic_calendar.full_sync.all_sources_empty",
            sources=[r["source"] for r in results],
            reason="every real source returned zero fetched rows in the same run — likely a parsing or site-change issue, not a genuinely empty calendar",
        )

    return {"total_fetched": total_fetched, "results": results}


async def run_imminent_recheck(horizon_hours: int = 24) -> dict:
    """Phase 5A.7's narrower, more frequent job — owner's explicit
    instruction: "do not repeatedly poll every source all day." Cheap
    when nothing is imminent (one DB query, zero network calls); only
    re-fetches a source whose category has an is_current row scheduled
    within the next `horizon_hours`."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=horizon_hours)

    async with AsyncSessionLocal() as db:
        imminent_categories = set((await db.execute(
            select(EconomicCalendarEvent.category)
            .where(
                EconomicCalendarEvent.is_current.is_(True),
                EconomicCalendarEvent.scheduled_at >= now,
                EconomicCalendarEvent.scheduled_at <= horizon,
            )
            .distinct()
        )).scalars().all())

    if not imminent_categories:
        log.info("economic_calendar.imminent_recheck.nothing_imminent", horizon_hours=horizon_hours)
        return {"checked_sources": [], "reason": "nothing scheduled within horizon"}

    registry = _build_registry()
    to_check = [reg for reg in registry if imminent_categories & set(reg.categories)]

    results = []
    for reg in to_check:
        try:
            result = await run_source_sync(reg.run_name, reg.fetch_fn)
        except Exception as exc:
            log.error("economic_calendar.imminent_recheck.source_exception", source=reg.run_name, error=str(exc)[:200])
            result = {"source": reg.run_name, "fetched": 0, "ok": False, "elapsed_ms": 0}
        results.append(result)

    log.info("economic_calendar.imminent_recheck.done", checked=[r["source"] for r in results],
              imminent_categories=sorted(imminent_categories))
    return {"checked_sources": [r["source"] for r in results], "results": results}

"""
Weekend Intelligence API — /api/intelligence/weekend/*  (Phase 1C, brief §4-8)

GET /current  — the current WeekendIntelligenceSnapshot, read-only.
GET /history  — version metadata for a target date, newest first (§8).

Both routes are pure reads over the already-persisted
WeekendIntelligenceSnapshot table (Phase 1B). Neither ever calls
build_weekend_intelligence() or writes anything — GET is cheap and
deterministic (§4). Response shape follows the existing router
convention in this codebase (see intelligence_market.py): plain dict
returns, broad try/except with a safe honest fallback rather than a
raised 500, `db` opened inline per-request via AsyncSessionLocal.
"""
from __future__ import annotations

from datetime import date, timezone

import structlog
from fastapi import APIRouter, Query

log = structlog.get_logger(__name__)
router = APIRouter()

# Bounds so a resolve step can never turn into an unbounded query — see
# module docstring on "no giant raw evidence payloads" (brief §5).
_MAX_OPPORTUNITIES_RESOLVED = 10
_MAX_HISTORICAL_ANALOGUES_RESOLVED = 5
_MAX_HISTORY_VERSIONS = 20


def _evidence_summary(evidence_refs: list[dict]) -> dict:
    from collections import Counter
    counts = Counter(e.get("source_type", "unknown") for e in evidence_refs)
    return {"total": len(evidence_refs), "by_source_type": dict(counts)}


async def _resolve_opportunities(db, opportunity_refs: list[str]) -> list[dict]:
    if not opportunity_refs:
        return []
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.db.models.opportunity import Opportunity

    ids = []
    for ref in opportunity_refs[:_MAX_OPPORTUNITIES_RESOLVED]:
        try:
            ids.append(int(ref))
        except (TypeError, ValueError):
            continue
    if not ids:
        return []
    rows = (await db.execute(
        select(Opportunity).where(Opportunity.id.in_(ids)).options(selectinload(Opportunity.companies))
    )).scalars().all()
    # A ref whose row no longer exists is simply absent from `rows` —
    # honestly omitted, not an error (brief §6).
    result = []
    for r in rows:
        # ai_summary.matters (2026-08-22, homepage card redesign) — a
        # real, already-persisted, purpose-written one-sentence reason
        # (see company_score_engine-style AI summary generation), not a
        # truncation of `title`. Some older/seed rows may predate AI
        # summary generation — omitted rather than fabricated when absent,
        # the frontend falls back to `title` in that case.
        ai_summary = r.ai_summary or {}
        top_companies = sorted(r.companies, key=lambda c: c.impact_score, reverse=True)[:3]
        result.append({
            "id": r.id, "title": r.title, "sectors": r.sectors, "risk_level": r.risk_level,
            "opportunity_score": r.opportunity_score, "confidence": r.confidence,
            "reason": ai_summary.get("matters") or None,
            "companies": [c.company_id for c in top_companies],
        })
    return result


async def _resolve_historical_analogues(db, refs: list[str]) -> list[dict]:
    if not refs:
        return []
    from sqlalchemy import select
    from app.db.models.historical_memory import HistoricalMarketEvent

    ids = refs[:_MAX_HISTORICAL_ANALOGUES_RESOLVED]
    rows = (await db.execute(
        select(HistoricalMarketEvent).where(HistoricalMarketEvent.id.in_(ids))
    )).scalars().all()
    by_id = {r.id: r for r in rows}
    out = []
    for ref in ids:
        r = by_id.get(ref)
        if r is None:
            continue  # honestly omitted — see module docstring
        out.append({
            "id": r.id, "event_title": r.event_title,
            "event_date": r.event_date.strftime("%b %d, %Y") if r.event_date else None,
            "category": r.category, "key_lesson": r.key_lesson, "nifty_1d": r.nifty_1d,
        })
    return out


def _snapshot_response(snapshot) -> dict:
    return {
        "available": True,
        "target_trading_date": snapshot.target_trading_date,
        "last_trading_date": snapshot.last_trading_date,
        "generated_at": snapshot.generated_at.astimezone(timezone.utc).isoformat() if snapshot.generated_at else None,
        "checkpoint_label": snapshot.checkpoint_label,
        "version": snapshot.version,
        "status": snapshot.status,
        "baseline_available": snapshot.market_snapshot_id is not None,
        "overall_bias": snapshot.overall_bias,
        "production_confidence": snapshot.production_confidence,
        "confidence_components": snapshot.confidence_components,
        "top_sectors": snapshot.top_sector_refs or [],
        "top_companies": snapshot.top_company_refs or [],
        # market_risks / confidence_warnings — Phase 1B's own split (see
        # risk_synthesis.py): risk_refs holds market risks only,
        # confidence_warning_refs holds process/data-quality caveats.
        "market_risks": snapshot.risk_refs or [],
        "confidence_warnings": snapshot.confidence_warning_refs or [],
        "new_since_close_count": len(snapshot.new_since_close_refs or []),
        "new_since_close": snapshot.new_since_close_refs or [],
        "changes_since_prior": snapshot.changes_since_prior or [],
        "evidence_summary": _evidence_summary(snapshot.evidence_refs or []),
        # experimental_signals and raw evidence_refs deliberately NOT
        # exposed (brief §5 — "Do NOT expose experimental signals
        # publicly yet", "Do NOT return giant raw evidence payloads").
    }


@router.get("/current")
async def get_current_weekend_intelligence():
    """The current (is_current=True) snapshot for the most relevant
    target_trading_date. `target_trading_date` may be passed to look up
    a specific date; otherwise resolves the session that would apply
    right now (same resolver Weekend Intelligence itself uses)."""
    from app.db.session import AsyncSessionLocal
    from app.services.weekend_intelligence.session_resolution import resolve_weekend_session
    from app.services.weekend_intelligence.versioning import get_current_snapshot

    try:
        async with AsyncSessionLocal() as db:
            _, target = resolve_weekend_session()
            snapshot = await get_current_snapshot(db, target)
            if snapshot is None:
                # Honest "nothing exists" state (brief §7) — NOT a fake
                # neutral snapshot, and NOT an HTTP error (this is a
                # legitimate, expected state most of the week).
                return {"available": False, "target_trading_date": target}

            response = _snapshot_response(snapshot)
            response["opportunities"] = await _resolve_opportunities(db, snapshot.opportunity_refs or [])
            response["historical_analogues"] = await _resolve_historical_analogues(
                db, snapshot.historical_analogue_refs or []
            )
            return response
    except Exception as exc:
        log.warning("weekend_intelligence_api.current_error", error=str(exc))
        return {"available": False, "error": str(exc)}


@router.get("/history")
async def get_weekend_intelligence_history(
    target_trading_date: str = Query(default=""),
):
    """Version metadata only (brief §8) — no giant payloads, capped,
    newest first. Defaults to the currently-resolved session's target
    date when none is supplied."""
    from app.db.session import AsyncSessionLocal
    from app.services.weekend_intelligence.session_resolution import resolve_weekend_session
    from app.services.weekend_intelligence.versioning import get_version_history

    try:
        async with AsyncSessionLocal() as db:
            target = target_trading_date or resolve_weekend_session()[1]
            history = await get_version_history(db, target)
            versions = [
                {
                    "version": s.version,
                    "checkpoint_label": s.checkpoint_label,
                    "generated_at": s.generated_at.astimezone(timezone.utc).isoformat() if s.generated_at else None,
                    "status": s.status,
                    "overall_bias": s.overall_bias,
                    "production_confidence": s.production_confidence,
                    "is_current": s.is_current,
                }
                for s in reversed(history[-_MAX_HISTORY_VERSIONS:])  # newest first, capped
            ]
            return {"target_trading_date": target, "versions": versions}
    except Exception as exc:
        log.warning("weekend_intelligence_api.history_error", error=str(exc))
        return {"target_trading_date": target_trading_date, "versions": [], "error": str(exc)}

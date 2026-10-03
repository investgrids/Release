"""
Company Rankings — the one real ranking surface over MarketRippleScoreSnapshot
(2026-09-26, Company Rankings migration; unified onto one methodology tag,
MARKETRIPPLE_SCORE_METHODOLOGY_VERSION, 2026-09-27). Banking and every
NONBANK_INDUSTRIAL_SECTORS sector are each ranked in their OWN separate
per-sector list — never merged into one cross-sector ranking — since a
company is only ever comparable to its real peer group, regardless of both
now sharing one headline formula. No other sector has an approved
methodology, so no other sector is ranked here, ever, regardless of demand.

This is a pure read layer over get_marketripple_score_projection(), the
exact same function CompanyPageClient.tsx's MarketRippleScoreCard already
calls per-symbol — never a second, parallel computation. That's what
guarantees the same company shows the identical score/rating/coverage/
timestamp on both the ranking table and its own Company page: one real
source of truth, read twice, not computed twice.

Never falls back to the older AI Company Score (company_score_engine.py)
for a bank that isn't ranked here — an unranked/unavailable bank is
reported as exactly that, with its real reason, never silently filled
with a different number that answers a different question.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS

# Provisional, explicitly unvalidated — see eligibility.py's own module
# docstring on REASON_STALE_FINANCIAL_DATA being "reserved but not
# enforced": no real lagging bank has ever existed to calibrate a
# threshold against. This one governs ranking-page display only (whether
# an otherwise-eligible score still counts as "fresh enough to rank"), not
# BANKING_V1_P1 eligibility itself. 30 days is a placeholder, not a
# researched cutoff.
_STALE_AFTER_DAYS = 30


def _is_stale(calculated_at: str | None) -> bool:
    if not calculated_at:
        return False
    try:
        dt = datetime.fromisoformat(calculated_at)
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    return age_days > _STALE_AFTER_DAYS


async def _latest_snapshots(db: AsyncSession, symbols: list[str]) -> dict[str, Any]:
    """symbol -> its latest current-methodology snapshot, in ONE query
    (was two reads per company, which doesn't scale to the full directory)."""
    from sqlalchemy import func, select

    from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot as S
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION

    if not symbols:
        return {}
    latest = (
        select(S.symbol, func.max(S.calculated_at).label("mx"))
        .where(S.methodology_version == MARKETRIPPLE_SCORE_METHODOLOGY_VERSION, S.symbol.in_(symbols))
        .group_by(S.symbol)
        .subquery()
    )
    rows = (await db.execute(
        select(S).join(latest, (S.symbol == latest.c.symbol) & (S.calculated_at == latest.c.mx))
    )).scalars().all()
    return {r.symbol: r for r in rows}


async def _get_sector_rankings(db: AsyncSession, sector: str, universe: list[str], methodology_version: str) -> dict[str, Any]:
    """Shared ranking logic for Banking and every NONBANK_INDUSTRIAL_SECTORS
    sector. Reads the same latest snapshot the Company page's projection
    reads (get_latest_snapshot's contract: newest current-methodology row per
    symbol), all at once. Per-sector ranking is deliberate: a Technology score
    and a Banking score are never comparable, so they are never in the same
    ranked list.

    Also computes a dev-only local-preview ranking (eligible score regardless
    of `publishable`) — a separate pass, never blended into `ranked`; the API
    layer strips it in real production."""
    from app.services.aipe.company_score_engine import _name_for

    snaps = await _latest_snapshots(db, universe)
    names = await _directory_names(db)

    ranked: list[dict] = []
    partial_coverage: list[dict] = []
    unavailable: list[dict] = []
    local_preview_candidates: list[dict] = []

    for symbol in universe:
        company_name = names.get(symbol) or _name_for(symbol) or symbol
        snap = snaps.get(symbol)
        if snap is None:
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "no_snapshot_computed_yet",
                "message": "No MarketRipple Score has been computed for this company yet.",
            })
            continue

        from app.services.marketripple_score.corporate_action_holds import score_hold_for
        from app.services.marketripple_score.eligibility import REASON_MARKET_INPUTS_UNVERIFIED
        from app.services.marketripple_score.public_projection import _public_block_message, public_block_reasons

        reasons = public_block_reasons(snap)
        eligible = not reasons
        calculated_at = snap.calculated_at.isoformat() if snap.calculated_at else None
        if not (snap.publication_block_reasons or []) and snap.score is not None:
            local_preview_candidates.append({"symbol": symbol, "company_name": company_name, "score": snap.score, "rating": snap.rating})

        if not eligible:
            hold = score_hold_for(symbol)
            block = _public_block_message(reasons)
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "ineligible",
                "state": ("needs_refresh" if reasons == [REASON_MARKET_INPUTS_UNVERIFIED]
                          else "score_hold" if hold else "peer_group_review" if "PEER_GROUP_UNDER_REVIEW" in reasons else "insufficient_data"),
                "message": hold.message if hold else (block[1] if block else "This company does not yet meet the publication bar."),
                "calculated_at": calculated_at,
            })
            continue
        if not snap.publishable:
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "publication_locked",
                "message": "This score exists but has not been approved for publication yet.",
                "calculated_at": calculated_at,
            })
            continue
        if _is_stale(calculated_at):
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "stale",
                "message": f"Last computed more than {_STALE_AFTER_DAYS} days ago.",
                "calculated_at": calculated_at,
            })
            continue
        if snap.pillar_coverage_status == "partial" or snap.score is None:
            partial_coverage.append({
                "symbol": symbol, "company_name": company_name,
                "message": snap.pillar_coverage_message or "Not enough pillars are available yet for a combined score.",
                "calculated_at": calculated_at,
            })
            continue
        ranked.append({
            "symbol": symbol, "company_name": company_name,
            "score": snap.score, "rating": snap.rating,
            "coverage_pct": snap.coverage_pct, "calculated_at": calculated_at,
            "peer_group": snap.peer_group,
        })

    from app.services.marketripple_score.peer_groups import GROUPED_SECTORS, peer_group_names

    if sector in GROUPED_SECTORS:
        # Ranked within the company's own peer group, never against the whole display sector.
        order = peer_group_names()
        ranked.sort(key=lambda r: (order.index(r["peer_group"]) if r["peer_group"] in order else len(order), -r["score"]))
        totals: dict[str, int] = {}
        for row in ranked:
            totals[row["peer_group"]] = totals.get(row["peer_group"], 0) + 1
        seen: dict[str, int] = {}
        for row in ranked:
            seen[row["peer_group"]] = seen.get(row["peer_group"], 0) + 1
            row["rank"] = seen[row["peer_group"]]
            row["group_total"] = totals[row["peer_group"]]
    else:
        ranked.sort(key=lambda r: r["score"], reverse=True)
        for i, row in enumerate(ranked):
            row["rank"] = i + 1

    local_preview_candidates.sort(key=lambda r: r["score"], reverse=True)
    local_preview_by_symbol = {
        row["symbol"]: {"score": row["score"], "rating": row["rating"], "rank": i + 1,
                        "total_ranked_in_sector": len(local_preview_candidates)}
        for i, row in enumerate(local_preview_candidates)
    }

    return {
        "sector": sector,
        "supported": True,
        "methodology_version": methodology_version,
        "ranked": ranked,
        "partial_coverage": partial_coverage,
        "unavailable": unavailable,
        "local_preview_by_symbol": local_preview_by_symbol,
        "total_universe": len(universe),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _directory_names(db: AsyncSession) -> dict[str, str]:
    from app.api.companies import get_full_company_directory

    return {row["symbol"]: row["name"] for row in await get_full_company_directory(db)}


async def get_banking_rankings(db: AsyncSession) -> dict[str, Any]:
    """The one real Banking ranking response — see _get_sector_rankings."""
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION

    return await _get_sector_rankings(db, "Banking", ALL_ELIGIBLE_NSE_BANKS, MARKETRIPPLE_SCORE_METHODOLOGY_VERSION)


async def get_industrial_sector_rankings(db: AsyncSession, sector: str) -> dict[str, Any]:
    """One NONBANK_INDUSTRIAL_SECTORS sector's ranking over every directory
    company in it (coverage.sector_candidates) — the same candidate set the
    refresh scores. `sector` must already be validated by the caller."""
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    from app.services.marketripple_score.coverage import sector_candidates

    universe = (await sector_candidates(db)).get(sector, [])
    return await _get_sector_rankings(db, sector, universe, MARKETRIPPLE_SCORE_METHODOLOGY_VERSION)


_ALL_COMPANIES_LOOKUP_CACHE: dict = {"data": None, "at": 0.0}
_ALL_COMPANIES_LOOKUP_TTL_S = 300.0

# Legacy per-sector reasons -> the public coverage states (coverage.py).
_REASON_TO_STATE = {
    "no_snapshot_computed_yet": "not_processed",
    "stale": "needs_refresh",
    "ineligible": "insufficient_data",
    "publication_locked": "insufficient_data",
}


async def _build_all_companies_lookup(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Every supported sector's ranking (Banking + all NONBANK_INDUSTRIAL_SECTORS
    over the full directory), merged into one symbol -> status lookup, cached
    briefly so paging through the directory doesn't repeat it per page."""
    import time as _time

    now = _time.monotonic()
    if _ALL_COMPANIES_LOOKUP_CACHE["data"] is not None and now - _ALL_COMPANIES_LOOKUP_CACHE["at"] < _ALL_COMPANIES_LOOKUP_TTL_S:
        return _ALL_COMPANIES_LOOKUP_CACHE["data"]

    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    from app.services.marketripple_score.coverage import STALE_AFTER_DAYS, _UNSUPPORTED_MESSAGES, coverage_state, sector_candidates
    from app.services.marketripple_score.peer_groups import REVIEW_SECTORS

    candidates = await sector_candidates(db)
    sector_results = [await get_banking_rankings(db)]
    for sector, universe in candidates.items():
        sector_results.append(await _get_sector_rankings(db, sector, universe, MARKETRIPPLE_SCORE_METHODOLOGY_VERSION))

    lookup: dict[str, dict[str, Any]] = {}
    for result in sector_results:
        is_banking = result["sector"] == "Banking"
        total_ranked = len(result["ranked"])
        for row in result["ranked"]:
            lookup[row["symbol"]] = {
                "status": "ranked", "score": row["score"], "rating": row["rating"],
                "coverage_pct": row["coverage_pct"], "calculated_at": row["calculated_at"],
                "rank": row["rank"], "total_ranked_in_sector": row.get("group_total", total_ranked),
                "peer_group": row.get("peer_group"),
                "message": None,
            }
        for row in result["partial_coverage"]:
            lookup[row["symbol"]] = {
                "status": "insufficient_data", "score": None, "rating": None, "coverage_pct": None,
                "calculated_at": row.get("calculated_at"), "rank": None, "total_ranked_in_sector": None,
                "message": row["message"],
            }
        for row in result["unavailable"]:
            state = row.get("state") or _REASON_TO_STATE.get(row["reason"], "insufficient_data")
            message = row["message"]
            if state == "not_processed" and result["sector"] in REVIEW_SECTORS:
                state, message = coverage_state(result["sector"], None)
            if is_banking and state in ("not_processed", "insufficient_data"):
                # Banks mostly lack the disclosure data their method needs.
                state, message = "unsupported", _UNSUPPORTED_MESSAGES["Banking"]
            elif state == "needs_refresh":
                calc = row.get("calculated_at")
                message = (f"Last calculated on {calc[:10]}. This score is more than {STALE_AFTER_DAYS} days old "
                           "and will be recalculated in the next scheduled run.") if calc else message
            elif state == "not_processed":
                message = "This company is supported, but its score hasn't been calculated yet."
            lookup[row["symbol"]] = {
                "status": state, "score": None, "rating": None, "coverage_pct": None,
                "calculated_at": row.get("calculated_at"), "rank": None, "total_ranked_in_sector": None,
                "message": message,
            }
        # LOCAL-DEV-ONLY — the API layer strips this in real production.
        for symbol, preview in result["local_preview_by_symbol"].items():
            lookup.setdefault(symbol, {
                "status": "unsupported", "score": None, "rating": None, "coverage_pct": None,
                "calculated_at": None, "rank": None, "total_ranked_in_sector": None, "message": None,
            })
            lookup[symbol]["local_preview"] = preview

    _ALL_COMPANIES_LOOKUP_CACHE["data"] = lookup
    _ALL_COMPANIES_LOOKUP_CACHE["at"] = now
    return lookup


async def get_all_companies_rankings(db: AsyncSession, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """The full, paginated Company Rankings directory: every company in the
    real Companies directory, eligible ones with their score/rank (scoped to
    their own sector), everyone else with an explicit coverage state and
    reason — never zero, never ranked across sectors."""
    import math

    from app.api.companies import get_full_company_directory
    from app.services.marketripple_score.coverage import coverage_state, score_sector_for

    directory = await get_full_company_directory(db)
    lookup = await _build_all_companies_lookup(db)

    total = len(directory)
    total_pages = max(1, math.ceil(total / page_size))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * page_size
    page_items = directory[start: start + page_size]

    rows = []
    for co in page_items:
        info = lookup.get(co["symbol"])
        if info is None:
            # Not a candidate in any scored sector: unsupported business type
            # or no reliable sector classification.
            state, message = coverage_state(score_sector_for(co["symbol"]), None, co["symbol"])
            rows.append({
                "symbol": co["symbol"], "company_name": co["name"], "sector": co["sector"],
                "status": state, "score": None, "rating": None, "coverage_pct": None,
                "rank": None, "total_ranked_in_sector": None, "calculated_at": None,
                "message": message, "local_preview": None,
            })
        else:
            rows.append({
                "symbol": co["symbol"], "company_name": co["name"], "sector": co["sector"],
                "local_preview": None,
                **info,
            })

    return {
        "total": total, "page": page, "page_size": page_size, "total_pages": total_pages,
        "companies": rows, "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_top_local_preview_scores(db: AsyncSession, limit: int = 5, publishable_only: bool = False) -> list[dict[str, Any]]:
    """LOCAL-DEV-ONLY (2026-09-27) — the real top-N companies by unified
    MarketRipple Score, REGARDLESS of `publishable`, mirroring
    companies.py's own /marketripple-score/local-preview per-symbol
    endpoint (same settings.is_production gate, same "S2 phase lock stays
    completely untouched" contract). Exists because every real caller of
    get_all_companies_rankings/_get_sector_rankings deliberately withholds
    `score` whenever publishable is False (which is every company today)
    -- there was no real path left for a "highest scores" leaderboard to
    show anything at all in local dev once that gate is respected
    correctly. Reads the latest MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    snapshot per symbol directly (never re-derives from the public
    projection, which would just return None for score here)."""
    from sqlalchemy import func, select

    from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
    from app.services.aipe.company_score_engine import _name_for
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION

    # Latest calculated_at per symbol under the current methodology, then
    # join back to get that row's real score/rating -- the same "latest
    # per symbol" contract get_latest_snapshot() enforces per-symbol,
    # applied here across every symbol at once.
    latest_per_symbol = (
        select(
            MarketRippleScoreSnapshot.symbol,
            func.max(MarketRippleScoreSnapshot.calculated_at).label("max_calculated_at"),
        )
        .where(MarketRippleScoreSnapshot.methodology_version == MARKETRIPPLE_SCORE_METHODOLOGY_VERSION)
        .group_by(MarketRippleScoreSnapshot.symbol)
        .subquery()
    )
    stmt = (
        select(MarketRippleScoreSnapshot)
        .join(
            latest_per_symbol,
            (MarketRippleScoreSnapshot.symbol == latest_per_symbol.c.symbol)
            & (MarketRippleScoreSnapshot.calculated_at == latest_per_symbol.c.max_calculated_at),
        )
        .where(MarketRippleScoreSnapshot.score.is_not(None))
    )
    if publishable_only:  # the public leaderboard (get_top_published_scores)
        stmt = stmt.where(MarketRippleScoreSnapshot.publishable.is_(True))
    if publishable_only:
        # Same public check as the Company page; over-fetch so the filter
        # can't leave the leaderboard short.
        from app.services.marketripple_score.public_projection import is_publicly_published

        rows = (await db.execute(stmt.order_by(MarketRippleScoreSnapshot.score.desc()).limit(limit * 3))).scalars().all()
        rows = [r for r in rows if is_publicly_published(r)][:limit]
    else:
        rows = (await db.execute(stmt.order_by(MarketRippleScoreSnapshot.score.desc()).limit(limit))).scalars().all()

    return [
        {
            "symbol": row.symbol, "company_name": _name_for(row.symbol) or row.symbol,
            "score": row.score, "rating": row.rating,
        }
        for row in rows
    ]


async def get_top_published_scores(db: AsyncSession, limit: int = 5) -> list[dict[str, Any]]:
    """The public top-N leaderboard across every supported sector: only
    snapshots that are publishable (real headline + passed eligibility)."""
    return await get_top_local_preview_scores(db, limit=limit, publishable_only=True)


def get_unsupported_sector_response(sector: str) -> dict[str, Any]:
    """Every non-Banking sector, today — honest, not an empty ranked list
    pretending to be complete. Never substitutes the older AI Company
    Score to fill the gap."""
    return {
        "sector": sector,
        "supported": False,
        "message": "MarketRipple Score is not yet available for this sector.",
        "ranked": [],
        "partial_coverage": [],
        "unavailable": [],
    }

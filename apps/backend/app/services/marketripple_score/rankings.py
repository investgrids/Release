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


async def _get_sector_rankings(db: AsyncSession, sector: str, universe: list[str], methodology_version: str) -> dict[str, Any]:
    """Shared ranking logic (NS1, owner instruction 2026-09-27) — extracted
    verbatim from get_banking_rankings' own original body, byte-for-byte
    unchanged behavior, just parameterized on (sector, universe,
    methodology_version) so the Non-Banking Industrial methodology reuses
    the exact same categorization instead of a second, hand-copied
    implementation. Every row still comes from
    get_marketripple_score_projection(db, symbol) — never recomputed here.
    Per-sector ranking is deliberate: a Technology score and a Banking
    score are never comparable, so they are never in the same ranked
    list — see this module's own docstring.

    Also computes `local_preview_rank`/`local_preview_score`/
    `local_preview_rating` on every row from get_company_marketripple_score_local_preview's
    same underlying data (real, eligible score regardless of `publishable`)
    — a SEPARATE ranking pass, never blended into `ranked`/`rank` above,
    so the honest public state is never perturbed by it. Callers (the API
    layer) are responsible for stripping these fields in real production,
    same settings.is_production convention as every other local-preview
    surface in this codebase."""
    from app.services.aipe.company_score_engine import _name_for
    from app.services.marketripple_score.public_projection import get_marketripple_score_projection
    from app.services.marketripple_score.snapshot import get_latest_snapshot

    ranked: list[dict] = []
    partial_coverage: list[dict] = []
    unavailable: list[dict] = []
    local_preview_candidates: list[dict] = []  # symbol, company_name, score, rating -- real & eligible, any publishable state

    for symbol in universe:
        company_name = _name_for(symbol) or symbol
        proj = await get_marketripple_score_projection(db, symbol)

        # Local-preview candidacy is evaluated from the real snapshot
        # directly (never from `proj`, which redacts score/rating whenever
        # publishable is False) -- the same real eligibility bar
        # (block_reason_codes empty) as everywhere else, just not gated on
        # the whole-feature publication lock.
        snap = await get_latest_snapshot(db, symbol)
        if snap is not None and not (snap.publication_block_reasons or []) and snap.score is not None:
            local_preview_candidates.append({"symbol": symbol, "company_name": company_name, "score": snap.score, "rating": snap.rating})

        if not proj.get("resolved") or not proj.get("snapshot"):
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "no_snapshot_computed_yet",
                "message": "No MarketRipple Score has been computed for this company yet.",
            })
            continue

        if not proj.get("publishable"):
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "publication_locked",
                "message": "This score exists but has not been approved for publication yet.",
            })
            continue

        if not proj.get("eligible"):
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "ineligible",
                "message": proj.get("block_message") or "This company does not yet meet the publication bar.",
            })
            continue

        calculated_at = proj.get("calculated_at")
        if _is_stale(calculated_at):
            unavailable.append({
                "symbol": symbol, "company_name": company_name, "reason": "stale",
                "message": f"Last computed more than {_STALE_AFTER_DAYS} days ago.",
                "calculated_at": calculated_at,
            })
            continue

        if proj.get("pillar_coverage_status") == "partial" or proj.get("score") is None:
            partial_coverage.append({
                "symbol": symbol, "company_name": company_name,
                "message": proj.get("pillar_coverage_message") or "Not enough pillars are available yet for a combined score.",
                "calculated_at": calculated_at,
            })
            continue

        ranked.append({
            "symbol": symbol, "company_name": company_name,
            "score": proj["score"],
            "rating": proj.get("rating"),
            "coverage_pct": proj.get("evidence_coverage_pct"),
            "calculated_at": calculated_at,
        })

    ranked.sort(key=lambda r: r["score"], reverse=True)
    for i, row in enumerate(ranked):
        row["rank"] = i + 1

    local_preview_candidates.sort(key=lambda r: r["score"], reverse=True)
    local_preview_by_symbol: dict[str, dict] = {}
    for i, row in enumerate(local_preview_candidates):
        local_preview_by_symbol[row["symbol"]] = {
            "score": row["score"], "rating": row["rating"],
            "rank": i + 1, "total_ranked_in_sector": len(local_preview_candidates),
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


async def get_banking_rankings(db: AsyncSession) -> dict[str, Any]:
    """The one real Banking ranking response — see _get_sector_rankings'
    own docstring for the shared logic this now calls."""
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION

    return await _get_sector_rankings(db, "Banking", ALL_ELIGIBLE_NSE_BANKS, MARKETRIPPLE_SCORE_METHODOLOGY_VERSION)


async def get_industrial_sector_rankings(db: AsyncSession, sector: str) -> dict[str, Any]:
    """The real Non-Banking Commercial & Industrial ranking response for
    one of sector_universe.py's NONBANK_INDUSTRIAL_SECTORS — a SEPARATE
    ranked list per sector (never merged with Banking's or another
    industrial sector's), since scores are only ever ranked within a real,
    comparable peer group even though Banking and Industrial now share one
    methodology tag. `sector` must already be validated as a real
    NONBANK_INDUSTRIAL_SECTORS member by the caller."""
    from app.services.marketripple_score.contracts import MARKETRIPPLE_SCORE_METHODOLOGY_VERSION
    from app.services.marketripple_score.sector_universe import sector_peer_universe

    return await _get_sector_rankings(db, sector, sector_peer_universe(sector), MARKETRIPPLE_SCORE_METHODOLOGY_VERSION)


_ALL_COMPANIES_LOOKUP_CACHE: dict = {"data": None, "at": 0.0}
_ALL_COMPANIES_LOOKUP_TTL_S = 300.0


async def _build_all_companies_lookup(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Runs every real supported sector's ranking ONCE (Banking + all 19
    NONBANK_INDUSTRIAL_SECTORS) and merges the results into one
    symbol -> real-status lookup, reused across every paginated page of
    get_all_companies_rankings() rather than recomputed per page request.
    A DB-only read layer (same as _get_sector_rankings itself) — cached
    briefly so a user paging through the full directory doesn't repeat all
    20 sector reads (~400+ per-symbol projection reads) on every page."""
    import time as _time

    now = _time.monotonic()
    if _ALL_COMPANIES_LOOKUP_CACHE["data"] is not None and now - _ALL_COMPANIES_LOOKUP_CACHE["at"] < _ALL_COMPANIES_LOOKUP_TTL_S:
        return _ALL_COMPANIES_LOOKUP_CACHE["data"]

    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    sector_results = [await get_banking_rankings(db)]
    for sector in NONBANK_INDUSTRIAL_SECTORS:
        sector_results.append(await get_industrial_sector_rankings(db, sector))

    lookup: dict[str, dict[str, Any]] = {}
    for result in sector_results:
        total_ranked = len(result["ranked"])
        for row in result["ranked"]:
            lookup[row["symbol"]] = {
                "status": "ranked", "score": row["score"], "rating": row["rating"],
                "coverage_pct": row["coverage_pct"], "calculated_at": row["calculated_at"],
                "rank": row["rank"], "total_ranked_in_sector": total_ranked,
                "message": None,
            }
        for row in result["partial_coverage"]:
            lookup[row["symbol"]] = {
                "status": "partial_coverage", "score": None, "rating": None, "coverage_pct": None,
                "calculated_at": row.get("calculated_at"), "rank": None, "total_ranked_in_sector": None,
                "message": row["message"],
            }
        for row in result["unavailable"]:
            lookup[row["symbol"]] = {
                "status": row["reason"], "score": None, "rating": None, "coverage_pct": None,
                "calculated_at": row.get("calculated_at"), "rank": None, "total_ranked_in_sector": None,
                "message": row["message"],
            }
        # LOCAL-DEV-ONLY (2026-09-27) — attaches a real rank/score/rating
        # regardless of `publishable`, on EVERY row (not just the ones
        # already "ranked" above), so a local dev build can actually verify
        # the full directory's real ordering while every company is still
        # publication-locked. Never overwrites `status`/`score` above --
        # the API layer decides whether to expose this at all (stripped in
        # real production).
        for symbol, preview in result["local_preview_by_symbol"].items():
            lookup.setdefault(symbol, {
                "status": "unsupported_sector", "score": None, "rating": None, "coverage_pct": None,
                "calculated_at": None, "rank": None, "total_ranked_in_sector": None, "message": None,
            })
            lookup[symbol]["local_preview"] = preview

    _ALL_COMPANIES_LOOKUP_CACHE["data"] = lookup
    _ALL_COMPANIES_LOOKUP_CACHE["at"] = now
    return lookup


async def get_all_companies_rankings(db: AsyncSession, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """The full, paginated Company Rankings directory (owner instruction,
    2026-09-27, "Company Rankings and UI": "show every company from the
    real Companies directory... with pagination... eligible companies show
    their canonical score, rating and calculation date; everyone else
    shows an explicit N/A with an honest reason, never zero, never
    ranked"). Iterates the SAME real company directory list_companies()
    itself reads (app.api.companies.get_full_company_directory), never a
    second, separately-curated list. Every ranked row's `rank` is real and
    scoped to its own sector's peer group only (via
    _build_all_companies_lookup's per-sector _get_sector_rankings calls) —
    a company is never ranked against a different sector's companies, and
    a company with no approved methodology for its sector reports
    "unsupported_sector" with an honest message, never a fabricated
    number and never a rank."""
    import math

    from app.api.companies import get_full_company_directory

    directory = await get_full_company_directory(db)
    lookup = await _build_all_companies_lookup(db)

    total = len(directory)
    total_pages = max(1, math.ceil(total / page_size))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * page_size
    page_items = directory[start: start + page_size]

    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS
    supported_sectors = {"Banking", *NONBANK_INDUSTRIAL_SECTORS}

    rows = []
    for co in page_items:
        info = lookup.get(co["symbol"])
        if info is None:
            # Not in any scored peer universe. Only say "sector not
            # supported" when that's actually true — a company in a
            # supported sector that simply isn't in the scored universe yet
            # (e.g. an extended-directory company) gets its own honest status.
            in_supported_sector = co["sector"] in supported_sectors
            rows.append({
                "symbol": co["symbol"], "company_name": co["name"], "sector": co["sector"],
                "status": "not_yet_scored" if in_supported_sector else "unsupported_sector",
                "score": None, "rating": None, "coverage_pct": None,
                "rank": None, "total_ranked_in_sector": None, "calculated_at": None,
                "message": (
                    "MarketRipple Score hasn't been computed for this company yet."
                    if in_supported_sector else "MarketRipple Score does not yet support this sector."
                ),
                "local_preview": None,
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

"""
Company Rankings — the one real ranking surface over MarketRippleScoreSnapshot
(2026-09-26, Company Rankings migration). Banking-only, matching the only
implemented methodology (BANKING_V1) — no other sector has an approved
model, so no other sector is ranked here, ever, regardless of demand.

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


async def get_banking_rankings(db: AsyncSession) -> dict[str, Any]:
    """The one real Banking ranking response. Every row's data comes from
    get_marketripple_score_projection(db, symbol) — never recomputed here,
    never read from a second table. Categorizes each of the 27 real
    ALL_ELIGIBLE_NSE_BANKS symbols into exactly one of: ranked (publishable,
    eligible, fresh, has a real score), partial_coverage (publishable and
    eligible but pillar_coverage_status=="partial" — no headline number
    yet), or unavailable (not publishable, not eligible, no snapshot yet,
    or stale) with the real reason. Never silently drops a bank — every
    real symbol in the universe appears in exactly one list."""
    from app.services.aipe.company_score_engine import _name_for
    from app.services.marketripple_score.public_projection import get_marketripple_score_projection

    ranked: list[dict] = []
    partial_coverage: list[dict] = []
    unavailable: list[dict] = []

    for symbol in ALL_ELIGIBLE_NSE_BANKS:
        company_name = _name_for(symbol) or symbol
        proj = await get_marketripple_score_projection(db, symbol)

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

    return {
        "sector": "Banking",
        "supported": True,
        "methodology_version": "BANKING_V1",
        "ranked": ranked,
        "partial_coverage": partial_coverage,
        "unavailable": unavailable,
        "total_universe": len(ALL_ELIGIBLE_NSE_BANKS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


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

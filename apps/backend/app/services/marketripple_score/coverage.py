"""
Who can get a MarketRipple Score, and why a company doesn't have one.

Owner decision 2026-09-28: every company in the real Companies directory
whose business type the method supports is a candidate — being absent from
the curated `_NSE_UNIVERSE` list no longer means "not available". A company's
scoring sector is its curated sector when it has one, otherwise its
source-attributed site sector (company_identity/sector_mapping.py).

Every company is in exactly one state:
  scored            — a published number
  not_processed     — supported, but never calculated under this method
  needs_refresh     — its last score is older than the freshness window;
                      shown with that last calculation date, never as
                      "not processed"
  insufficient_data — calculated, but missing/invalid data failed a check
  unsupported       — a business type the method can't score yet (banks,
                      finance, insurance) or no reliable sector at all
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

STATE_SCORED = "scored"
STATE_NOT_PROCESSED = "not_processed"
STATE_NEEDS_REFRESH = "needs_refresh"
STATE_INSUFFICIENT_DATA = "insufficient_data"
STATE_UNSUPPORTED = "unsupported"

STATE_LABELS = {
    STATE_SCORED: "Scored",
    STATE_NOT_PROCESSED: "Not processed yet",
    STATE_NEEDS_REFRESH: "Score needs refresh",
    STATE_INSUFFICIENT_DATA: "Insufficient data",
    STATE_UNSUPPORTED: "Not supported yet",
}

# Rankings hides scores older than this; the Company page and Rankings both
# show them as needs_refresh (same window, one definition).
STALE_AFTER_DAYS = 30

_UNSUPPORTED_MESSAGES = {
    "Banking": "Bank scores need filed disclosure data (NPA, capital ratios), which MarketRipple is still adding.",
    "Finance": "Lenders and financial-services companies need a separate method, which MarketRipple is still building.",
    "Insurance": "Insurers need a separate method, which MarketRipple is still building.",
}
_NO_SECTOR_MESSAGE = "This company has no reliable sector classification yet, so it can't be compared with peers."
_NOT_PROCESSED_MESSAGE = "This company is supported, but its score hasn't been calculated yet. It will appear after the next scheduled run."
_MISSING_PILLAR_MESSAGE = "MarketRipple couldn't get enough verified financial, valuation or price data to calculate a score."


def score_sector_for(symbol: str) -> str | None:
    """The sector a company is scored and ranked in."""
    from app.services.aipe.company_score_engine import _sector_for
    from app.services.company_identity.sector_mapping import site_sector_for

    return _sector_for(symbol) or site_sector_for(symbol.upper().split(".")[0]) or None


def is_supported_sector(sector: str | None) -> bool:
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    return sector in NONBANK_INDUSTRIAL_SECTORS


async def sector_candidates(db: AsyncSession) -> dict[str, list[str]]:
    """Real Companies directory -> {supported sector: [symbols]}, sorted.
    Banking keeps its own universe (ALL_ELIGIBLE_NSE_BANKS) and is not here."""
    from app.api.companies import get_full_company_directory
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    from app.services.marketripple_score.peer_groups import GROUPED_SECTORS, unmatched_reason

    out: dict[str, set[str]] = {s: set() for s in NONBANK_INDUSTRIAL_SECTORS}
    for row in await get_full_company_directory(db):
        sector = score_sector_for(row["symbol"])
        if sector in out and not (sector in GROUPED_SECTORS and unmatched_reason(row["symbol"]) is not None):
            out[sector].add(row["symbol"])
    return {s: sorted(v) for s, v in out.items()}


def is_stale(calculated_at: datetime | str | None) -> bool:
    if not calculated_at:
        return False
    dt = datetime.fromisoformat(calculated_at) if isinstance(calculated_at, str) else calculated_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400 > STALE_AFTER_DAYS


def _date_label(dt: datetime | None) -> str:
    return dt.strftime("%d %b %Y") if dt else "an earlier date"


def coverage_state(sector: str | None, snap: Any | None, symbol: str | None = None) -> tuple[str, str | None]:
    """(state, public message) for one company from its latest snapshot."""
    from app.services.marketripple_score.public_projection import _public_block_message

    if sector in _UNSUPPORTED_MESSAGES:
        return STATE_UNSUPPORTED, _UNSUPPORTED_MESSAGES[sector]
    if not sector:
        return STATE_UNSUPPORTED, _NO_SECTOR_MESSAGE
    if not is_supported_sector(sector):
        return STATE_UNSUPPORTED, f"MarketRipple Score doesn't support the {sector} sector yet."
    from app.services.marketripple_score.peer_groups import GROUPED_SECTORS, unmatched_reason

    sym = symbol or getattr(snap, "symbol", None)
    if sector in GROUPED_SECTORS and unmatched_reason(sym) is not None:
        return STATE_UNSUPPORTED, f"No matching peer group: {unmatched_reason(sym)}"
    if snap is None:
        return STATE_NOT_PROCESSED, _NOT_PROCESSED_MESSAGE
    if is_stale(snap.calculated_at):
        return STATE_NEEDS_REFRESH, (
            f"Last calculated on {_date_label(snap.calculated_at)}. This score is out of date and "
            "will be recalculated in the next scheduled run."
        )
    from app.services.marketripple_score.corporate_action_holds import score_hold_for
    from app.services.marketripple_score.data_quality import snapshot_data_quality_reasons
    from app.services.marketripple_score.eligibility import (
        REASON_INSUFFICIENT_MARKET_HISTORY, REASON_MARKET_INPUTS_UNVERIFIED,
    )
    from app.services.marketripple_score.market_behaviour import snapshot_lacks_market_history
    from app.services.marketripple_score.public_projection import is_publicly_published

    hold = score_hold_for(getattr(snap, "symbol", None))
    if hold is not None:
        return STATE_INSUFFICIENT_DATA, hold.message
    if is_publicly_published(snap) and snap.score is not None:
        return STATE_SCORED, None
    reasons = list(snap.publication_block_reasons or [])
    reasons += [r for r in snapshot_data_quality_reasons(snap) if r not in reasons]
    if snap.publishable and snapshot_lacks_market_history(snap) and REASON_INSUFFICIENT_MARKET_HISTORY not in reasons:
        reasons.append(REASON_INSUFFICIENT_MARKET_HISTORY)
    block = _public_block_message(reasons)
    state = STATE_NEEDS_REFRESH if reasons == [REASON_MARKET_INPUTS_UNVERIFIED] else STATE_INSUFFICIENT_DATA
    return state, block[1] if block else _MISSING_PILLAR_MESSAGE


def coverage_fields(sector: str | None, snap: Any | None, symbol: str | None = None) -> dict[str, Any]:
    """The public coverage block every score response carries."""
    state, message = coverage_state(sector, snap, symbol)
    return {
        "coverage_state": state,
        "coverage_label": STATE_LABELS[state],
        "coverage_message": message,
        "last_calculated_at": snap.calculated_at.isoformat() if snap is not None and snap.calculated_at else None,
        # The peer group the score was ranked against (percentile scores move when it changes).
        "peer_count": getattr(snap, "peer_universe_count", None) if snap is not None else None,
        "sector": sector,
        "peer_group": getattr(snap, "peer_group", None) if snap is not None else None,
    }

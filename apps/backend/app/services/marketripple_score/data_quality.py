"""
Public data-quality gate (owner decision 2026-10-03, after the audit of the
421 public scores). A stored score is shown only if its inputs are current
and verifiable — checked from the stored record itself, so it also governs
snapshots computed before the rule existed.

  STALE_FINANCIAL_DATA   the newest financial statement period is more than
                         ~15 months old. Found live: all 26 public banks were
                         scored on FY2025 Q3 disclosures (quarter ended
                         Dec 2024) because nothing refreshes that store.
  MARKET_INPUTS_UNVERIFIED  no recorded, completed-session price inputs:
                         legacy snapshots (computed intraday, partial candle)
                         have none, and a new one must prove its dated closes
                         stop at the run's cutoff and its own series reaches
                         the market's last session.

This verifies the data a score was built from. It says nothing about whether
a higher score predicts better investment returns.
"""
from __future__ import annotations

from datetime import date

from app.services.marketripple_score.eligibility import (
    REASON_MARKET_INPUTS_UNVERIFIED, REASON_NO_MATCHING_PEER_GROUP, REASON_PEER_GROUP_UNDER_REVIEW, REASON_STALE_FINANCIAL_DATA,
)

STALE_FINANCIAL_AFTER_DAYS = 456  # ~15 months: a late filer still passes, a missed filing cycle doesn't
_NIFTY = "^NSEI"


def financial_period_end(value) -> date | None:
    """A statement period end from an ISO date, or from a bank's 'FYyyyyQq'
    label (FY2025 = year ending Mar-2025, so Q3 ended Dec-2024)."""
    if not value:
        return None
    s = str(value).strip()
    if s.upper().startswith("FY"):
        try:
            year = int(s[2:6])
            quarter = int(s[7]) if len(s) >= 8 and s[6].upper() == "Q" else 4
            return {1: date(year - 1, 6, 30), 2: date(year - 1, 9, 30), 3: date(year - 1, 12, 31), 4: date(year, 3, 31)}[quarter]
        except (ValueError, KeyError):
            return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def financial_data_is_stale(value, today: date | None = None) -> bool:
    end = financial_period_end(value)
    return end is not None and ((today or date.today()) - end).days > STALE_FINANCIAL_AFTER_DAYS


def market_inputs_unverified_reason(inputs, symbol: str) -> str | None:
    """None when the stored provenance proves completed-session inputs;
    otherwise the specific failure."""
    if not isinstance(inputs, dict):
        return "no recorded market inputs (computed before input provenance existed)"
    cutoff = inputs.get("cutoff_date")
    series = inputs.get("series") or {}
    if not cutoff or not series:
        return "no cutoff date or series recorded"
    ends = {ticker: s.get("observation_end") for ticker, s in series.items()}
    if any(e is None for e in ends.values()):
        return "a price series has no observation dates"
    if any(e > cutoff for e in ends.values()):
        return "a price series runs past the completed-session cutoff"
    own_end, market_end = ends.get(f"{symbol.upper()}.NS"), ends.get(_NIFTY)
    if own_end is None or market_end is None:
        return "own or market series missing"
    if own_end < market_end:
        return f"own price series ends {own_end}, before the market's last session {market_end}"
    return None


def peer_group_reasons(snap) -> list[str]:
    """Grouped sectors only (peer_groups.py). No company is public unless it was
    calculated against its own peer group AND the sector has been released."""
    from app.services.marketripple_score.coverage import score_sector_for
    from app.services.marketripple_score.peer_groups import GROUPED_SECTORS, REVIEW_SECTORS, peer_group_for, unmatched_reason

    symbol = str(getattr(snap, "symbol", ""))
    sector = score_sector_for(symbol)
    if sector not in GROUPED_SECTORS:
        return []
    if unmatched_reason(symbol) is not None or peer_group_for(symbol) is None:
        return [REASON_NO_MATCHING_PEER_GROUP]
    if sector in REVIEW_SECTORS or not getattr(snap, "peer_group", None):
        return [REASON_PEER_GROUP_UNDER_REVIEW]
    return []


def snapshot_data_quality_reasons(snap, today: date | None = None) -> list[str]:
    reasons = []
    if financial_data_is_stale(getattr(snap, "financial_data_as_of", None), today):
        reasons.append(REASON_STALE_FINANCIAL_DATA)
    if market_inputs_unverified_reason(getattr(snap, "market_behaviour_inputs", None), str(getattr(snap, "symbol", ""))):
        reasons.append(REASON_MARKET_INPUTS_UNVERIFIED)
    reasons += peer_group_reasons(snap)
    return reasons

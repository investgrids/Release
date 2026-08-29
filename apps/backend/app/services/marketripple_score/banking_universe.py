"""
Canonical Banking peer universe — S4.5 (owner decision, 2026-08-29).

S4's peer-universe sensitivity test found that the choice of comparison
population is not a backend configuration detail: 3 of the original 5
banks moved 9-18 Financial Strength points purely from widening the peer
group from 5 to 27 real banks (see
artifacts/marketripple_score_s4_wide_banking_validation.md §3). The owner's
decision: the MarketRipple Score answers "how does this bank compare with
the investable NSE banking universe," not a hand-picked subset — so
`ALL_ELIGIBLE_NSE_BANKS` is the one canonical peer group for Banking V1,
not an implementation detail each caller can silently vary.

Derived from the real, live company universe (`app.api.companies`) rather
than hand-copied — this list moves automatically if that universe changes,
instead of silently drifting out of sync with it.
"""
from __future__ import annotations

from datetime import date


def _all_eligible_nse_banks() -> list[str]:
    from app.api.companies import _NSE_UNIVERSE

    return sorted({row["symbol"] for row in _NSE_UNIVERSE if row.get("sector") == "Banking"})


ALL_ELIGIBLE_NSE_BANKS: list[str] = _all_eligible_nse_banks()

# S4 validated this exact set (27 real banks) — a real, dated snapshot for
# methodology metadata (MarketRippleScore.peer_universe_as_of). Not
# recomputed per-request: the universe is expected to be effectively
# static day-to-day, and pinning it avoids a score's peer_universe_count
# silently drifting mid-session if _NSE_UNIVERSE is ever hot-reloaded.
PEER_UNIVERSE_AS_OF: date = date(2026, 8, 29)

# Kept for a future, separate "Large Private Bank Rank" analytic (owner's
# own framing) — must NEVER be used as the default for the primary
# MarketRipple Score again; that default is ALL_ELIGIBLE_NSE_BANKS.
LARGE_PRIVATE_PEER_GROUP = ["ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN"]

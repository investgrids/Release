"""
Canonical non-Banking sector peer universes — NS1 (owner instruction,
2026-09-27), same real-data-first discipline as banking_universe.py's own
ALL_ELIGIBLE_NSE_BANKS: derived live from the real company universe
(`app.api.companies._NSE_UNIVERSE`), never a hand-typed list (a hand-typed
sample list is exactly how this initiative's own data-inventory pass hit
two stale symbols — TATAMOTORS, real-renamed to TMPV per company_entity.py's
own documented 2025-10-24 rename, and a delisted GMRINFRA-shaped gap —
before falling back to the live universe caught it).

Cohort selection is a real, measured decision (scripts/ns1_nonbank_data_inventory.py),
not an assumption: these 7 sectors showed real, live, multi-period revenue/
net income, EBIT, interest expense, total debt, stockholders equity, and
total assets/current liabilities for the large majority of sampled real
companies — a standardized commercial/industrial statement shape. Finance
(NBFC/AMC/Insurance-style balance sheets) and Banking are deliberately
excluded — sampled Finance names (BAJFINANCE, SBILIFE) were real but
missing EBIT/current-liabilities/total-debt in exactly the pattern a
different statement structure produces, not a data-fetch failure.

NONBANK_INDUSTRIAL_SECTORS is the one canonical list this methodology's
callers should use — not a per-caller decision, matching the reasoning
banking_universe.py's own module docstring already established for why
peer population is a methodology decision, not a caller-configurable
detail.
"""
from __future__ import annotations

from datetime import date

# NS1 cohort (owner instruction, 2026-09-27) — measured, not assumed; see
# module docstring and scripts/ns1_nonbank_data_inventory.py's real output.
NONBANK_INDUSTRIAL_SECTORS: list[str] = [
    "Technology", "FMCG", "Automotive", "Pharmaceuticals",
    "Chemicals", "Consumer", "Metals",
]

# Sectors explicitly measured-and-excluded (structural reason, not "not
# tried yet") — kept here, not silently dropped, so a future pass doesn't
# have to re-derive why. All other real sectors in _NSE_UNIVERSE
# (Infrastructure, Power, Energy, Real Estate, Telecom, Media, Cement,
# Healthcare, Textiles, Electronics, Retail, Defence, Insurance, ETF,
# REIT, InvIT) were NOT sampled in this pass at all — "not yet measured",
# a different status from the structural exclusions below.
NONBANK_STRUCTURALLY_EXCLUDED_SECTORS: dict[str, str] = {
    "Finance": (
        "NBFC/AMC/Insurance-style balance sheets — real sampled names "
        "(BAJFINANCE, SBILIFE) were missing EBIT, Current Liabilities, "
        "and/or Total Debt in the pattern a financial-company statement "
        "structure produces, not a fetch failure. Needs its own "
        "regulatory-capital/AUM-based methodology, not attempted here."
    ),
    "Insurance": "Same structural reason as Finance — actuarial/embedded-value metrics, not sampled or attempted here.",
    "Banking": "Already has its own real, frozen BANKING_V1 methodology — this cohort never applies to it.",
}


def sector_peer_universe(sector: str) -> list[str]:
    """The real, live peer population for one NONBANK_INDUSTRIAL_SECTORS
    entry, derived from the real company universe exactly like
    ALL_ELIGIBLE_NSE_BANKS — never a hand-typed sample."""
    from app.api.companies import _NSE_UNIVERSE

    return sorted({row["symbol"] for row in _NSE_UNIVERSE if row.get("sector") == sector})


# Pinned snapshot date for methodology metadata (peer_universe_as_of),
# same real-dated-snapshot discipline as banking_universe.py's
# PEER_UNIVERSE_AS_OF — avoids a score's peer_universe_count silently
# drifting mid-session if _NSE_UNIVERSE is ever hot-reloaded.
NONBANK_PEER_UNIVERSE_AS_OF: date = date(2026, 9, 27)

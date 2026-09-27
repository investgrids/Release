"""
Canonical non-Banking sector peer universes — NS1 (owner instruction,
2026-09-27), same real-data-first discipline as banking_universe.py's own
ALL_ELIGIBLE_NSE_BANKS: derived live from the real company universe
(`app.api.companies._NSE_UNIVERSE`), never a hand-typed list (a hand-typed
sample list is exactly how this initiative's own data-inventory pass hit
two stale symbols — TATAMOTORS, real-renamed to TMPV per company_entity.py's
own documented 2025-10-24 rename, and a delisted GMRINFRA-shaped gap —
before falling back to the live universe caught it).

Cohort selection is a real, measured decision, not an assumption:

  - NS1 (scripts/ns1_nonbank_data_inventory.py, 2026-09-27): 7 sectors
    sampled first, showed real, live, multi-period revenue/net income,
    EBIT, interest expense, total debt, stockholders equity, and total
    assets/current liabilities for the large majority of sampled real
    companies.
  - NS2 (scripts/ns2_remaining_sectors_data_inventory.py, 2026-09-27,
    owner instruction to keep pushing coverage): sampled the 12 sectors
    NS1 had left unmeasured — every single one of 35 real sampled
    companies across all 12 had the SAME complete statement shape (100%
    hit rate). This confirmed the real dividing line was never "these
    specific 7 industries" — it's financial-intermediary businesses
    (Banking/Finance/Insurance, whose balance sheets are leverage/capital-
    driven, not operating-margin-driven) versus every other real,
    operating company. All 12 were added to the cohort on that evidence.
  - NS3 (scripts/ns3_finance_feebased_data_inventory.py, 2026-09-27):
    tested whether the "Finance" sector label hides real, non-lending,
    fee-based businesses (exchanges, depositories, rating agencies,
    wealth/broking) that might fit anyway. CDSL, MCX, CRISIL, CAMS, and
    ANGELONE all showed the same complete real statement shape. NOT added
    to NONBANK_INDUSTRIAL_SECTORS here, deliberately — sector_peer_universe()
    pulls the WHOLE "Finance" label, which is genuinely dominated by NBFCs/
    insurers/housing-finance lenders; blending 5 fee-based names into that
    peer pool would compare them against a structurally different
    population. This needs its own small, explicitly-curated peer
    group (a real "Financial Market Infrastructure" sub-list), not a
    blanket sector inclusion — a scoped, ready-to-build follow-up, the
    real data already gathered, not attempted in this pass.

Finance and Insurance sectors themselves stay excluded — sampled names
(BAJFINANCE, SBILIFE) were real but missing EBIT/current-liabilities/
total-debt in exactly the pattern a lender/insurer statement structure
produces, not a data-fetch failure.

NONBANK_INDUSTRIAL_SECTORS is the one canonical list this methodology's
callers should use — not a per-caller decision, matching the reasoning
banking_universe.py's own module docstring already established for why
peer population is a methodology decision, not a caller-configurable
detail.
"""
from __future__ import annotations

from datetime import date

# NS1 + NS2 cohort (owner instruction, 2026-09-27) — measured, not
# assumed; see module docstring and scripts/ns1_nonbank_data_inventory.py
# + scripts/ns2_remaining_sectors_data_inventory.py's real output.
NONBANK_INDUSTRIAL_SECTORS: list[str] = [
    # NS1 (round 1)
    "Technology", "FMCG", "Automotive", "Pharmaceuticals",
    "Chemicals", "Consumer", "Metals",
    # NS2 (round 2) — every sampled company in every one of these 12
    # sectors showed the same complete real statement shape as NS1's own.
    "Infrastructure", "Power", "Energy", "Real Estate", "Telecom", "Media",
    "Cement", "Healthcare", "Textiles", "Electronics", "Retail", "Defence",
]

# Sectors explicitly measured-and-excluded (structural reason, not "not
# tried yet") — kept here, not silently dropped, so a future pass doesn't
# have to re-derive why. Only Finance/Insurance/Banking remain here after
# NS2 — every other real sector in _NSE_UNIVERSE has now been measured and
# included (ETF/REIT/InvIT aren't real operating companies at all and were
# never candidates for a company score in the first place).
NONBANK_STRUCTURALLY_EXCLUDED_SECTORS: dict[str, str] = {
    "Finance": (
        "NBFC/AMC/Insurance-style balance sheets — real sampled names "
        "(BAJFINANCE, SBILIFE) were missing EBIT, Current Liabilities, "
        "and/or Total Debt in the pattern a financial-company statement "
        "structure produces, not a fetch failure. Needs its own "
        "regulatory-capital/AUM-based methodology, not attempted here. "
        "NOTE (NS3): a handful of fee-based names within this label "
        "(CDSL, MCX, CRISIL, CAMS, ANGELONE) DO have the standard "
        "statement shape and are ready for a small, separately-curated "
        "peer group — see module docstring."
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

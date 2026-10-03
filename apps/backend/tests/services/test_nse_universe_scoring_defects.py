"""
2026-09-28 — production MarketRipple Score refresh: 149/424 (35%) companies
came back with valuation=None. Live re-fetch of a 30-symbol sample found
real pe/pb/EPS data for 28 of them, confirming the dominant cause was
transient yfinance throttling during the ~58-minute batch, not a real data
gap (see valuation.py's retry-fix docstrings). Two real, permanent
data-mapping defects were found alongside it, both silently excluding real
companies from the entire scoring cohort rather than producing an honest
None with a reason. These tests guard against both recurring, and against
any future _NSE_UNIVERSE entry drifting out of sync with the sector names
sector_peer_universe() matches on exact string equality.
"""
from __future__ import annotations

from app.api.companies import _NSE_UNIVERSE
from app.services.marketripple_score.sector_universe import (
    NONBANK_INDUSTRIAL_SECTORS, NONBANK_STRUCTURALLY_EXCLUDED_SECTORS, sector_peer_universe,
)

# Every other real label seen in _NSE_UNIVERSE that is NOT a scored sector,
# and is not a typo of one — reviewed 2026-09-28. A label appearing here
# must genuinely have no supported methodology, not just be spelled
# differently from one that does.
_KNOWN_UNSCORED_LABELS = {
    "Aviation", "Exchange", "NBFC", "Broking", "Fintech", "New-age",
    "ETF", "REIT", "InvIT",
}


def test_every_nse_universe_sector_label_is_a_real_scored_or_known_unscored_name():
    """Guards the exact-string-match contract sector_peer_universe() relies
    on: every _NSE_UNIVERSE sector label is either one of the real scored
    names (NONBANK_INDUSTRIAL_SECTORS + Banking) or an explicitly reviewed
    unscored one — never a near-miss typo (e.g. "Auto" vs "Automotive",
    "Infra" vs "Infrastructure") that silently drops a real company out of
    every scoring run with no error and no reason ever shown."""
    scored = set(NONBANK_INDUSTRIAL_SECTORS) | set(NONBANK_STRUCTURALLY_EXCLUDED_SECTORS) | {"Banking"}
    allowed = scored | _KNOWN_UNSCORED_LABELS
    seen = {row["sector"] for row in _NSE_UNIVERSE}
    assert seen <= allowed, f"unreviewed sector label(s): {seen - allowed}"


def test_ashokley_is_automotive_not_the_old_auto_typo():
    row = next(r for r in _NSE_UNIVERSE if r["symbol"] == "ASHOKLEY")
    assert row["sector"] == "Automotive"
    assert "ASHOKLEY" in sector_peer_universe("Automotive")


def test_gmrairport_and_irb_are_infrastructure_not_the_old_infra_typo():
    for symbol in ("GMRAIRPORT", "IRB"):
        row = next(r for r in _NSE_UNIVERSE if r["symbol"] == symbol)
        assert row["sector"] == "Infrastructure"
    universe = sector_peer_universe("Infrastructure")
    assert "GMRAIRPORT" in universe
    assert "IRB" in universe


def test_tatamotors_stale_ticker_is_gone_tmpv_is_the_live_successor():
    """TATAMOTORS.NS is a real 404 on yfinance (2025-10-24 NSE rename) —
    confirmed live 2026-09-28. It must never be a scoring candidate again;
    TMPV, the real live successor, must be."""
    symbols = {r["symbol"] for r in _NSE_UNIVERSE}
    assert "TATAMOTORS" not in symbols
    assert "TMPV" in symbols
    universe = sector_peer_universe("Automotive")
    assert "TATAMOTORS" not in universe
    assert "TMPV" in universe


def test_tmpv_still_resolves_a_tata_motors_search():
    row = next(r for r in _NSE_UNIVERSE if r["symbol"] == "TMPV")
    assert "tata motors" in row["aliases"]


def test_heg_is_listed_under_its_current_nse_symbol_hegam():
    """NSE renamed HEG -> HEGAM (effective 2026-09-22, same ISIN). The old
    symbol must not remain a second candidate for the same company."""
    symbols = {r["symbol"] for r in _NSE_UNIVERSE}
    assert "HEGAM" in symbols
    assert "HEG" not in symbols
    row = next(r for r in _NSE_UNIVERSE if r["symbol"] == "HEGAM")
    assert "heg" in row["aliases"]

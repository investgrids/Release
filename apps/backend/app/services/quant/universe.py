"""
V1 validation universe — Phase 2B §1/§7.

Phase 2A decision (§33.B): NIFTY 50, not the full ~510-company universe.
Goal is measuring whether a quantitative model works for Indian equities
at all before spending warehouse/inference budget on a larger set.

Canonical bare symbols (Phase 2A §4 / symbols.py) — no ".NS" suffix here;
that's applied only at the point of a provider call.

This list is a real, standard NIFTY 50 constituent set. Index
membership rotates periodically (NSE reconstitutes the index roughly
semi-annually) — this is a reasonable V1 snapshot, not a live-synced
feed. Phase 2B does not build index-membership tracking; if a
constituent changes, this list is edited by hand, same as this
codebase's existing static company universe (app/api/companies.py).

TATAMOTORS — investigated (Phase 2C), not fixed. Tata Motors demerged
into two entities effective October 2025: the pre-demerger company
(with all its historical OHLCV) was renamed Tata Motors Passenger
Vehicles Ltd and now trades as "TMPV" on NSE; the "TATAMOTORS" name was
reused for the newly-demerged commercial-vehicle entity, which only
began trading Nov 12 2025 and — confirmed live via a direct yfinance
call — is not yet indexed by Yahoo Finance under that symbol (a
provider-side gap for a very recently listed entity, not a code bug).
This is a genuine symbol-identity discontinuity, not a data-availability
failure: "TATAMOTORS" pre- and post-October-2025 are legally different
companies. Per explicit instruction, this is NOT silently remapped to
TMPV or any other ticker here — TATAMOTORS stays in the universe and
simply has no PriceBar history until a real decision is made about
which entity (if either) "TATAMOTORS" should mean going forward.
Missing history -> no prediction for this symbol, never a substitution.
"""
from __future__ import annotations

NIFTY_50: tuple[str, ...] = (
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
)

assert len(NIFTY_50) == 50, f"expected 50 constituents, got {len(NIFTY_50)}"
assert len(set(NIFTY_50)) == 50, "duplicate symbol in NIFTY_50"

# Phase 2C §"performance by sector" — real GICS-style sector tags for the
# V1 universe, needed for quant_research.py's sector segmentation. Not a
# live-synced feed (same caveat as NIFTY_50 itself above); hand-maintained.
SECTOR: dict[str, str] = {
    "ADANIENT": "Diversified", "ADANIPORTS": "Infrastructure", "APOLLOHOSP": "Healthcare",
    "ASIANPAINT": "Consumer", "AXISBANK": "Financials", "BAJAJ-AUTO": "Auto",
    "BAJFINANCE": "Financials", "BAJAJFINSV": "Financials", "BEL": "Industrials",
    "BHARTIARTL": "Telecom", "CIPLA": "Healthcare", "COALINDIA": "Energy",
    "DRREDDY": "Healthcare", "EICHERMOT": "Auto", "ETERNAL": "Consumer",
    "GRASIM": "Materials", "HCLTECH": "IT", "HDFCBANK": "Financials",
    "HDFCLIFE": "Financials", "HEROMOTOCO": "Auto", "HINDALCO": "Materials",
    "HINDUNILVR": "Consumer", "ICICIBANK": "Financials", "INDUSINDBK": "Financials",
    "INFY": "IT", "ITC": "Consumer", "JIOFIN": "Financials",
    "JSWSTEEL": "Materials", "KOTAKBANK": "Financials", "LT": "Industrials",
    "M&M": "Auto", "MARUTI": "Auto", "NESTLEIND": "Consumer",
    "NTPC": "Energy", "ONGC": "Energy", "POWERGRID": "Energy",
    "RELIANCE": "Energy", "SBILIFE": "Financials", "SBIN": "Financials",
    "SHRIRAMFIN": "Financials", "SUNPHARMA": "Healthcare", "TATACONSUM": "Consumer",
    "TATAMOTORS": "Auto", "TATASTEEL": "Materials", "TCS": "IT",
    "TECHM": "IT", "TITAN": "Consumer", "TRENT": "Consumer",
    "ULTRACEMCO": "Materials", "WIPRO": "IT",
}
assert set(SECTOR.keys()) == set(NIFTY_50), "SECTOR must tag every NIFTY_50 constituent, no more no less"

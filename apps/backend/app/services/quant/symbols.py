"""
Canonical symbol resolution — Phase 2B §2.

Phase 2A audit finding: this app's canonical internal symbol is the bare
NSE trading symbol (e.g. "RELIANCE", no exchange suffix) — confirmed
across the company universe, Event.companies, PredictionRecord.
target_entities, and the MarketDataService domain types. But there was
no shared module for it: ~15 independent call sites each inlined their
own `f"{symbol}.NS"` construction (market_data.py, yfinance_provider.py,
companies.py, sectors.py, ai_search/enrichment.py,
company_fundamentals_service.py, theme_worker.py — see the audit for
exact citations), and only one of them (prediction_service.py) even
checked for an existing suffix first.

This module is the one place Quant Intelligence resolves a canonical
symbol to a provider-specific ticker. It does not replace the existing
inline call sites (out of scope for Phase 2B — touching ~15 unrelated
files is real, separate cleanup risk); it exists so nothing new in the
quant layer invents an 16th ad hoc convention.
"""
from __future__ import annotations

import re

# Same suffix set prediction_service.py already checks for, reused
# rather than re-invented — a symbol already carrying one of these is
# left untouched.
_ALREADY_SUFFIXED = (".NS", ".BO", "=X", "=F")


def to_yfinance(symbol: str) -> str:
    """Canonical bare symbol -> yfinance NSE ticker.

    "RELIANCE" -> "RELIANCE.NS". Index tickers (leading "^", e.g.
    "^NSEI") and already-suffixed symbols pass through unchanged.
    """
    s = symbol.strip().upper()
    if s.startswith("^") or s.endswith(_ALREADY_SUFFIXED):
        return s
    return f"{s}.NS"


def from_yfinance(ticker: str) -> str:
    """Provider ticker -> canonical bare symbol. Inverse of to_yfinance().

    "RELIANCE.NS" -> "RELIANCE". Strips ".NS"/".BO" only — index tickers
    and other suffixes (=X/=F) are returned unchanged, since those
    aren't equity symbols this app treats as "canonical company symbols"
    anywhere else either.
    """
    return re.sub(r"\.(NS|BO)$", "", ticker.strip().upper())


def to_fyers(symbol: str) -> str:
    """Canonical bare symbol -> Fyers ticker ("RELIANCE" -> "NSE:RELIANCE-EQ").

    Mirrors fyers_rest.py::_symbol_to_fyers's equity-only construction
    (that module's own _INDEX_MAP handles index tickers separately and
    is not duplicated here — Phase 2B's warehouse is equities-only, §7).
    """
    return f"NSE:{symbol.strip().upper()}-EQ"


def is_canonical(symbol: str) -> bool:
    """True if `symbol` is already in bare canonical form (no provider suffix)."""
    s = symbol.strip().upper()
    return not s.endswith(_ALREADY_SUFFIXED) and not s.startswith("^") and ":" not in s

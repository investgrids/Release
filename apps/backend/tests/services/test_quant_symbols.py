"""
Phase 2B §2 — canonical symbol resolver, offline (no DB, no network).
"""
from __future__ import annotations

from app.services.quant.symbols import to_yfinance, from_yfinance, to_fyers, is_canonical


def test_bare_symbol_gets_ns_suffix():
    assert to_yfinance("RELIANCE") == "RELIANCE.NS"
    assert to_yfinance("reliance") == "RELIANCE.NS"


def test_index_ticker_passes_through_unchanged():
    assert to_yfinance("^NSEI") == "^NSEI"
    assert to_yfinance("^NSEBANK") == "^NSEBANK"


def test_already_suffixed_symbol_is_not_double_suffixed():
    assert to_yfinance("RELIANCE.NS") == "RELIANCE.NS"
    assert to_yfinance("SOMETICKER.BO") == "SOMETICKER.BO"


def test_from_yfinance_strips_suffix_back_to_canonical():
    assert from_yfinance("RELIANCE.NS") == "RELIANCE"
    assert from_yfinance("reliance.ns") == "RELIANCE"


def test_from_yfinance_leaves_index_tickers_unchanged():
    assert from_yfinance("^NSEI") == "^NSEI"


def test_round_trip_is_stable():
    for symbol in ("RELIANCE", "TCS", "M&M", "BAJAJ-AUTO"):
        assert from_yfinance(to_yfinance(symbol)) == symbol.upper()


def test_to_fyers_format():
    assert to_fyers("RELIANCE") == "NSE:RELIANCE-EQ"


def test_is_canonical():
    assert is_canonical("RELIANCE") is True
    assert is_canonical("RELIANCE.NS") is False
    assert is_canonical("^NSEI") is False
    assert is_canonical("NSE:RELIANCE-EQ") is False

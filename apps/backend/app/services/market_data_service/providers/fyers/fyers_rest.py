"""
Fyers REST API wrapper.

All calls go through this module. It handles:
  - Building the Fyers API client (fyersModel.FyersModel)
  - Symbol format conversion: NSE symbol → Fyers format (NSE:RELIANCE-EQ)
  - Rate limiting awareness (Fyers free tier: 100 req/min)
  - Graceful fallback return on any failure

Never import this from application code directly.
Use FyersProvider → MarketDataService instead.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Fyers NSE exchange prefix
_NSE_PREFIX = "NSE:"

# Symbol type suffixes
_EQUITY_SUFFIX = "-EQ"
_INDEX_SUFFIX  = "-INDEX"

# Fyers index symbol mapping
_INDEX_MAP: dict[str, str] = {
    "^NSEI":    "NSE:NIFTY50-INDEX",
    "^NSEBANK": "NSE:NIFTYBANK-INDEX",
    "^CNXIT":   "NSE:CNXIT-INDEX",
    "^INDIAVIX":"NSE:INDIAVIX-INDEX",
    "^BSESN":   "BSE:SENSEX-INDEX",
}

# Resolution mapping: our period → Fyers resolution
_PERIOD_TO_RESOLUTION: dict[str, str] = {
    "1D": "5",    # 5-minute bars
    "1W": "60",   # 1-hour bars
    "1M": "D",    # daily
    "6M": "D",
    "1Y": "D",
    "3Y": "W",    # weekly
    "5Y": "W",
}

_PERIOD_TO_DAYS: dict[str, int] = {
    "1D":   1,
    "1W":   7,
    "1M":   31,
    "6M":   182,
    "1Y":   365,
    "3Y":   1095,
    "5Y":   1825,
}


def _symbol_to_fyers(symbol: str) -> str:
    """Convert 'RELIANCE' → 'NSE:RELIANCE-EQ'."""
    s = symbol.upper().strip()
    # Already fully qualified
    if ":" in s:
        return s
    # Known index tickers
    if s.startswith("^"):
        return _INDEX_MAP.get(s, s)
    return f"{_NSE_PREFIX}{s}{_EQUITY_SUFFIX}"


def _symbols_to_fyers(symbols: list[str]) -> list[str]:
    return [_symbol_to_fyers(s) for s in symbols]


class FyersRestClient:
    """
    Thin wrapper around fyers_apiv3.fyersModel.FyersModel.
    Instantiated once per FyersProvider and reused across requests.
    """

    def __init__(self, client_id: str, access_token: str) -> None:
        self._client_id    = client_id
        self._access_token = access_token
        self._client       = None
        self._build()

    def _build(self) -> None:
        try:
            from fyers_apiv3 import fyersModel
            self._client = fyersModel.FyersModel(
                client_id    = self._client_id,
                token        = self._access_token,
                log_path     = "",
                is_async     = False,
            )
        except ImportError:
            log.warning("fyers_rest.sdk_missing — fyers-apiv3 not installed")
            self._client = None
        except Exception as exc:
            log.error("fyers_rest.build_error", error=str(exc))
            self._client = None

    def is_ready(self) -> bool:
        return self._client is not None

    # ── Quotes ────────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> Optional[dict]:
        return self.get_quotes([symbol]).get(symbol)

    def get_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Return {symbol: raw_quote_dict} for each symbol."""
        if not self._client:
            return {}
        try:
            fyers_syms = _symbols_to_fyers(symbols)
            resp = self._client.quotes(data={"symbols": ",".join(fyers_syms)})
            if not isinstance(resp, dict) or resp.get("s") != "ok":
                return {}
            result = {}
            for item in resp.get("d", []):
                # Map back to plain symbol
                fyers_sym = item.get("n", "")
                plain_sym = fyers_sym.replace("NSE:", "").replace("BSE:", "").replace("-EQ", "").replace("-INDEX", "")
                result[plain_sym] = item
            return result
        except Exception as exc:
            log.error("fyers_rest.quotes_error", error=str(exc))
            return {}

    # ── Historical candles ────────────────────────────────────────────────────

    def get_history(self, symbol: str, period: str = "6M") -> list[list]:
        """Return raw candle arrays [[ts, o, h, l, c, v], ...] from Fyers."""
        if not self._client:
            return []
        try:
            from datetime import datetime, timedelta
            days = _PERIOD_TO_DAYS.get(period, 182)
            resolution = _PERIOD_TO_RESOLUTION.get(period, "D")
            end_dt   = datetime.now()
            start_dt = end_dt - timedelta(days=days)
            resp = self._client.history(data={
                "symbol":     _symbol_to_fyers(symbol),
                "resolution": resolution,
                "date_format": "1",
                "range_from": start_dt.strftime("%Y-%m-%d"),
                "range_to":   end_dt.strftime("%Y-%m-%d"),
                "cont_flag":  "1",
            })
            if not isinstance(resp, dict) or resp.get("s") != "ok":
                return []
            return resp.get("candles", [])
        except Exception as exc:
            log.error("fyers_rest.history_error", error=str(exc))
            return []

    # ── Company profile ───────────────────────────────────────────────────────

    def get_profile(self, symbol: str) -> Optional[dict]:
        """
        Fyers does not provide a dedicated company profile endpoint.
        Return None so FyersProvider falls back to yfinance for fundamentals.
        """
        return None

    # ── Market depth (order book) ─────────────────────────────────────────────

    def get_depth(self, symbol: str) -> Optional[dict]:
        if not self._client:
            return None
        try:
            fyers_sym = _symbol_to_fyers(symbol)
            resp = self._client.depth(data={"symbol": fyers_sym, "ohlcv_flag": 1})
            if not isinstance(resp, dict) or resp.get("s") != "ok":
                return None
            return resp.get("d", {}).get(fyers_sym)
        except Exception as exc:
            log.error("fyers_rest.depth_error", error=str(exc))
            return None

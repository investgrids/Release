"""Transform raw provider data → standard IndexQuote model."""
from __future__ import annotations

import math
from typing import Optional

from ..types import IndexQuote


def _safe_float(v, default: float = 0.0) -> float:
    try:
        f = float(v or default)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


def from_yfinance_fast_info(name: str, ticker: str, fast_info, flag: str = "") -> Optional[IndexQuote]:
    try:
        price = _safe_float(fast_info.last_price)
        prev  = _safe_float(fast_info.previous_close)
        if not price or not prev:
            return None
        change = price - prev
        pct    = (change / prev) * 100
        return IndexQuote(
            name           = name,
            ticker         = ticker,
            value          = round(price,  2),
            change         = round(change, 2),
            change_percent = round(pct,    4),
            flag           = flag,
        )
    except Exception:
        return None


def from_dict(name: str, ticker: str, price: float, prev: float, flag: str = "") -> Optional[IndexQuote]:
    if not price or not prev:
        return None
    change = price - prev
    pct    = (change / prev) * 100
    return IndexQuote(
        name           = name,
        ticker         = ticker,
        value          = round(price,  2),
        change         = round(change, 2),
        change_percent = round(pct,    4),
        flag           = flag,
    )

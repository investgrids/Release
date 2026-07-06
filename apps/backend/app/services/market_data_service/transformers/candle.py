"""Transform raw provider OHLCV data → standard Candle model."""
from __future__ import annotations

import math
from typing import Optional

from ..types import Candle


def _safe_float(v, default: float = 0.0) -> float:
    try:
        f = float(v or default)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


def from_yfinance_row(idx, row) -> Optional[Candle]:
    """Build a Candle from a yfinance DataFrame row."""
    try:
        def _col(name: str) -> float:
            val = row.get(name, 0)
            if hasattr(val, "iloc"):
                val = val.iloc[0]
            return _safe_float(val)

        close = _col("Close")
        if close == 0.0:
            return None

        ts = idx.strftime("%Y-%m-%dT%H:%M:%S") if hasattr(idx, "strftime") else str(idx)

        return Candle(
            timestamp = ts,
            open      = _col("Open"),
            high      = _col("High"),
            low       = _col("Low"),
            close     = close,
            volume    = int(_col("Volume")),
        )
    except Exception:
        return None


def from_fyers_candle(raw: list) -> Optional[Candle]:
    """
    Build a Candle from a Fyers candle array.
    Fyers format: [timestamp_unix, open, high, low, close, volume]
    """
    try:
        from datetime import datetime
        ts_unix = int(raw[0])
        ts_str  = datetime.utcfromtimestamp(ts_unix).strftime("%Y-%m-%dT%H:%M:%S")
        return Candle(
            timestamp = ts_str,
            open      = _safe_float(raw[1]),
            high      = _safe_float(raw[2]),
            low       = _safe_float(raw[3]),
            close     = _safe_float(raw[4]),
            volume    = int(_safe_float(raw[5])),
        )
    except Exception:
        return None


def to_chart_points(candles: list[Candle], date_format: str = "%b %d") -> list[dict]:
    """Convert candles to [{"label": ..., "value": close}] for sparklines."""
    result = []
    for c in candles:
        try:
            from datetime import datetime
            dt  = datetime.fromisoformat(c.timestamp)
            lbl = dt.strftime(date_format)
        except Exception:
            lbl = c.timestamp[:10]
        result.append({"label": lbl, "value": c.close})
    return result

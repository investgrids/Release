"""Transform raw provider data → standard SectorPerformance model."""
from __future__ import annotations

import math
from typing import Optional

from ..types import SectorPerformance


def _safe_float(v, default: float = 0.0) -> float:
    try:
        f = float(v or default)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


def from_pct(sector_id: str, name: str, change_pct: float) -> SectorPerformance:
    return SectorPerformance(
        id             = sector_id,
        name           = name,
        change_percent = round(change_pct, 4),
    )


def from_yfinance_fast_info(sector_id: str, name: str, fast_info) -> Optional[SectorPerformance]:
    try:
        price = _safe_float(fast_info.last_price)
        prev  = _safe_float(fast_info.previous_close)
        if not price or not prev:
            return None
        pct = (price - prev) / prev * 100
        return from_pct(sector_id, name, pct)
    except Exception:
        return None

"""
PriceBar — durable daily OHLCV warehouse (Phase 2B §1/§6).

Confirmed by the Phase 2A architecture audit: no existing table
(MarketSnapshot, HistoricalMarketEvent, PredictionRecord) stores a
per-symbol OHLCV time series — every price value in this app was fetched
live and discarded. This is the first table that persists one.

One table for all timeframes (a `timeframe` column), not a table per
timeframe — daily only in V1 (Phase 2B §1), matching this codebase's
existing preference for one flexible table over many narrow ones (see
MarketSnapshot's own `snapshot_type` column for the same pattern).

`adjusted_close` is intentionally separate from `close`: every current
yfinance call site in this app uses `auto_adjust=True`, which folds
split/dividend adjustment into OHLC directly — so `close` here is
*already* adjusted. `adjusted_close` exists to record a provider that
returns unadjusted data without losing the ability to tell later, not
because Kronos needs two different numbers today (Phase 2A §5: adjusted
OHLCV is what this app has ever validated).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Float, Integer, String,
    Date, DateTime, UniqueConstraint, Index,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PriceBar(Base):
    __tablename__ = "price_bars"

    id             = Column(String(36),  primary_key=True)   # UUID, matches PredictionRecord convention
    symbol         = Column(String(32),  nullable=False, index=True)   # canonical bare symbol (Phase 2A §4) — "RELIANCE", never "RELIANCE.NS"
    timeframe      = Column(String(8),   nullable=False, default="1d")  # "1d" only in V1
    bar_date       = Column(Date,        nullable=False, index=True)    # trading date this bar covers

    open           = Column(Float,       nullable=False)
    high           = Column(Float,       nullable=False)
    low            = Column(Float,       nullable=False)
    close          = Column(Float,       nullable=False)
    volume         = Column(Integer,     nullable=True)   # nullable: indices have no volume

    adjusted_close = Column(Float,       nullable=True)   # see module docstring — usually None; `close` is already adjusted
    is_adjusted    = Column(Boolean,     nullable=False, default=True)   # True for every yfinance fetch in this app (auto_adjust=True)

    source         = Column(String(16),  nullable=False, default="yfinance")   # provenance — "yfinance" | "fyers"
    data_quality   = Column(String(24),  nullable=False, default="good")
    # good | thin_volume | gap_detected | corporate_action_uncertain — see price_warehouse.py

    ingested_at    = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "bar_date", name="ux_price_bars_symbol_tf_date"),
        Index("ix_price_bars_symbol_date", "symbol", "bar_date"),
    )

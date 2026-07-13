"""
Historical Market Memory — DB model.

Stores real Indian market events with verified price reactions.
Used to ground AI analysis in historical evidence instead of hallucinations.
"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, Text, JSON
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class HistoricalMarketEvent(Base):
    """
    One entry = one verified historical market event with real price outcomes.

    Similarity is computed across: category, sector overlap, sentiment,
    market regime, interest rate trend, crude trend — all structured fields.
    No vector DB required.
    """
    __tablename__ = "historical_market_events"

    id = Column(String(64), primary_key=True, index=True)

    # ── Identity ───────────────────────────────────────────────────────────────
    event_title       = Column(Text, nullable=False)
    event_date        = Column(DateTime(timezone=True), nullable=False, index=True)
    category          = Column(String(64), nullable=False, index=True)
    # "Monetary Policy" | "Union Budget" | "Geopolitical" | "Corporate Crisis"
    # "Global Market Shock" | "Infrastructure Policy" | "Regulatory"
    # "Commodity Shock" | "Election" | "Sectoral Policy" | "Trade Policy"
    sentiment         = Column(String(16), nullable=True)   # bullish/bearish/neutral/mixed

    # ── Classification ─────────────────────────────────────────────────────────
    sectors           = Column(JSON, nullable=False, default=list)
    companies         = Column(JSON, nullable=False, default=list)  # NSE symbols
    tags              = Column(JSON, nullable=False, default=list)  # free-text searchable keywords

    # ── Market context at time of event (used for similarity matching) ─────────
    market_regime          = Column(String(16), nullable=True)   # bull/bear/recovery/sideways
    interest_rate_trend    = Column(String(16), nullable=True)   # rising/falling/stable
    crude_trend            = Column(String(16), nullable=True)   # rising/falling/stable
    interest_rate_level    = Column(Float, nullable=True)        # RBI repo rate % at event time
    vix_level              = Column(Float, nullable=True)        # India VIX at event time

    # ── Nifty 50 market reactions (% change from event date close) ─────────────
    nifty_1d          = Column(Float, nullable=True)   # e.g. -5.9 means -5.9%
    nifty_3d          = Column(Float, nullable=True)
    nifty_1w          = Column(Float, nullable=True)
    nifty_1m          = Column(Float, nullable=True)

    # ── Sector-level reactions ─────────────────────────────────────────────────
    # {"Banking": +2.1, "IT": -0.5, "Infrastructure": +8.3}
    sector_reactions  = Column(JSON, nullable=False, default=dict)

    # ── Stock-level outcomes ───────────────────────────────────────────────────
    # [{"symbol": "LT", "name": "L&T", "return_1w": 9.2, "return_1m": 14.5,
    #   "reason": "Direct capex beneficiary"}]
    historical_winners = Column(JSON, nullable=False, default=list)
    historical_losers  = Column(JSON, nullable=False, default=list)

    # ── Intelligence scores ────────────────────────────────────────────────────
    opportunity_score  = Column(Float, nullable=True)  # 0-100
    risk_score         = Column(Float, nullable=True)  # 0-100
    confidence         = Column(Float, nullable=True)  # how reliable is this historical data

    # ── Narrative ──────────────────────────────────────────────────────────────
    what_happened     = Column(Text, nullable=True)   # 1-2 sentence summary
    key_lesson        = Column(Text, nullable=True)   # what did this teach us

    # ── Metadata ───────────────────────────────────────────────────────────────
    source            = Column(String(32), nullable=False, default="seed")  # seed/auto/manual
    created_at        = Column(DateTime(timezone=True), default=_now, index=True)

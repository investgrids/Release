from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, Text, JSON
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class EventTriage(Base):
    """AI triage result for every ingested event."""
    __tablename__ = "event_triage"

    id = Column(String, primary_key=True, index=True)
    event_id = Column(String, nullable=False, index=True)
    source = Column(String(64), nullable=False)           # news/policy/price/synthetic
    headline = Column(Text, nullable=False)
    urgency = Column(Integer, nullable=False, default=0)   # 0–10
    importance = Column(Integer, nullable=False, default=0)
    confidence = Column(Integer, nullable=False, default=0)
    sentiment = Column(String(16), nullable=True)          # bullish/bearish/neutral
    horizon = Column(String(16), nullable=True)            # intraday/short/long
    market_impact = Column(String(16), nullable=True)      # high/medium/low
    is_structural = Column(Boolean, nullable=False, default=False)
    direction = Column(String(16), nullable=True)          # up/down/sideways
    one_liner = Column(Text, nullable=True)
    themes = Column(JSON, nullable=False, default=list)
    sectors = Column(JSON, nullable=False, default=list)
    tickers = Column(JSON, nullable=False, default=list)
    broadcast = Column(Boolean, nullable=False, default=False)
    refresh_homepage = Column(Boolean, nullable=False, default=False)
    triaged_at = Column(DateTime(timezone=True), default=_now, index=True)


class MarketSnapshot(Base):
    """Periodic snapshot of market state — used to detect material change."""
    __tablename__ = "market_snapshots"

    id = Column(String, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), default=_now, index=True)
    nifty_level = Column(Float, nullable=True)
    nifty_change_pct = Column(Float, nullable=True)
    banknifty_level = Column(Float, nullable=True)
    banknifty_change_pct = Column(Float, nullable=True)
    vix = Column(Float, nullable=True)
    advances = Column(Integer, nullable=True)
    declines = Column(Integer, nullable=True)
    fii_net = Column(Float, nullable=True)
    sector_ranks = Column(JSON, nullable=False, default=list)
    top_themes = Column(JSON, nullable=False, default=list)
    mood = Column(String(32), nullable=True)
    story_hash = Column(String(64), nullable=True)


class MarketStory(Base):
    """AI-generated market narrative — updated every 5 min on material change."""
    __tablename__ = "market_stories"

    id = Column(String, primary_key=True, index=True)
    generated_at = Column(DateTime(timezone=True), default=_now, index=True)
    story = Column(Text, nullable=False)
    mood = Column(String(32), nullable=True)
    pulse = Column(String(4), nullable=True)               # +/=/-
    sector_rotation = Column(Text, nullable=True)
    direction = Column(String(16), nullable=True)
    opportunity = Column(Text, nullable=True)
    risk = Column(Text, nullable=True)
    trader_watch = Column(Text, nullable=True)
    investor_watch = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)
    events_included = Column(JSON, nullable=False, default=list)
    previous_story_hash = Column(String(64), nullable=True)
    story_hash = Column(String(64), nullable=True, index=True)
    nifty_at = Column(Float, nullable=True)
    vix_at = Column(Float, nullable=True)


class ThemeState(Base):
    """Current scoring state for each of the 12 active market themes."""
    __tablename__ = "theme_state"

    id = Column(String, primary_key=True, index=True)
    theme = Column(String(128), nullable=False, index=True, unique=True)
    score = Column(Float, nullable=False, default=0.0)     # 0–100
    momentum = Column(String(16), nullable=True)           # rising/falling/stable
    top_stocks = Column(JSON, nullable=False, default=list)
    top_events = Column(JSON, nullable=False, default=list)
    news_count_24h = Column(Integer, nullable=False, default=0)
    price_signal = Column(Float, nullable=True)
    news_signal = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

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
    origin = Column(String(128), nullable=True)            # real outlet, e.g. "Economic Times", "NSE"
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
    """Periodic snapshot of market state — used to detect material change.

    Weekend Intelligence Phase 1A: this table was defined for exactly this
    purpose but nothing ever wrote to it (confirmed zero writes anywhere in
    the repo, see WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §1). Extended
    here with snapshot_type/pcr/max_pain/top_movers rather than creating a
    new table, and price_monitor.py now writes exactly one immutable
    snapshot_type="close" row per trading session — see
    services/intelligence/price_monitor.py's capture_close_snapshot().
    Every other field on this model stays exactly as it was; periodic
    (non-close) snapshots are still not written by anything in Phase 1A —
    that would be a separate, unrequested change (see design doc §3: "do
    not start persisting periodic snapshots every 2 minutes unless there
    is a demonstrated requirement").
    """
    __tablename__ = "market_snapshots"

    id = Column(String, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), default=_now, index=True)
    # "periodic" (unused today, reserved for a future cadence) | "close"
    # (the one kind Phase 1A actually writes — see capture_close_snapshot).
    snapshot_type = Column(String(16), nullable=False, default="periodic", index=True)
    # trading_date, not a literal weekday name — see design doc §6/§18 on
    # avoiding "Friday"-shaped naming so this generalizes once a real
    # holiday calendar exists. YYYY-MM-DD, IST calendar date of the session
    # this snapshot represents (not the UTC date `ts` might fall on).
    trading_date = Column(String(10), nullable=True, index=True)
    nifty_level = Column(Float, nullable=True)
    nifty_change_pct = Column(Float, nullable=True)
    banknifty_level = Column(Float, nullable=True)
    banknifty_change_pct = Column(Float, nullable=True)
    vix = Column(Float, nullable=True)
    advances = Column(Integer, nullable=True)
    declines = Column(Integer, nullable=True)
    fii_net = Column(Float, nullable=True)
    # NSE Nifty PCR / max pain at capture time — nullable, never a
    # substituted default when the live fetch fails (design doc §9).
    pcr = Column(Float, nullable=True)
    max_pain = Column(Float, nullable=True)
    # Compact close-time top movers only — [{"symbol": "...", "change_pct": ...}],
    # never a copy of full quote payloads (design doc §3).
    top_movers = Column(JSON, nullable=False, default=list)
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

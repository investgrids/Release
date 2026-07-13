from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, Text, JSON
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class CompanyAnnouncement(Base):
    """Corporate announcements ingested from BSE/NSE feeds."""
    __tablename__ = "company_announcements"

    id = Column(String, primary_key=True, index=True)
    symbol = Column(String(32), nullable=True, index=True)
    company_name = Column(String(256), nullable=True)
    source = Column(String(16), nullable=False, default="NSE")   # NSE | BSE
    category = Column(String(64), nullable=True)                 # Board Meeting, Results, Dividend…
    subject = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    announcement_date = Column(DateTime(timezone=True), nullable=True, index=True)
    attachment_url = Column(Text, nullable=True)
    impact_score = Column(Integer, nullable=True)                # 0-10, AI-assigned
    sentiment = Column(String(16), nullable=True)               # bullish/bearish/neutral
    is_high_impact = Column(Boolean, nullable=False, default=False)
    sectors = Column(JSON, nullable=False, default=list)
    themes = Column(JSON, nullable=False, default=list)
    ai_summary = Column(Text, nullable=True)
    ingested_at = Column(DateTime(timezone=True), default=_now, index=True)

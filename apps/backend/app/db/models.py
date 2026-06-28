from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import mapped_column
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    summary = Column(Text, nullable=False)
    impact_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    sectors = Column(JSON, nullable=False, default=list)
    companies = Column(JSON, nullable=False, default=list)
    category = Column(String(64), nullable=True)
    published_at = Column(DateTime(timezone=True), default=_now)


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(String, primary_key=True, index=True)
    headline = Column(String(512), nullable=False)
    summary = Column(Text, nullable=False)
    source = Column(String(128), nullable=False)
    published_at = Column(String(64), nullable=False)
    companies = Column(JSON, nullable=False, default=list)
    impact_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True, index=True)
    category = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    date = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)


class RadarOpportunity(Base):
    __tablename__ = "radar_opportunities"

    id = Column(String, primary_key=True, index=True)
    theme = Column(String(256), nullable=False)
    score = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    beneficiaries = Column(JSON, nullable=False, default=list)


class Story(Base):
    __tablename__ = "stories"

    id = Column(String, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    theme = Column(String(128), nullable=False)
    image = Column(String(512), nullable=False)


class SectorData(Base):
    __tablename__ = "sector_data"

    id = Column(String, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    value = Column(String(16), nullable=False)
    positive = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), default=_now)

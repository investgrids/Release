"""
Phase 5A.8 — response schemas for the canonical Economic Calendar API.

scheduled_at is always UTC; scheduled_at_ist is the same instant
rendered for Indian users (Phase 5A §4's explicit requirement: "API
must be able to render IST for Indian users while preserving original
source timezone"); source_timezone preserves the source's own zone so
nothing about the original announcement is lost.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EconomicCalendarEventOut(BaseModel):
    id: str
    title: str
    category: str
    country: str
    region: str | None
    scheduled_at: datetime
    scheduled_at_ist: datetime
    source_timezone: str
    importance: str
    actual: float | None
    forecast: float | None
    previous: float | None
    unit: str | None
    status: str
    source: str
    source_tier: str
    companies: list[str]
    sectors: list[str]
    themes: list[str]
    last_verified_at: datetime


class SourceHealthOut(BaseModel):
    source: str
    is_real_source: bool
    current_rows: int
    last_verified_at: str | None
    is_stale: bool
    next_scheduled_at: str | None

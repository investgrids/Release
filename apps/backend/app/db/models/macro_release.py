"""
MacroRelease — structured representation of a macro-economic data release
(CPI, GDP, IIP, WPI, GST, trade balance, fiscal deficit, employment, and
foreign central-bank decisions), as opposed to treating these as generic
Event/news rows with only a headline.

Phase 7 (2026-08 audit): before this, a CPI print or a GST collections
release was indistinguishable in the data model from any other policy
press release — no metric/value/unit/period fields, just a headline
string. This table doesn't replace Event (a MacroRelease row is created
ALONGSIDE the Event row already created from the same RawItem by
ingest_tasks._create_events, sharing the same id) — it's an additional,
optional structured layer populated only when app.services.macro_extraction
can confidently parse a real number out of the source text. No row is
created, and no field is guessed, when it can't.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, JSON, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MacroRelease(Base):
    __tablename__ = "macro_releases"

    id = Column(String, primary_key=True)
    # Same id as the Event row created from the same source item, where one
    # exists — lets a consumer join back to the generic Event/EventCoverage
    # pipeline without a separate foreign-key relationship to maintain.
    event_id = Column(String, nullable=True, index=True)

    metric = Column(String(32), nullable=False, index=True)
    # CPI | GDP | IIP | WPI | GST | TRADE_BALANCE | FISCAL_DEFICIT | EMPLOYMENT
    # FED_DECISION | ECB_DECISION | CHINA_MACRO

    # ── Real, extracted values only — every one of these stays NULL rather
    # than being guessed or defaulted when the source text doesn't clearly
    # state it. expected_value in particular is NEVER populated by this
    # codebase today — no ingested source provides a verified analyst
    # consensus figure, and Phase 21's rule is absolute on this point. ──
    release_value  = Column(Float, nullable=True)
    previous_value = Column(Float, nullable=True)
    expected_value = Column(Float, nullable=True)
    unit           = Column(String(16), nullable=True)   # "%", "₹cr", "$bn"
    period         = Column(String(32), nullable=True)   # "July 2026", "Q1 FY27"

    geography = Column(String(32), nullable=False, default="India")
    importance = Column(String(16), nullable=True)  # Critical | High | Medium | Low

    # Sector sensitivity is a small, static, documented mapping per metric
    # (see macro_extraction.SECTOR_SENSITIVITY) — structural knowledge, not
    # a per-release AI inference. Company-level exposure is NOT populated
    # here — that needs real per-company evidence this extractor doesn't
    # have, so affected_companies always stays an empty list, never guessed.
    affected_sectors   = Column(JSON, nullable=False, default=list)
    affected_companies = Column(JSON, nullable=False, default=list)

    source      = Column(String(64), nullable=True)   # PIB | RBI
    source_url  = Column(Text, nullable=True)
    headline    = Column(Text, nullable=False)
    raw_summary = Column(Text, nullable=True)

    release_date = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now, index=True)

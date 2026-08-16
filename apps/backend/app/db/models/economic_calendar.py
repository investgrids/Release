"""
EconomicCalendarEvent — Phase 5A.1.

"What is scheduled to happen?" — deliberately separate from MacroRelease
("what actually happened?", app/db/models/macro_release.py). The Phase
5A audit found every existing model either retrospective-only
(MacroRelease, GovernmentPolicy, CompanyAnnouncement, Event) or
schema-incompatible (the legacy CalendarEvent's `date` is a display
string, not a real datetime) — this is a new table because nothing
existing could honestly represent "this hasn't happened yet."

Identity design (owner's explicit correction to the original audit
draft): `identity_key` is `category:country:reference_period` and
NEVER includes scheduled_at. A postponed release (e.g. US CPI for July
2026 moved from Aug 12 to Aug 13) is still the same economic event —
putting the date in the identity would make a reschedule look like a
brand-new, unrelated event to the ingestion system. `reference_period`
is the period being measured for data releases ("2026-07"), or a
deterministic occurrence anchor (the scheduled month) for meeting-type
events with no natural "period" (RBI MPC, FOMC, ECB) — stable across an
intra-month reschedule, which is the realistic case; a shift to a
different month is rare/notable enough to be treated as a new
occurrence, a reasonable boundary rather than an edge case worth extra
machinery.

Versioning: `is_current` + a partial unique index on `identity_key`
(same proven pattern as WeekendIntelligenceSnapshot's versioning.py —
reused, not reinvented). A genuine revision (a corrected number
published after the fact) creates a NEW row with `is_current=True`,
flips the prior row's `is_current` to False, and links back via
`revision_of` — the prior value is never lost. The everyday
scheduled -> released transition is NOT a revision; it's the same row,
same version, `status` and `actual`/`released_at` updated in place,
exactly like every other append-preferring table in this codebase
(MacroRelease, PriceBar) already treats "update the one real row" vs.
"a new fact happened" as different operations.

`macro_release_id` is an optional forward link to the MacroRelease row
created once the release actually happens (own request: "create the
calendar contract so this relationship isn't impossible later" —
deliberately not a hard FK-required-at-creation-time relationship,
since a MacroRelease row for this event doesn't exist yet when the
calendar row is first scheduled).

`forecast` stays NULL in V1 — the audit found no reliable free
consensus-forecast source for any market. Never fabricated, matching
MacroRelease.expected_value's existing, identical rule.

`source_tier` (owner's explicit naming: "confidence sounds like a
probability; tier means provenance authority") — "tier_1" (official
issuing institution) / "tier_2" (reputable but not first-party) /
"tier_3" (news confirmation only). A lower tier may fill a field a
higher tier hasn't already set, never overwrite one a higher tier did
— enforced by the sync engine (Phase 5A.6), not by this schema alone.

No row is ever deleted after release — this is what lets Phase 5A's
data eventually answer "RBI decision -> Nifty reaction" the same way
Phase 2D's price-outcome research already does.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    JSON, String, Text, text,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EconomicCalendarEvent(Base):
    __tablename__ = "economic_calendar_events"

    id             = Column(String(36), primary_key=True)

    # ── Identity (see module docstring — never includes scheduled_at) ──────
    identity_key      = Column(String(128), nullable=False, index=True)   # "category:country:reference_period"
    reference_period  = Column(String(32), nullable=False)                # "2026-07" (measured period) or occurrence-anchor month
    version           = Column(Integer, nullable=False, default=1)
    is_current        = Column(Boolean, nullable=False, default=True, index=True)
    revision_of       = Column(String(36), ForeignKey("economic_calendar_events.id"), nullable=True)

    # ── What / where ─────────────────────────────────────────────────────
    title    = Column(String(256), nullable=False)
    category = Column(String(32), nullable=False, index=True)   # "rbi_policy" | "india_cpi" | "fomc" | "us_cpi" | "us_jobs" | ...
    country  = Column(String(8),  nullable=False, index=True)   # "IN" | "US" | "EU" | "GB"
    region   = Column(String(32), nullable=True)

    # ── When — UTC-aware always, source's own timezone preserved separately
    #    so a render is never a guess (Phase 5A §4) ────────────────────────
    scheduled_at     = Column(DateTime(timezone=True), nullable=False, index=True)
    source_timezone  = Column(String(64), nullable=False)   # IANA name, e.g. "Asia/Kolkata", "America/New_York"

    # ── Deterministic, category-based — never LLM-decided (Phase 5A §9) ───
    importance = Column(String(16), nullable=False)   # "critical" | "high" | "medium" | "low"

    # ── Values — forecast stays NULL in V1, never fabricated ──────────────
    actual   = Column(Float, nullable=True)
    forecast = Column(Float, nullable=True)
    previous = Column(Float, nullable=True)
    unit     = Column(String(32), nullable=True)

    status      = Column(String(16), nullable=False, default="scheduled")   # "scheduled" | "released" | "revised" | "cancelled"
    released_at = Column(DateTime(timezone=True), nullable=True)

    # ── Provenance ──────────────────────────────────────────────────────
    source       = Column(String(16), nullable=False)   # "rbi" | "mospi" | "fed" | "bls" | "bea" | "eurostat" | "ecb" | "seed"
    source_url   = Column(Text, nullable=True)
    source_tier  = Column(String(8), nullable=False)     # "tier_1" | "tier_2" | "tier_3"

    companies = Column(JSON, nullable=False, default=list)
    sectors   = Column(JSON, nullable=False, default=list)
    themes    = Column(JSON, nullable=False, default=list)

    # ── Forward link to the eventual real-outcome row — optional, filled
    #    in later once the release actually happens (Phase 2D-style
    #    scheduled -> released -> outcome research becomes possible without
    #    a redesign) ─────────────────────────────────────────────────────
    macro_release_id = Column(String(36), ForeignKey("macro_releases.id"), nullable=True)

    last_verified_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    created_at       = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at       = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        # At most one CURRENT row per identity — a revision inserts a new
        # row and flips the prior one's is_current to False rather than
        # overwriting it (same pattern as WeekendIntelligenceSnapshot's
        # versioning.py — reused, not reinvented).
        Index(
            "ux_ece_identity_current",
            "identity_key",
            unique=True,
            sqlite_where=text("is_current = 1"),
            postgresql_where=text("is_current = true"),
        ),
        Index("ix_ece_scheduled_at", "scheduled_at"),
        Index("ix_ece_country_category", "country", "category"),
    )

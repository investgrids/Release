"""
Global transmission relationships — an ISOLATED store for the Global Markets
Brief's "potential India impact" layer (2026-10-20).

Deliberately NOT part of the shared intelligence graph (ig_nodes/ig_edges):
that graph has 15+ consumers (Ripple Intelligence, AI Search ripple, the
decision engine, /api/graph, company ripple, …), so adding global-factor
nodes/edges there would change their established behavior. This table is read
ONLY by the Global Markets Brief's deterministic linkage query and by nothing
else, keeping Ripple Intelligence untouched.

A row is a documented POTENTIAL transmission path (e.g. "US 10Y yields rise →
pressure on Indian rate-sensitive sectors"). It is eligible to produce a
hypothesis only when human-approved AND backed by a real cited source — a row
existing is never, by itself, evidence. Zero approved rows ⇒ zero India
implications, which is the correct empty state, not an incomplete build.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class GlobalTransmissionRelationship(Base):
    __tablename__ = "global_transmission_relationships"

    id = Column(String, primary_key=True, index=True)

    # Source: a global market factor (not a free-text string downstream — the
    # linkage query matches observed triggers on source_factor).
    source_factor = Column(String(48), nullable=False, index=True)   # e.g. "US_10Y_YIELD", "DXY", "BRENT", "US_RISK_OFF", "FED_POLICY"
    source_factor_label = Column(String(96), nullable=False)

    # Target: a supported Indian instrument / sector / indicator.
    target_type = Column(String(16), nullable=False)                 # "sector" | "instrument" | "indicator"
    target_key = Column(String(48), nullable=False)                  # e.g. "rate_sensitive", "USDINR", "oil_sensitive", "fii_flows"
    target_label = Column(String(96), nullable=False)

    # Semantics: effect on the target when the source factor RISES.
    direction = Column(String(8), nullable=False)                    # "positive" | "negative"
    confidence = Column(Float, nullable=False, default=0.0)          # 0.0–1.0

    # Explicit transmission window (no silent default — the linkage rule tests
    # for a defined, non-negative window).
    lag_days_min = Column(Integer, nullable=True)
    lag_days_max = Column(Integer, nullable=True)

    # Evidence + provenance.
    evidence_basis = Column(Text, nullable=False)                    # the reasoning / what the relationship claims
    citation = Column(Text, nullable=True)                           # a REAL source; required for eligibility (human-supplied)
    provenance = Column(String(24), nullable=False, default="human_curated")

    # Human approval gate — the ONLY way a row becomes eligible.
    approved = Column(Boolean, nullable=False, default=False)
    approved_by = Column(String(64), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

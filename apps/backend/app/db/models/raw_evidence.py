"""
RawEvidence — Phase 1B Batch 2 (owner instruction, 2026-08-23).

The immutable provenance layer underneath news_articles/events/
government_policies/Development Memory — confirmed by the Phase 1A audit
to not previously exist anywhere in the codebase (every fetcher
discarded its raw content the instant parsing completed). This table
does NOT replace or duplicate DevelopmentEvidence; it sits one layer
below the existing normalization pipeline, purely additive.

Identity, corrected per owner instruction (2026-08-23):
  evidence_key  = stable identity of the real-world source item —
                  f"{source_type}:{provider's own raw id}", reusing the
                  SAME id each provider already computes and that
                  news_articles.id/events.id already use as identity
                  throughout the rest of this codebase, rather than
                  inventing a third, competing notion of "identity" for
                  the same real-world items. Constant across versions.
  payload_hash  = sha256 of the raw (pre-normalize) payload — changes
                  when the source's actual content changes.
  UNIQUE(evidence_key, payload_hash) — an identical re-fetch (same key,
  same hash) is suppressed at write time (see raw_evidence.py); a
  genuine content change (same key, new hash) becomes a new row, an
  immutable version, never an overwrite of the old one.

published_at is nullable and only ever a real parsed datetime — never a
relative string like "2h ago" (the confirmed news_articles.published_at
bug from the Phase 1A audit). observed_at is always real (when this
fetch actually happened) and is the reliable anchor when a source's own
publication time can't be trusted or parsed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RawEvidence(Base):
    __tablename__ = "raw_evidence"

    id            = Column(String(36), primary_key=True)

    evidence_key  = Column(String(200), nullable=False, index=True)
    payload_hash  = Column(String(64), nullable=False)

    source_id     = Column(String(64), ForeignKey("sources.id"), nullable=False, index=True)
    source_type   = Column(String(24), nullable=False)   # rss | nse | rbi | pib | sebi | fed
    external_id   = Column(String(200), nullable=True)   # the provider's own raw id, where present

    title         = Column(String(512), nullable=True)
    published_at  = Column(DateTime(timezone=True), nullable=True)   # real parsed datetime only, or NULL — never a relative string
    observed_at   = Column(DateTime(timezone=True), nullable=False)   # always real — when this fetch happened
    ingested_at   = Column(DateTime(timezone=True), nullable=False, default=_now)

    source_url    = Column(String(1000), nullable=True)
    raw_payload   = Column(Text, nullable=True)   # JSON-serialized raw (pre-normalize) provider dict
    mime_type     = Column(String(32), nullable=False, default="application/json")

    quality       = Column(String(24), nullable=False, default="good")
    # good | filtered | invalid | parse_error — never silently discarded; a
    # failure still gets a real row if a raw payload was actually obtained
    # (see raw_evidence.py's capture logic for exactly which cases apply)

    __table_args__ = (
        UniqueConstraint("evidence_key", "payload_hash", name="ux_raw_evidence_identity"),
        Index("ix_raw_evidence_source_observed", "source_id", "observed_at"),
    )

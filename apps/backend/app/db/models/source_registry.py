"""
Source Registry — Phase 1B Batch 1 (owner instruction, 2026-08-23:
"Seed minimal Source Registry before tables that reference it").

Describes every external source MarketRipple actually pulls from, with
an honest `rights_basis` per source — the Phase 1A audit found only one
source (US Fed) carries any explicit rights-basis reasoning in code;
this table makes that answer explicit and required for every source,
including honest "unofficial_scraped_api" / "unverified" answers rather
than silence.

MarketObservation and (later) RawEvidence both FK into this table —
built and seeded first so those tables never reference a source_id that
doesn't exist.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id                = Column(String(64), primary_key=True)   # stable slug, e.g. "yfinance_india_vix"
    name              = Column(String(200), nullable=False)
    domain            = Column(String(200), nullable=True)
    source_type       = Column(String(24), nullable=False)   # rss | api | csv | json | http | scrape | document
    collection_method = Column(String(48), nullable=False)   # e.g. "official RSS", "unofficial internal JSON API (scraped)"
    frequency         = Column(String(32), nullable=True)     # human-readable — "15min", "daily 3AM IST", etc.
    priority          = Column(Integer, nullable=False, default=5)

    # Honest answer required per source — never left silent (Phase 1A finding).
    rights_basis      = Column(String(32), nullable=False, default="unverified")
    # public_domain | official_rss | official_api | unofficial_scraped_api | vendor_data | unverified
    robots_checked    = Column(Boolean, nullable=False, default=False)
    rate_limit        = Column(String(64), nullable=True)

    last_success      = Column(DateTime(timezone=True), nullable=True)
    last_failure      = Column(DateTime(timezone=True), nullable=True)
    notes             = Column(Text, nullable=True)

    created_at        = Column(DateTime(timezone=True), nullable=False, default=_now)

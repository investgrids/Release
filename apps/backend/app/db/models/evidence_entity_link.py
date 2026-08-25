"""
EvidenceEntityLink — real evidence-to-entity relationships (Warehouse
Consumption Phase 2, "the major unlock", per owner decision 2026-08-25).

The audit (artifacts/warehouse_consumption_audit.md §6) proved, on real
production data, that RawEvidence has no working path to any company: two
independent structural gaps (an id-scheme mismatch for NSE evidence, an
always-empty companies field for RSS evidence), and that a naive keyword/
title match over RawEvidence reproduces the exact 3IINFOLTD/IIFL
contamination shape (surfacing ICICI Lombard, a Senores Pharmaceuticals
filing that only names ICICI Bank as its lender, and an "ICICI Direct"
byline alongside genuine ICICI Bank evidence).

Deliberately NOT a single `entity_id` column on RawEvidence: evidence is
naturally many-to-many with entities (one RBI policy release can concern
several banks at once; a single NSE filing concerns exactly one company
today, but that's a property of the source, not a reason to force a
1:1 schema everywhere). A single column would force arrays/JSON or
duplication the moment a many-entity source is wired up.

Also deliberately does NOT touch RawEvidence.evidence_key/external_id
(the NSE seq_id) at all -- evidence identity and entity identity are
different concepts and this table exists specifically so fixing one
never requires compromising the other. See raw_evidence.py's own
docstring for why evidence_key intentionally uses seq_id, not an_no.

FKs into company_entities.entity_id (Company Master, C2) -- the real,
permanent, symbol-independent identity, not a ticker string. Only
whatever is actually resolvable to a real, unambiguous CompanyEntity row
gets a link; anything unresolved/ambiguous stays unlinked rather than
guessed (see resolver.py's own ResolutionStatus.UNRESOLVED/CONFLICT).

relationship_type + resolution_method record *why* a link exists, not
just *that* it exists -- deliberately starting with only what the real
producers can currently prove:
  relationship_type="subject", resolution_method="source_symbol" -- the
  one real, deterministic, no-AI-involved case today: an NSE filing's own
  `symbol` field names the company the filing is about. Richer types
  (mentioned/counterparty/peer/sector_affected) are NOT built here --
  no current producer can support them with real, provable evidence yet.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceEntityLink(Base):
    __tablename__ = "evidence_entity_links"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    raw_evidence_id   = Column(String(36), ForeignKey("raw_evidence.id"), nullable=False, index=True)
    entity_id         = Column(String(32), ForeignKey("company_entities.entity_id"), nullable=False, index=True)

    relationship_type = Column(String(24), nullable=False)   # subject | (mentioned/counterparty/peer/sector_affected -- not built yet)
    resolution_method = Column(String(32), nullable=False)   # source_symbol | (existing_entity_resolver -- not built yet)
    # NULL for deterministic resolution (source_symbol) -- confidence only
    # applies once a probabilistic resolution_method is actually built.
    confidence        = Column(Float, nullable=True)

    created_at        = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        # One evidence item can name the same entity only once per
        # relationship_type -- re-running the backfill or re-capturing the
        # same item must never create duplicate links.
        UniqueConstraint("raw_evidence_id", "entity_id", "relationship_type", name="ux_evidence_entity_link_identity"),
        Index("ix_evidence_entity_link_entity", "entity_id", "relationship_type"),
    )

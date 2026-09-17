"""
SourceDocument — Deep Filing Evidence Phase 1A (owner design, 2026-09-17).

The Document Evidence Layer, built before any structured fact schema.
NSE's `corporate-announcements` feed only ever carries the filing's own
one-line subject text (see raw_evidence.py) -- the Source Reality Audit
(2026-09-17, 24 real specimens across acquisitions/results/orders/
corporate-actions/regulatory disclosures) confirmed that a real,
substantial, genuinely text-extractable PDF attachment exists for
100% of real NSE filings sampled, and in 5/6 spot-checked cases
contained the exact investor-relevant fact the bare NSE subject line
lacked (ZODIAC's subsidiary/business detail, SUNSHINE's real revenue/
profit numbers, etc.) -- while NSE's own `hasXbrl` announcement-feed
flag was confirmed NON-AUTHORITATIVE (true in 100% of 1,861 filings
checked regardless of category; the real per-symbol signal is the
separate `corporates-financial-results` XBRL endpoint, which returned
ZERO rows for exactly the small/mid-cap companies causing Article V2's
"editorially thin" finding). This module stores the immutable,
provenance-bearing PDF evidence that closes that gap -- extraction
itself is another EVIDENCE representation, not intelligence; no LLM is
involved anywhere in this module.

Identity mirrors raw_evidence.py's own established pattern: a re-fetch
that produces byte-identical content is suppressed (see
source_document.py's capture logic); a genuine content change at the
same URL (NSE re-serving different bytes) becomes a NEW immutable
version, never a silent overwrite of the old row -- `content_hash` is
part of the row's identity, not just a change-detection aid.

No OCR (owner instruction): a document with no meaningfully extractable
text becomes TEXT_UNAVAILABLE, not a best-effort scan. Every downstream
structured fact this layer eventually feeds must be traceable back to
one exact SourceDocument row and (once a fact extractor exists) a page
within it -- this table is that anchor.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# extraction_status -- did we get real, usable text out of this document at all.
# Mirrors financial_fact.py's own "source truth is not quality truth" split:
# a status here is about what happened during fetch/parse, never a judgment
# about the CONTENT's investor relevance (that's the future fact extractor's job).
EXTRACTED = "EXTRACTED"                     # real, non-trivial text obtained
TEXT_UNAVAILABLE = "TEXT_UNAVAILABLE"       # fetched and parsed fine, but ~zero real text (scanned/image PDF) -- no OCR attempted, by design
FETCH_FAILED = "FETCH_FAILED"               # network/HTTP error or timeout -- never got the bytes at all
UNSUPPORTED_MIME = "UNSUPPORTED_MIME"       # downloaded bytes don't carry a real PDF signature -- never handed to a parser
SIZE_LIMIT_EXCEEDED = "SIZE_LIMIT_EXCEEDED" # real safety bound (bytes before download, pages after) -- refused, not truncated silently
PARSE_FAILED = "PARSE_FAILED"               # pypdf raised on a document that did pass the MIME/size checks -- a real parser failure, not a data-availability fact


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(String(36), primary_key=True)

    # The RawEvidence row whose own raw_payload named this document's
    # attachment URL -- every SourceDocument traces back to exactly one
    # real, already-provenanced announcement.
    raw_evidence_id = Column(String(36), ForeignKey("raw_evidence.id"), nullable=False, index=True)

    canonical_url = Column(String(1000), nullable=False)
    content_hash = Column(String(64), nullable=True)   # sha256 of the raw downloaded bytes; NULL only when FETCH_FAILED (no bytes obtained)
    byte_size = Column(Integer, nullable=True)
    mime_type = Column(String(64), nullable=True)      # server's own Content-Type header, recorded as reported -- never trusted for the UNSUPPORTED_MIME decision itself (see source_document.py: that check is on the real byte signature)

    retrieved_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    extraction_status = Column(String(24), nullable=False, index=True)
    extraction_method = Column(String(32), nullable=True)          # e.g. "pypdf"
    extraction_method_version = Column(String(32), nullable=True)
    error_detail = Column(Text, nullable=True)                     # real exception text when extraction_status isn't EXTRACTED

    page_count = Column(Integer, nullable=True)
    # JSON-serialized list[str], one entry per page, in document order --
    # this IS the page-boundary record a future fact extractor cites as
    # provenance (page N == page_texts[N-1]). NULL whenever extraction_status
    # != EXTRACTED -- never a partial/best-effort list.
    page_texts_json = Column(Text, nullable=True)

    __table_args__ = (
        # A byte-identical re-fetch of the same announcement's attachment
        # is suppressed at write time; a real content change (NSE serving
        # different bytes from the same URL) becomes a new row -- see
        # module docstring. NULL content_hash (FETCH_FAILED) rows are
        # never deduplicated against each other or anything else.
        UniqueConstraint("raw_evidence_id", "content_hash", name="ux_source_document_identity"),
        Index("ix_source_document_raw_evidence", "raw_evidence_id"),
    )

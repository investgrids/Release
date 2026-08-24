"""
Company Master — the authoritative company/security identity layer (C2).

CompanyEntity is keyed by a permanent internal entity_id, never by exchange
symbol — symbol is an attribute (see CompanyAlias), not the identity. This
directly targets the identity-fragmentation the C1 reconciliation measured
against real data: 22 duplicate Intelligence Graph identities for the same
company (RELIANCE / RELIANCE.NS / NSE:RELIANCE all being one real company),
plus real corporate-action cases — NSE's own symbol-change history shows
TATAMOTORS -> TMPV (24-OCT-2025) and LTI -> LTIM (05-DEC-2022) — where a
symbol-keyed identity would silently lose continuity across a rename.

See artifacts/company_identity_c1_reconciliation.md for the real data this
was built against, and app/services/company_identity/ for the
classifier/resolver/importer that populate and query these tables.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Integer, Index

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_entity_id() -> str:
    return f"cmp_{uuid.uuid4().hex[:12]}"


class CompanyEntity(Base):
    """One row per real, distinct company/security — never a symbol, an
    index, a commodity, or an FX/bond reference (see
    app.services.company_identity.classifier, which gates what's even
    allowed to reach this table). entity_id is permanent: it is never
    reassigned across a symbol or ISIN change on the SAME legal entity,
    and a genuinely new entity (e.g. TMCV, a fresh listing with its own
    ISIN born out of the same demerger that produced TMPV) always gets its
    own new entity_id rather than reusing an old one."""

    __tablename__ = "company_entities"

    entity_id         = Column(String(32), primary_key=True, default=_gen_entity_id)
    company_name      = Column(String(256), nullable=False)
    isin              = Column(String(12), nullable=True, unique=True, index=True)
    exchange          = Column(String(16), nullable=False, default="NSE")
    symbol            = Column(String(32), nullable=False, index=True)
    series            = Column(String(8), nullable=True)
    listing_status    = Column(String(16), nullable=False, default="active")  # active | delisted | suspended | unknown
    listing_date      = Column(Date, nullable=True)
    sector            = Column(String(64), nullable=True)  # only when sourced — never inferred/guessed
    industry          = Column(String(64), nullable=True)
    source            = Column(String(32), nullable=False, default="nse_eq_l")
    source_updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    created_at        = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at        = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_company_entities_symbol_exchange", "symbol", "exchange"),
    )


class CompanyAlias(Base):
    """Every symbol/name a company has ever been known by — always real and
    sourced, never a fuzzy-matched guess (the resolver refuses to create
    one from a string-similarity heuristic).

    alias_type distinguishes *why* two strings resolve to the same
    entity_id, which matters because they're sourced completely
    differently:
      symbol            current official exchange symbol, sourced straight
                         from the live NSE EQ file at import time.
      old_symbol         a real, dated historical rename, sourced from
                         NSE's own symbolchange.csv (e.g. TELCO ->
                         TATAMOTORS -> TMPV is two old_symbol rows on
                         TMPV's entity_id, each with its own validity
                         window derived from the real rename dates).
      provider_symbol      a real ticker used by some OTHER data source
                         that never was the official NSE symbol — e.g. the
                         Intelligence Graph's own `ticker` field has
                         "CEAT"/"HPCL"/"IOCL" where NSE's real symbols are
                         CEATLTD/HINDPETRO/IOC. Sourced from that other
                         system's own data, not guessed.
      name                 the company name string itself, for name-based
                         lookup.
    valid_to = NULL means still valid today. A symbol can be reused by a
    LATER, unrelated entity (NSE genuinely does this), so alias_value
    alone is never assumed unique — uniqueness is (alias_value,
    alias_type, exchange, valid_to IS NULL) for "the current holder",
    enforced by the resolver, not a DB constraint (a DB-level unique
    constraint can't express "unique only while still valid")."""

    __tablename__ = "company_aliases"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    entity_id   = Column(String(32), ForeignKey("company_entities.entity_id"), nullable=False, index=True)
    alias_type  = Column(String(16), nullable=False)  # symbol | old_symbol | provider_symbol | name
    alias_value = Column(String(256), nullable=False, index=True)
    exchange    = Column(String(16), nullable=True)
    valid_from  = Column(Date, nullable=True)
    valid_to    = Column(Date, nullable=True)  # NULL = still valid
    source      = Column(String(64), nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_company_aliases_value_type", "alias_value", "alias_type"),
    )

"""
AI Company Intelligence Signal — one row per (source, company) extraction.

Every published IntelligenceArticle's companies_affected[] and every
OpportunityCompany row is a real, already-computed signal about a specific
company. Previously these lived only inside their parent's JSON/row and had
to be re-parsed per feature (bestStocks.ts re-fetches all opportunities on
every request; nothing read companies_affected in aggregate at all). This
table extracts each mention once into a normalized, indexed row so a single
aggregation query (company_score_engine.py) can power company pages, sector
pages, best-stocks pages, and eventually AI Search — instead of separate
ranking logic per feature.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AICompanySignal(Base):
    __tablename__ = "ai_company_signals"

    id           = Column(Integer, primary_key=True, autoincrement=True)

    # ── Source ────────────────────────────────────────────────────────────
    source_type  = Column(String(16), nullable=False, index=True)  # "article" | "opportunity"
    source_id    = Column(String(64), nullable=False, index=True)  # IntelligenceArticle.id or Opportunity.id (str)

    # ── Company ───────────────────────────────────────────────────────────
    symbol       = Column(String(32), nullable=False, index=True)  # NSE symbol, no .NS suffix
    company_name = Column(String(200), nullable=True)
    sector       = Column(String(64), nullable=True, index=True)   # resolved via _NSE_UNIVERSE at write time

    # ── Signal ────────────────────────────────────────────────────────────
    # Real per-mention magnitude, signed by direction (+ for positive/up,
    # - for negative/down, 0 for neutral) — never a fabricated precision:
    # articles use event_score (urgency*10, ~0-100), opportunities use their
    # own real impact_score (~0-100). Same 0-100 scale either way.
    signed_magnitude = Column(Float, nullable=False, default=0.0)
    confidence       = Column(Float, nullable=True)   # 0-1, real (article.confidence_score / OpportunityCompany.confidence)
    quality          = Column(Float, nullable=True)   # 0-1, real (article.quality_score); null for opportunity-sourced (no equivalent gate)
    reason           = Column(Text, nullable=True)

    # ── Timing (denormalized so the aggregator's recency decay doesn't need
    #    a join back to the source row) ───────────────────────────────────
    signal_at    = Column(DateTime(timezone=True), nullable=False, index=True)  # source's published_at/created_at
    created_at   = Column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_signal_symbol_at", "symbol", "signal_at"),
        Index("ix_signal_source", "source_type", "source_id"),
    )

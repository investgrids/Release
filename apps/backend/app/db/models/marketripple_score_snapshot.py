"""
MarketRippleScoreSnapshot — S5-A. Persisted, point-in-time result of
compute_marketripple_score(), so a Company-page request never has to
perform a live 27-bank sequential fetch (the real, measured 37-40 minute
S4 problem) — it reads the most recent real snapshot instead. One row per
(symbol, calculated_at); the latest row per symbol is authoritative.

Every field here is a real value the engine already computes and returns
via MarketRippleScore/PillarScore (contracts.py) — this model persists
that contract, it does not invent new derived data. entity_id is resolved
via app.services.company_identity.qualification.resolve_entity_by_any_symbol
at write time, the same real resolver the rest of the Company Identity
work (C1-C5) already uses — never a second, ad hoc symbol->entity lookup.

market_data_as_of / intelligence_as_of are deliberately set equal to
calculated_at, not a more granular per-metric timestamp: Market Behaviour
is a live yfinance read at compute time (no other real "as of" exists to
report), and Current Intelligence's compute_company_score() doesn't
currently expose its most recent contributing signal's own timestamp.
Reporting a fabricated finer-grained time would be false precision — the
honest answer is "as of when this snapshot was computed."
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, Integer, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MarketRippleScoreSnapshot(Base):
    __tablename__ = "marketripple_score_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Entity ────────────────────────────────────────────────────────────
    entity_id = Column(String(32), nullable=True, index=True)  # real CompanyEntity.entity_id when resolvable
    symbol = Column(String(32), nullable=False, index=True)

    # ── Score ─────────────────────────────────────────────────────────────
    score = Column(Float, nullable=True)
    rating = Column(String(16), nullable=True)  # "Strong" | "Positive" | "Neutral" | "Cautious" | None

    financial_strength = Column(Float, nullable=True)
    valuation = Column(Float, nullable=True)
    market_behaviour = Column(Float, nullable=True)
    current_intelligence = Column(Float, nullable=True)

    coverage_pct = Column(Float, nullable=False)             # MarketRippleScore.overall_coverage_pct
    financial_coverage_pct = Column(Float, nullable=True)    # financial_strength pillar's own coverage_pct

    # ── Methodology/version — real, structural (S4.5) ────────────────────
    methodology_version = Column(String(32), nullable=False)
    peer_universe = Column(JSON, nullable=False, default=list)
    peer_universe_count = Column(Integer, nullable=False, default=0)
    peer_universe_as_of = Column(Date, nullable=True)

    # ── Timing ────────────────────────────────────────────────────────────
    calculated_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    financial_data_as_of = Column(String(16), nullable=True)  # real "FYyyyyQq" of the newest fact actually used
    market_data_as_of = Column(DateTime(timezone=True), nullable=True)
    intelligence_as_of = Column(DateTime(timezone=True), nullable=True)

    # ── Publication gate ──────────────────────────────────────────────────
    publishable = Column(Boolean, nullable=False, default=False)
    publication_block_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now)

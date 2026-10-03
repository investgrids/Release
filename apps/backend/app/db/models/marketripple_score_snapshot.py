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

market_data_as_of / intelligence_as_of remain the aggregate snapshot time.
Market Behaviour's per-input daily source windows and retrieval time are
stored separately in market_behaviour_inputs; Current Intelligence's
compute_company_score() still does not expose its latest contributing
signal timestamp.
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
    # Each pillar's own real coverage_pct (S5-B needs all four, not just
    # Financial Strength, to build a real per-pillar eligibility picture —
    # never derived/estimated, each is the exact value PillarScore itself
    # returned for that pillar's real computation). financial_coverage_pct
    # stays scaled against the original 12-metric ambition (S3-D's own
    # honest-disclosure denominator) — kept for that disclosure, but is
    # deliberately NOT what publication eligibility is computed from; see
    # financial_metrics_used_count below.
    financial_coverage_pct = Column(Float, nullable=True)
    valuation_coverage_pct = Column(Float, nullable=True)
    market_behaviour_coverage_pct = Column(Float, nullable=True)
    current_intelligence_coverage_pct = Column(Float, nullable=True)
    # Bounded price/benchmark observations and the exact derived inputs used
    # by Market Behaviour; existing snapshots remain NULL.
    market_behaviour_inputs = Column(JSON, nullable=True)

    # The peer group this score was ranked against inside a grouped display sector
    # (peer_groups.py). NULL for ungrouped sectors and for snapshots computed before
    # peer groups existed; those are never public in a grouped sector.
    peer_group = Column(String(48), nullable=True)

    # S5-B (owner decision, 2026-08-25) — the real, direct count of the 7
    # currently-scoreable Financial Strength metrics actually used, read
    # straight from PillarScore.metrics_used at persist time. NOT derived
    # from financial_coverage_pct's 12-metric denominator — that
    # reconstruction was explicitly rejected as "historical implementation
    # baggage" for a publication decision. financial_metrics_total_count
    # is REAL_BANKING_METRICS_TOTAL (7) for Banking, None for any
    # not-yet-scoped sector.
    financial_metrics_used_count = Column(Integer, nullable=True)
    financial_metrics_total_count = Column(Integer, nullable=True)

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
    # publishable/publication_block_reason: the STANDING, whole-initiative
    # phase lock (owner decision since S2 — "S2 may calculate, may not
    # replace the Company-page score yet"), unchanged by S5-B. Stays False
    # for every real snapshot until S5-E's real, multi-cycle shadow
    # validation actually passes — that has been reaffirmed at every S5
    # checkpoint and is not what this batch changes.
    publishable = Column(Boolean, nullable=False, default=False)
    publication_block_reason = Column(Text, nullable=True)

    # publication_policy_version/publication_block_reasons: the NEW,
    # separate, real per-bank BANKING_V1_P1 verdict (S5-B) — whether THIS
    # bank's own evidence would clear the publication bar, independent of
    # the standing phase lock above. Empty list = this bank's real
    # evidence is sufficient under BANKING_V1_P1 today; the phase lock is
    # the only thing still holding `publishable` at False for it.
    publication_policy_version = Column(String(32), nullable=True)
    publication_block_reasons = Column(JSON, nullable=True)

    # Comparability interim rule (2026-09-26 audit follow-up) — whether this
    # snapshot's `score` reflects all 4 pillars ("complete") or was withheld
    # because fewer than 4 produced a real number ("partial" — see
    # engine.py's own field docstring for why a renormalized partial blend
    # isn't shown as a headline number). Persisted so a caller can render
    # "Partial coverage — N of 4 pillars" instead of a generic "Unavailable"
    # once this feature is ever unlocked, without recomputing anything.
    pillar_coverage_status = Column(String(16), nullable=True)
    pillar_coverage_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now)

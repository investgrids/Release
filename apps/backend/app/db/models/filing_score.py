"""
Filing-backed MarketRipple Score — persistence (shadow, versioned, immutable runs).

One FilingScoreRun is one full computation of the filing-backed method over the whole universe. Its FilingScoreSnapshot rows are written once and never
updated; a run becomes readable only when it is marked complete and activated, and activation is a pointer move (is_active), so rollback is moving the
pointer back to the previous complete run, or to none. Nothing here is read by any public page unless FILING_SCORE_PUBLIC is turned on (settings), and the
live scorer is untouched either way.

Raw filings are NOT stored in the database (they are large and the file system has filled before): each snapshot keeps the extracted figures, the filing's
sha256, its NSE archive URL and sequence id, so any row can be re-verified by re-fetching the exact filing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Index, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FilingScoreRun(Base):
    __tablename__ = "filing_score_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    method_version = Column(String(48), nullable=False, index=True)       # e.g. "NSE_FILING_SCORE_V3"
    status = Column(String(16), nullable=False, default="running")        # running | complete | failed | rolled_back
    is_active = Column(Boolean, nullable=False, default=False, index=True)  # the run the (flagged) readers use; at most one per method_version
    started_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    activation_seq = Column(Integer, nullable=True)                       # monotonic per method_version: orders activations without relying on clock resolution
    trigger = Column(String(32), nullable=True)                           # "manual" | "scheduled"
    counts = Column(JSON, nullable=True)                                  # scored / withheld per segment, reasons
    contracts = Column(JSON, nullable=True)                               # contract versions used (industrial / bank / fin / scorer)
    notes = Column(Text, nullable=True)


class FilingScoreSnapshot(Base):
    __tablename__ = "filing_score_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "symbol", name="uq_filing_score_run_symbol"), Index("ix_filing_score_symbol_run", "symbol", "run_id"))

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    segment = Column(String(24), nullable=False)                          # industrial | bank | fin_lenders | fin_other
    peer_group = Column(String(64), nullable=True)

    state = Column(String(12), nullable=False)                            # scored | withheld
    score = Column(Float, nullable=True)
    rating = Column(String(16), nullable=True)
    financial_strength = Column(Float, nullable=True)
    valuation = Column(Float, nullable=True)
    market_behaviour = Column(Float, nullable=True)
    coverage_pct = Column(Float, nullable=True)
    metrics_used = Column(Integer, nullable=True)

    withheld_reason = Column(String(64), nullable=True)                   # exact reason code when state == withheld
    na_label = Column(String(96), nullable=True)                          # user-facing label for a withheld state (e.g. "N/A - Valuation Data Discrepancy")
    metadata_flags = Column(JSON, nullable=True)                          # e.g. ["[Core Earnings / Pre-Exceptional Adjusted]"]
    rule_tags = Column(JSON, nullable=True)                               # e.g. ["V2-Rule-4A-ExceptionalLossBypass"]

    metrics = Column(JSON, nullable=True)                                 # scored metric values (negative values kept as filed)
    valuation_detail = Column(JSON, nullable=True)                        # pe / pb, market cap and its source, display values for loss / negative equity
    provenance = Column(JSON, nullable=True)                              # filing seq id, file id, sha256, URL, scope, period end, audit statement
    inputs = Column(JSON, nullable=True)                                  # extracted figures (crore), prior-year figures, reference multiples used by the guard
    contract_version = Column(String(48), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

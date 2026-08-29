"""
Financial Fact — one row per (symbol, metric, period, consolidation scope),
sourced from a real, traceable regulatory filing. Built for the S3 banking-
fundamentals initiative (MarketRipple Score S1-S3, see artifacts/
marketripple_score_s3a_reliability_and_casa_check.md) but deliberately
reusable — not coupled to the score engine. Real consumers beyond the score:
Company Financials, AI Search, future Article Truth Layer.

Owner's explicit design rules (2026-08-25), all encoded structurally, not
just in comments:

  1. Consolidation scope is load-bearing, not metadata. Bank-regulatory
     ratios (CET1, NPA%) are only ever reported on the Non-Consolidated
     (standalone) filing — confirmed live across 5 real banks x 4 real
     quarters, 20/20. `consolidation_scope` is part of the row's identity
     (see the unique index below), not an afterthought column.

  2. Source truth and quality truth are separate columns. A value NSE
     actually filed is never silently "corrected" — extraction_status
     records whether we got a real value from the source at all;
     quality_status/quality_reason separately record whether that real
     value looks trustworthy (e.g. the real, confirmed-live ICICIBANK Q1
     FY25 Gross NPA of 0.02% against a ~2% trailing trend — a real
     anomaly to flag, not silently drop or "fix").

  3. Missing is never zero, and a metric this app cannot source at all
     (CASA, Provision Coverage Ratio, total CAR — confirmed live absent
     from both the Quarterly and Annual real XBRL taxonomies) still gets
     an explicit row with extraction_status=SOURCE_UNAVAILABLE, not a
     silently-absent one indistinguishable from "never checked."

  4. CAR is never derived as CET1 + AdditionalTier1 — that omits Tier 2
     and would produce a number that looks like real CAR but isn't. CET1
     and AdditionalTier1 are stored as their own real, distinct metrics;
     `car_total` is registered as a known metric_code but always written
     with extraction_status=SOURCE_UNAVAILABLE until a real source for it
     is found.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# extraction_status — did we get a real value from the source at all
EXTRACTION_POPULATED = "POPULATED"
EXTRACTION_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"  # confirmed: this source doesn't carry this metric at all
EXTRACTION_TAG_MISSING = "TAG_MISSING"                # this filing's own XBRL omitted a tag other filings of the same type carry
EXTRACTION_PARSE_FAILED = "PARSE_FAILED"              # real fetch/parse error, not a data-availability fact

# quality_status — given a real populated value, is it trustworthy
QUALITY_OK = "OK"
QUALITY_ANOMALY = "ANOMALY"   # deviates sharply from this symbol's own trailing observations
QUALITY_STALE = "STALE"       # real value, but from an old period relative to when it's being read
QUALITY_IMPLAUSIBLE_SCALE = "IMPLAUSIBLE_SCALE"  # value itself is outside any plausible real-world
# range for this metric/unit (S4.5) — independent of this symbol's own history, catches a filer
# whose values are internally consistent (so the within-entity check above finds nothing wrong)
# but wrong relative to the metric's real-world meaning, e.g. a genuine XBRL scale/unit error.
# Never a correction: value is preserved exactly as filed, only quality_status/quality_reason change.


class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── Entity ────────────────────────────────────────────────────────────
    symbol = Column(String(32), nullable=False, index=True)  # NSE symbol, no .NS suffix

    # ── Metric ────────────────────────────────────────────────────────────
    metric_code = Column(String(64), nullable=False, index=True)  # e.g. "gross_npa_pct", "cet1_ratio", "deposits"
    metric_name = Column(String(200), nullable=False)             # human-readable, e.g. "Gross NPA %"
    value = Column(Float, nullable=True)                          # real value, or None when not POPULATED
    unit = Column(String(16), nullable=False)                     # "pct" | "inr" | "ratio"

    # ── Period ────────────────────────────────────────────────────────────
    fiscal_year = Column(Integer, nullable=False, index=True)     # e.g. 2025 for FY25
    fiscal_quarter = Column(Integer, nullable=True)               # 1-4, null for Annual facts
    period_type = Column(String(16), nullable=False)              # "Quarterly" | "Annual"
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)

    # ── Scope — load-bearing, see module docstring rule 1 ──────────────────
    consolidation_scope = Column(String(20), nullable=False)      # "Non-Consolidated" | "Consolidated"

    # ── Provenance — every value must trace to a real, fetchable document ──
    source_provider = Column(String(16), nullable=False, default="NSE")
    source_document_url = Column(Text, nullable=True)             # the real XBRL file URL
    source_document_id = Column(String(64), nullable=True)        # NSE's own seqNumber
    source_tag = Column(String(120), nullable=True)                # the exact real XBRL tag name (e.g. "in-bse-fin:CET1Ratio")
    taxonomy = Column(String(120), nullable=True)                  # e.g. "banking_entry_point_2019-09-30"

    # ── Status — see module docstring rule 2/3 ──────────────────────────────
    extraction_status = Column(String(24), nullable=False, index=True)
    quality_status = Column(String(16), nullable=True)             # null when extraction_status != POPULATED
    quality_reason = Column(Text, nullable=True)

    # ── Timing ────────────────────────────────────────────────────────────
    published_at = Column(DateTime(timezone=True), nullable=True)  # NSE's real broadCastDate for this filing
    observed_at = Column(DateTime(timezone=True), default=_now, nullable=False)  # when this app ingested it

    __table_args__ = (
        # One real fact per (symbol, metric, period, scope) — a re-ingest of
        # the same real filing must upsert, never duplicate.
        Index(
            "ux_fact_identity", "symbol", "metric_code", "fiscal_year", "fiscal_quarter",
            "period_type", "consolidation_scope", unique=True,
        ),
        Index("ix_fact_symbol_metric", "symbol", "metric_code"),
    )

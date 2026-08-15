"""
WeekendIntelligenceSnapshot — versioned, weekend-scoped intelligence
synthesis record.

Phase 1A (foundation only — see WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md
§6/§27): this model, its versioning helpers, and the evidence-normalization/
materiality building blocks in app/services/weekend_intelligence/ are
persisted here, but nothing yet WRITES a synthesized snapshot — that's
Phase 1B's aggregator. Phase 1A only needs the schema and the atomic
create/supersede mechanics to exist and be tested.

Design principle (§6): reference IDs, not copied blobs. Every `*_refs`
field below stores small id/reference lists — companies, opportunities,
historical analogues, evidence source rows — resolved against their real
source tables at read time, not duplicated here. Only genuinely-
synthesized-here summary fields (`overall_bias`, `top_sector_refs`,
`changes_since_prior`) are inline JSON, the same pattern
HomepageDailySnapshot.sectors already uses successfully at a smaller scale.

Immutability (§7/§14): once committed, a row's intelligence content is
never mutated — only `is_current` flips to False when a newer version for
the same target_trading_date is created. See
app/services/weekend_intelligence/versioning.py for the atomic
create-and-supersede helper that enforces this.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, JSON, String, Text, text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WeekendIntelligenceSnapshot(Base):
    __tablename__ = "weekend_intelligence_snapshots"

    # ── Identity / versioning ─────────────────────────────────────────────────
    id = Column(String, primary_key=True, index=True)
    # The next trading session this snapshot is FOR (e.g. the Monday after
    # a weekend) — YYYY-MM-DD. Named target_trading_date, not "monday",
    # deliberately (design doc §18): a real holiday calendar should be able
    # to slot in later without renaming anything.
    target_trading_date = Column(String(10), nullable=False, index=True)
    # The prior trading session this snapshot is BASED ON (e.g. the Friday
    # before). Named last_trading_date, not "friday", for the same reason.
    last_trading_date = Column(String(10), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    generated_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    # Human-facing label for this checkpoint, e.g. "Saturday AM" — display
    # only, never parsed back into scheduling logic.
    checkpoint_label = Column(String(64), nullable=True)

    # ok | degraded | insufficient_evidence — see design doc §22.
    status = Column(String(24), nullable=False, default="ok", index=True)

    # ── Production synthesis (Phase 1B populates these — nullable here on
    #    purpose, per this task's explicit scope: "no aggregation yet") ───────
    overall_bias = Column(String(32), nullable=True)
    production_confidence = Column(Float, nullable=True)

    # ── Reference fields — IDs/compact refs, not copied content (§6) ─────────
    top_sector_refs = Column(JSON, nullable=False, default=list)          # [{sector, score}]
    top_company_refs = Column(JSON, nullable=False, default=list)         # [{symbol, evidence_item_refs:[...]}]
    opportunity_refs = Column(JSON, nullable=False, default=list)         # [opportunity_id, ...]
    risk_refs = Column(JSON, nullable=False, default=list)                # [{description, evidence_item_refs:[...]}]
    historical_analogue_refs = Column(JSON, nullable=False, default=list)  # [historical_market_event_id, ...]

    changes_since_prior = Column(JSON, nullable=False, default=list)      # the §5 delta, evidence-level
    evidence_refs = Column(JSON, nullable=False, default=list)            # [{"source_type":..., "source_id":...}, ...]

    # FK-shaped reference to the trading-session close baseline (§2) this
    # snapshot was built against. Plain String, not a SQLAlchemy
    # ForeignKey — MarketSnapshot.id is itself a plain String primary key
    # with no relationship() wired up anywhere in this codebase's existing
    # style for that model, so a bare column matches the surrounding
    # convention rather than introducing the first FK on that table.
    market_snapshot_id = Column(String, nullable=True, index=True)

    # Internal-only — never serialized in any user-facing API response
    # (design doc §14/§21). {"kronos": {"prediction_record_id": ..., "experimental_confidence": ...}}
    experimental_signals = Column(JSON, nullable=True)

    # Free-text rationale for a non-"ok" status — e.g. which sources were
    # unavailable (§22). Not structured; this is a human-debugging aid,
    # not something downstream code should parse.
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        # DB-level "at most one current row per target_trading_date" guard
        # (§13: "prefer DB-level protection if practical... do not
        # overengineer distributed locking"). A brand-new table, so this
        # can be a real SQLAlchemy Index (create_all() creates it directly)
        # rather than a schema_patches.py runtime ALTER — that mechanism
        # is only needed for columns/indexes added to already-deployed
        # tables. Partial-index syntax differs by dialect (this codebase
        # supports both SQLite dev / Postgres prod, per opportunity.py's
        # own docstring), hence both sqlite_where and postgresql_where.
        Index(
            "ux_weekend_snapshot_current_per_target",
            "target_trading_date",
            unique=True,
            sqlite_where=text("is_current = 1"),
            postgresql_where=text("is_current = true"),
        ),
    )

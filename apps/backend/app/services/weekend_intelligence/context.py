"""
WeekendContext — the internal handoff DTO into the existing Monday
opening-prediction engine (Phase 1C, brief §9/§10).

Deliberately NOT the full API response shape (app/api/weekend_intelligence.py)
— this is a compact structure containing only what
opening_prediction_service.py genuinely needs to fold weekend evidence
into a Monday call, per brief §9: "It should contain only information
the opening engine genuinely needs." No raw evidence_refs, no
confidence_components breakdown, no changes_since_prior — those stay in
the public API response, not the internal handoff.

get_weekend_context_for_session() is the ONLY way the opening engine
should ever touch Weekend Intelligence — it must never import
WeekendIntelligenceSnapshot, versioning.py, or the aggregator directly
(brief §10: "Do not make the opening prediction service understand
Weekend Intelligence persistence internals").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.weekend_intelligence import bias as bias_mod

# Snapshot statuses this DTO can honestly represent — see aggregator.py's
# STATUS_OK/STATUS_DEGRADED/STATUS_INSUFFICIENT_EVIDENCE, reused verbatim
# rather than re-declared with different spellings.
_VALID_STATUSES = {"ok", "degraded", "insufficient_evidence"}

# opportunity_refs on the snapshot are bare Opportunity ids (brief §6/§9
# of Phase 1B: "reference IDs, not copied blobs"), so building
# major_opportunities requires one small batched resolve query — capped
# here to bound cost, since aggregator.py's opportunity_refs list itself
# has no upper limit.
_MAX_OPPORTUNITY_RESOLVE = 5

# A snapshot older than this relative to "now" is treated as stale even
# if target_trading_date nominally matches — guards against a checkpoint
# that silently stopped running (scheduler down, DB issue) from handing
# the opening engine multi-day-old "weekend" evidence as if it were
# current. Generous on purpose: the last legitimate checkpoint before a
# Monday morning call is Sunday 18:00 IST, so a live snapshot can
# legitimately be ~14-16h old at Monday 08:30 IST.
_MAX_SNAPSHOT_AGE_HOURS = 36


@dataclass
class SignalRef:
    """One compact directional signal — a sector or company, never a raw
    evidence item (brief §9's own field naming: top_sector_signals /
    top_company_signals, not top_sector_evidence)."""
    id: str            # sector name or company symbol
    direction: str      # positive | negative | mixed | neutral
    confidence: float
    evidence_count: int


@dataclass
class ItemRef:
    """One compact opportunity/risk line — description + severity only,
    no evidence_refs (those stay in the public API, not this DTO)."""
    description: str
    severity: str | None = None


@dataclass
class WeekendContext:
    target_trading_date: str
    generated_at: datetime
    status: str  # ok | degraded | insufficient_evidence

    overall_bias: str
    production_confidence: float

    top_sector_signals: list[SignalRef] = field(default_factory=list)
    top_company_signals: list[SignalRef] = field(default_factory=list)

    major_opportunities: list[ItemRef] = field(default_factory=list)
    major_risks: list[ItemRef] = field(default_factory=list)

    meaningful_development_count: int = 0
    # Brief §14 double-count guard: source_ids (source_type=="event" only
    # — the one evidence type Monday's own event layer also reads
    # directly, see opening_prediction_service._gather_events) behind the
    # meaningful-development count above. NOT a general evidence dump —
    # deliberately just enough for a consumer to detect "this event is
    # already in my own input" without WeekendContext needing to carry
    # full evidence_refs (brief §9's minimalism). Free to compute: Phase
    # 1B's new_since_close_refs already carries source_type/source_id.
    meaningful_development_event_ids: frozenset[str] = field(default_factory=frozenset)

    baseline_available: bool = False

    # Provenance — needed by prediction_recording.py (brief §25/§26) and
    # by the double-count guard (brief §14), never by the opening engine
    # itself for scoring.
    snapshot_id: str = ""
    snapshot_version: int = 0

    @property
    def has_directional_signal(self) -> bool:
        """Brief §19: insufficient_evidence must contribute ZERO
        directional signal. This is the single check every consumer
        (opening engine, prediction recording) should use rather than
        re-deriving the rule from status/bias/confidence separately."""
        if self.status == "insufficient_evidence":
            return False
        return self.overall_bias != bias_mod.NEUTRAL and self.production_confidence > 0


def _signal_refs(rows: list[dict], id_key: str) -> list[SignalRef]:
    """rows are WeekendIntelligenceSnapshot.top_sector_refs /
    top_company_refs — already-compact dicts (aggregator.py's
    _top_sector_refs/_top_company_refs), not ORM objects. id_key is
    "sector" or "symbol" depending on which ref list this is.

    IMPORTANT asymmetry, verified against aggregator.py directly:
    top_sector_refs' directional field is literally named "direction"
    (positive/negative/mixed/neutral — sector_synthesis.SectorSignal.direction).
    top_company_refs' directional field is named "state" (e.g.
    "high_conviction_watch" — company_synthesis.CompanySignal.state), NOT
    "direction" — a real bug caught here before it shipped: reading
    r.get("direction") for company rows would silently return None for
    every company, every time, defaulting every company's SignalRef.direction
    to "neutral" and making it invisible to both the opening-engine prompt
    and prediction_recording.py's direction mapping."""
    out = []
    for r in rows:
        rid = r.get(id_key)
        if not rid:
            continue
        raw_direction = r.get("direction") if id_key == "sector" else r.get("state")
        out.append(SignalRef(
            id=rid,
            direction=raw_direction or "neutral",
            confidence=float(r.get("score") if id_key == "sector" else r.get("confidence") or 0.0),
            evidence_count=int(r.get("evidence_count") or 0),
        ))
    return out


def _item_refs(rows: list[dict]) -> list[ItemRef]:
    out = []
    for r in rows:
        desc = r.get("description")
        if not desc:
            continue
        out.append(ItemRef(description=desc, severity=r.get("severity")))
    return out


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _resolve_opportunities(db: AsyncSession, opportunity_refs: list[str]) -> list[ItemRef]:
    """One small batched query resolving bare opportunity_refs (ids) into
    compact ItemRefs — never N+1, capped to _MAX_OPPORTUNITY_RESOLVE. A
    ref whose Opportunity row no longer exists is silently omitted, not
    an error (brief §6: "do not fail the entire response... omit the
    missing reference honestly" — same rule applied here for the
    internal DTO)."""
    if not opportunity_refs:
        return []
    from sqlalchemy import select
    from app.db.models.opportunity import Opportunity

    ids = []
    for ref in opportunity_refs[:_MAX_OPPORTUNITY_RESOLVE]:
        try:
            ids.append(int(ref))
        except (TypeError, ValueError):
            continue
    if not ids:
        return []
    rows = (await db.execute(select(Opportunity).where(Opportunity.id.in_(ids)))).scalars().all()
    return [ItemRef(description=r.title, severity=r.risk_level) for r in rows]


async def get_weekend_context_for_session(
    db: AsyncSession, target_trading_date: str, *, now: datetime | None = None,
) -> WeekendContext | None:
    """
    Locate, validate, and transform the current WeekendIntelligenceSnapshot
    for target_trading_date into a WeekendContext — or return None when no
    valid context exists (brief §10: "return None when unavailable/invalid").

    Rejection reasons (brief §12), each logged so a missing handoff is
    diagnosable rather than silently mysterious:
      - no current snapshot exists for target_trading_date at all
      - snapshot.target_trading_date doesn't literally match the session
        being predicted (brief §11 — never a weekday==Monday check; this
        is the ONLY activation gate, so a future Tuesday target after a
        holiday works automatically without touching this function)
      - snapshot.generated_at is older than _MAX_SNAPSHOT_AGE_HOURS
      - malformed status (defensive — should never happen given
        aggregator.py's own STATUS_* constants, but this loader must not
        propagate a garbage value into the opening engine)

    Never rejects merely for status == "degraded" (brief §12 — a
    degraded snapshot may still contain useful evidence; its reduced
    quality is propagated via WeekendContext.status, not by returning
    None).
    """
    import structlog
    from app.services.weekend_intelligence.versioning import get_current_snapshot

    log = structlog.get_logger(__name__)
    now = _aware(now) or datetime.now(timezone.utc)

    snapshot = await get_current_snapshot(db, target_trading_date)
    if snapshot is None:
        log.info("weekend_context.rejected", reason="no_snapshot", target_trading_date=target_trading_date)
        return None

    if snapshot.target_trading_date != target_trading_date:
        # Defensive — get_current_snapshot already filters on this, but
        # the activation rule (brief §11) is stated here explicitly as
        # the interface contract, not assumed from the query layer.
        log.info("weekend_context.rejected", reason="target_session_mismatch",
                 snapshot_target=snapshot.target_trading_date, requested_target=target_trading_date)
        return None

    if not snapshot.is_current:
        log.info("weekend_context.rejected", reason="not_current", snapshot_id=snapshot.id)
        return None

    generated_at = _aware(snapshot.generated_at)
    if generated_at is None or generated_at > now:
        log.info("weekend_context.rejected", reason="invalid_generated_at", snapshot_id=snapshot.id)
        return None
    age_hours = (now - generated_at).total_seconds() / 3600
    if age_hours > _MAX_SNAPSHOT_AGE_HOURS:
        log.info("weekend_context.rejected", reason="stale", snapshot_id=snapshot.id, age_hours=round(age_hours, 1))
        return None

    if snapshot.status not in _VALID_STATUSES:
        log.info("weekend_context.rejected", reason="malformed_status", snapshot_id=snapshot.id, status=snapshot.status)
        return None

    major_opportunities = await _resolve_opportunities(db, snapshot.opportunity_refs or [])

    context = WeekendContext(
        target_trading_date=snapshot.target_trading_date,
        generated_at=generated_at,
        status=snapshot.status,
        overall_bias=snapshot.overall_bias or bias_mod.NEUTRAL,
        production_confidence=float(snapshot.production_confidence or 0.0),
        top_sector_signals=_signal_refs(snapshot.top_sector_refs or [], "sector"),
        top_company_signals=_signal_refs(snapshot.top_company_refs or [], "symbol"),
        major_opportunities=major_opportunities,
        major_risks=_item_refs(snapshot.risk_refs or []),
        meaningful_development_count=len(snapshot.new_since_close_refs or []),
        meaningful_development_event_ids=frozenset(
            r["source_id"] for r in (snapshot.new_since_close_refs or [])
            if r.get("source_type") == "event" and r.get("source_id")
        ),
        baseline_available=snapshot.market_snapshot_id is not None,
        snapshot_id=snapshot.id,
        snapshot_version=snapshot.version,
    )
    log.info(
        "weekend_context.loaded", target_trading_date=target_trading_date, snapshot_id=snapshot.id,
        snapshot_version=snapshot.version, status=snapshot.status,
        production_confidence=context.production_confidence, age_hours=round(age_hours, 1),
    )
    return context

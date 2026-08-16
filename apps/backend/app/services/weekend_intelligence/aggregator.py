"""
Weekend Intelligence aggregator — the Phase 1B orchestration entry point,
brief §21.

    build_weekend_intelligence(db, target_trading_date, checkpoint_time)

Deliberately does NOT run the material-change gate itself (brief §24's
checkpoint execution order runs that gate BEFORE deciding whether to call
this function at all — see checkpoints.py). This function always does
the full synthesis when called; the checkpoint runner decides whether
that's worth doing.

Fully deterministic — no LLM call. The brief explicitly permits an LLM
only for narrative/reasoning polish and requires the structured snapshot
to be "still be creatable without the LLM" (§20) — Phase 1B ships the
structured version only, so that requirement is trivially satisfied and
there is nothing non-deterministic to test, retry, or degrade around.
This is a deliberate scope decision, not an oversight (see the Phase 1B
completion report for the reasoning).

Pipeline (deviates from the brief's §21 numbered order in one place,
explained inline where it happens — historical analogues are computed
BEFORE risk synthesis, not after, since one risk type ("weak historical
analogue") needs to know the analogue count):

  resolve session -> load baseline -> load evidence -> cluster ->
  sector signals -> company signals -> attach opportunities ->
  historical analogues -> market risks + confidence warnings ->
  new-since-close -> changes-since-prior -> confidence -> bias ->
  status -> persist immutable version

Post-review refinement (pre-commit, same phase): risks are now split
into market_risks vs confidence_warnings (see risk_synthesis.py's
module docstring for why), sector/company output is capped to a
"primary" ranked set instead of returning every signal detected, and a
new new_since_close_* pair answers "what's new since Friday's close"
directly from the evidence window — a different, smaller, and more
useful number than changes_since_prior, which only measures drift
against a PRIOR SNAPSHOT VERSION and is trivially "everything is new"
on a first-ever checkpoint (see changes.py's module docstring).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence import MarketSnapshot
from app.services.weekend_intelligence import bias as bias_mod
from app.services.weekend_intelligence import confidence as confidence_mod
from app.services.weekend_intelligence.changes import compute_changes
from app.services.weekend_intelligence.company_synthesis import CompanySignal, synthesize_companies
from app.services.weekend_intelligence.dedup import EvidenceCluster, cluster_evidence
from app.services.weekend_intelligence.evidence_window import collect_evidence_since
from app.services.weekend_intelligence.historical_integration import find_historical_analogues
from app.services.weekend_intelligence.materiality import select_new_since_close
from app.services.weekend_intelligence.risk_synthesis import (
    Risk,
    synthesize_confidence_warnings,
    synthesize_market_risks,
)
from app.services.weekend_intelligence.sector_synthesis import SectorSignal, synthesize_sectors
from app.services.weekend_intelligence.session_resolution import last_trading_date
from app.services.weekend_intelligence.versioning import create_next_version, get_current_snapshot

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_INSUFFICIENT_EVIDENCE = "insufficient_evidence"

# "Primary" = deterministically ranked (sector/company synthesis already
# sort by (evidence_count, confidence) descending) and capped to what's
# actually worth a reader's attention — not "everything we detected."
# These same refs are also what changes.py diffs against on the next
# checkpoint, so a smaller, more stable primary set also means less
# change-tracking noise from entities that were never significant.
_PRIMARY_SECTOR_LIMIT = 5
_PRIMARY_COMPANY_LIMIT = 12


@dataclass
class WeekendIntelligenceResult:
    """In-memory result of one aggregator run — everything the caller
    needs either to persist a new snapshot version or to inspect without
    persisting (checkpoints.py's materiality-gated dry paths, and Phase
    1B's local verification pass, both use this)."""
    target_trading_date: str
    last_trading_date: str
    baseline_available: bool
    market_snapshot_id: str | None
    status: str
    overall_bias: str
    production_confidence: float
    confidence_breakdown: dict
    clusters: list[EvidenceCluster]
    sector_signals: list[SectorSignal]
    company_signals: list[CompanySignal]
    market_risks: list[Risk]
    confidence_warnings: list[Risk]
    opportunity_refs: list[str]
    historical_analogue_refs: list[str]
    historical_analogues_raw: list[dict]
    changes: list[dict]
    new_since_close_count: int
    new_since_close_refs: list[dict]
    evidence_refs: list[dict]
    evidence_count: int


async def _load_close_baseline(db: AsyncSession, last_trading_date_str: str) -> MarketSnapshot | None:
    return (await db.execute(
        select(MarketSnapshot).where(
            MarketSnapshot.trading_date == last_trading_date_str,
            MarketSnapshot.snapshot_type == "close",
        )
    )).scalar_one_or_none()


def _evidence_window_since(baseline: MarketSnapshot | None, last_trading_date_str: str) -> datetime:
    """The real close-capture timestamp when a baseline exists (brief
    §4: "do NOT reconstruct the close from current market APIs" — this
    reuses the baseline's own recorded `ts`, never recomputes one).

    When no baseline exists, falls back to a SYNTHETIC window boundary —
    last_trading_date at 15:30 IST — used only to bound the evidence
    SQL query, never stored anywhere or presented as real market data.
    This is categorically different from fabricating a close snapshot:
    it's just "where does the evidence window start," not a market-state
    claim.
    """
    if baseline is not None and baseline.ts is not None:
        return baseline.ts if baseline.ts.tzinfo else baseline.ts.replace(tzinfo=timezone.utc)
    from app.services.intelligence.engine import _IST
    d = date.fromisoformat(last_trading_date_str)
    naive_close = datetime(d.year, d.month, d.day, 15, 30, tzinfo=_IST)
    return naive_close.astimezone(timezone.utc)


def _top_sector_refs(signals: list[SectorSignal]) -> list[dict]:
    return [
        {"sector": s.sector, "score": s.confidence, "direction": s.direction, "evidence_count": s.evidence_count}
        for s in signals[:_PRIMARY_SECTOR_LIMIT]
    ]


def _top_company_refs(signals: list[CompanySignal]) -> list[dict]:
    return [
        {
            "symbol": c.symbol, "state": c.state, "confidence": c.confidence,
            "evidence_count": c.evidence_count,
            "evidence_item_refs": (
                c.opportunity_refs + c.event_refs + c.announcement_refs + c.company_signal_refs + c.news_refs
            ),
        }
        for c in signals[:_PRIMARY_COMPANY_LIMIT]
    ]


def _new_since_close_refs(clusters: list[EvidenceCluster]) -> list[dict]:
    return [
        {
            "source_type": c.representative.source_type,
            "source_id": c.representative.source_id,
            "title": c.representative.title,
            "direction": c.net_direction,
            "sectors": sorted(c.sectors),
            "companies": sorted(c.companies),
        }
        for c in clusters
    ]


def _determine_status(evidence_count: int, baseline_available: bool, has_source_failure: bool = False) -> str:
    """Deterministic, per brief §27. Missing baseline always yields
    degraded regardless of evidence volume — real evidence-based
    intelligence can still be produced, it's just not verified against a
    real close price/breadth baseline (brief §4). Zero evidence yields
    insufficient_evidence regardless of baseline — there is nothing to
    synthesize. Never "degraded" purely because it's a weekend/closed
    market (brief §27's explicit non-example) — that's not one of the
    two conditions checked here at all.

    Phase 1E hardening: `has_source_failure` (one of the 6 evidence
    sources failed to read this checkpoint — collect_evidence_since's
    per-source isolation) ALSO forces degraded, even when the baseline
    IS available — a partial evidence read is its own, independent
    data-quality gap, not something baseline_available speaks to. Never
    downgraded to insufficient_evidence purely from a source failure —
    the sources that DID succeed may still carry real evidence."""
    if evidence_count == 0:
        return STATUS_INSUFFICIENT_EVIDENCE
    if not baseline_available or has_source_failure:
        return STATUS_DEGRADED
    return STATUS_OK


async def build_weekend_intelligence(
    db: AsyncSession, target_trading_date: str, checkpoint_time: datetime,
) -> WeekendIntelligenceResult:
    last_trading_date_str = last_trading_date(date.fromisoformat(target_trading_date)).isoformat()

    baseline = await _load_close_baseline(db, last_trading_date_str)
    baseline_available = baseline is not None

    since = _evidence_window_since(baseline, last_trading_date_str)
    until = checkpoint_time if checkpoint_time.tzinfo else checkpoint_time.replace(tzinfo=timezone.utc)
    failed_sources: list[str] = []
    evidence = await collect_evidence_since(db, since, until, failed_sources=failed_sources)

    clusters = await cluster_evidence(db, evidence)

    sector_signals = synthesize_sectors(clusters, baseline_sector_ranks=(baseline.sector_ranks if baseline else None))
    company_signals = synthesize_companies(clusters)

    opportunity_refs = sorted({
        m.source_id for c in clusters for m in c.members if m.source_type == "opportunity"
    })

    # Historical analogues computed before risk synthesis (deviates from
    # the brief's §21 listed order 10-then-11) — synthesize_risks needs
    # historical_analogue_count to populate the WEAK_HISTORICAL_ANALOGUE
    # risk type; computing it after risks would mean that risk type could
    # never actually fire. See module docstring.
    historical_analogues = await find_historical_analogues(clusters)
    historical_analogue_refs = [str(a["id"]) for a in historical_analogues]

    source_type_counts = dict(Counter(e.source_type for e in evidence))
    market_risks = synthesize_market_risks(sector_signals, company_signals)
    confidence_warnings = synthesize_confidence_warnings(
        company_signals,
        baseline_available=baseline_available,
        historical_analogue_count=len(historical_analogues),
        total_evidence_count=len(evidence),
        source_type_counts=source_type_counts,
        source_failures=failed_sources,
    )

    # "New since market close" — see module docstring. Independent of
    # whether a prior snapshot version exists, unlike changes_since_prior
    # below.
    new_since_close_clusters = select_new_since_close(clusters)

    current = await get_current_snapshot(db, target_trading_date)
    changes = compute_changes(
        sector_signals, company_signals,
        prior_top_sector_refs=(current.top_sector_refs if current else None),
        prior_top_company_refs=(current.top_company_refs if current else None),
    )

    production_confidence, breakdown = confidence_mod.compute_production_confidence(
        clusters, baseline_available=baseline_available, historical_analogues=historical_analogues,
    )

    overall_bias = bias_mod.compute_overall_bias(sector_signals, company_signals)
    status = _determine_status(len(evidence), baseline_available, has_source_failure=bool(failed_sources))

    if status == STATUS_INSUFFICIENT_EVIDENCE:
        # Brief §19: an empty/near-empty weekend must not invent
        # opportunities or a directional lean — pin bias to neutral
        # explicitly rather than trusting whatever compute_overall_bias
        # happened to return over zero-weight input (it already returns
        # NEUTRAL for zero total weight, but pinning it here makes the
        # invariant explicit and independent of that function's internals).
        overall_bias = bias_mod.NEUTRAL

    evidence_refs = [{"source_type": e.source_type, "source_id": e.source_id} for e in evidence]

    return WeekendIntelligenceResult(
        target_trading_date=target_trading_date,
        last_trading_date=last_trading_date_str,
        baseline_available=baseline_available,
        market_snapshot_id=(baseline.id if baseline else None),
        status=status,
        overall_bias=overall_bias,
        production_confidence=production_confidence,
        confidence_breakdown=breakdown.as_dict(),
        clusters=clusters,
        sector_signals=sector_signals,
        company_signals=company_signals,
        market_risks=market_risks,
        confidence_warnings=confidence_warnings,
        opportunity_refs=opportunity_refs,
        historical_analogue_refs=historical_analogue_refs,
        historical_analogues_raw=historical_analogues,
        changes=[c.as_dict() for c in changes],
        new_since_close_count=len(new_since_close_clusters),
        new_since_close_refs=_new_since_close_refs(new_since_close_clusters),
        evidence_refs=evidence_refs,
        evidence_count=len(evidence),
    )


async def persist_weekend_intelligence(
    db: AsyncSession, result: WeekendIntelligenceResult, *, checkpoint_label: str | None = None,
):
    """Persists `result` as the next immutable version for its
    target_trading_date, via Phase 1A's create_next_version (atomic
    supersede-and-insert). Caller commits."""
    return await create_next_version(
        db,
        target_trading_date=result.target_trading_date,
        last_trading_date=result.last_trading_date,
        checkpoint_label=checkpoint_label,
        status=result.status,
        overall_bias=result.overall_bias,
        production_confidence=result.production_confidence,
        top_sector_refs=_top_sector_refs(result.sector_signals),
        top_company_refs=_top_company_refs(result.company_signals),
        opportunity_refs=result.opportunity_refs,
        risk_refs=[
            {"description": r.description, "risk_type": r.risk_type, "severity": r.severity,
             "evidence_refs": r.evidence_refs, "related_sectors": r.related_sectors,
             "related_companies": r.related_companies}
            for r in result.market_risks
        ],
        confidence_warning_refs=[
            {"description": r.description, "risk_type": r.risk_type, "severity": r.severity,
             "evidence_refs": r.evidence_refs, "related_sectors": r.related_sectors,
             "related_companies": r.related_companies}
            for r in result.confidence_warnings
        ],
        historical_analogue_refs=result.historical_analogue_refs,
        changes_since_prior=result.changes,
        new_since_close_refs=result.new_since_close_refs,
        evidence_refs=result.evidence_refs,
        market_snapshot_id=result.market_snapshot_id,
        experimental_signals=None,  # brief §14 — Kronos not part of Phase 1B, stays empty
        confidence_components=result.confidence_breakdown,
    )

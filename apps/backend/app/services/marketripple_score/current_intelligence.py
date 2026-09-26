"""
Current Intelligence pillar — S2-B. Reuses compute_company_score() verbatim,
never a second, competing evidence-scoring engine. The only new work here is
wrapping the real output in the PillarScore contract.

2026-09-26 Current Intelligence audit — two real findings acted on here:

1. compute_company_score() now deduplicates signals that trace back to the
   same real event_id (see company_score_engine.py::_dedupe_signals_by_event)
   before this pillar ever sees them, so contributing_signal_count no longer
   double-counts one real event that produced both an article and an
   opportunity. This pillar surfaces the resulting contributing_event_count/
   supporting_source_count/unresolved_lineage fields rather than hiding them.

2. The old ">=10 contributing signals = COMPLETE" threshold is RETIRED, not
   replaced with a different unvalidated number. It had no defensible basis
   (own prior docstring: "candidate threshold, not validated") and, with
   pre-dedup counts, was measuring inflated evidence volume rather than
   independent real events. This pillar now only ever reports INSUFFICIENT
   (no real contributing evidence) or PARTIAL (some) — COMPLETE requires a
   real, separately-validated completeness policy that does not exist yet.
   coverage_pct is kept as a descriptive fill number only; it never grants
   COMPLETE status.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.contracts import PillarScore, PillarStatus

_DESCRIPTIVE_SIGNAL_SCALE = 10  # coverage_pct denominator only — never a status threshold, see module docstring


async def score_current_intelligence(db: AsyncSession, symbol: str) -> PillarScore:
    from app.services.aipe.company_score_engine import compute_company_score

    result = await compute_company_score(db, symbol)
    contributing = result.get("contributing_signal_count", 0)
    total = result.get("signal_count", 0)
    contributing_events = result.get("contributing_event_count", 0)
    contributing_no_lineage = result.get("contributing_no_lineage_count", 0)
    supporting_sources = result.get("supporting_source_count", 0)
    unresolved_lineage = result.get("unresolved_lineage", [])

    if result.get("score") is None or contributing == 0:
        return PillarScore(
            name="current_intelligence", score=None, coverage_pct=0.0,
            status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["contributing_evidence"],
            sources=["ai_company_signals"],
            detail={
                "signal_count": total, "contributing_signal_count": 0,
                "contributing_event_count": 0, "contributing_no_lineage_count": 0,
                "supporting_source_count": supporting_sources,
                "unresolved_lineage": unresolved_lineage,
            },
        )

    coverage_pct = round(min(100.0, contributing / _DESCRIPTIVE_SIGNAL_SCALE * 100), 1)

    return PillarScore(
        name="current_intelligence",
        score=result["score"],
        coverage_pct=coverage_pct,
        status=PillarStatus.PARTIAL,  # never COMPLETE — see module docstring
        metrics_used=["ai_company_score"],
        metrics_missing=["validated_completeness_policy"],
        sources=["ai_company_signals (published analysis + opportunity tracking)"],
        detail={
            "signal_count": total,
            "contributing_signal_count": contributing,
            "contributing_event_count": contributing_events,
            "contributing_no_lineage_count": contributing_no_lineage,
            "supporting_source_count": supporting_sources,
            "unresolved_lineage": unresolved_lineage,
            "risk_level": result.get("risk_level"),
            "trend": result.get("trend"),
        },
    )

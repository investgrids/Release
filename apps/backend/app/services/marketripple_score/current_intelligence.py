"""
Current Intelligence pillar — S2-B. Reuses compute_company_score() verbatim,
never a second, competing evidence-scoring engine. The only new work here is
wrapping the real output in the PillarScore contract, using the cleaned
contributing_signal_count semantics (2026-08-25) as the real coverage
signal instead of the raw, noise-inflated signal_count.

Coverage/status thresholds below (>=10 contributing signals = COMPLETE,
1-9 = PARTIAL, 0 = INSUFFICIENT) are an explicit candidate policy, not a
validated one — flagged for review once the 5-bank comparison in engine.py
is inspected, same as every other threshold in this phase.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.contracts import PillarScore, PillarStatus

_SUFFICIENT_CONTRIBUTING_SIGNALS = 10  # candidate threshold, not validated


async def score_current_intelligence(db: AsyncSession, symbol: str) -> PillarScore:
    from app.services.aipe.company_score_engine import compute_company_score

    result = await compute_company_score(db, symbol)
    contributing = result.get("contributing_signal_count", 0)
    total = result.get("signal_count", 0)

    if result.get("score") is None or contributing == 0:
        return PillarScore(
            name="current_intelligence", score=None, coverage_pct=0.0,
            status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["contributing_evidence"],
            sources=["ai_company_signals"],
            detail={"signal_count": total, "contributing_signal_count": 0},
        )

    coverage_pct = round(min(100.0, contributing / _SUFFICIENT_CONTRIBUTING_SIGNALS * 100), 1)
    status = PillarStatus.COMPLETE if contributing >= _SUFFICIENT_CONTRIBUTING_SIGNALS else PillarStatus.PARTIAL

    return PillarScore(
        name="current_intelligence",
        score=result["score"],
        coverage_pct=coverage_pct,
        status=status,
        metrics_used=["ai_company_score"],
        metrics_missing=[] if status == PillarStatus.COMPLETE else ["sufficient_contributing_evidence_volume"],
        sources=["ai_company_signals (published analysis + opportunity tracking)"],
        detail={
            "signal_count": total,
            "contributing_signal_count": contributing,
            "risk_level": result.get("risk_level"),
            "trend": result.get("trend"),
        },
    )

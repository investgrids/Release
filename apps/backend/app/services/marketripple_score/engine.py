"""
MarketRippleScore engine — S2-A/D. Composes the 4 pillars with the owner's
candidate weights (Financial Strength 40 / Valuation 20 / Market Behaviour
15 / Current Intelligence 25) — explicitly unvalidated; see the 5-bank
comparison this module is built to support before trusting them.

publishable is hardcoded False for the whole S2 phase per owner decision
("S2 may calculate. S2 may test. S2 may not replace the Company-page score
yet.") — not a computed gate on coverage today, a deliberate phase lock.
Left as an explicit field (not just a docstring rule) so activating it
later is a one-line change with a real, traceable reason, not a silent
behavior flip.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.contracts import MarketRippleScore, PillarScore, PillarStatus
from app.services.marketripple_score.current_intelligence import score_current_intelligence
from app.services.marketripple_score.financial_strength import score_financial_strength
from app.services.marketripple_score.market_behaviour import score_market_behaviour
from app.services.marketripple_score.valuation import score_valuation

CANDIDATE_WEIGHTS = {
    "financial_strength": 0.40,
    "valuation": 0.20,
    "market_behaviour": 0.15,
    "current_intelligence": 0.25,
}

_PUBLISH_LOCK_REASON = (
    "S2 phase lock (owner decision, 2026-08-25): Financial Strength is real "
    "but PARTIAL for every Banking symbol (8 of 12 proposed metrics missing, "
    "including both asset-quality and both capital-adequacy metrics — see "
    "artifacts/marketripple_score_s1_feasibility_audit.md). This score is "
    "computed and inspectable but never publishable until S3 (banking "
    "fundamentals sourcing) closes that gap or a decision is made to "
    "publish anyway with the coverage caveat shown."
)


def _label_for(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Positive"
    if score >= 45:
        return "Neutral"
    return "Cautious"


async def compute_marketripple_score(db: AsyncSession, symbol: str) -> MarketRippleScore:
    """Computes all 4 pillars concurrently (they share no mutable state)
    and composes them into one MarketRippleScore. The single real entry
    point for S2 — used directly by the 5-bank comparison in
    scripts/marketripple_score_five_bank_comparison.py."""
    import asyncio
    from app.services.aipe.company_score_engine import _sector_for

    symbol = symbol.upper()
    sector = _sector_for(symbol)

    fs, val, mkt, ci = await asyncio.gather(
        score_financial_strength(symbol, sector),
        score_valuation(symbol, sector),
        score_market_behaviour(symbol, sector),
        score_current_intelligence(db, symbol),
    )

    pillars: dict[str, PillarScore] = {
        "financial_strength": fs, "valuation": val, "market_behaviour": mkt, "current_intelligence": ci,
    }
    usable = {name: p for name, p in pillars.items() if p.score is not None}
    if not usable:
        return MarketRippleScore(
            symbol=symbol, score=None, label=None, publishable=False,
            publish_reason="No pillar produced a real score for this symbol.",
            pillars=pillars, weights=CANDIDATE_WEIGHTS, overall_coverage_pct=0.0,
        )

    used_weight = sum(CANDIDATE_WEIGHTS[name] for name in usable)
    overall_score = round(sum(p.score * CANDIDATE_WEIGHTS[name] for name, p in usable.items()) / used_weight, 1)
    overall_coverage = round(sum(p.coverage_pct * CANDIDATE_WEIGHTS[name] for name, p in usable.items()) / used_weight, 1)

    return MarketRippleScore(
        symbol=symbol, score=overall_score, label=_label_for(overall_score),
        publishable=False, publish_reason=_PUBLISH_LOCK_REASON,
        pillars=pillars, weights=CANDIDATE_WEIGHTS, overall_coverage_pct=overall_coverage,
    )

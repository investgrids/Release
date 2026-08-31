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

from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS, PEER_UNIVERSE_AS_OF
from app.services.marketripple_score.contracts import BANKING_METHODOLOGY_VERSION, MarketRippleScore, PillarScore, PillarStatus
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


async def compute_marketripple_score(
    db: AsyncSession, symbol: str, peer_group: list[str] | None = None,
) -> MarketRippleScore:
    """Composes all 4 pillars into one MarketRippleScore. The single real
    entry point for S2/S3-D/S4 — used directly by the 5-bank comparison in
    scripts/marketripple_score_five_bank_comparison.py.

    peer_group: S4's peer-universe sensitivity test needs to run the
    IDENTICAL frozen scoring formula against a wider real population —
    None (default) preserves the production 5-bank behavior byte-for-byte;
    passing a wider real list only changes which real companies the
    percentile ranking is computed against, never the formula itself.

    S3-D note: financial_strength now also queries the real FinancialFact
    store (for Gross NPA/Net NPA/CET1/ROA), so it and current_intelligence
    both touch `db` — they must run sequentially, not via asyncio.gather,
    since SQLAlchemy's AsyncSession isn't safe for concurrent use by
    multiple coroutines. valuation/market_behaviour are pure yfinance and
    stay concurrent with each other."""
    import asyncio
    from app.services.aipe.company_score_engine import _sector_for

    symbol = symbol.upper()
    sector = _sector_for(symbol)

    fs = await score_financial_strength(db, symbol, sector, peer_group=peer_group)
    ci = await score_current_intelligence(db, symbol)
    val, mkt = await asyncio.gather(
        score_valuation(symbol, sector, peer_group=peer_group),
        score_market_behaviour(symbol, sector),
    )

    pillars: dict[str, PillarScore] = {
        "financial_strength": fs, "valuation": val, "market_behaviour": mkt, "current_intelligence": ci,
    }

    # S4.5 — the real peer population this computation actually used
    # travels with the score itself (never just implicit backend config),
    # so the same bank can't silently get a different score from a
    # different caller. Banking gets its own versioned methodology tag;
    # other, not-yet-built sectors keep the generic placeholder.
    if sector == "Banking":
        methodology_version = BANKING_METHODOLOGY_VERSION
        actual_peer_universe = peer_group if peer_group is not None else ALL_ELIGIBLE_NSE_BANKS
        peer_universe_as_of = PEER_UNIVERSE_AS_OF
    else:
        methodology_version = None  # falls back to the dataclass field default
        actual_peer_universe = []
        peer_universe_as_of = None

    usable = {name: p for name, p in pillars.items() if p.score is not None}
    if not usable:
        kwargs = dict(
            symbol=symbol, score=None, label=None, publishable=False,
            publish_reason="No pillar produced a real score for this symbol.",
            pillars=pillars, weights=CANDIDATE_WEIGHTS, overall_coverage_pct=0.0,
            peer_universe=actual_peer_universe, peer_universe_count=len(actual_peer_universe),
            peer_universe_as_of=peer_universe_as_of,
        )
        if methodology_version is not None:
            kwargs["methodology_version"] = methodology_version
        return MarketRippleScore(**kwargs)

    used_weight = sum(CANDIDATE_WEIGHTS[name] for name in usable)
    overall_score = round(sum(p.score * CANDIDATE_WEIGHTS[name] for name, p in usable.items()) / used_weight, 1)
    overall_coverage = round(sum(p.coverage_pct * CANDIDATE_WEIGHTS[name] for name, p in usable.items()) / used_weight, 1)

    kwargs = dict(
        symbol=symbol, score=overall_score, label=_label_for(overall_score),
        publishable=False, publish_reason=_PUBLISH_LOCK_REASON,
        pillars=pillars, weights=CANDIDATE_WEIGHTS, overall_coverage_pct=overall_coverage,
        peer_universe=actual_peer_universe, peer_universe_count=len(actual_peer_universe),
        peer_universe_as_of=peer_universe_as_of,
    )
    if methodology_version is not None:
        kwargs["methodology_version"] = methodology_version
    return MarketRippleScore(**kwargs)

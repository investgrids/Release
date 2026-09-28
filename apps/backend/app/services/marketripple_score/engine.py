"""
MarketRippleScore engine — S2-A/D, unified by owner instruction 2026-09-27
("one score calculation"). ONE shared headline function (compute_headline
below) now composes every supported company's score — Banking and every
NONBANK_INDUSTRIAL_SECTORS sector alike — using the exact same rule:
Financial Strength/Valuation/Market Behaviour are the three REQUIRED,
fixed-weight pillars (8/15, 4/15, 3/15, kept as exact Fractions so the
blend never accumulates decimal-rounding error); all three or no headline
number, never a renormalized subset. Current Intelligence is computed and
shown in full for every company but never enters this blend, present or
not — it is supporting evidence about the company, not a scoring input.

Sector-specific code still produces the raw Financial Strength PillarScore
itself (financial_strength.py dispatches Banking's NPA/CET1/ROA-based
metrics vs. Industrial's revenue-growth/ROE-based metrics) — only the
headline composition, rating bands and missing-pillar rule are now
identical across sectors, per the owner's explicit instruction: "Banks and
non-banks may use different raw metrics to produce Financial Strength, but
the headline function, rating bands and missing-pillar rule must be
identical."

This replaces two separate, now-retired rules: Banking's original 4-pillar
dynamic-renormalization composition (CANDIDATE_WEIGHTS, complete only at
4-of-4, real and tested from 2026-08-25 until this unification) and
NONBANK_INDUSTRIAL_V2's own dedicated 3-pillar function
(compute_nonbank_headline, introduced hours earlier the same day,
2026-09-27, to fix 82% of non-bank companies losing their headline over
thin Current Intelligence evidence — see contracts.py's own history). Both
real, deliberate, already-shipped designs; this unification keeps V2's
3-pillar/fixed-weight shape (the right one) and extends it to Banking
too, rather than inventing a third rule. A real, deliberate consequence:
Banking scores can change under this unification (a bank no longer needs
Current Intelligence to get a headline number) — see
MARKETRIPPLE_SCORE_METHODOLOGY_VERSION in contracts.py for why that's
tagged as a genuinely new methodology, not a silent reinterpretation of
BANKING_V1's old rows.

Publication (owner decision 2026-09-28, lifting the 2026-08-25 S2 phase
lock): the engine marks a score publishable whenever it produced a real
headline number. snapshot.py then withholds it again unless the company
also passes every publication-eligibility check, so a partial or
ineligible score is never public. Unsupported sectors are never
publishable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS, PEER_UNIVERSE_AS_OF
from app.services.marketripple_score.contracts import (
    MARKETRIPPLE_SCORE_METHODOLOGY_VERSION,
    MarketRippleScore, PillarScore, PillarStatus,
)
from app.services.marketripple_score.current_intelligence import score_current_intelligence
from app.services.marketripple_score.financial_strength import score_financial_strength
from app.services.marketripple_score.market_behaviour import score_market_behaviour
from app.services.marketripple_score.sector_universe import (
    NONBANK_INDUSTRIAL_SECTORS, NONBANK_PEER_UNIVERSE_AS_OF, sector_peer_universe,
)
from app.services.marketripple_score.valuation import score_valuation

# The ONE shared headline rule (owner instruction, 2026-09-27) — every
# supported sector (Banking and NONBANK_INDUSTRIAL_SECTORS alike) requires
# exactly these three pillars, weighted identically. Not a fresh arbitrary
# split — derived by renormalizing this engine's original 2026-08-25
# candidate weights (Financial Strength 40 / Valuation 20 / Market
# Behaviour 15, ignoring Current Intelligence's 25) across just these
# three, preserving their original relative priority ordering: 0.40/0.75,
# 0.20/0.75, 0.15/0.75 — the owner-agreed exact rational form of that is
# 8/15, 4/15, 3/15.
REQUIRED_HEADLINE_PILLARS = ("financial_strength", "valuation", "market_behaviour")
_HEADLINE_EXACT_WEIGHTS: dict[str, Fraction] = {
    "financial_strength": Fraction(8, 15),
    "valuation": Fraction(4, 15),
    "market_behaviour": Fraction(3, 15),
}
HEADLINE_WEIGHTS: dict[str, float] = {
    name: float(w) for name, w in _HEADLINE_EXACT_WEIGHTS.items()
}

# Structured reason codes for compute_headline()'s "unavailable" outcome —
# never a bare free-text-only failure, same discipline as eligibility.py's
# own REASON_* constants.
HEADLINE_REASON_MISSING_PILLAR = "MISSING_REQUIRED_PILLAR"
HEADLINE_REASON_INVALID_SCORE_RANGE = "INVALID_PILLAR_SCORE_RANGE"

_NO_HEADLINE_REASON = "No headline score: a required pillar is missing or invalid."


@dataclass
class HeadlineResult:
    score: float | None
    label: str | None
    status: str  # "complete" | "partial" | "insufficient"
    reason_code: str | None
    message: str
    missing_pillars: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    coverage_pct: float | None = None


def compute_headline(pillars: dict[str, PillarScore]) -> HeadlineResult:
    """THE one real function that turns real Financial Strength/Valuation/
    Market Behaviour PillarScores into the MARKETRIPPLE_SCORE_V1 headline
    number, for every supported sector (owner instruction, 2026-09-27:
    "one shared function for every supported company... the headline
    function, rating bands and missing-pillar rule must be identical").
    Validates each required pillar's score is a real value in [0, 100],
    computes the exact-fraction weighted blend, assigns the rating label
    (via the shared `_label_for`), and returns a STRUCTURED reason
    whenever a headline can't be computed. Current Intelligence, even if
    present in `pillars`, is never read by this function at all — it
    structurally cannot affect the output, regardless of what any caller
    passes in."""
    invalid: list[tuple[str, float]] = []
    missing: list[str] = []
    for name in REQUIRED_HEADLINE_PILLARS:
        p = pillars.get(name)
        score = p.score if p is not None else None
        if score is None:
            missing.append(name)
        elif not (0.0 <= score <= 100.0):
            invalid.append((name, score))

    if invalid:
        return HeadlineResult(
            score=None, label=None, status="insufficient",
            reason_code=HEADLINE_REASON_INVALID_SCORE_RANGE,
            message=(
                f"Refusing to compute a headline: pillar(s) outside the real 0-100 range: {invalid}. "
                "This indicates a real bug upstream, not a data-availability gap."
            ),
        )

    if missing:
        n_required = len(REQUIRED_HEADLINE_PILLARS)
        n_ok = n_required - len(missing)
        status = "insufficient" if n_ok == 0 else "partial"
        return HeadlineResult(
            score=None, label=None, status=status,
            reason_code=HEADLINE_REASON_MISSING_PILLAR,
            message=(
                f"{'Partial' if status == 'partial' else 'Insufficient'} coverage — {n_ok} of {n_required} "
                "required pillars (Financial Strength, Valuation, Market Behaviour). Current Intelligence "
                "is shown separately as evidence, never required for this score."
            ),
            missing_pillars=missing,
        )

    exact_score = sum(
        Fraction(pillars[name].score).limit_denominator(10**9) * _HEADLINE_EXACT_WEIGHTS[name]
        for name in REQUIRED_HEADLINE_PILLARS
    )
    exact_coverage = sum(
        Fraction(pillars[name].coverage_pct).limit_denominator(10**9) * _HEADLINE_EXACT_WEIGHTS[name]
        for name in REQUIRED_HEADLINE_PILLARS
    )
    score = round(float(exact_score), 1)
    return HeadlineResult(
        score=score, label=_label_for(score), status="complete", reason_code=None,
        message=(
            "Complete coverage — 3 of 3 required pillars (Financial Strength, Valuation, Market Behaviour). "
            "Current Intelligence is shown separately as evidence, not part of this score."
        ),
        weights=HEADLINE_WEIGHTS, coverage_pct=round(float(exact_coverage), 1),
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
    industrial_cache: dict | None = None,
) -> MarketRippleScore:
    """Composes all 4 pillars into one MarketRippleScore via the ONE shared
    headline function (compute_headline). The single real entry point for
    every supported sector.

    peer_group: S4's peer-universe sensitivity test needs to run the
    IDENTICAL frozen scoring formula against a wider real population —
    None (default) preserves the production default peer universe
    byte-for-byte; passing a wider real list only changes which real
    companies the percentile ranking is computed against, never the
    formula itself.

    industrial_cache (NS1 round 2, 2026-09-27): an optional
    {"financial_inputs": ..., "valuation_snapshots": ..., "benchmarks": ...}
    map, each built by the matching prefetch_* helper in
    financial_strength_industrial.py/valuation.py, forwarded to each
    pillar's own `prefetched`/`prefetched_benchmarks` parameter. Has NO
    effect on Banking (its own branches in every pillar never read this).
    None (default, every existing caller) preserves the original per-call
    fetch behavior exactly — this parameter exists purely so a batch
    computing many companies in the same real sector can fetch that
    sector's shared peer/benchmark data ONCE instead of once per company;
    see scripts/s11_shared_fetch_sector_backfill.py for the real caller.

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
    industrial_cache = industrial_cache or {}

    fs = await score_financial_strength(
        db, symbol, sector, peer_group=peer_group,
        prefetched=industrial_cache.get("financial_inputs"),
    )
    ci = await score_current_intelligence(db, symbol)
    val, mkt = await asyncio.gather(
        score_valuation(symbol, sector, peer_group=peer_group, prefetched=industrial_cache.get("valuation_snapshots")),
        score_market_behaviour(symbol, sector, prefetched_benchmarks=industrial_cache.get("benchmarks")),
    )

    pillars: dict[str, PillarScore] = {
        "financial_strength": fs, "valuation": val, "market_behaviour": mkt, "current_intelligence": ci,
    }

    # S4.5 — the real peer population this computation actually used
    # travels with the score itself (never just implicit backend config),
    # so the same company can't silently get a different score from a
    # different caller. Banking and NONBANK_INDUSTRIAL_SECTORS each keep
    # their own real peer universe (a Technology score is never compared
    # against a Banking peer pool) but now share ONE methodology tag and
    # ONE headline function — see this module's own docstring.
    if sector == "Banking":
        actual_peer_universe = peer_group if peer_group is not None else ALL_ELIGIBLE_NSE_BANKS
        peer_universe_as_of = PEER_UNIVERSE_AS_OF
    elif sector in NONBANK_INDUSTRIAL_SECTORS:
        actual_peer_universe = peer_group if peer_group is not None else sector_peer_universe(sector)
        peer_universe_as_of = NONBANK_PEER_UNIVERSE_AS_OF
    else:
        actual_peer_universe = []
        peer_universe_as_of = None

    if sector != "Banking" and sector not in NONBANK_INDUSTRIAL_SECTORS:
        # No approved methodology exists for this sector at all yet
        # (Finance/Insurance and any other not-yet-built sector) — honest
        # "unsupported," never a fabricated number and never ranked.
        return MarketRippleScore(
            symbol=symbol, score=None, label=None, publishable=False,
            publish_reason="No approved MarketRipple Score methodology exists for this sector yet.",
            pillars=pillars, weights=HEADLINE_WEIGHTS, overall_coverage_pct=0.0,
            peer_universe=[], peer_universe_count=0, peer_universe_as_of=None,
            pillar_coverage_status="insufficient",
            pillar_coverage_message="No approved MarketRipple Score methodology exists for this sector yet.",
        )

    # MARKETRIPPLE_SCORE_V1 (owner instruction, 2026-09-27) — the ONE real
    # function that validates the three required pillars, computes the
    # exact-fraction weighted headline, assigns its rating, and returns a
    # structured reason when it can't, for every supported sector alike.
    # `ci` stays real, computed, and fully visible in `pillars` — evidence
    # about the company, presented separately, never read by
    # compute_headline at all, let alone folded into the weighted number.
    headline = compute_headline(pillars)
    return MarketRippleScore(
        symbol=symbol, score=headline.score, label=headline.label,
        publishable=headline.score is not None,
        publish_reason=None if headline.score is not None else (headline.message or _NO_HEADLINE_REASON),
        pillars=pillars, weights=HEADLINE_WEIGHTS,
        overall_coverage_pct=headline.coverage_pct if headline.coverage_pct is not None else 0.0,
        peer_universe=actual_peer_universe, peer_universe_count=len(actual_peer_universe),
        peer_universe_as_of=peer_universe_as_of, methodology_version=MARKETRIPPLE_SCORE_METHODOLOGY_VERSION,
        pillar_coverage_status=headline.status, pillar_coverage_message=headline.message,
    )

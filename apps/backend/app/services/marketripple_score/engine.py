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

from dataclasses import dataclass, field
from fractions import Fraction

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS, PEER_UNIVERSE_AS_OF
from app.services.marketripple_score.contracts import (
    BANKING_METHODOLOGY_VERSION, NONBANK_INDUSTRIAL_METHODOLOGY_VERSION,
    MarketRippleScore, PillarScore, PillarStatus,
)
from app.services.marketripple_score.current_intelligence import score_current_intelligence
from app.services.marketripple_score.financial_strength import score_financial_strength
from app.services.marketripple_score.market_behaviour import score_market_behaviour
from app.services.marketripple_score.sector_universe import (
    NONBANK_INDUSTRIAL_SECTORS, NONBANK_PEER_UNIVERSE_AS_OF, sector_peer_universe,
)
from app.services.marketripple_score.valuation import score_valuation

CANDIDATE_WEIGHTS = {
    "financial_strength": 0.40,
    "valuation": 0.20,
    "market_behaviour": 0.15,
    "current_intelligence": 0.25,
}

# NONBANK_INDUSTRIAL_V2 (owner instruction, 2026-09-27) — a versioned,
# DELIBERATE redesign, not a Banking-formula change (Banking's own
# CANDIDATE_WEIGHTS/4-pillar rule above stays exactly as it is, forever,
# until its own methodology is deliberately revised). Real problem this
# closes: after the NS1/NS2 full-cohort backfill, 326 of 397 non-bank
# companies (82%) showed a real, complete 3-of-3 Financial Strength/
# Valuation/Market Behaviour result but no headline number at all, purely
# because Current Intelligence (real evidence density, not a financial
# metric) found no contributing signal for them — the OLD 4-pillar
# comparability rule (inherited from Banking's own design) was
# withholding a real, defensible score over a pillar that measures
# something structurally different (evidence coverage, not company
# fundamentals) and is far thinner for most non-bank companies than for
# the 27 heavily-covered real banks it was designed against.
#
# V2's fix: Financial Strength, Valuation, and Market Behaviour are the
# three REQUIRED, WEIGHTED pillars for a non-bank headline score — fixed,
# disclosed weights below, never adaptively renormalized across however
# many of the three happen to be available (all three or no headline
# number, same honest-withholding principle Banking already uses, just
# against a 3-pillar bar instead of 4). Current Intelligence is still
# computed and still shown in full, real detail (never hidden) — it is
# evidence ABOUT the company, presented under its own separate label, and
# never enters this weighted blend at all, present or not. A caller can
# tell the two pillar classes apart via `weights` on the returned
# MarketRippleScore: NONBANK_INDUSTRIAL_V2's `weights` dict has no
# "current_intelligence" key, unlike Banking's.
#
# Weights: NOT a fresh arbitrary split — derived by renormalizing
# engine.py's own original candidate weights (Financial Strength 40 /
# Valuation 20 / Market Behaviour 15, ignoring Current Intelligence's 25)
# across just these three, preserving their original relative priority
# ordering rather than re-deciding it from scratch: 0.40/0.75, 0.20/0.75,
# 0.15/0.75 — the owner-agreed EXACT rational form of that is 8/15, 4/15,
# 3/15. Kept as Fraction (not a rounded float) so the headline computation
# itself in compute_nonbank_headline() below never accumulates decimal-
# rounding error; NONBANK_INDUSTRIAL_V2_WEIGHTS (float, derived FROM the
# exact fractions, not the reverse) exists only for display/API/ranking
# disclosure, never for the actual weighted sum.
NONBANK_INDUSTRIAL_V2_REQUIRED_PILLARS = ("financial_strength", "valuation", "market_behaviour")
_NONBANK_INDUSTRIAL_V2_EXACT_WEIGHTS: dict[str, Fraction] = {
    "financial_strength": Fraction(8, 15),
    "valuation": Fraction(4, 15),
    "market_behaviour": Fraction(3, 15),
}
NONBANK_INDUSTRIAL_V2_WEIGHTS: dict[str, float] = {
    name: float(w) for name, w in _NONBANK_INDUSTRIAL_V2_EXACT_WEIGHTS.items()
}

# Structured reason codes for compute_nonbank_headline()'s "unavailable"
# outcome — never a bare free-text-only failure, same discipline as
# eligibility.py's own REASON_* constants.
NONBANK_HEADLINE_REASON_MISSING_PILLAR = "MISSING_REQUIRED_PILLAR"
NONBANK_HEADLINE_REASON_INVALID_SCORE_RANGE = "INVALID_PILLAR_SCORE_RANGE"

_PUBLISH_LOCK_REASON = (
    "S2 phase lock (owner decision, 2026-08-25): Financial Strength is real "
    "but PARTIAL for every Banking symbol (8 of 12 proposed metrics missing, "
    "including both asset-quality and both capital-adequacy metrics — see "
    "artifacts/marketripple_score_s1_feasibility_audit.md). This score is "
    "computed and inspectable but never publishable until S3 (banking "
    "fundamentals sourcing) closes that gap or a decision is made to "
    "publish anyway with the coverage caveat shown."
)


@dataclass
class NonBankHeadlineResult:
    score: float | None
    label: str | None
    status: str  # "complete" | "partial" | "insufficient"
    reason_code: str | None
    message: str
    missing_pillars: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    coverage_pct: float | None = None


def compute_nonbank_headline(pillars: dict[str, PillarScore]) -> NonBankHeadlineResult:
    """THE one real function that turns real Financial Strength/Valuation/
    Market Behaviour PillarScores into the NONBANK_INDUSTRIAL_V2 headline
    number (owner instruction, 2026-09-27) — validates each required
    pillar's score is a real value in [0, 100], computes the exact-
    fraction weighted blend, assigns the rating label (via the same
    `_label_for` Banking already uses — one shared rating scale, not a
    second one), and returns a STRUCTURED reason (never just a free-text
    message) whenever a headline can't be computed. Current Intelligence,
    even if present in `pillars`, is never read by this function at all —
    it structurally cannot affect the output, regardless of what any
    caller passes in."""
    invalid: list[tuple[str, float]] = []
    missing: list[str] = []
    for name in NONBANK_INDUSTRIAL_V2_REQUIRED_PILLARS:
        p = pillars.get(name)
        score = p.score if p is not None else None
        if score is None:
            missing.append(name)
        elif not (0.0 <= score <= 100.0):
            invalid.append((name, score))

    if invalid:
        return NonBankHeadlineResult(
            score=None, label=None, status="insufficient",
            reason_code=NONBANK_HEADLINE_REASON_INVALID_SCORE_RANGE,
            message=(
                f"Refusing to compute a headline: pillar(s) outside the real 0-100 range: {invalid}. "
                "This indicates a real bug upstream, not a data-availability gap."
            ),
        )

    if missing:
        n_required = len(NONBANK_INDUSTRIAL_V2_REQUIRED_PILLARS)
        n_ok = n_required - len(missing)
        status = "insufficient" if n_ok == 0 else "partial"
        return NonBankHeadlineResult(
            score=None, label=None, status=status,
            reason_code=NONBANK_HEADLINE_REASON_MISSING_PILLAR,
            message=(
                f"{'Partial' if status == 'partial' else 'Insufficient'} coverage — {n_ok} of {n_required} "
                "required pillars (Financial Strength, Valuation, Market Behaviour). Current Intelligence "
                "is shown separately as evidence, never required for this score."
            ),
            missing_pillars=missing,
        )

    exact_score = sum(
        Fraction(pillars[name].score).limit_denominator(10**9) * _NONBANK_INDUSTRIAL_V2_EXACT_WEIGHTS[name]
        for name in NONBANK_INDUSTRIAL_V2_REQUIRED_PILLARS
    )
    exact_coverage = sum(
        Fraction(pillars[name].coverage_pct).limit_denominator(10**9) * _NONBANK_INDUSTRIAL_V2_EXACT_WEIGHTS[name]
        for name in NONBANK_INDUSTRIAL_V2_REQUIRED_PILLARS
    )
    score = round(float(exact_score), 1)
    return NonBankHeadlineResult(
        score=score, label=_label_for(score), status="complete", reason_code=None,
        message=(
            "Complete coverage — 3 of 3 required pillars (Financial Strength, Valuation, Market Behaviour). "
            "Current Intelligence is shown separately as evidence, not part of this score."
        ),
        weights=NONBANK_INDUSTRIAL_V2_WEIGHTS, coverage_pct=round(float(exact_coverage), 1),
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
    """Composes all 4 pillars into one MarketRippleScore. The single real
    entry point for S2/S3-D/S4 — used directly by the 5-bank comparison in
    scripts/marketripple_score_five_bank_comparison.py.

    peer_group: S4's peer-universe sensitivity test needs to run the
    IDENTICAL frozen scoring formula against a wider real population —
    None (default) preserves the production 5-bank behavior byte-for-byte;
    passing a wider real list only changes which real companies the
    percentile ranking is computed against, never the formula itself.

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
    # so the same bank can't silently get a different score from a
    # different caller. Banking gets its own versioned methodology tag;
    # other, not-yet-built sectors keep the generic placeholder.
    if sector == "Banking":
        methodology_version = BANKING_METHODOLOGY_VERSION
        actual_peer_universe = peer_group if peer_group is not None else ALL_ELIGIBLE_NSE_BANKS
        peer_universe_as_of = PEER_UNIVERSE_AS_OF
    elif sector in NONBANK_INDUSTRIAL_SECTORS:
        # NS1 (owner instruction, 2026-09-27) — a real, separate
        # methodology tag and peer universe; Banking's own branch above is
        # completely untouched by this addition.
        methodology_version = NONBANK_INDUSTRIAL_METHODOLOGY_VERSION
        actual_peer_universe = peer_group if peer_group is not None else sector_peer_universe(sector)
        peer_universe_as_of = NONBANK_PEER_UNIVERSE_AS_OF
    else:
        methodology_version = None  # falls back to the dataclass field default
        actual_peer_universe = []
        peer_universe_as_of = None

    if sector in NONBANK_INDUSTRIAL_SECTORS:
        # NONBANK_INDUSTRIAL_V2 (owner instruction, 2026-09-27) — the ONE
        # real function that validates the three required pillars,
        # computes the exact-fraction weighted headline, assigns its
        # rating, and returns a structured reason when it can't. A
        # genuinely separate composition rule from Banking's below, not a
        # generalized shared formula, so Banking's own real, tested
        # behavior can never be perturbed by this branch. `ci` stays real,
        # computed, and fully visible in `pillars` — evidence about the
        # company, presented separately, never read by compute_nonbank_headline
        # at all, let alone folded into the weighted number.
        headline = compute_nonbank_headline(pillars)
        return MarketRippleScore(
            symbol=symbol, score=headline.score, label=headline.label,
            publishable=False, publish_reason=_PUBLISH_LOCK_REASON,
            pillars=pillars, weights=NONBANK_INDUSTRIAL_V2_WEIGHTS,
            overall_coverage_pct=headline.coverage_pct if headline.coverage_pct is not None else 0.0,
            peer_universe=actual_peer_universe, peer_universe_count=len(actual_peer_universe),
            peer_universe_as_of=peer_universe_as_of, methodology_version=methodology_version,
            pillar_coverage_status=headline.status, pillar_coverage_message=headline.message,
        )

    # Banking (and any not-yet-built sector) — completely unchanged from
    # before NONBANK_INDUSTRIAL_V2 existed. Dynamic subset of ALL declared
    # pillars, renormalized against CANDIDATE_WEIGHTS, complete only at
    # 4-of-4 — Banking's own real, tested comparability rule, untouched.
    usable = {name: p for name, p in pillars.items() if p.score is not None}
    if not usable:
        kwargs = dict(
            symbol=symbol, score=None, label=None, publishable=False,
            publish_reason="No pillar produced a real score for this symbol.",
            pillars=pillars, weights=CANDIDATE_WEIGHTS, overall_coverage_pct=0.0,
            peer_universe=actual_peer_universe, peer_universe_count=len(actual_peer_universe),
            peer_universe_as_of=peer_universe_as_of,
            pillar_coverage_status="insufficient",
            pillar_coverage_message="No pillar produced a real score for this symbol.",
        )
        if methodology_version is not None:
            kwargs["methodology_version"] = methodology_version
        return MarketRippleScore(**kwargs)

    used_weight = sum(CANDIDATE_WEIGHTS[name] for name in usable)
    overall_score = round(sum(p.score * CANDIDATE_WEIGHTS[name] for name, p in usable.items()) / used_weight, 1)
    overall_coverage = round(sum(p.coverage_pct * CANDIDATE_WEIGHTS[name] for name, p in usable.items()) / used_weight, 1)

    total_pillars = len(pillars)
    if len(usable) < total_pillars:
        # Comparability interim rule — see contracts.py's own field docstring.
        # A renormalized 2-of-4 (or 3-of-4) blend is not comparable to a
        # 4-of-4 one, so no headline number or ranking eligibility until a
        # real shadow comparison says which partial combinations are safe.
        # Per-pillar scores that WERE produced stay fully visible in
        # `pillars` — only the combined number is withheld.
        pillar_coverage_status = "partial"
        pillar_coverage_message = f"Partial coverage — {len(usable)} of {total_pillars} pillars"
        headline_score, headline_label = None, None
    else:
        pillar_coverage_status = "complete"
        pillar_coverage_message = f"Complete coverage — {total_pillars} of {total_pillars} pillars"
        headline_score, headline_label = overall_score, _label_for(overall_score)

    kwargs = dict(
        symbol=symbol, score=headline_score, label=headline_label,
        publishable=False, publish_reason=_PUBLISH_LOCK_REASON,
        pillars=pillars, weights=CANDIDATE_WEIGHTS, overall_coverage_pct=overall_coverage,
        peer_universe=actual_peer_universe, peer_universe_count=len(actual_peer_universe),
        peer_universe_as_of=peer_universe_as_of,
        pillar_coverage_status=pillar_coverage_status,
        pillar_coverage_message=pillar_coverage_message,
    )
    if methodology_version is not None:
        kwargs["methodology_version"] = methodology_version
    return MarketRippleScore(**kwargs)

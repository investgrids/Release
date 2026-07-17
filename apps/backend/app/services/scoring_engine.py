"""
Centralized Scoring Engine — the single source of every score shown anywhere
in the app (Event Impact, Company Impact, Sector Strength, Theme Strength,
Opportunity, Risk, AI Confidence, Ripple Strength).

Hard rules this module enforces:
  1. No score is ever invented. Every sub-component is either a real,
     caller-supplied signal or it is left as None and excluded from the
     formula — the weight it would have used is redistributed across the
     components that *do* have real data (see `_weighted_composite`).
  2. If too little real data is available to produce a meaningful score,
     the model returns `status="insufficient_data"`, `score=None` — never
     a fabricated number. Callers/UI must render "Insufficient verified
     data to calculate score." in that case, not a placeholder digit.
  3. `confidence` on every result is not a vibe — it is literally how much
     of the formula's weight was backed by real data (`coverage`), so a
     3-of-10-signal score is honestly labeled low-confidence even if the
     score itself looks fine.
  4. Every model returns the same contract (`ScoreResult`) with `score`,
     `confidence`, `breakdown`, `reasoning`, `updated_at`, `version` — no
     page-specific shapes, no ad hoc component calculating its own number.

This module is pure: it takes typed inputs and returns a ScoreResult. It
does not fetch data itself. Callers (pipelines, API routes, workers) own
gathering real signals (DB queries, market_data, the intelligence graph,
historical memory, confidence_service) and pass them in. This keeps the
formulas testable and keeps "never fabricate" enforceable in one place,
while letting each call site be wired in independently over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

ENGINE_VERSION = "Score Engine v1"


# ─────────────────────────────────────────────────────────────────────────────
# Shared contract
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ScoreResult:
    score:      Optional[float]
    confidence: Optional[float]
    breakdown:  dict
    reasoning:  list
    status:     str = "ok"                 # "ok" | "insufficient_data"
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version:    str = ENGINE_VERSION

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "breakdown": self.breakdown,
            "reasoning": self.reasoning,
            "status": self.status,
            "updated_at": self.updated_at,
            "version": self.version,
        }


def _insufficient(reason: str, partial_breakdown: Optional[dict] = None) -> ScoreResult:
    return ScoreResult(
        score=None,
        confidence=None,
        breakdown=partial_breakdown or {},
        reasoning=[reason],
        status="insufficient_data",
    )


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


# Minimum fraction of a formula's total weight that must be backed by real
# data before we're willing to publish a score at all. Below this, too much
# of the number would be silently interpolated from nothing.
_MIN_COVERAGE = 0.35


def _weighted_composite(
    components: dict,  # name -> (value_0_100_or_None, weight)
) -> tuple:
    """
    Combine named 0-100 sub-scores into one 0-100 composite, weighted.

    Components with value=None are excluded entirely — their weight is
    redistributed proportionally across the components that have real
    data, so missing signals never get silently treated as zero (which
    would fabricate a penalty) or as average (which would fabricate a
    value). Returns (score, breakdown, coverage) where coverage is the
    fraction of total intended weight that was actually backed by data.
    """
    total_weight = sum(w for _, w in components.values())
    available = {k: (v, w) for k, (v, w) in components.items() if v is not None}
    if not available or total_weight <= 0:
        return None, {}, 0.0

    available_weight = sum(w for _, w in available.values())
    breakdown: dict = {}
    score = 0.0
    for name, (v, w) in available.items():
        contribution = _clamp(v) * (w / available_weight)
        breakdown[name] = round(contribution, 1)
        score += contribution

    coverage = available_weight / total_weight
    return round(_clamp(score), 1), breakdown, round(coverage, 2)


def historical_calibration(current_score: float, similar_events: list, score_field: str = "opportunity_score") -> dict:
    """
    Step-7 style calibration: compare a freshly computed score against the
    similarity-weighted average of the same metric across real historical
    events (as returned by historical_memory_service.find_similar_events).

    Returns {} if no similar events were found — calibration is additive
    context, never a substitute for real inputs elsewhere in the formula.
    """
    scored = [
        (e["similarity"], e[score_field])
        for e in (similar_events or [])
        if e.get(score_field) is not None and e.get("similarity") is not None
    ]
    if not scored:
        return {}

    total_w = sum(s for s, _ in scored)
    if total_w <= 0:
        return {}
    weighted_avg = sum(s * v for s, v in scored) / total_w
    deviation = round(current_score - weighted_avg, 1)

    return {
        "historical_average": round(weighted_avg, 1),
        "deviation": deviation,
        "similar_event_count": len(scored),
        "note": (
            f"Current score is {abs(deviation):.0f} points "
            f"{'above' if deviation >= 0 else 'below'} the historical average "
            f"of {len(scored)} similar past events."
            if deviation else
            f"Matches the historical average of {len(scored)} similar past events."
        ),
    }


def ripple_reach_score(ripple_result: Optional[dict]) -> tuple:
    """
    Shared by the Ripple Strength model AND fed into Event Impact's
    "ripple_reach" component (Step 6: deeper/wider ripple → higher impact).

    `ripple_result` is the dict returned by
    intelligence_graph_service.ripple_from_node(). Returns
    (reach_score_0_100 or None, breakdown, reasoning_bullets).
    """
    if not ripple_result or not ripple_result.get("impacts"):
        return None, {}, []

    impacts = ripple_result["impacts"]
    total_impacted = len(impacts)
    weights = [i["accumulated_weight"] for i in impacts]
    depths = [i["depth"] for i in impacts]
    node_types = {i["node"]["node_type"] for i in impacts if i.get("node")}

    breadth = _clamp(total_impacted * 8)                       # 8 pts / impacted node, caps ~13 nodes
    avg_weight_score = _clamp((sum(weights) / len(weights)) * 100) if weights else 0.0
    depth_score = _clamp((max(depths) / 5.0) * 100) if depths else 0.0
    diversity_score = _clamp(len(node_types) * 20)              # 20 pts / distinct node type

    parts = {
        "reach_breadth":  (breadth, 30),
        "avg_weight":     (avg_weight_score, 30),
        "max_depth":      (depth_score, 20),
        "type_diversity": (diversity_score, 20),
    }
    score, breakdown, _coverage = _weighted_composite(parts)

    reasoning = [
        f"Ripples reach {total_impacted} connected entities",
        f"Deepest chain: {max(depths) if depths else 0} hops",
        f"Spans {len(node_types)} entity type(s): {', '.join(sorted(node_types))}",
    ]
    return score, breakdown, reasoning


# ─────────────────────────────────────────────────────────────────────────────
# 1. Event Impact Score
# ─────────────────────────────────────────────────────────────────────────────

_EVENT_TYPE_SEVERITY = {
    "monetary policy":       92, "union budget":          90,
    "geopolitical":          85, "global market shock":   90,
    "corporate crisis":      75, "regulatory":             70,
    "infrastructure policy": 72, "sectoral policy":        68,
    "commodity shock":       78, "election":               74,
    "trade policy":          70, "earnings":               55,
    "macro":                 50,
}


@dataclass
class EventImpactInputs:
    event_type:            Optional[str] = None        # category string, matched case-insensitively
    market_breadth:        Optional[float] = None       # 0-100, e.g. % of index advancing
    economic_importance:   Optional[float] = None       # 0-100, keyword/severity based
    companies_affected:    Optional[int] = None
    sectors_affected:      Optional[int] = None
    historical_impact:     Optional[float] = None       # 0-100, from historical_calibration()
    news_volume:           Optional[int] = None         # count of related articles
    source_quality:        Optional[float] = None       # 0-100 (govt/regulatory=high, generic RSS=low)
    published_at:          Optional[datetime] = None    # for recency decay
    ripple_result:         Optional[dict] = None         # from intelligence_graph_service.ripple_from_node


def _recency_score(published_at: Optional[datetime]) -> Optional[float]:
    if not published_at:
        return None
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600.0
    if hours < 0:
        hours = 0
    if hours <= 1:
        return 100.0
    if hours <= 6:
        return 85.0
    if hours <= 24:
        return 65.0
    if hours <= 72:
        return 40.0
    if hours <= 168:
        return 20.0
    return 8.0


def score_event_impact(inp: EventImpactInputs) -> ScoreResult:
    event_type_score = None
    if inp.event_type:
        event_type_score = _EVENT_TYPE_SEVERITY.get(inp.event_type.strip().lower())

    ripple_score, ripple_breakdown, ripple_reasons = ripple_reach_score(inp.ripple_result)

    companies_score = _clamp(inp.companies_affected * 12) if inp.companies_affected is not None else None
    sectors_score = _clamp(inp.sectors_affected * 22) if inp.sectors_affected is not None else None
    news_volume_score = _clamp(inp.news_volume * 6) if inp.news_volume is not None else None
    recency = _recency_score(inp.published_at)

    parts = {
        "event_type":          (event_type_score,          12),
        "market_breadth":      (inp.market_breadth,         10),
        "economic_importance": (inp.economic_importance,    14),
        "companies_affected":  (companies_score,            10),
        "sector_coverage":     (sectors_score,               10),
        "historical_impact":   (inp.historical_impact,       14),
        "news_volume":         (news_volume_score,            8),
        "source_quality":      (inp.source_quality,           8),
        "recency":             (recency,                      6),
        "ripple_reach":        (ripple_score,                 8),
    }
    score, breakdown, coverage = _weighted_composite(parts)

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute an Event Impact Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown,
        )

    reasoning = []
    if event_type_score:
        reasoning.append(f"Event category: {inp.event_type}")
    if inp.companies_affected:
        reasoning.append(f"{inp.companies_affected} listed companies affected")
    if inp.sectors_affected:
        reasoning.append(f"Spans {inp.sectors_affected} sector(s)")
    if inp.historical_impact is not None:
        reasoning.append(f"Historical precedent score: {inp.historical_impact:.0f}/100")
    if inp.news_volume:
        reasoning.append(f"{inp.news_volume} related news articles")
    reasoning.extend(ripple_reasons)
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score,
        confidence=round(coverage * 100, 1),
        breakdown=breakdown,
        reasoning=reasoning,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Company Impact Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompanyImpactInputs:
    revenue_exposure:      Optional[float] = None   # 0-100, % of revenue tied to the affected theme/sector — not yet sourced from any provider
    sector_exposure:       Optional[float] = None    # 0-100, how directly the company's sector matches the event's sectors
    news_mentions:         Optional[int] = None       # count mentioning this symbol
    market_cap:            Optional[float] = None      # absolute, for log-scaled weight
    institutional_holding_pct: Optional[float] = None  # 0-100, real yfinance heldPercentInstitutions
    order_book_growth:     Optional[float] = None      # 0-100 — not yet sourced (no structured order-book data feed)
    volume:                Optional[float] = None
    avg_volume:            Optional[float] = None
    historical_sensitivity: Optional[float] = None     # 0-100, from historical_winners/losers match strength
    ripple_result:          Optional[dict] = None       # graph impacts touching this company's node


def _log_scale_market_cap(market_cap: Optional[float]) -> Optional[float]:
    if not market_cap or market_cap <= 0:
        return None
    import math
    # ₹5,000 Cr (small-cap floor) → ~20, ₹15L Cr (largest caps) → ~100
    lo, hi = math.log10(5_000 * 1e7), math.log10(15_00_000 * 1e7)
    v = math.log10(market_cap)
    return _clamp(((v - lo) / (hi - lo)) * 100)


def score_company_impact(inp: CompanyImpactInputs) -> ScoreResult:
    market_cap_score = _log_scale_market_cap(inp.market_cap)
    news_mentions_score = _clamp(inp.news_mentions * 10) if inp.news_mentions is not None else None
    volume_score = None
    if inp.volume is not None and inp.avg_volume:
        volume_score = _clamp((inp.volume / inp.avg_volume) * 50)

    ripple_score, _rb, ripple_reasons = ripple_reach_score(inp.ripple_result)

    parts = {
        "revenue_exposure":       (inp.revenue_exposure, 12),
        "sector_exposure":        (inp.sector_exposure, 14),
        "news_mentions":          (news_mentions_score, 10),
        "market_cap_weight":      (market_cap_score, 10),
        "institutional_interest": (inp.institutional_holding_pct, 12),
        "order_book":             (inp.order_book_growth, 8),
        "current_volume":         (volume_score, 10),
        "historical_sensitivity": (inp.historical_sensitivity, 14),
        "ripple_connections":     (ripple_score, 10),
    }
    score, breakdown, coverage = _weighted_composite(parts)

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified company-level signals to compute a Company Impact Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown,
        )

    reasoning = []
    if inp.sector_exposure:
        reasoning.append(f"Sector exposure match: {inp.sector_exposure:.0f}/100")
    if inp.institutional_holding_pct:
        reasoning.append(f"{inp.institutional_holding_pct:.1f}% institutional holding")
    if inp.news_mentions:
        reasoning.append(f"Mentioned in {inp.news_mentions} related articles")
    if inp.historical_sensitivity is not None:
        reasoning.append(f"Historical sensitivity: {inp.historical_sensitivity:.0f}/100")
    reasoning.extend(ripple_reasons)
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(score=score, confidence=round(coverage * 100, 1), breakdown=breakdown, reasoning=reasoning)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sector Strength Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SectorStrengthInputs:
    avg_company_performance: Optional[float] = None   # 0-100, avg pct_change of sector constituents rescaled
    news_flow:                Optional[int] = None      # count of sector-tagged news
    institutional_flow:       Optional[float] = None     # 0-100, avg institutional holding change/level
    market_breadth:           Optional[float] = None
    momentum:                 Optional[float] = None      # 0-100, short-term price momentum
    relative_strength:        Optional[float] = None      # 0-100, sector return vs index return
    economic_drivers:         Optional[float] = None      # 0-100, policy/macro tailwind score
    historical_trend:         Optional[float] = None       # 0-100, from historical_calibration()


def score_sector_strength(inp: SectorStrengthInputs) -> ScoreResult:
    news_flow_score = _clamp(inp.news_flow * 5) if inp.news_flow is not None else None

    parts = {
        "avg_company_performance": (inp.avg_company_performance, 18),
        "news_flow":                (news_flow_score, 10),
        "institutional_flow":       (inp.institutional_flow, 12),
        "market_breadth":           (inp.market_breadth, 10),
        "momentum":                 (inp.momentum, 16),
        "relative_strength":        (inp.relative_strength, 14),
        "economic_drivers":         (inp.economic_drivers, 10),
        "historical_trend":         (inp.historical_trend, 10),
    }
    score, breakdown, coverage = _weighted_composite(parts)

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified sector-level signals to compute a Sector Strength Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown,
        )

    reasoning = []
    if inp.momentum is not None:
        reasoning.append(f"Momentum: {inp.momentum:.0f}/100")
    if inp.relative_strength is not None:
        reasoning.append(f"Relative strength vs index: {inp.relative_strength:.0f}/100")
    if inp.news_flow:
        reasoning.append(f"{inp.news_flow} sector-related news items")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(score=score, confidence=round(coverage * 100, 1), breakdown=breakdown, reasoning=reasoning)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Theme Strength Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ThemeStrengthInputs:
    related_events_count:    Optional[int] = None
    company_participation:   Optional[int] = None     # distinct companies tagged to this theme
    news_trend:               Optional[float] = None    # 0-100, momentum of article volume over time
    government_support:       Optional[float] = None     # 0-100, presence/strength of real policy backing
    global_trend:              Optional[float] = None      # 0-100, whether the theme is trending internationally
    historical_momentum:       Optional[float] = None       # 0-100, from historical_calibration()


def score_theme_strength(inp: ThemeStrengthInputs) -> ScoreResult:
    events_score = _clamp(inp.related_events_count * 10) if inp.related_events_count is not None else None
    participation_score = _clamp(inp.company_participation * 8) if inp.company_participation is not None else None

    parts = {
        "related_events":       (events_score, 20),
        "company_participation": (participation_score, 20),
        "news_trend":            (inp.news_trend, 18),
        "government_support":    (inp.government_support, 16),
        "global_trend":           (inp.global_trend, 12),
        "historical_momentum":    (inp.historical_momentum, 14),
    }
    score, breakdown, coverage = _weighted_composite(parts)

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute a Theme Strength Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown,
        )

    reasoning = []
    if inp.related_events_count:
        reasoning.append(f"{inp.related_events_count} related events tracked")
    if inp.company_participation:
        reasoning.append(f"{inp.company_participation} companies participating")
    if inp.government_support:
        reasoning.append(f"Government support signal: {inp.government_support:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(score=score, confidence=round(coverage * 100, 1), breakdown=breakdown, reasoning=reasoning)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Opportunity Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OpportunityInputs:
    positive_catalysts:  Optional[float] = None   # 0-100, count/strength of real bullish catalysts found
    valuation:            Optional[float] = None    # 0-100, e.g. inverse percentile of PE vs sector peers
    momentum:             Optional[float] = None
    business_outlook:      Optional[float] = None    # 0-100, from real AI reasoning grounded in filings/news, not a guess
    sector_strength:        Optional[float] = None     # feed from score_sector_strength(...).score
    ai_conviction:           Optional[float] = None      # 0-100, must be derived from confidence_service, not self-rated by the LLM
    historical_success_rate: Optional[float] = None       # 0-100, from historical_calibration() on similar past setups


def score_opportunity(inp: OpportunityInputs) -> ScoreResult:
    parts = {
        "positive_catalysts":  (inp.positive_catalysts, 16),
        "valuation":            (inp.valuation, 14),
        "momentum":             (inp.momentum, 16),
        "business_outlook":      (inp.business_outlook, 14),
        "sector_strength":        (inp.sector_strength, 14),
        "ai_conviction":           (inp.ai_conviction, 12),
        "historical_success":       (inp.historical_success_rate, 14),
    }
    score, breakdown, coverage = _weighted_composite(parts)

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute an Opportunity Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown,
        )

    reasoning = []
    if inp.positive_catalysts is not None:
        reasoning.append(f"Positive catalyst strength: {inp.positive_catalysts:.0f}/100")
    if inp.valuation is not None:
        reasoning.append(f"Valuation attractiveness: {inp.valuation:.0f}/100")
    if inp.historical_success_rate is not None:
        reasoning.append(f"Historical success rate on similar setups: {inp.historical_success_rate:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(score=score, confidence=round(coverage * 100, 1), breakdown=breakdown, reasoning=reasoning)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Risk Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskInputs:
    macro_risk:          Optional[float] = None
    policy_uncertainty:   Optional[float] = None
    volatility:            Optional[float] = None    # 0-100, from VIX level / beta
    geopolitical_risk:      Optional[float] = None
    earnings_risk:           Optional[float] = None    # 0-100, e.g. earnings surprise dispersion / guidance cuts
    liquidity_risk:           Optional[float] = None     # 0-100, inverse of volume/float
    historical_downside:       Optional[float] = None      # 0-100, from historical_calibration() on risk_score field


def score_risk(inp: RiskInputs) -> ScoreResult:
    parts = {
        "macro_risk":          (inp.macro_risk, 16),
        "policy_uncertainty":   (inp.policy_uncertainty, 14),
        "volatility":            (inp.volatility, 18),
        "geopolitical_risk":      (inp.geopolitical_risk, 12),
        "earnings_risk":           (inp.earnings_risk, 14),
        "liquidity_risk":           (inp.liquidity_risk, 12),
        "historical_downside":       (inp.historical_downside, 14),
    }
    score, breakdown, coverage = _weighted_composite(parts)

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute a Risk Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown,
        )

    reasoning = []
    if inp.volatility is not None:
        reasoning.append(f"Volatility signal: {inp.volatility:.0f}/100")
    if inp.geopolitical_risk is not None:
        reasoning.append(f"Geopolitical risk: {inp.geopolitical_risk:.0f}/100")
    if inp.historical_downside is not None:
        reasoning.append(f"Historical downside precedent: {inp.historical_downside:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(score=score, confidence=round(coverage * 100, 1), breakdown=breakdown, reasoning=reasoning)


# ─────────────────────────────────────────────────────────────────────────────
# 7. AI Confidence Score — wraps confidence_service (already implements
#    exactly this: confidence in the CONCLUSION, not the LLM's self-rating)
# ─────────────────────────────────────────────────────────────────────────────

def score_ai_confidence(factors) -> ScoreResult:
    """
    `factors` is a confidence_service.ConfidenceFactors built from real
    signals (source count, historical matches, market/sector confirmation,
    macro alignment, volatility regime). Wraps the existing weighted
    formula into the standard ScoreResult contract.
    """
    from app.services.confidence_service import calculate_confidence

    # Evidence check on the *raw* inputs, not the post-computed breakdown —
    # ConfidenceFactors() defaults company_sensitivity="medium" and
    # ai_certainty=5 even with zero real evidence, which would otherwise
    # silently produce a non-null score built entirely from placeholders.
    has_evidence = (
        factors.source_count > 0
        or factors.historical_count > 0
        or factors.market_confirming > 0
        or factors.sector_confirming > 0
        or factors.macro_aligned
    )
    if not has_evidence:
        return _insufficient("No verifiable evidence signals were available to assess confidence.")

    result = calculate_confidence(factors)

    return ScoreResult(
        score=result.total_score,
        confidence=result.total_score,   # for this model score and confidence are the same measure by definition
        breakdown={k: v for k, v in result.breakdown.items() if k != "total"},
        reasoning=result.reasons,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. Ripple Strength Score
# ─────────────────────────────────────────────────────────────────────────────

def score_ripple_strength(ripple_result: Optional[dict]) -> ScoreResult:
    score, breakdown, reasoning = ripple_reach_score(ripple_result)
    if score is None:
        return _insufficient("No graph connections found to compute a Ripple Strength Score.")

    # ripple_reach_score doesn't compute coverage (it's always fully-populated
    # once a ripple_result exists), so confidence here reflects reach breadth
    # instead — a ripple touching 1 node is real but thin evidence.
    total_impacted = len(ripple_result.get("impacts", []))
    confidence = round(_clamp(40 + total_impacted * 6), 1)

    return ScoreResult(score=score, confidence=confidence, breakdown=breakdown, reasoning=reasoning)

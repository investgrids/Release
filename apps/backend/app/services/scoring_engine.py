"""
Centralized Scoring Engine — the single source of every score shown anywhere
in the app (Event Impact, Company Impact, Sector Strength, Theme Strength,
Opportunity, Risk, AI Confidence, Ripple Strength).

Architecture (see app/services/feature_extraction.py for the layer upstream
of this one):

    Raw data -> Feature Extraction Engine -> Scoring Engine -> Ripple Engine -> Frontend

This module NEVER derives a signal from raw data itself — no timestamp math,
no log-scaling a market cap, no walking a ripple graph. It only receives
already-named 0-100 features (or None, when a signal genuinely isn't
available) and combines them. That boundary is what keeps every page's
score computed from the same evidence instead of each page approximating
its own version of "recency" or "ripple reach".

Hard rules this module enforces:
  1. No score is ever invented. Every sub-component is either a real,
     caller-supplied feature or it is left as None and excluded from the
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
     `confidence`, `breakdown`, `top_contributors`, `reasoning`,
     `updated_at`, `version` — no page-specific shapes.
  5. Formulas are versioned. Weight tables live in `_WEIGHTS[model][version]`
     and a stored `ScoreResult.version` (e.g. "Event Impact v1.0") always
     tells you exactly which formula produced a number, even after the
     weights are retuned in a later version — old reports stay
     reproducible instead of silently drifting when weights change.
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
    score:            Optional[float]
    confidence:        Optional[float]
    breakdown:           dict
    reasoning:             list
    top_contributors:        list = field(default_factory=list)   # [{label, value, signed_contribution, direction}]
    status:                    str = "ok"                          # "ok" | "insufficient_data"
    updated_at:                   str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version:                        str = ENGINE_VERSION

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "breakdown": self.breakdown,
            "top_contributors": self.top_contributors,
            "reasoning": self.reasoning,
            "status": self.status,
            "updated_at": self.updated_at,
            "version": self.version,
        }


def _insufficient(reason: str, partial_breakdown: Optional[dict] = None, version: str = ENGINE_VERSION) -> ScoreResult:
    return ScoreResult(
        score=None,
        confidence=None,
        breakdown=partial_breakdown or {},
        reasoning=[reason],
        status="insufficient_data",
        version=version,
    )


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _label(name: str) -> str:
    return name.replace("_", " ").title()


# Minimum fraction of a formula's total weight that must be backed by real
# data before we're willing to publish a score at all. Below this, too much
# of the number would be silently interpolated from nothing.
_MIN_COVERAGE = 0.35


def _weighted_composite(components: dict) -> tuple:
    """
    Combine named 0-100 sub-scores into one 0-100 composite, weighted.

    components: name -> (value_0_100_or_None, weight)

    Components with value=None are excluded entirely — their weight is
    redistributed proportionally across the components that have real
    data, so missing signals never get silently treated as zero (which
    would fabricate a penalty) or as average (which would fabricate a
    value).

    Returns (score, breakdown, coverage, top_contributors):
      breakdown         — {name: contribution_points} for every available component
      coverage          — fraction of total intended weight backed by real data
      top_contributors  — components ranked by |signed deviation from neutral (50)|,
                           i.e. how much each one pushed the score up/down from a
                           neutral midpoint — this is what powers the "Top Drivers"
                           UI (Phase 4), derived from the same numbers, not invented.
    """
    total_weight = sum(w for _, w in components.values())
    available = {k: (v, w) for k, (v, w) in components.items() if v is not None}
    if not available or total_weight <= 0:
        return None, {}, 0.0, []

    available_weight = sum(w for _, w in available.values())
    breakdown: dict = {}
    contributors: list = []
    score = 0.0
    for name, (v, w) in available.items():
        share = w / available_weight
        contribution = _clamp(v) * share
        breakdown[name] = round(contribution, 1)
        score += contribution

        signed = round((_clamp(v) - 50.0) * share, 1)
        if signed != 0:
            contributors.append({
                "label": _label(name),
                "value": round(_clamp(v), 1),
                "signed_contribution": signed,
                "direction": "up" if signed > 0 else "down",
            })

    contributors.sort(key=lambda c: abs(c["signed_contribution"]), reverse=True)
    coverage = available_weight / total_weight
    return round(_clamp(score), 1), breakdown, round(coverage, 2), contributors


def _compute(
    model_key: str,
    friendly_name: str,
    values: dict,
    version: Optional[str] = None,
    min_coverage: float = _MIN_COVERAGE,
) -> tuple:
    """
    Shared versioned-formula runner (Phase 3): looks up the weight table for
    `model_key`/`version` (defaulting to that model's current version),
    combines it with the caller's feature values, and returns everything
    a model function needs to build its ScoreResult — including the exact
    "<Friendly Name> v<version>" string that gets stamped onto the result
    so a stored score always names the formula that produced it, even
    after weights are retuned in a later version.
    """
    version = version or CURRENT_VERSION[model_key]
    weights = _WEIGHTS[model_key][version]
    parts = {name: (values.get(name), w) for name, w in weights.items()}
    score, breakdown, coverage, contributors = _weighted_composite(parts)
    formula_version = f"{friendly_name} {version}"
    return score, breakdown, coverage, contributors, formula_version


def historical_calibration(current_score: float, similar_events: list, score_field: str = "opportunity_score") -> dict:
    """
    Step-7 style calibration: compare a freshly computed score against the
    similarity-weighted average of the same metric across real historical
    events (as returned by historical_memory_service.find_similar_events).

    This is post-hoc explanatory context, not a scoring input — the input
    equivalent (`historical_similarity`, `historical_avg_impact`) is
    produced upstream by feature_extraction.extract_historical_features().

    Returns {} if no similar events were found.
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


# ─────────────────────────────────────────────────────────────────────────────
# Versioned weight tables (Phase 3) — one entry per model, keyed by version.
# Adding a new version is: append a new key here, bump CURRENT_VERSION, and
# any stored ScoreResult still names the exact version that produced it.
# ─────────────────────────────────────────────────────────────────────────────

_WEIGHTS: dict = {
    "event_impact": {
        "v1.0": {
            "event_magnitude": 12, "market_breadth": 8, "economic_significance": 14,
            "company_count": 9, "sector_count": 9, "historical_similarity": 7,
            "historical_avg_impact": 7, "news_volume": 7, "source_quality": 7,
            "institutional_mentions": 6, "recency": 6, "ripple_depth": 4, "ripple_width": 4,
        },
    },
    "company_impact": {
        "v1.0": {
            "revenue_exposure": 12, "sector_exposure": 14, "news_mentions": 10,
            "market_cap_weight": 10, "institutional_interest": 12, "order_book_growth": 8,
            "current_volume": 10, "historical_sensitivity": 14, "ripple_depth": 5, "ripple_width": 5,
        },
    },
    "sector_strength": {
        "v1.0": {
            "avg_company_performance": 18, "news_flow": 10, "institutional_flow": 12,
            "market_breadth": 10, "momentum": 16, "relative_strength": 14,
            "economic_drivers": 10, "historical_trend": 10,
        },
    },
    "theme_strength": {
        "v1.0": {
            "related_events": 20, "company_participation": 20, "news_trend": 18,
            "government_support": 16, "global_trend": 12, "historical_momentum": 14,
        },
    },
    "opportunity": {
        "v1.0": {
            "positive_catalysts": 16, "valuation": 14, "momentum": 16, "business_outlook": 14,
            "sector_strength": 14, "ai_conviction": 12, "historical_success": 14,
        },
    },
    "risk": {
        "v1.0": {
            "macro_risk": 16, "policy_uncertainty": 14, "volatility": 18,
            "geopolitical_risk": 12, "earnings_risk": 14, "liquidity_risk": 12, "historical_downside": 14,
        },
    },
    "ripple_strength": {
        "v1.0": {"ripple_depth": 45, "ripple_width": 45, "entity_breadth": 10},
    },
}

CURRENT_VERSION: dict = {
    "event_impact":    "v1.0",
    "company_impact":  "v1.0",
    "sector_strength": "v1.0",
    "theme_strength":  "v1.0",
    "opportunity":     "v1.0",
    "risk":            "v1.0",
    "ripple_strength": "v1.0",
    "ai_confidence":   "v1.0",   # delegates to confidence_service; versioned for symmetry/discoverability
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Event Impact Score — consumes app.services.feature_extraction.EventFeatures
# ─────────────────────────────────────────────────────────────────────────────

def score_event_impact(features, version: Optional[str] = None) -> ScoreResult:
    """`features` is an EventFeatures (or any object/dict with the same field names)."""
    values = features.__dict__ if hasattr(features, "__dict__") else dict(features)
    score, breakdown, coverage, contributors, formula_version = _compute(
        "event_impact", "Event Impact", values, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute an Event Impact Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown, formula_version,
        )

    reasoning = []
    if values.get("event_magnitude"):
        reasoning.append(f"Event magnitude: {values['event_magnitude']:.0f}/100")
    if values.get("company_count_raw"):
        reasoning.append(f"{values['company_count_raw']} listed companies affected")
    if values.get("sector_count_raw"):
        reasoning.append(f"Spans {values['sector_count_raw']} sector(s)")
    if values.get("historical_similarity") is not None:
        reasoning.append(f"{values['historical_similarity']:.0f}% match to similar historical events")
    if values.get("news_volume_raw"):
        reasoning.append(f"{values['news_volume_raw']} related news articles")
    if values.get("ripple_depth") is not None:
        reasoning.append(f"Ripple reaches {values['ripple_depth']:.0f}/100 depth, {values.get('ripple_width', 0):.0f}/100 width")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Company Impact Score — consumes feature_extraction.CompanyFeatures
# ─────────────────────────────────────────────────────────────────────────────

def score_company_impact(features, version: Optional[str] = None) -> ScoreResult:
    values = features.__dict__ if hasattr(features, "__dict__") else dict(features)
    score, breakdown, coverage, contributors, formula_version = _compute(
        "company_impact", "Company Impact", values, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified company-level signals to compute a Company Impact Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown, formula_version,
        )

    reasoning = []
    if values.get("sector_exposure"):
        reasoning.append(f"Sector exposure match: {values['sector_exposure']:.0f}/100")
    if values.get("institutional_interest"):
        reasoning.append(f"{values['institutional_interest']:.1f}% institutional holding")
    if values.get("historical_sensitivity") is not None:
        reasoning.append(f"Historical sensitivity: {values['historical_sensitivity']:.0f}/100")
    if values.get("ripple_depth") is not None:
        reasoning.append(f"Ripple reaches {values['ripple_depth']:.0f}/100 depth")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sector Strength Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SectorStrengthInputs:
    avg_company_performance: Optional[float] = None
    news_flow:                 Optional[float] = None    # already scaled 0-100 by caller (news count -> signal)
    institutional_flow:          Optional[float] = None
    market_breadth:                Optional[float] = None
    momentum:                        Optional[float] = None
    relative_strength:                 Optional[float] = None
    economic_drivers:                    Optional[float] = None
    historical_trend:                      Optional[float] = None


def score_sector_strength(inp: SectorStrengthInputs, version: Optional[str] = None) -> ScoreResult:
    score, breakdown, coverage, contributors, formula_version = _compute(
        "sector_strength", "Sector Strength", inp.__dict__, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified sector-level signals to compute a Sector Strength Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown, formula_version,
        )

    reasoning = []
    if inp.momentum is not None:
        reasoning.append(f"Momentum: {inp.momentum:.0f}/100")
    if inp.relative_strength is not None:
        reasoning.append(f"Relative strength vs index: {inp.relative_strength:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Theme Strength Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ThemeStrengthInputs:
    related_events:         Optional[float] = None    # already scaled 0-100 by caller
    company_participation:    Optional[float] = None    # already scaled 0-100 by caller
    news_trend:                 Optional[float] = None
    government_support:           Optional[float] = None
    global_trend:                    Optional[float] = None
    historical_momentum:               Optional[float] = None


def score_theme_strength(inp: ThemeStrengthInputs, version: Optional[str] = None) -> ScoreResult:
    score, breakdown, coverage, contributors, formula_version = _compute(
        "theme_strength", "Theme Strength", inp.__dict__, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute a Theme Strength Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown, formula_version,
        )

    reasoning = []
    if inp.government_support:
        reasoning.append(f"Government support signal: {inp.government_support:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Opportunity Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OpportunityInputs:
    positive_catalysts:  Optional[float] = None
    valuation:             Optional[float] = None
    momentum:                Optional[float] = None
    business_outlook:          Optional[float] = None
    sector_strength:              Optional[float] = None   # feed from score_sector_strength(...).score
    ai_conviction:                  Optional[float] = None   # must come from confidence_service, not LLM self-rating
    historical_success:               Optional[float] = None


def score_opportunity(inp: OpportunityInputs, version: Optional[str] = None) -> ScoreResult:
    score, breakdown, coverage, contributors, formula_version = _compute(
        "opportunity", "Opportunity", inp.__dict__, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute an Opportunity Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown, formula_version,
        )

    reasoning = []
    if inp.positive_catalysts is not None:
        reasoning.append(f"Positive catalyst strength: {inp.positive_catalysts:.0f}/100")
    if inp.historical_success is not None:
        reasoning.append(f"Historical success rate on similar setups: {inp.historical_success:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Risk Score
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskInputs:
    macro_risk:            Optional[float] = None
    policy_uncertainty:      Optional[float] = None
    volatility:                Optional[float] = None
    geopolitical_risk:           Optional[float] = None
    earnings_risk:                 Optional[float] = None
    liquidity_risk:                   Optional[float] = None
    historical_downside:                Optional[float] = None


def score_risk(inp: RiskInputs, version: Optional[str] = None) -> ScoreResult:
    score, breakdown, coverage, contributors, formula_version = _compute(
        "risk", "Risk", inp.__dict__, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient(
            "Not enough verified signals to compute a Risk Score "
            f"(only {round(coverage * 100)}% of the formula had real data).",
            breakdown, formula_version,
        )

    reasoning = []
    if inp.volatility is not None:
        reasoning.append(f"Volatility signal: {inp.volatility:.0f}/100")
    if inp.historical_downside is not None:
        reasoning.append(f"Historical downside precedent: {inp.historical_downside:.0f}/100")
    if not reasoning:
        reasoning.append(f"Composite of {len(breakdown)} verified signal(s)")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )


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

    formula_version = f"AI Confidence {CURRENT_VERSION['ai_confidence']}"

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
        return _insufficient("No verifiable evidence signals were available to assess confidence.", version=formula_version)

    result = calculate_confidence(factors)
    breakdown = {k: v for k, v in result.breakdown.items() if k != "total"}

    contributors = sorted(
        (
            {"label": _label(k), "value": v, "signed_contribution": v, "direction": "up" if v >= 0 else "down"}
            for k, v in breakdown.items() if v
        ),
        key=lambda c: abs(c["signed_contribution"]), reverse=True,
    )

    return ScoreResult(
        score=result.total_score,
        confidence=result.total_score,   # for this model score and confidence are the same measure by definition
        breakdown=breakdown,
        top_contributors=contributors,
        reasoning=result.reasons,
        version=formula_version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. Ripple Strength Score — consumes feature_extraction.extract_ripple_features()
# ─────────────────────────────────────────────────────────────────────────────

def score_ripple_strength(ripple_features: dict, version: Optional[str] = None) -> ScoreResult:
    """`ripple_features` is the dict returned by feature_extraction.extract_ripple_features()."""
    entities = ripple_features.get("entities_reached") or 0
    entity_breadth = _clamp(entities * 8) if entities else None

    values = {
        "ripple_depth": ripple_features.get("ripple_depth"),
        "ripple_width": ripple_features.get("ripple_width"),
        "entity_breadth": entity_breadth,
    }
    score, breakdown, coverage, contributors, formula_version = _compute(
        "ripple_strength", "Ripple Strength", values, version
    )

    if score is None or coverage < _MIN_COVERAGE:
        return _insufficient("No graph connections found to compute a Ripple Strength Score.", breakdown, formula_version)

    reasoning = [
        f"Ripples reach {entities} connected entities",
        f"Deepest chain: {ripple_features.get('max_depth_hops', 0)} hops",
    ]
    types = ripple_features.get("entity_types") or []
    if types:
        reasoning.append(f"Spans {len(types)} entity type(s): {', '.join(types)}")

    return ScoreResult(
        score=score, confidence=round(coverage * 100, 1), breakdown=breakdown,
        top_contributors=contributors, reasoning=reasoning, version=formula_version,
    )

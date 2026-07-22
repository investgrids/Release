"""
Market Intelligence Scoring Engine — Phase 2.

Computes the 8 named scores (Opportunity, Risk, Driver Strength, Evidence
Strength, Theme Strength, Sector Momentum, Market Confidence, Catalyst)
purely from real, already-fetched signals. No LLM call happens anywhere in
this file. Every function is pure and documented with exactly which real
inputs feed it — matching the house style already established by
confidence_service.py (evidence-based, deterministic, no arbitrary
per-instance numbers).

Where a real scoring engine already exists elsewhere in the codebase, this
module REUSES it rather than computing a second, competing number:
  - Opportunity Score  → app.pipeline.opportunity_generator._score_opportunity
                          (already real: base + event/company/sector counts).
                          Nothing to compute here — see biggest_opportunity
                          .opportunity_score, already threaded through
                          market_intelligence_service.get_market_pulse().
  - Theme Strength     → app.services.intelligence.theme_worker
                          (already real: 0.6×live price move + 0.4×24h news
                          count, recomputed every 10 min). theme_strength()
                          below is a documented passthrough, not a new formula.
  - Market Confidence  → app.services.confidence_service.calculate_confidence
                          (already real, deterministic). market_confidence()
                          below builds real ConfidenceFactors from Market
                          Pulse signals and calls straight through.

The remaining four (Risk, Driver Strength, Evidence Strength, Sector
Momentum, Catalyst — five, not four; Opportunity/Theme/Confidence are the
three reused) are new, and are the actual new work in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime as _datetime


# ── Driver Strength ───────────────────────────────────────────────────────────
# How directly a verified driver explains a stock's move. Base score is set
# by driver_type (see market_intelligence_service._DRIVER_TAGS — corporate
# results/policy are the most direct real evidence, theme membership and
# divergence are explanatory but indirect). The only per-instance adjustment
# is the matched event's own real urgency (0–10, from EventTriage) when the
# driver is event-backed — a real DB value, not invented for this score.
_DRIVER_TYPE_BASE: dict[str, float] = {
    "corporate_results": 90.0,
    "government_policy": 90.0,
    "corporate_news":     70.0,
    "sector_theme":       55.0,
    "divergence":         40.0,
}


def score_driver_strength(driver_type: str, event_urgency: int | None = None) -> float:
    base = _DRIVER_TYPE_BASE.get(driver_type, 50.0)
    if event_urgency is not None:
        base += (event_urgency - 5) * 2  # real triage urgency, ±10 swing
    return round(min(100.0, max(0.0, base)), 1)


# ── Evidence Strength ─────────────────────────────────────────────────────────
# How much independent real corroboration backs a claim — a *count* of
# distinct real signal types (event match, theme match, momentum divergence
# check), not how directly any single one explains the move (that's Driver
# Strength). Zero real signals found = low score, not zero, since "we looked
# and found nothing" is still informative, just weak.
_EVIDENCE_BY_SIGNAL_COUNT = {0: 10.0, 1: 45.0, 2: 72.0}


def score_evidence_strength(verified_driver_count: int) -> float:
    return _EVIDENCE_BY_SIGNAL_COUNT.get(verified_driver_count, 90.0)


# ── Theme Strength ────────────────────────────────────────────────────────────
# Documented passthrough — the real number already exists (Theme Engine,
# theme_worker.py, live every 10 min). Never recompute it here.
def theme_strength(theme: dict) -> float:
    return round(float(theme.get("score") or 0.0), 1)


# ── Sector Momentum ───────────────────────────────────────────────────────────
# Normalizes a sector's real % change (from get_sector_changes(), a live
# sector-ETF quote) onto a 0–100 scale, centered at 50 = flat. ±3.3% maps to
# the 0/100 extremes — sector ETFs rarely move further than that in a single
# session, so this keeps the scale meaningful rather than everything
# clustering near 50. Same real number the frontend already shows as "+X.X%"
# and the Leading/Lagging split in market_intelligence_service — this just
# re-expresses it on a 0–100 scale for comparability with the other scores.
def score_sector_momentum(pct_change: float) -> float:
    return round(min(100.0, max(0.0, 50.0 + pct_change * 15.0)), 1)


# ── Risk Score ─────────────────────────────────────────────────────────────────
# Market-wide, built from three real signals: India VIX level (real live
# quote), count of real high-urgency bearish triaged events in the last 24h,
# and the real magnitude of declining sectors. VIX regime bands are the
# exact ones confidence_service.py already uses, for consistency across the
# codebase rather than a second set of invented thresholds.
def _vix_component(vix: float) -> float:
    if vix <= 0:  return 15.0   # no real reading — treat as unknown, not "calm"
    if vix < 12:  return 10.0
    if vix < 18:  return 25.0
    if vix < 25:  return 45.0
    return 65.0


def score_risk(
    vix: float,
    bearish_high_urgency_count: int,
    lagging_sectors: list[dict],
    entity_bearish_event_count: int = 0,
) -> float:
    """
    entity_bearish_event_count is optional and defaults to 0 (fully
    backward-compatible with market_pulse, which has no single named
    entity to score against). Without it, this formula is entirely
    market-wide — VIX, market-wide bearish events, lagging sectors — so two
    completely different stocks asked about in the same moment get an
    identical risk score. When a caller has a real per-entity bearish-event
    count (real DB/news rows keyword-matched to that specific company, not
    invented), pass it here so the score can actually differ between
    entities, capped separately from the market-wide event component so
    one company's news can't swamp the market-level read.
    """
    vix_pts = _vix_component(vix)
    event_pts = min(20.0, bearish_high_urgency_count * 4.0)
    lag_magnitude = sum(
        abs(float(str(s.get("value", "0")).replace("%", "").replace("+", "")))
        for s in lagging_sectors
    )
    sector_pts = min(15.0, lag_magnitude * 3.0)
    entity_pts = min(15.0, entity_bearish_event_count * 5.0)
    return round(min(100.0, vix_pts + event_pts + sector_pts + entity_pts), 1)


# ── Catalyst Score ────────────────────────────────────────────────────────────
# From the real upcoming-calendar (read_upcoming_calendar) — weighted by how
# market-moving the category typically is and how soon it lands. Both the
# category and the date are real DB fields; only the weights themselves are
# a judgment call (documented, not hidden).
_CATALYST_CATEGORY_WEIGHT: dict[str, float] = {
    "monetary policy": 25.0, "rbi": 25.0,
    "results": 20.0, "earnings": 20.0,
    "macro": 18.0,
    "government": 15.0, "policy": 15.0,
    "global": 12.0,
}
_CATALYST_DEFAULT_WEIGHT = 8.0


def _proximity_weight(days_out: int) -> float:
    if days_out <= 3:  return 1.0
    if days_out <= 7:  return 0.7
    if days_out <= 14: return 0.4
    return 0.2


def score_catalysts(calendar_items: list[dict], today: _date | None = None) -> float:
    today = today or _datetime.now().date()
    total = 0.0
    for item in calendar_items[:5]:
        cat = (item.get("category") or "").lower()
        weight = next((w for k, w in _CATALYST_CATEGORY_WEIGHT.items() if k in cat), _CATALYST_DEFAULT_WEIGHT)
        try:
            item_date = _datetime.strptime(item.get("date", ""), "%b %d, %Y").date()
            days_out = max(0, (item_date - today).days)
        except (ValueError, TypeError):
            days_out = 7  # unparseable date — treat as medium-term, not zero
        total += weight * _proximity_weight(days_out)
    return round(min(100.0, total), 1)


# ── Market Confidence ─────────────────────────────────────────────────────────
# Thin wrapper around the already-real confidence_service.calculate_confidence
# — builds real ConfidenceFactors from Market Pulse's own real signals
# instead of a second competing confidence formula.
@dataclass
class MarketConfidenceInputs:
    matched_event_count: int
    movers_confirming_direction: int
    sectors_confirming_direction: int
    macro_aligned: bool
    macro_reason: str
    vix_level: float


def market_confidence(inputs: MarketConfidenceInputs):
    from app.services.confidence_service import ConfidenceFactors, calculate_confidence, _vix_regime
    factors = ConfidenceFactors(
        source_count=inputs.matched_event_count,
        historical_count=0, historical_accuracy=0.0,
        market_confirming=inputs.movers_confirming_direction,
        company_sensitivity="medium",
        sector_confirming=inputs.sectors_confirming_direction,
        macro_aligned=inputs.macro_aligned,
        macro_reason=inputs.macro_reason,
        ai_certainty=5,  # neutral — this runs before any LLM call, no self-rating exists yet
        vix_level=inputs.vix_level,
        volatility_regime=_vix_regime(inputs.vix_level),
    )
    return calculate_confidence(factors)

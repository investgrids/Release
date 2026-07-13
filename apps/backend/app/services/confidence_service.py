"""
Evidence-based confidence scoring engine.

Replaces arbitrary AI-guessed confidence values with a calculated score
derived from 8 observable signals. Produces a level (Low / Medium / High /
Very High) and a list of human-readable bullet points explaining why.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfidenceFactors:
    source_count:        int   = 0      # number of distinct news/event sources
    historical_count:    int   = 0      # similar past events found
    historical_accuracy: float = 0.0   # avg accuracy of those events (0.0–1.0)
    market_confirming:   int   = 0      # sectors/indices already moving in expected direction
    market_move_pct:     float = 0.0   # magnitude of that move (%)
    company_sensitivity: str   = "medium"  # low | medium | high
    sector_confirming:   int   = 0      # sector peers confirming
    macro_aligned:       bool  = False
    macro_reason:        str   = ""
    ai_certainty:        int   = 5      # 1–10 from AI self-rating
    vix_level:           float = 0.0
    volatility_regime:   str   = "normal"  # low | normal | high | very_high


@dataclass
class ConfidenceResult:
    total_score: float          # 0–100
    level:       str            # Low | Medium | High | Very High
    reasons:     list[str]      # bullet points for UI
    explanation: str            # injected into AI prompt
    breakdown:   dict[str, float]


def _vix_regime(vix: float) -> str:
    if vix <= 0:  return "normal"
    if vix < 12:  return "low"
    if vix < 18:  return "normal"
    if vix < 25:  return "high"
    return "very_high"


# Maximum raw score is ~115 (all signals fire at full, VIX bonus included).
# Capped at 100. Thresholds calibrated so a typical high-quality query with
# 5 sources + 4 historical events + macro aligned lands at High (≥ 52).
_THRESHOLDS = [
    (72, "Very High"),
    (52, "High"),
    (30, "Medium"),
    (0,  "Low"),
]


def calculate_confidence(f: ConfidenceFactors) -> ConfidenceResult:
    breakdown: dict[str, float] = {}
    reasons:   list[str]        = []

    # 1 — Source count (0–15)
    _sc      = min(f.source_count, 5)
    src_pts  = [0, 3, 6, 9, 12, 15][_sc]
    breakdown["sources"] = src_pts
    if f.source_count >= 4:
        reasons.append(f"{f.source_count} trusted sources")
    elif f.source_count >= 2:
        reasons.append(f"{f.source_count} news & event sources")

    # 2 — Historical similarity (0–25): count weight (max 10) + accuracy weight (max 15)
    hist_count_pts = min(f.historical_count * 2, 10)
    hist_acc_pts   = round(f.historical_accuracy * 15, 1)
    hist_pts       = hist_count_pts + hist_acc_pts
    breakdown["historical"] = hist_pts
    if f.historical_count >= 3:
        acc_pct = round(f.historical_accuracy * 100)
        reasons.append(f"{f.historical_count} similar historical events (avg {acc_pct}% accuracy)")
    elif f.historical_count > 0:
        reasons.append(f"{f.historical_count} similar historical event{'s' if f.historical_count > 1 else ''} found")

    # 3 — Market confirmation (0–20)
    mkt_base = {0: 0, 1: 8, 2: 14}.get(min(f.market_confirming, 2), 20)
    mkt_pts  = min(mkt_base + (4 if f.market_move_pct >= 0.5 else 0), 20)
    breakdown["market_confirmation"] = mkt_pts
    if f.market_confirming >= 2:
        reasons.append(f"{f.market_confirming} sectors already moving in expected direction")
    elif f.market_confirming == 1:
        reasons.append("Sector already confirming the trend")

    # 4 — Company sensitivity (0–10)
    sens_pts = {"high": 10, "medium": 6, "low": 3}.get(f.company_sensitivity, 0)
    breakdown["company_sensitivity"] = sens_pts

    # 5 — Sector confirmation (0–15)
    sec_pts = {0: 0, 1: 5, 2: 10}.get(min(f.sector_confirming, 2), 15)
    breakdown["sector_confirmation"] = sec_pts
    if f.sector_confirming >= 2:
        reasons.append(f"{f.sector_confirming} sector peers confirming")

    # 6 — Macro alignment (0–15)
    macro_pts = 15 if f.macro_aligned else 0
    breakdown["macro_alignment"] = macro_pts
    if f.macro_aligned:
        tag = f.macro_reason or "Market direction"
        reasons.append(f"{tag} aligns with this analysis")

    # 7 — AI certainty (0–10)
    ai_pts = round((min(max(f.ai_certainty, 1), 10) / 10.0) * 10, 1)
    breakdown["ai_certainty"] = ai_pts

    # 8 — Volatility adjustment (−10 to +5)
    regime  = f.volatility_regime or _vix_regime(f.vix_level)
    vol_adj = {"low": 5, "normal": 0, "high": -5, "very_high": -10}.get(regime, 0)
    breakdown["volatility"] = vol_adj
    if regime == "very_high":
        reasons.append("High market volatility reduces signal reliability")
    elif regime == "high":
        reasons.append("Elevated volatility adds uncertainty")
    elif regime == "low":
        reasons.append("Low-volatility environment — high signal clarity")

    raw   = sum(breakdown.values())
    total = round(min(max(raw, 0), 100), 1)
    breakdown["total"] = total

    level = next(lbl for threshold, lbl in _THRESHOLDS if total >= threshold)

    if not reasons:
        reasons.append(f"Score {total:.0f}/100 based on available signals")

    bullet_lines = "\n".join(f"• {r}" for r in reasons)
    explanation  = (
        f"CONFIDENCE ASSESSMENT: {level} ({total:.0f}/100)\n"
        f"Evidence:\n{bullet_lines}\n"
        f"Cite this confidence level and these evidence points explicitly in your analysis."
    )

    return ConfidenceResult(
        total_score=total,
        level=level,
        reasons=reasons,
        explanation=explanation,
        breakdown=breakdown,
    )

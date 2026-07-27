"""
Post-specialist processing: evidence score + the 6-part confidence
breakdown. Both computed server-side from real signals — never trusted from
raw LLM output (same principle as V2's existing evidence-based confidence).

Reuses V2's `confidence_service.calculate_confidence()` unchanged as the
proven, already-calibrated scoring engine — the user-facing 6-part
breakdown is a *view* over that engine's own internal breakdown dict
(mapped from raw point-scales to 0-100 percentages of each component's own
max), plus one genuinely new signal (data_freshness) confidence_service
doesn't compute today.

Enrichment/graph-build/ripple-chain assembly (_enrich_sync, _build_graph,
_classify_ripple_position, _fetch_chart_sync) are intentionally NOT
duplicated here — pipeline.py imports and calls V2's originals directly,
since that mechanism is untouched and doesn't need a typed wrapper.
"""
from __future__ import annotations

from datetime import datetime, timezone


def compute_evidence_score(evidence) -> dict:
    """1-5 star rating + a checklist of what actually backs the answer —
    both derived from the real EvidenceBundle, never LLM-guessed."""
    checklist = evidence.evidence_checklist()
    backed = sum(1 for v in checklist.values() if v)
    total_categories = len(checklist)
    # Source count also factors in — a checklist category can be "true" from
    # a single thin source; genuine breadth (more sources) should count too.
    source_bonus = min(evidence.source_count, 10) / 10  # 0-1
    coverage = backed / total_categories if total_categories else 0
    combined = (coverage * 0.7) + (source_bonus * 0.3)
    stars = max(1, min(5, round(combined * 5)))
    return {"stars": stars, "checklist": checklist, "source_count": evidence.source_count}


def _freshness_score(evidence) -> float:
    """0-100: how recent is the underlying evidence. Mirrors the benchmark
    runner's own score_freshness() logic (relative "Nm ago" strings or ISO
    timestamps), kept independent since this runs server-side per-request,
    not as a post-hoc benchmark scoring pass."""
    import re
    now = datetime.now(timezone.utc)
    ages_min: list[float] = []
    for item in (evidence.news or []) + (evidence.events or []):
        ts = item.get("published_at") or item.get("date")
        if not ts or not isinstance(ts, str):
            continue
        rel = re.match(r"(\d+)\s*([mhd])\s*ago", ts.strip().lower())
        if rel:
            n, unit = int(rel.group(1)), rel.group(2)
            ages_min.append(n * (1 if unit == "m" else 60 if unit == "h" else 1440))
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages_min.append(max(0.0, (now - dt).total_seconds() / 60))
        except ValueError:
            continue
    if not ages_min:
        return 50.0  # no timestamped evidence at all — neutral, not zero (absence isn't staleness)
    newest = min(ages_min)
    # Full marks under 1 hour old, decaying to a floor of 20 by 7 days.
    if newest <= 60:
        return 100.0
    if newest >= 10080:  # 7 days
        return 20.0
    return round(100 - (newest - 60) / (10080 - 60) * 80, 1)


def compute_confidence_breakdown(evidence, parsed: dict, mie_state: dict | None = None) -> dict:
    """The 6-part breakdown: evidence_quality / market_confirmation /
    historical_similarity / data_freshness / reasoning_confidence /
    final_confidence. final_confidence is V2's own calculate_confidence()
    total_score verbatim — the other 5 are a readable view over the same
    engine's internal signals (see module docstring)."""
    from app.services.confidence_service import ConfidenceFactors, calculate_confidence

    mie_state = mie_state or {}
    signals = mie_state.get("signals", {})
    macro_aligned = False
    macro_reason = ""
    sentiment = (parsed.get("sentiment") or "neutral").lower()
    mie_dir = signals.get("direction", "")
    if (mie_dir == "up" and sentiment == "bullish") or (mie_dir == "down" and sentiment == "bearish"):
        macro_aligned = True
        macro_reason = signals.get("top_theme", "")

    hist_accuracy = (
        sum(h.get("confidence", 80) for h in evidence.similar_historical) / (100.0 * len(evidence.similar_historical))
        if evidence.similar_historical else 0.0
    )
    vix = float(evidence.vix_level or 0)
    vix_regime = "very_high" if vix > 25 else "high" if vix > 18 else "low" if 0 < vix < 12 else "normal"

    factors = ConfidenceFactors(
        source_count=evidence.source_count,
        historical_count=len(evidence.similar_historical),
        historical_accuracy=hist_accuracy,
        macro_aligned=macro_aligned,
        macro_reason=macro_reason,
        ai_certainty=int(parsed.get("confidence_self_rating", 5) or 5),
        vix_level=vix,
        volatility_regime=vix_regime,
    )
    result = calculate_confidence(factors)
    bd = result.breakdown

    # Normalize each raw point-scale to a 0-100 % of its own max (see
    # confidence_service.py's own comments for these maxes: sources 15,
    # historical 25, market_confirmation 20, company_sensitivity 10,
    # sector_confirmation 15, ai_certainty 10).
    evidence_quality = round(
        min(100, (bd.get("sources", 0) + bd.get("company_sensitivity", 0) + bd.get("sector_confirmation", 0)) / 40 * 100), 1
    )
    market_confirmation = round(min(100, bd.get("market_confirmation", 0) / 20 * 100), 1)
    historical_similarity = round(min(100, bd.get("historical", 0) / 25 * 100), 1)
    reasoning_confidence = round(min(100, bd.get("ai_certainty", 0) / 10 * 100), 1)
    data_freshness = _freshness_score(evidence)

    return {
        "evidence_quality": evidence_quality,
        "market_confirmation": market_confirmation,
        "historical_similarity": historical_similarity,
        "data_freshness": data_freshness,
        "reasoning_confidence": reasoning_confidence,
        "final_confidence": result.total_score,
        "level": result.level,
        "reasons": result.reasons,
    }

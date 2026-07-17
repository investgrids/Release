"""
Decision Intelligence Engine — the deterministic core. No LLM call happens
here. Every field on `DecisionResult` is computed from fused evidence and
ranked drivers; the answer template later hands this struct to the LLM as
fact to elaborate on, not as something to invent.

Phase 2 wires real market/macro/historical/ripple signals into
`ConfidenceFactors` from whichever retrievers the intent actually
requested — Phase 1 could only ever report these at zero since those
retrievers didn't exist. `missing_data` is now computed per-request: a
signal is only flagged missing if the intent's own retriever list didn't
include it (or included it but it degraded this run), not from a blanket
Phase-1-era hardcoded list.
"""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, DriverScore, Evidence
from app.services.confidence_service import ConfidenceFactors, calculate_confidence

# Maps a "signal category" a query might need to the retriever key(s) that
# supply it, and the human-readable note used when that category is absent.
_SIGNAL_SOURCES: dict[str, tuple[str, ...]] = {
    "market_data": ("market",),
    "ripple_analysis": ("ripple", "intelligence_graph"),
    "historical_precedent": ("historical_similarity",),
    "macro_data": ("macro",),
}
_SIGNAL_NOTES: dict[str, str] = {
    "market_data": "live price/sector-move confirmation",
    "ripple_analysis": "cross-entity impact propagation",
    "historical_precedent": "similar past events",
    "macro_data": "VIX/rates/currency context",
}


def _mood_from_evidence(evidence: list[Evidence], drivers: list[DriverScore]) -> str:
    mood_ev = next((e for e in evidence if e.id == "intelligence_publishing:market_mood"), None)
    if mood_ev is not None:
        return str(mood_ev.raw.get("mood", "Uncertain"))
    tailwinds = sum(1 for d in drivers if d.direction == "tailwind")
    headwinds = sum(1 for d in drivers if d.direction == "headwind")
    if tailwinds > headwinds * 1.5:
        return "Bullish"
    if headwinds > tailwinds * 1.5:
        return "Bearish"
    return "Mixed"


def _verdict_from_drivers(drivers: list[DriverScore], mood: str, decision_profile: str) -> str | None:
    if decision_profile != "verdict":
        return None
    tailwind_score = sum(d.score for d in drivers if d.direction == "tailwind")
    headwind_score = sum(d.score for d in drivers if d.direction == "headwind")
    if tailwind_score == 0 and headwind_score == 0:
        return "Neutral — Insufficient Evidence"
    if tailwind_score > headwind_score * 1.4:
        return "Positive Bias"
    if headwind_score > tailwind_score * 1.4:
        return "Cautious"
    return "Mixed — Balanced Signals"


def _risk_level(confidence_level: str, drivers: list[DriverScore]) -> str:
    mixed_in_top3 = any(d.direction == "mixed" for d in drivers[:3])
    if confidence_level == "Low" or mixed_in_top3:
        return "High"
    if confidence_level == "Medium":
        return "Medium"
    tailwind_dominant = sum(1 for d in drivers if d.direction == "tailwind") > sum(
        1 for d in drivers if d.direction == "headwind"
    )
    return "Low" if tailwind_dominant else "Medium"


def _horizon_for(decision_profile: str) -> str:
    return "3-6 Months" if decision_profile == "verdict" else "Immediate / Near-Term"


def _opportunities_and_risks(drivers: list[DriverScore]) -> tuple[list[dict], list[dict]]:
    opportunities = [
        {"label": d.label, "score": d.score, "why": f"{d.label} is a tailwind (score {d.score}/100)"}
        for d in drivers if d.direction == "tailwind"
    ][:5]
    risks = [
        {"label": d.label, "score": d.score, "why": f"{d.label} is a headwind (score {d.score}/100)"}
        for d in drivers if d.direction == "headwind"
    ][:5]
    return opportunities, risks


def _beneficiaries_and_losers(evidence: list[Evidence]) -> tuple[list[str], list[str]]:
    entity_scores: dict[str, tuple[float, str]] = {}
    for e in evidence:
        if not e.entity or e.polarity not in ("positive", "negative"):
            continue
        score = e.magnitude * e.confidence
        if e.entity not in entity_scores or score > entity_scores[e.entity][0]:
            entity_scores[e.entity] = (score, e.polarity)

    beneficiaries = sorted(
        (ent for ent, (_, pol) in entity_scores.items() if pol == "positive"),
        key=lambda ent: entity_scores[ent][0], reverse=True,
    )[:5]
    losers = sorted(
        (ent for ent, (_, pol) in entity_scores.items() if pol == "negative"),
        key=lambda ent: entity_scores[ent][0], reverse=True,
    )[:5]
    return beneficiaries, losers


def _market_factors(evidence: list[Evidence], mood: str) -> tuple[int, float, int]:
    """Returns (market_confirming, market_move_pct, sector_confirming)."""
    market_ev = [e for e in evidence if e.source == "market"]
    if not market_ev:
        return 0, 0.0, 0
    expected_positive = mood.lower() not in ("bearish", "cautious bear", "panic")
    confirming = [
        e for e in market_ev
        if (e.polarity == "positive") == expected_positive and e.polarity in ("positive", "negative")
    ]
    sector_confirming = sum(1 for e in confirming if e.id.startswith("market:sector:"))
    index_confirming = sum(1 for e in confirming if e.id.startswith("market:index:"))
    market_move_pct = max((e.magnitude * 3.0 for e in market_ev), default=0.0)   # magnitude was scaled by /3.0 at retrieval
    return index_confirming, round(market_move_pct, 2), sector_confirming


def _macro_factors(evidence: list[Evidence], mood: str) -> tuple[bool, str, float, str]:
    """Returns (macro_aligned, macro_reason, vix_level, volatility_regime)."""
    macro_ev = next((e for e in evidence if e.id == "macro:india_vix"), None)
    if macro_ev is None:
        return False, "", 0.0, "normal"
    vix_level = float(macro_ev.raw.get("vix", 0) or 0)
    regime = str(macro_ev.raw.get("regime", "normal"))
    expected_negative_mood = mood.lower() in ("bearish", "cautious bear", "panic")
    macro_aligned = (macro_ev.polarity == "negative") == expected_negative_mood
    macro_reason = f"India VIX ({vix_level:.1f}, {regime.replace('_', ' ')})" if macro_aligned else ""
    return macro_aligned, macro_reason, vix_level, regime


def _historical_factors(evidence: list[Evidence]) -> tuple[int, float]:
    """Returns (historical_count, historical_accuracy)."""
    hist_ev = [e for e in evidence if e.source == "historical_similarity"]
    if not hist_ev:
        return 0, 0.0
    avg_confidence = sum(e.confidence for e in hist_ev) / len(hist_ev)
    return len(hist_ev), round(avg_confidence, 2)


def _historical_probability(evidence: list[Evidence]) -> dict | None:
    hist_ev = [e for e in evidence if e.source == "historical_similarity"]
    quant_ev = [e for e in evidence if e.source == "quant_signal"]
    if not hist_ev and not quant_ev:
        return None
    return {
        "available": True,
        "similar_events_found": len(hist_ev),
        "similar_events": [{"claim": e.claim, "confidence": e.confidence} for e in hist_ev[:5]],
        "calibration_signals": [{"claim": e.claim} for e in quant_ev],
    }


def _ripple_reach(evidence: list[Evidence]) -> dict | None:
    ripple_ev = [e for e in evidence if e.source == "ripple"]
    if not ripple_ev:
        return None
    return {
        "available": True,
        "total_impacted": len(ripple_ev),
        "impacts": [
            {"entity": e.entity, "claim": e.claim, "polarity": e.polarity, "weight": round(e.magnitude, 2)}
            for e in sorted(ripple_ev, key=lambda e: e.magnitude, reverse=True)[:8]
        ],
    }


def build_decision(
    evidence: list[Evidence],
    drivers: list[DriverScore],
    decision_profile: str,
    conflicting_entities: list[str],
    degraded_retrievers: list[str],
    requested_retrievers: list[str],
) -> DecisionResult:
    source_count = len({e.source for e in evidence})
    avg_evidence_confidence = (
        sum(e.confidence for e in evidence) / len(evidence) if evidence else 0.0
    )
    ai_certainty = round(min(max(avg_evidence_confidence * 10, 1), 10))

    mood = _mood_from_evidence(evidence, drivers)
    market_confirming, market_move_pct, sector_confirming = _market_factors(evidence, mood)
    macro_aligned, macro_reason, vix_level, volatility_regime = _macro_factors(evidence, mood)
    historical_count, historical_accuracy = _historical_factors(evidence)

    factors = ConfidenceFactors(
        source_count=source_count,
        historical_count=historical_count,
        historical_accuracy=historical_accuracy,
        market_confirming=market_confirming,
        market_move_pct=market_move_pct,
        company_sensitivity="medium",
        sector_confirming=sector_confirming,
        macro_aligned=macro_aligned,
        macro_reason=macro_reason,
        ai_certainty=ai_certainty,
        vix_level=vix_level,
        volatility_regime=volatility_regime,
    )
    confidence = calculate_confidence(factors)

    verdict = _verdict_from_drivers(drivers, mood, decision_profile)
    risk_level = _risk_level(confidence.level, drivers)
    horizon = _horizon_for(decision_profile)
    opportunities, risks = _opportunities_and_risks(drivers)
    beneficiaries, losers = _beneficiaries_and_losers(evidence)

    missing_data: list[str] = []
    for signal, source_keys in _SIGNAL_SOURCES.items():
        requested = any(k in requested_retrievers for k in source_keys)
        have_evidence = any(e.source in source_keys for e in evidence)
        if not requested:
            missing_data.append(f"{signal} — not applicable to this question's intent")
        elif not have_evidence:
            missing_data.append(f"{signal} — {_SIGNAL_NOTES[signal]} unavailable this run")
    if conflicting_entities:
        missing_data.append(
            f"conflicting signals on: {', '.join(conflicting_entities[:5])} — sources disagree, confidence dampened"
        )
    if degraded_retrievers:
        missing_data.append(f"retrievers unavailable this run: {', '.join(degraded_retrievers)}")
    if not evidence:
        missing_data.append("no evidence retrieved for this query — answer will be low-confidence")

    return DecisionResult(
        verdict=verdict,
        confidence=confidence,
        risk_level=risk_level,
        horizon=horizon,
        mood=mood,
        drivers=drivers,
        opportunities=opportunities,
        risks=risks,
        historical_probability=_historical_probability(evidence),
        ripple_reach=_ripple_reach(evidence),
        beneficiaries=beneficiaries,
        losers=losers,
        missing_data=missing_data,
    )

"""
Market Intelligence Service — single source of real, verified "what's moving
and why" market data, now scored by the Phase 2 Market Intelligence Scoring
Engine (market_scoring_engine.py).

Nothing in this module is AI-generated. Every field is either a live
market-data fetch (yfinance-backed, via app.services.market_data), a real
signal already computed elsewhere (theme scores from the Theme Engine,
triaged events from the Intelligence Priority Queue, opportunity scores from
the Opportunity Engine), or a deterministic score computed from those real
inputs by market_scoring_engine.py — this module's only job is to assemble
and cross-reference them.

AI explanation is a separate, downstream step (see ai_search_service.py's
market_pulse prompt) that is only ever allowed to describe what is returned
here, never to choose or alter it. Any page that needs to answer "which
stocks did well and why" / "what's the best sector right now" should call
get_market_pulse() instead of re-deriving this independently.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog

from app.services.market_scoring_engine import (
    score_driver_strength, score_evidence_strength, theme_strength,
    score_sector_momentum, score_risk, score_catalysts,
    market_confidence, MarketConfidenceInputs,
)

log = structlog.get_logger(__name__)

_TOP_N_SECTORS = 4
_TOP_N_MOVERS = 6

# ── Verified-driver classifier ────────────────────────────────────────────────
# Deterministic tagging of a REAL matched headline — this never invents the
# event, it only labels what kind of real event it is (driver_type) and how
# directly it explains a price move (confidence tier), so the UI can show a
# checkmark chip instead of a wall of prose. Order matters: first match wins,
# most specific/highest-confidence patterns first.
_DRIVER_TAGS: list[tuple[re.Pattern, str, str, str]] = [
    # pattern, label, driver_type, confidence
    (re.compile(r"\b(miss(?:es|ed)?|declin\w*|falls?|drop\w*|weak(?:er)?)\b.{0,25}\b(results?|profit|revenue|earnings|pat)\b", re.I),
     "Weak Results", "corporate_results", "High"),
    (re.compile(r"\b(results?|profit|revenue|earnings|q[1-4]|pat)\b", re.I),
     "Strong Results", "corporate_results", "High"),
    (re.compile(r"\b(order|contract|win[s]?|bags?|deal)\b", re.I),
     "New Order / Contract Win", "corporate_news", "High"),
    (re.compile(r"\b(approv\w*|licen[cs]e[ds]?|clearance|greenlit|nod from)\b", re.I),
     "Regulatory Approval", "government_policy", "High"),
    (re.compile(r"\b(probe|fraud|investigat\w*|scrutiny|penalt\w*|fine[ds]?)\b", re.I),
     "Regulatory Scrutiny", "government_policy", "High"),
    (re.compile(r"\b(acqui\w*|merger|stake|buyout)\b", re.I),
     "M&A Activity", "corporate_news", "Medium"),
    (re.compile(r"\b(launch\w*|unveil\w*|new product)\b", re.I),
     "Product Launch", "corporate_news", "Medium"),
    (re.compile(r"\b(upgrad\w*|raises? target|buy rating)\b", re.I),
     "Analyst Upgrade", "corporate_news", "Medium"),
    (re.compile(r"\b(downgrad\w*|cuts? target|sell rating)\b", re.I),
     "Analyst Downgrade", "corporate_news", "Medium"),
    (re.compile(r"\b(resign\w*|steps? down|quits?)\b", re.I),
     "Management Change", "corporate_news", "Medium"),
]


def _classify_driver(headline: str) -> tuple[str, str, str]:
    """Returns (label, driver_type, confidence_tier). Falls back to a generic
    but still real "Related News" tag when no specific keyword matches."""
    for pattern, label, driver_type, confidence in _DRIVER_TAGS:
        if pattern.search(headline or ""):
            return label, driver_type, confidence
    return "Related News", "corporate_news", "Medium"


def _verified_drivers_for(symbol: str, change_pct: float, themes: list[dict], events: list[dict]) -> list[dict]:
    """
    Real, checkable signals behind a stock's move today — never AI-invented.
    Priority order: corporate results/news → government policy (both from
    real triaged events) → sector theme membership → momentum divergence.
    Each driver now carries a real driver_strength (0-100, from
    market_scoring_engine.score_driver_strength) alongside the qualitative
    confidence_tier. Returns [] when nothing real was found; callers must
    render that as "no verified driver identified," never paper over it.
    """
    drivers: list[dict] = []
    sym_upper = symbol.upper()

    # 1) Real triaged events mentioning this ticker (results/news/policy —
    #    the top of the priority waterfall, since these are the most direct
    #    and specific real evidence available).
    for e in events:
        tickers = [t.upper() for t in (e.get("tickers") or [])]
        if sym_upper not in tickers:
            continue
        headline = e.get("one_liner") or e.get("headline") or ""
        label, driver_type, confidence = _classify_driver(headline)
        drivers.append({
            "driver": label, "driver_type": driver_type, "confidence_tier": confidence,
            "evidence": headline, "related_event_ids": [e.get("id")] if e.get("id") else [],
            "confidence_score": None,  # Reserved: not the same as driver_strength — see market_scoring_engine docstring.
            "driver_strength": score_driver_strength(driver_type, e.get("urgency")),
        })

    # 2) Theme / sector momentum membership (Theme Engine — real, 10-min
    #    live score) — lower priority than a direct event match, since it
    #    explains sector-wide drift, not this specific stock's move.
    for t in themes:
        top_stocks = t.get("top_stocks") or []
        match = next((s for s in top_stocks if (s.get("sym") or "").upper() == sym_upper), None)
        if not match:
            continue
        momentum = (t.get("momentum") or "stable").lower()
        drivers.append({
            "driver": f"Sector Momentum — {t.get('theme', 'Unknown')}",
            "driver_type": "sector_theme", "confidence_tier": "Medium",
            "evidence": f"{t.get('theme', 'This sector')} theme is {momentum} (score {round(t.get('score') or 0)}/100).",
            "related_event_ids": [], "confidence_score": None,
            "driver_strength": score_driver_strength("sector_theme"),
            "theme_strength": theme_strength(t),
        })
        # A stock moving opposite to its own theme's momentum is a real,
        # checkable divergence signal — explanatory, not a primary cause.
        stock_up = change_pct > 0
        if (stock_up and momentum == "falling") or (not stock_up and momentum == "rising"):
            drivers.append({
                "driver": "Stock-Specific Move", "driver_type": "divergence", "confidence_tier": "Medium",
                "evidence": f"{symbol} is moving against its own sector's {momentum} momentum — likely idiosyncratic, not sector-wide.",
                "related_event_ids": [], "confidence_score": None,
                "driver_strength": score_driver_strength("divergence"),
            })
        break

    return drivers[:4]


def _pct(sector: dict) -> float:
    try:
        return float((sector.get("value") or "0").replace("%", "").replace("+", ""))
    except (ValueError, TypeError):
        return 0.0


async def get_market_pulse() -> dict:
    """
    Real-data-first market pulse: status, indices, sector leaders/laggards
    (each with a real 0-100 momentum score), top movers (each with verified
    drivers + evidence strength attached), the one real opportunity/risk
    already computed elsewhere in the app, market-wide Risk Score and Market
    Confidence, a Catalyst Score from the real upcoming calendar, and what's
    next. No LLM call happens in this function — it is pure assembly,
    cross-referencing, and deterministic scoring of already-real signals.
    """
    from app.services.market_data import (
        get_market_status, get_extended_indices, get_sector_changes, get_top_movers,
    )
    from app.services.intelligence.engine import (
        get_intelligence_state, read_top_events, read_upcoming_calendar,
    )

    status = get_market_status()
    indices, sectors, movers, mie, events, watch_next = await asyncio.gather(
        get_extended_indices(),
        get_sector_changes(),
        get_top_movers(),
        get_intelligence_state(),
        read_top_events(limit=60, min_urgency=4, hours=24),
        read_upcoming_calendar(limit=4),
        return_exceptions=True,
    )
    indices    = indices if isinstance(indices, list) else []
    sectors    = sectors if isinstance(sectors, list) else []
    movers     = movers if isinstance(movers, dict) else {}
    mie        = mie if isinstance(mie, dict) else {}
    events     = events if isinstance(events, list) else []
    watch_next = watch_next if isinstance(watch_next, list) else []

    themes  = mie.get("themes") or []
    signals = mie.get("signals") or {}
    direction = (signals.get("direction") or "sideways").lower()

    sectors_sorted  = sorted(sectors, key=_pct, reverse=True)

    def _with_momentum(s: dict) -> dict:
        return {**s, "momentum_score": score_sector_momentum(_pct(s))}

    leading_sectors = [_with_momentum(s) for s in sectors_sorted[:_TOP_N_SECTORS]]
    lagging_raw     = sectors_sorted[-_TOP_N_SECTORS:] if len(sectors_sorted) > _TOP_N_SECTORS else []
    lagging_sectors = [_with_momentum(s) for s in reversed(lagging_raw)]

    def _enrich(mover: dict) -> dict:
        try:
            change_pct = float(str(mover.get("value", "0")).replace("%", "").replace("+", ""))
        except (ValueError, TypeError):
            change_pct = 0.0
        drivers = _verified_drivers_for(mover.get("ticker", ""), change_pct, themes, events)
        return {
            **mover,
            "change_pct": change_pct,
            "verified_drivers": drivers,
            "evidence_strength": score_evidence_strength(len(drivers)),
        }

    top_gainers = [_enrich(m) for m in (movers.get("gainers") or [])[:_TOP_N_MOVERS]]
    top_losers  = [_enrich(m) for m in (movers.get("losers")  or [])[:_TOP_N_MOVERS]]

    # ── Market-wide scores ──────────────────────────────────────────────────
    # vix_quote["value"] is the real VIX *level* (e.g. "12.56"), not a %
    # change — use that directly; "pct" on the VIX quote is its own daily
    # % move, not the level score_risk() needs.
    vix_quote = next((i for i in indices if "VIX" in i.get("name", "").upper()), None)
    try:
        vix_level = float(str(vix_quote.get("value", "0")).replace(",", "")) if vix_quote else 0.0
    except (ValueError, TypeError):
        vix_level = 0.0

    # Named selection, not a positional slice — India VIX is real risk
    # context that belongs in the summary and must not get silently dropped
    # depending on dict ordering.
    _WANT_INDICES = ("NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX")
    display_indices = [i for name in _WANT_INDICES for i in indices if i.get("name") == name] or indices[:4]

    bearish_high_urgency = sum(
        1 for e in events if (e.get("sentiment") == "bearish" and (e.get("urgency") or 0) >= 7)
    )
    risk_score = score_risk(vix_level, bearish_high_urgency, lagging_sectors)

    movers_up = sum(1 for m in top_gainers + top_losers if m.get("change_pct", 0) > 0)
    movers_down = len(top_gainers) + len(top_losers) - movers_up
    movers_confirming = movers_up if direction == "up" else movers_down if direction == "down" else 0
    sectors_confirming = len(leading_sectors) if direction == "up" else len(lagging_sectors) if direction == "down" else 0
    matched_event_count = sum(
        1 for m in (top_gainers + top_losers) for d in m["verified_drivers"] if d.get("related_event_ids")
    )
    macro_aligned = (direction in ("up", "down")) and (
        (direction == "up" and movers_up >= movers_down) or (direction == "down" and movers_down > movers_up)
    )
    conf_result = market_confidence(MarketConfidenceInputs(
        matched_event_count=matched_event_count,
        movers_confirming_direction=movers_confirming,
        sectors_confirming_direction=sectors_confirming,
        macro_aligned=macro_aligned,
        macro_reason=f"Overall market direction ({direction})" if macro_aligned else "",
        vix_level=vix_level,
    ))

    catalyst_score = score_catalysts(watch_next)

    biggest_opportunity = mie.get("biggest_opportunity")

    result = {
        "generated_at":       mie.get("generated_at"),
        "market_status":      status,
        "indices":            display_indices,
        "market_mood":        signals.get("mood"),
        "market_direction":   signals.get("direction"),
        "leading_sectors":    leading_sectors,
        "lagging_sectors":    lagging_sectors,
        "top_gainers":        top_gainers,
        "top_losers":         top_losers,
        "most_active":        movers.get("active") or [],
        "biggest_opportunity": biggest_opportunity,
        "biggest_risk":       mie.get("biggest_risk"),
        "what_to_watch_next": watch_next,
        # ── Phase 2: Market Intelligence Scoring Engine ─────────────────────
        # opportunity_score and theme_strength are NOT computed here — they're
        # real numbers already produced by the Opportunity Engine and Theme
        # Engine respectively (see biggest_opportunity.opportunity_score, and
        # each sector-theme verified_driver's theme_strength). Only risk,
        # market confidence, and catalysts are new computations, both listed
        # here at market level for convenience.
        "scores": {
            "opportunity_score": (biggest_opportunity or {}).get("opportunity_score"),
            "risk_score": risk_score,
            "market_confidence": {
                "score": conf_result.total_score,
                "level": conf_result.level,
                "reasons": conf_result.reasons,
                "breakdown": conf_result.breakdown,
            },
            "catalyst_score": catalyst_score,
        },
    }
    log.info(
        "market_intelligence.pulse_assembled",
        gainers=len(top_gainers), losers=len(top_losers), sectors=len(sectors_sorted),
        risk_score=risk_score, market_confidence=conf_result.total_score, catalyst_score=catalyst_score,
    )
    return result

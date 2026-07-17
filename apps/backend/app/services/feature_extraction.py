"""
Feature Extraction Engine — the only place raw data gets turned into the
named signals the Scoring Engine consumes.

Architecture:

    Raw data (events, news, companies, ripple graph, historical memory)
        |
        v
    Feature Extraction Engine   <-- this file
        |
        v
    Scoring Engine (app/services/scoring_engine.py)
        |
        v
    Ripple Engine / Frontend

scoring_engine.py must never re-derive a signal from raw rows — recency
decay, ripple depth/width, market-cap log-scaling, volume ratios, source
trust tiers all live here instead. This keeps "what does source_quality
mean" defined in exactly one place, and lets every caller (a worker, a
pipeline, an API route) reuse the same extraction instead of each one
approximating its own version of the same signal.

Every function here is pure: given raw values already fetched by the
caller, return named 0-100 (or count/None) features. No DB calls, no
network calls. A feature is None when the underlying raw data wasn't
available — extraction never invents a value to fill the gap; that's
the Scoring Engine's `_weighted_composite` job (redistribute weight
across what's real), not this layer's.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


# ─────────────────────────────────────────────────────────────────────────────
# Shared sub-extractors — reused across event/company/ripple feature sets
# ─────────────────────────────────────────────────────────────────────────────

_HIGH_TRUST_SOURCES = {
    "rbi", "sebi", "pib", "moneycontrol", "economic times", "the economic times",
    "business standard", "livemint", "reuters", "bloomberg", "nse", "bse",
    "government of india", "ministry",
}
_MEDIUM_TRUST_SOURCES = {"cnbc-tv18", "cnbc tv18", "zee business", "financial express", "mint"}


def extract_source_quality(source: Optional[str]) -> Optional[float]:
    """0-100 trust tier for a single source string. None if source unknown."""
    if not source:
        return None
    s = source.strip().lower()
    if any(k in s for k in _HIGH_TRUST_SOURCES):
        return 95.0
    if any(k in s for k in _MEDIUM_TRUST_SOURCES):
        return 75.0
    return 55.0  # real source, just not in the high/medium trust vocabulary yet


def extract_recency(published_at: Optional[datetime], now: Optional[datetime] = None) -> Optional[float]:
    """0-100 freshness score with exponential-ish decay. None if no timestamp."""
    if not published_at:
        return None
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
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


def extract_volatility_change(vix_current: Optional[float], vix_baseline: Optional[float]) -> Optional[float]:
    """0-100 magnitude of a VIX move relative to its baseline. None if either side is missing."""
    if vix_current is None or vix_baseline is None or vix_baseline <= 0:
        return None
    pct_change = abs(vix_current - vix_baseline) / vix_baseline * 100.0
    return _clamp(pct_change * 4.0)  # a 25% VIX move saturates the scale


def extract_market_cap_score(market_cap: Optional[float]) -> Optional[float]:
    """Log-scaled 0-100: ~5,000 Cr (small-cap floor) -> ~20, ~15L Cr (largest caps) -> ~100."""
    if not market_cap or market_cap <= 0:
        return None
    lo, hi = math.log10(5_000 * 1e7), math.log10(15_00_000 * 1e7)
    v = math.log10(market_cap)
    return _clamp(((v - lo) / (hi - lo)) * 100)


def extract_volume_signal(volume: Optional[float], avg_volume: Optional[float]) -> Optional[float]:
    """0-100 signal for how far current volume runs above its average. None if either is missing."""
    if volume is None or not avg_volume:
        return None
    return _clamp((volume / avg_volume) * 50.0)


_RIPPLE_MAX_DEPTH = 5


def extract_ripple_features(ripple_result: Optional[dict]) -> dict:
    """
    Turn a raw intelligence_graph_service.ripple_from_node() result into the
    two named ripple signals the Scoring Engine actually consumes:
      ripple_depth — how far downstream the effect reaches (0-100, deeper = higher)
      ripple_width — how many distinct entities/entity-types it touches (0-100)
    Both None if there's no ripple data (e.g. the source entity isn't in the graph).
    """
    if not ripple_result or not ripple_result.get("impacts"):
        return {"ripple_depth": None, "ripple_width": None, "entities_reached": 0}

    impacts = ripple_result["impacts"]
    depths = [i["depth"] for i in impacts]
    node_types = {i["node"]["node_type"] for i in impacts if i.get("node")}

    depth_score = _clamp((max(depths) / _RIPPLE_MAX_DEPTH) * 100) if depths else None
    width_score = _clamp(len(impacts) * 7 + len(node_types) * 10) if impacts else None

    return {
        "ripple_depth": depth_score,
        "ripple_width": width_score,
        "entities_reached": len(impacts),
        "entity_types": sorted(node_types),
        "max_depth_hops": max(depths) if depths else 0,
    }


def extract_historical_features(similar_events: Optional[list], score_field: str = "opportunity_score") -> dict:
    """
    From historical_memory_service.find_similar_events() output, derive two
    distinct signals:
      historical_similarity — how closely the best matches resemble this event (0-100)
      historical_avg_impact — similarity-weighted average magnitude of those
                               past events' outcomes (0-100), i.e. "how big did
                               it get last time", not "have we seen this before"
    """
    events = similar_events or []
    if not events:
        return {"historical_similarity": None, "historical_avg_impact": None, "similar_event_count": 0}

    similarities = [e["similarity"] for e in events if e.get("similarity") is not None]
    weighted = [
        (e["similarity"], e[score_field])
        for e in events
        if e.get("similarity") is not None and e.get(score_field) is not None
    ]

    hist_similarity = round(sum(similarities) / len(similarities), 1) if similarities else None

    hist_avg_impact = None
    total_w = sum(s for s, _ in weighted)
    if weighted and total_w > 0:
        hist_avg_impact = round(sum(s * v for s, v in weighted) / total_w, 1)

    return {
        "historical_similarity": hist_similarity,
        "historical_avg_impact": hist_avg_impact,
        "similar_event_count": len(events),
    }


_GOV_LEVEL_KEYWORDS = {
    100: {"union cabinet", "prime minister", "rbi monetary policy", "union budget"},
    90:  {"rbi", "sebi", "ministry of finance", "finance ministry"},
    75:  {"ministry", "government of india", "regulatory", "ordinance", "cabinet"},
    60:  {"state government", "psu", "public sector"},
}


def extract_government_level(source: Optional[str] = None, government_body: Optional[str] = None) -> Optional[float]:
    """
    0-100 tier of official/government backing behind an event. None when
    neither field indicates any government/regulatory involvement at all
    (i.e. this is genuinely unknown, not "zero government support").
    """
    text = " ".join(t for t in (source, government_body) if t).strip().lower()
    if not text:
        return None
    for level, keywords in sorted(_GOV_LEVEL_KEYWORDS.items(), reverse=True):
        if any(k in text for k in keywords):
            return float(level)
    return None


_MACRO_CATEGORIES = {
    "monetary policy", "union budget", "geopolitical", "global market shock",
    "trade policy", "election", "infrastructure policy",
}

_EVENT_TYPE_SEVERITY = {
    "monetary policy":       92, "union budget":          90,
    "geopolitical":          85, "global market shock":   90,
    "corporate crisis":      75, "regulatory":             70,
    "infrastructure policy": 72, "sectoral policy":        68,
    "commodity shock":       78, "election":               74,
    "trade policy":          70, "earnings":               55,
    "macro":                 50,
}


def extract_event_magnitude(event_type: Optional[str]) -> Optional[float]:
    """0-100 severity of this event *within its own category* (a rate hike is inherently bigger news than an earnings beat)."""
    if not event_type:
        return None
    return _EVENT_TYPE_SEVERITY.get(event_type.strip().lower())


def extract_economic_significance(event_type: Optional[str], government_level: Optional[float]) -> Optional[float]:
    """0-100 signal for how far an event's reach extends into the broader economy (vs. affecting one company/sector)."""
    is_macro = bool(event_type) and event_type.strip().lower() in _MACRO_CATEGORIES
    if not is_macro and government_level is None:
        return None
    base = 70.0 if is_macro else 35.0
    if government_level is not None:
        return round(_clamp((base + government_level) / 2), 1)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# EVENT features — the exact vocabulary the Event Impact model consumes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EventFeatures:
    event_magnitude:       Optional[float] = None   # 0-100, severity within category
    sector_count:           Optional[float] = None     # 0-100, scaled from distinct-sectors-touched count
    company_count:            Optional[float] = None     # 0-100, scaled from distinct-companies-touched count
    market_cap_affected:       Optional[float] = None      # 0-100, log-scaled combined market cap
    government_level:           Optional[float] = None       # 0-100, official/regulatory backing tier
    historical_similarity:       Optional[float] = None        # 0-100, how closely past events match
    historical_avg_impact:        Optional[float] = None         # 0-100, weighted avg outcome of those matches
    news_volume:                   Optional[float] = None           # 0-100, scaled from related-article count
    source_quality:                  Optional[float] = None           # 0-100, avg trust tier of sources
    institutional_mentions:            Optional[float] = None            # 0-100, avg institutional holding % across affected companies
    ripple_depth:                        Optional[float] = None             # 0-100, deepest downstream hop reached
    ripple_width:                          Optional[float] = None              # 0-100, breadth of entities/types touched
    economic_significance:                   Optional[float] = None               # 0-100, economy-wide reach
    recency:                                   Optional[float] = None                # 0-100, freshness decay
    volatility_change:                           Optional[float] = None               # 0-100, VIX move magnitude
    market_breadth:                                Optional[float] = None                # 0-100, % of index confirming direction (kept from Phase 1)

    # Raw counts, kept alongside the scaled signals above purely for
    # human-readable reasoning text ("3 sectors affected") — never fed
    # into the weighted formula themselves (that's what the scaled
    # fields above are for).
    sector_count_raw:  Optional[int] = None
    company_count_raw: Optional[int] = None
    news_volume_raw:   Optional[int] = None


def extract_event_features(
    *,
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    government_body: Optional[str] = None,
    published_at: Optional[datetime] = None,
    companies_affected: Optional[list] = None,   # [{"symbol":, "market_cap":, "held_institutions_pct":}, ...]
    sectors_affected: Optional[list] = None,      # [str, ...]
    news_items: Optional[list] = None,             # [{"source": str}, ...]
    ripple_result: Optional[dict] = None,
    similar_historical_events: Optional[list] = None,
    vix_current: Optional[float] = None,
    vix_baseline: Optional[float] = None,
    market_breadth: Optional[float] = None,
) -> EventFeatures:
    """Turn raw event data into the named 0-100 features score_event_impact() consumes."""
    companies_affected = companies_affected or []
    sectors_affected = sectors_affected or []
    news_items = news_items or []

    gov_level = extract_government_level(source, government_body)
    ripple = extract_ripple_features(ripple_result)
    hist = extract_historical_features(similar_historical_events, score_field="opportunity_score")

    source_qualities = [q for q in (extract_source_quality(n.get("source")) for n in news_items) if q is not None]
    avg_source_quality = round(sum(source_qualities) / len(source_qualities), 1) if source_qualities else None

    total_market_cap = sum(c.get("market_cap") or 0 for c in companies_affected) or None

    inst_pcts = [c["held_institutions_pct"] for c in companies_affected if c.get("held_institutions_pct") is not None]
    avg_inst = round(sum(inst_pcts) / len(inst_pcts), 1) if inst_pcts else None

    sector_n, company_n, news_n = len(sectors_affected), len(companies_affected), len(news_items)

    return EventFeatures(
        event_magnitude=extract_event_magnitude(event_type),
        sector_count=_clamp(sector_n * 22) if sector_n else None,
        company_count=_clamp(company_n * 12) if company_n else None,
        market_cap_affected=extract_market_cap_score(total_market_cap),
        government_level=gov_level,
        historical_similarity=hist["historical_similarity"],
        historical_avg_impact=hist["historical_avg_impact"],
        news_volume=_clamp(news_n * 6) if news_n else None,
        source_quality=avg_source_quality,
        institutional_mentions=avg_inst,
        ripple_depth=ripple["ripple_depth"],
        ripple_width=ripple["ripple_width"],
        economic_significance=extract_economic_significance(event_type, gov_level),
        recency=extract_recency(published_at),
        volatility_change=extract_volatility_change(vix_current, vix_baseline),
        market_breadth=market_breadth,
        sector_count_raw=sector_n or None,
        company_count_raw=company_n or None,
        news_volume_raw=news_n or None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY features — vocabulary the Company Impact model consumes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompanyFeatures:
    revenue_exposure:        Optional[float] = None   # 0-100 — no structured provider yet, always None until sourced
    sector_exposure:           Optional[float] = None    # 0-100, caller-supplied match strength between company sector and event sectors
    news_mentions:                Optional[float] = None    # 0-100, scaled mention count
    market_cap_weight:               Optional[float] = None    # 0-100, log-scaled
    institutional_interest:             Optional[float] = None    # 0-100, real held_institutions %
    order_book_growth:                     Optional[float] = None    # 0-100 — no structured provider yet, always None until sourced
    current_volume:                           Optional[float] = None    # 0-100, volume vs. avg_volume ratio
    historical_sensitivity:                      Optional[float] = None    # 0-100, caller-supplied from historical winners/losers match
    ripple_depth:                                   Optional[float] = None    # 0-100
    ripple_width:                                      Optional[float] = None    # 0-100


def extract_company_features(
    *,
    sector_exposure: Optional[float] = None,
    news_mention_count: Optional[int] = None,
    market_cap: Optional[float] = None,
    institutional_holding_pct: Optional[float] = None,
    volume: Optional[float] = None,
    avg_volume: Optional[float] = None,
    historical_sensitivity: Optional[float] = None,
    ripple_result: Optional[dict] = None,
) -> CompanyFeatures:
    """Turn raw company + market data into the named 0-100 features score_company_impact() consumes."""
    ripple = extract_ripple_features(ripple_result)
    news_score = _clamp(news_mention_count * 10) if news_mention_count is not None else None

    return CompanyFeatures(
        revenue_exposure=None,   # not sourced yet — see module docstring; not fabricated as a guess
        sector_exposure=sector_exposure,
        news_mentions=news_score,
        market_cap_weight=extract_market_cap_score(market_cap),
        institutional_interest=institutional_holding_pct,
        order_book_growth=None,  # not sourced yet — no structured order-book feed exists
        current_volume=extract_volume_signal(volume, avg_volume),
        historical_sensitivity=historical_sensitivity,
        ripple_depth=ripple["ripple_depth"],
        ripple_width=ripple["ripple_width"],
    )

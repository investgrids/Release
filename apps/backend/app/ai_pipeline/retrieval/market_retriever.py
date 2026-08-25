"""
Market Retriever — live index levels, sector moves, and top gainers/losers.
Broad market-condition evidence, not tied to entity resolution; this is
what lets the Decision Intelligence Engine's confidence scoring actually
populate `market_confirming`/`sector_confirming` (both hardcoded to 0 in
Phase 1 since this retriever didn't exist yet).

Warehouse Consumption Phase 2 (2026-08-25, per artifacts/warehouse_
consumption_audit.md): every Evidence item this retriever produced used
to carry `timestamp=None` unconditionally — this file has never actually
known *when* the market state it describes was true-as-of. Wiring in
`get_latest_market_observations()` fixes that for the metrics Warehouse
already tracks reliably, and adds real evidence (global indices,
commodities, macro rates) this retriever had zero visibility into before,
since nothing here previously called anything but `market_data.py`'s
India-focused live fetchers.

Two different integration shapes, deliberately:
- Global indices / commodities / macro rates / India VIX cross-check:
  purely additive — Warehouse is the only source for these today, so a
  missing/stale row just means that one piece of evidence doesn't exist
  this cycle (matches read_service.py's own "never fabricate" contract),
  never a fallback to a live call that doesn't exist for these anyway.
- Sector moves: real fallback. 9 of 54 Warehouse metrics (7 of them
  sector ETFs) are currently failing 100% of the time in production
  (confirmed live, see the audit) — a blind swap would silently regress
  AI Search's sector coverage for those sectors starting today. Instead,
  Warehouse's value is used per-sector only when it's real and current;
  the pre-existing live `get_sector_changes()` call still backstops
  every sector Warehouse doesn't have a good answer for right now, so
  coverage never gets worse than it already was, and improves
  automatically as the 9 broken metrics get fixed (a tracked follow-up,
  not part of this change).
"""
from __future__ import annotations

import re

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.market_data import get_extended_indices, get_sector_changes, get_top_movers
from app.services.warehouse.read_service import get_latest_market_observations

# metric -> (human label, unit suffix for the claim sentence)
_WAREHOUSE_GLOBAL_METRICS = {
    "GLOBAL_DOW_JONES":  "Dow Jones",
    "GLOBAL_SP500":      "S&P 500",
    "GLOBAL_NASDAQ":     "Nasdaq",
    "GLOBAL_FTSE100":    "FTSE 100",
    "GLOBAL_DAX":        "DAX",
    "GLOBAL_CAC40":      "CAC 40",
    "GLOBAL_NIKKEI225":  "Nikkei 225",
    "GLOBAL_HANGSENG":   "Hang Seng",
    "GLOBAL_SHANGHAI":   "Shanghai Composite",
    "GLOBAL_KOSPI":      "KOSPI",
    "US_VIX":            "US VIX",
}
_WAREHOUSE_COMMODITY_METRICS = {
    "COMMODITY_GOLD":     ("Gold", "usd_per_oz"),
    "COMMODITY_SILVER":   ("Silver", "usd_per_oz"),
    "COMMODITY_WTI":      ("WTI Crude", "usd_per_barrel"),
    "BRENT":              ("Brent Crude", "usd_per_barrel"),
}
_WAREHOUSE_MACRO_METRICS = {
    "US_TREASURY_10Y":   "US 10Y Treasury yield",
    "INDIA_10Y_GSEC":    "India 10Y G-Sec yield",
    "USDINR":            "USD/INR",
}
_ALL_WAREHOUSE_ADDITIVE_METRICS = (
    list(_WAREHOUSE_GLOBAL_METRICS) + list(_WAREHOUSE_COMMODITY_METRICS) + list(_WAREHOUSE_MACRO_METRICS)
)

# Sector display name -> Warehouse metric, reusing the exact same
# transform market_observations.py::_capture_sector_performance() uses
# to write these rows (f"SECTOR_{name.upper().replace(' ', '_')}") --
# not a second, independently-maintained mapping.
def _sector_metric(name: str) -> str:
    return f"SECTOR_{name.upper().replace(' ', '_')}"


def _parse_pct(value: str) -> float:
    m = re.search(r"-?\d+\.?\d*", value or "")
    return float(m.group()) if m else 0.0


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    evidence: list[Evidence] = []

    # One real query for everything Warehouse might answer this cycle --
    # the sector fallback below and the purely-additive block both read
    # from this single dict rather than each issuing their own query.
    sector_metrics = [_sector_metric(name) for name in (
        "IT", "Banking", "Pharma", "Auto", "Energy", "FMCG",
        "Infra", "Metal", "Realty", "PSU Bank", "Private Bank", "Media",
    )]
    try:
        warehouse = await get_latest_market_observations(
            ctx.db, metrics=sector_metrics + _ALL_WAREHOUSE_ADDITIVE_METRICS,
        )
    except Exception:
        warehouse = {}

    try:
        indices = await get_extended_indices()
    except Exception:
        indices = []
    for idx in indices[:6]:
        pct = float(idx.get("pct", 0) or 0)
        evidence.append(Evidence(
            id=f"market:index:{idx.get('name')}",
            source="market",
            entity=idx.get("name"),
            claim=f"{idx.get('name')} is at {idx.get('value')} ({idx.get('change')})",
            polarity="positive" if idx.get("positive") else "negative",
            magnitude=min(abs(pct) / 3.0, 1.0),
            confidence=0.7,
            timestamp=None,
            raw=idx,
        ))

    # Sector moves: Warehouse's real, timestamped value when it has a
    # current one; the live fetch (still called, still cached 5min by
    # market_data.py itself) backstops any sector Warehouse doesn't --
    # see this module's own docstring for why a blind swap isn't safe yet.
    sectors_needing_live_fallback: set[str] = set()
    for name in ("IT", "Banking", "Pharma", "Auto", "Energy", "FMCG",
                 "Infra", "Metal", "Realty", "PSU Bank", "Private Bank", "Media"):
        snap = warehouse.get(_sector_metric(name))
        if snap is not None and snap.has_real_value and snap.is_current:
            pct = snap.value
            evidence.append(Evidence(
                id=f"market:sector:{name}",
                source="market",
                entity=name,
                claim=f"{name} sector is {'+' if pct >= 0 else ''}{pct:.2f}% today",
                polarity="positive" if pct >= 0 else "negative",
                magnitude=min(abs(pct) / 3.0, 1.0),
                confidence=0.65,
                timestamp=snap.observation_time,
                raw={"metric": snap.metric, "quality": snap.quality, "source_id": snap.source_id},
            ))
        else:
            sectors_needing_live_fallback.add(name)

    if sectors_needing_live_fallback:
        try:
            sectors = await get_sector_changes()
        except Exception:
            sectors = []
        for s in sectors:
            if s.get("name") not in sectors_needing_live_fallback:
                continue
            pct = _parse_pct(s.get("value", ""))
            evidence.append(Evidence(
                id=f"market:sector:{s.get('name')}",
                source="market",
                entity=s.get("name"),
                claim=f"{s.get('name')} sector is {s.get('value')} today",
                polarity="positive" if s.get("positive") else "negative",
                magnitude=min(abs(pct) / 3.0, 1.0),
                confidence=0.65,
                timestamp=None,
                raw=s,
            ))

    # Additive: global indices / commodities / macro rates -- real data
    # this retriever had no source for at all before Warehouse existed.
    # Absent, never fabricated, whenever Warehouse doesn't have a current
    # real row -- no live fallback exists for these today.
    for metric, label in _WAREHOUSE_GLOBAL_METRICS.items():
        snap = warehouse.get(metric)
        if snap is None or not snap.has_real_value or not snap.is_current:
            continue
        pct = (snap.extra or {}).get("pct")
        evidence.append(Evidence(
            id=f"market:global:{metric}", source="market", entity=label,
            claim=f"{label} is at {snap.value:,.2f}" + (f" ({'+' if pct >= 0 else ''}{pct:.2f}%)" if pct is not None else ""),
            polarity="positive" if (pct or 0) >= 0 else "negative",
            magnitude=min(abs(pct) / 3.0, 1.0) if pct is not None else 0.3,
            confidence=0.6, timestamp=snap.observation_time,
            raw={"metric": metric, "quality": snap.quality, "source_id": snap.source_id},
        ))

    for metric, (label, unit) in _WAREHOUSE_COMMODITY_METRICS.items():
        snap = warehouse.get(metric)
        if snap is None or not snap.has_real_value or not snap.is_current:
            continue
        evidence.append(Evidence(
            id=f"market:commodity:{metric}", source="market", entity=label,
            claim=f"{label} is at {snap.value:,.2f} {unit.replace('_', ' ')}",
            polarity="neutral", magnitude=0.3, confidence=0.55,
            timestamp=snap.observation_time,
            raw={"metric": metric, "quality": snap.quality, "source_id": snap.source_id},
        ))

    for metric, label in _WAREHOUSE_MACRO_METRICS.items():
        snap = warehouse.get(metric)
        if snap is None or not snap.has_real_value or not snap.is_current:
            continue
        evidence.append(Evidence(
            id=f"market:macro:{metric}", source="market", entity=label,
            claim=f"{label} is at {snap.value:,.4f}",
            polarity="neutral", magnitude=0.25, confidence=0.55,
            timestamp=snap.observation_time,
            raw={"metric": metric, "quality": snap.quality, "source_id": snap.source_id},
        ))

    try:
        movers = await get_top_movers()
    except Exception:
        movers = {}
    for g in (movers.get("gainers") or [])[:3]:
        evidence.append(Evidence(
            id=f"market:mover:{g.get('ticker')}", source="market", entity=g.get("ticker"),
            claim=f"{g.get('company')} is up {g.get('value')} today",
            polarity="positive", magnitude=0.6, confidence=0.6, timestamp=None, raw=g,
        ))
    for l in (movers.get("losers") or [])[:3]:
        evidence.append(Evidence(
            id=f"market:mover:{l.get('ticker')}", source="market", entity=l.get("ticker"),
            claim=f"{l.get('company')} is down {l.get('value')} today",
            polarity="negative", magnitude=0.6, confidence=0.6, timestamp=None, raw=l,
        ))

    return evidence


RETRIEVER_REGISTRY.register("market")(RetrieverSpec(key="market", fetch=_fetch, timeout_s=15.0))

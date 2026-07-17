"""
Market Retriever — live index levels, sector moves, and top gainers/losers.
Broad market-condition evidence, not tied to entity resolution; this is
what lets the Decision Intelligence Engine's confidence scoring actually
populate `market_confirming`/`sector_confirming` (both hardcoded to 0 in
Phase 1 since this retriever didn't exist yet).
"""
from __future__ import annotations

import re

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.market_data import get_extended_indices, get_sector_changes, get_top_movers


def _parse_pct(value: str) -> float:
    m = re.search(r"-?\d+\.?\d*", value or "")
    return float(m.group()) if m else 0.0


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    evidence: list[Evidence] = []

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

    try:
        sectors = await get_sector_changes()
    except Exception:
        sectors = []
    for s in sectors[:10]:
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

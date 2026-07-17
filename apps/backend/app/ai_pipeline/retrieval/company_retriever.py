"""
Company Retriever — resolves company entities mentioned in the query (via
the shared `entity_resolver`), then pulls recent NSE/BSE announcements and
basic valuation fundamentals (P/E, P/B, 52-week range, market cap) for
each.
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.ai_pipeline.retrieval.entity_resolver import resolve_entities
from app.services.company_announcements_service import get_recent_announcements
from app.services.company_fundamentals_service import get_fundamentals

_SENTIMENT_POLARITY = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    entities = await resolve_entities(ctx.query, limit=5)
    companies = [e for e in entities if e["node_type"] == "company" and e.get("ticker")]
    if not companies:
        return []

    symbols = [c["ticker"].replace(".NS", "").replace(".BO", "") for c in companies][:3]
    evidence: list[Evidence] = []

    for symbol in symbols:
        try:
            announcements = await get_recent_announcements(symbol=symbol, limit=5)
        except Exception:
            announcements = []
        for a in announcements:
            evidence.append(Evidence(
                id=f"company:announcement:{a.get('id')}",
                source="company",
                entity=symbol,
                claim=a.get("ai_summary") or a.get("subject") or a.get("description", "")[:200],
                polarity=_SENTIMENT_POLARITY.get(a.get("sentiment"), "neutral"),
                magnitude=min(max(float(a.get("impact_score", 5.0) or 5.0) / 10.0, 0.0), 1.0),
                confidence=0.6 if a.get("is_high_impact") else 0.45,
                timestamp=None,
                raw=a,
            ))

    try:
        fundamentals = await get_fundamentals(symbols)
    except Exception:
        fundamentals = {}
    for symbol, f in fundamentals.items():
        parts = []
        if f.get("pe"):
            parts.append(f"P/E {f['pe']}")
        if f.get("pb"):
            parts.append(f"P/B {f['pb']}")
        if f.get("52w_low") and f.get("52w_high"):
            parts.append(f"52W range {f['52w_low']}-{f['52w_high']}")
        if not parts:
            continue
        evidence.append(Evidence(
            id=f"company:fundamentals:{symbol}",
            source="company",
            entity=symbol,
            claim=f"{symbol} valuation: {', '.join(parts)}",
            polarity="neutral",   # valuation alone doesn't imply direction
            magnitude=0.4,
            confidence=0.6,
            timestamp=None,
            raw=f,
        ))

    return evidence


RETRIEVER_REGISTRY.register("company")(RetrieverSpec(key="company", fetch=_fetch, timeout_s=15.0))

"""
Historical Similarity Retriever — wraps `historical_memory_service` to find
verified past events resembling the current query, via lightweight keyword
extraction of category/sectors from the query text (all
`find_similar_events` query fields are optional; this fills in what can be
inferred and lets similarity scoring do the rest).
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.historical_memory_service import find_similar_events

_SECTOR_NAMES = {
    "banking", "it", "technology", "defence", "energy", "pharma", "auto",
    "fmcg", "metals", "realty", "telecom", "power", "finance", "infrastructure",
    "railway", "railways", "healthcare", "manufacturing", "chemicals",
}
_CATEGORY_KEYWORDS = {
    "monetary_policy": ("rbi", "repo rate", "interest rate", "rate cut", "rate hike"),
    "policy": ("budget", "gst", "policy", "government", "regulation"),
    "geopolitical": ("war", "geopolitical", "sanctions", "conflict", "tension"),
    "commodity": ("crude", "oil", "gold", "commodity", "opec"),
    "election": ("election", "poll result", "government formation"),
    "pandemic": ("pandemic", "covid", "lockdown"),
}


def _infer_category(query_lower: str) -> str | None:
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in query_lower for k in keywords):
            return category
    return None


def _infer_sectors(query_lower: str) -> list[str]:
    return [s for s in _SECTOR_NAMES if s in query_lower]


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    query_lower = ctx.query.lower()
    hist_query = {
        "category": _infer_category(query_lower),
        "sectors": _infer_sectors(query_lower),
    }
    if not hist_query["category"] and not hist_query["sectors"]:
        return []   # nothing to match against — better to skip than fetch a near-random top-N

    try:
        similar = await find_similar_events(hist_query, limit=5, min_similarity=25.0)
    except Exception:
        return []

    evidence: list[Evidence] = []
    for event in similar:
        nifty_1w = event.get("nifty_1w")
        polarity = "neutral"
        if isinstance(nifty_1w, (int, float)):
            polarity = "positive" if nifty_1w > 0.5 else ("negative" if nifty_1w < -0.5 else "neutral")
        similarity = float(event.get("similarity", 0) or 0) / 100.0
        evidence.append(Evidence(
            id=f"historical_similarity:{event.get('id')}",
            source="historical_similarity",
            entity=(event.get("sectors") or [None])[0] if event.get("sectors") else None,
            claim=(
                f"{event.get('event_title')} ({event.get('event_date')}): "
                f"{event.get('key_lesson') or event.get('what_happened', '')}"
            )[:280],
            polarity=polarity,
            magnitude=min(max(similarity, 0.0), 1.0),
            confidence=min(max(float(event.get("confidence", 0.5) or 0.5), 0.0), 1.0),
            timestamp=None,
            raw=event,
        ))

    return evidence


RETRIEVER_REGISTRY.register("historical_similarity")(
    RetrieverSpec(key="historical_similarity", fetch=_fetch, timeout_s=10.0)
)

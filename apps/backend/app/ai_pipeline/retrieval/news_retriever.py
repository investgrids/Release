"""
News Retriever — wraps `news_fetcher.get_live_news`, filtered to articles
whose headline/summary overlap the query's keywords (same word-overlap
approach as `ai_search_service._search_news`'s live-news branch).
"""
from __future__ import annotations

import re

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.news_fetcher import get_live_news


def _words(query: str) -> list[str]:
    return [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2][:8]


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    ws = _words(ctx.query)
    try:
        articles = await get_live_news(limit=20) or []
    except Exception:
        return []

    def _matches(a: dict) -> bool:
        if not ws:
            return True
        text = (a.get("headline", "") + " " + a.get("summary", "")).lower()
        return any(w in text for w in ws)

    matched = [a for a in articles if _matches(a)][:8]
    if not matched:
        # No word-overlap hits (or a purely generic "what's happening" query
        # whose own words won't appear in article text) — fall back to the
        # top live headlines by impact score rather than returning nothing.
        matched = sorted(articles, key=lambda a: float(a.get("impact_score", 0) or 0), reverse=True)[:5]

    evidence: list[Evidence] = []
    for a in matched:
        impact = float(a.get("impact_score", 5.0) or 5.0)
        evidence.append(Evidence(
            id=f"news:{a.get('id')}",
            source="news",
            entity=(a.get("companies") or [None])[0] if a.get("companies") else None,
            claim=(a.get("summary") or a.get("headline") or "")[:280],
            polarity="neutral",
            magnitude=min(max(impact / 10.0, 0.0), 1.0),
            confidence=0.5,
            timestamp=None,
            raw=a,
        ))
    return evidence


RETRIEVER_REGISTRY.register("news")(RetrieverSpec(key="news", fetch=_fetch, timeout_s=20.0))

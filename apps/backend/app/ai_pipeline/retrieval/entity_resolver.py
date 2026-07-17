"""
Entity Resolver — free-text query -> candidate entities, from two sources:

1. The intelligence graph (`get_full_graph`) — real nodes with a working
   node_id, usable for BFS traversal (`ripple_retriever`,
   `intelligence_graph_retriever`). Only companies/sectors/themes already
   mentioned in a triaged event end up here — it is not a full company
   directory.
2. The static NSE company universe (`app.api.companies._NSE_UNIVERSE`,
   ~260 names+aliases) — covers well-known companies (e.g. HAL, BEL) that
   may not yet have a graph node. These carry `in_graph: False` and a
   synthetic id; `company_retriever` can still use their ticker directly
   against yfinance/NSE data (which needs no graph membership at all), but
   callers that need real graph traversal must filter to `in_graph: True`.

Without source 2, a query like "Compare HAL and BEL" would silently return
zero company evidence whenever neither company happens to already be a
graph node — the retriever would degrade gracefully (no crash), but the
answer would be needlessly generic when real ticker-level data was one
static lookup away.
"""
from __future__ import annotations

import re

from app.services.intelligence_graph_service import get_full_graph

_MIN_WORD_LEN = 4


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 2}


def _nse_universe() -> list[dict]:
    from app.api.companies import _NSE_UNIVERSE
    return _NSE_UNIVERSE


async def resolve_entities(query: str, *, limit: int = 5) -> list[dict]:
    """
    Returns up to `limit` candidate entities as
    `{"id", "label", "node_type", "ticker", "score", "in_graph"}`, sorted by
    score desc, graph matches taking priority over universe-only matches at
    equal score. An empty result means no confident match, not an error.
    """
    query_lower = query.lower()
    query_words = _words(query)

    scored: list[tuple[float, dict]] = []

    graph = await get_full_graph()
    matched_tickers: set[str] = set()
    for n in graph.get("nodes", []):
        label = str(n.get("label", ""))
        ticker = str(n.get("ticker") or "")
        if not label:
            continue
        label_lower = label.lower()

        score = 0.0
        if label_lower and label_lower in query_lower:
            score += 3.0   # whole label appears verbatim — strongest signal
        if ticker and ticker.lower() in query_words:
            score += 3.0   # exact ticker mentioned as its own word
        label_words = _words(label)
        overlap = sum(1 for w in label_words if len(w) >= _MIN_WORD_LEN and w in query_words)
        score += overlap * 1.0

        if score > 0:
            scored.append((score, {
                "id": n["id"], "label": n["label"], "node_type": n["node_type"],
                "ticker": n.get("ticker"), "in_graph": True,
            }))
            if ticker:
                matched_tickers.add(ticker.upper())

    for c in _nse_universe():
        symbol = c["symbol"]
        if symbol.upper() in matched_tickers:
            continue   # already matched via the graph — don't double-count
        aliases = c.get("aliases", []) + [c["name"].lower(), symbol.lower()]
        score = 0.0
        if any(a in query_lower for a in aliases if len(a) >= 3):
            score += 3.0
        elif symbol.lower() in query_words:
            score += 3.0
        if score > 0:
            scored.append((score, {
                "id": f"company:{symbol.lower()}", "label": c["name"], "node_type": "company",
                "ticker": symbol, "in_graph": False,
            }))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [{**entity, "score": s} for s, entity in scored[:limit]]

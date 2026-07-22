"""Market Intelligence Graph API — /api/graph/*"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import require_admin_key

log = structlog.get_logger(__name__)
router = APIRouter()

# In-process price cache: {ticker: (ts, data)}
_price_cache: dict[str, tuple[float, dict]] = {}
_PRICE_TTL = 120  # 2-minute freshness for live prices

# Cap concurrent yfinance threads — Yahoo throttles hard above ~6 parallel requests
# from the same IP, causing long hangs that trigger gunicorn's 120 s worker timeout.
_YF_SEM = asyncio.Semaphore(6)
_YF_CALL_TIMEOUT = 9.0  # seconds per individual yfinance call


def _yf_price(ticker: str) -> dict | None:
    """Synchronous yfinance fast_info fetch — run in executor."""
    now = time.time()
    if ticker in _price_cache and now - _price_cache[ticker][0] < _PRICE_TTL:
        return _price_cache[ticker][1]
    try:
        import yfinance as yf
        fi = yf.Ticker(ticker).fast_info
        price = float(fi.last_price or 0)
        prev  = float(fi.previous_close or 0)
        if not price or not prev:
            return None
        change = price - prev
        pct    = round((change / prev) * 100, 2)
        result = {"price": round(price, 2), "change": round(change, 2), "pct": pct, "positive": change >= 0}
        _price_cache[ticker] = (now, result)
        return result
    except Exception:
        return None


def _yf_sparkline(ticker: str, points: int = 8) -> list[float]:
    """Return last N intraday hourly close prices normalised to % change from open."""
    try:
        import yfinance as yf, math
        hist = yf.download(ticker, period="1d", interval="60m", progress=False, auto_adjust=True, timeout=8)
        if hist.empty:
            return []
        closes: list[float] = []
        for _, row in hist.iterrows():
            c = row["Close"]
            if hasattr(c, "iloc"):
                c = c.iloc[0]
            v = float(c)
            if not math.isnan(v) and not math.isinf(v):
                closes.append(v)
        if len(closes) < 2:
            return []
        base = closes[0] or 1
        pcts = [round((v / base - 1) * 100, 3) for v in closes]
        return pcts[-points:]
    except Exception:
        return []


@router.get("/full")
async def get_full_graph():
    """All nodes + edges for graph visualisation. Cached 5 min."""
    from app.services.intelligence_graph_service import get_full_graph
    return await get_full_graph()


@router.get("/subgraph/{node_id:path}")
async def get_subgraph(node_id: str, hops: int = Query(2, ge=1, le=4)):
    """N-hop undirected neighbourhood around a node."""
    from app.services.intelligence_graph_service import get_subgraph
    return await get_subgraph(node_id, hops)


@router.get("/ripple/{node_id:path}")
async def get_ripple(
    node_id: str,
    change: str = Query("rise", description="rise | fall | shock"),
    max_depth: int = Query(5, ge=1, le=8),
):
    """
    BFS ripple analysis from a source node.

    change=rise  → entity increases / strengthens  (e.g. crude oil rises)
    change=fall  → entity decreases / weakens       (e.g. crude oil falls)
    change=shock → large-magnitude shock (same direction as rise but wider cascade)
    """
    if change not in ("rise", "fall", "shock"):
        raise HTTPException(400, "change must be 'rise', 'fall', or 'shock'")
    from app.services.intelligence_graph_service import ripple_from_node
    return await ripple_from_node(node_id, change, max_depth)


@router.get("/stats")
async def get_stats():
    """Node and edge counts by type."""
    from app.services.intelligence_graph_service import get_full_graph
    from collections import Counter
    g = await get_full_graph()
    return {
        "total_nodes":   len(g["nodes"]),
        "total_edges":   len(g["edges"]),
        "nodes_by_type": dict(Counter(n["node_type"] for n in g["nodes"])),
        "edges_by_type": dict(Counter(e["edge_type"] for e in g["edges"])),
    }


@router.get("/live")
async def get_live_data():
    """
    Live price data for all ticker-bearing nodes in the graph.
    Also returns lightweight topology metadata so clients can detect graph changes.
    Prices are cached 2 minutes in-process; graph topology is fetched from Redis/DB.
    """
    from app.services.intelligence_graph_service import get_full_graph

    graph = await get_full_graph()

    # Collect unique tickers from nodes
    ticker_map: dict[str, str] = {}   # ticker → node_id
    for n in graph["nodes"]:
        t = (n.get("ticker") or "").strip()
        if t and t not in ticker_map:
            ticker_map[t] = n["id"]

    # Add key benchmark tickers not necessarily in graph nodes
    BENCHMARKS = {
        "^NSEI":    "index:nifty-50",
        "^NSEBANK": "index:bank-nifty",
        "^CNXIT":   "index:nifty-it",
        "USDINR=X": "currency:usd-inr",
        "GC=F":     "commodity:gold",
        "BZ=F":     "commodity:crude-oil",
    }
    for tkr, nid in BENCHMARKS.items():
    # Only add if not already from a node
        if tkr not in ticker_map:
            ticker_map[tkr] = nid

    # Fetch all prices concurrently in executor.
    # Semaphore caps parallel Yahoo requests to 6; wait_for kills hangers after 9 s.
    loop = asyncio.get_running_loop()

    async def _fetch_one(ticker: str) -> tuple[str, dict | None]:
        async with _YF_SEM:
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, _yf_price, ticker),
                    timeout=_YF_CALL_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.warning("graph.live.yf_timeout", ticker=ticker)
                result = None
        return ticker, result

    results = await asyncio.gather(*[_fetch_one(t) for t in ticker_map])

    prices: dict[str, dict] = {}
    for ticker, data in results:
        if data:
            node_id = ticker_map[ticker]
            prices[node_id] = {**data, "ticker": ticker}

    # Lightweight topology fingerprint: node count + edge count
    topology = {
        "node_count": len(graph["nodes"]),
        "edge_count":  len(graph["edges"]),
    }

    return {
        "prices":     prices,
        "topology":   topology,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/live/sparkline/{node_id:path}")
async def get_node_sparkline(node_id: str):
    """Return intraday sparkline for a specific ticker-bearing node."""
    from app.services.intelligence_graph_service import get_full_graph
    graph = await get_full_graph()
    node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if not node or not node.get("ticker"):
        raise HTTPException(404, "Node not found or has no ticker")

    loop = asyncio.get_running_loop()
    async with _YF_SEM:
        try:
            sparkline = await asyncio.wait_for(
                loop.run_in_executor(None, _yf_sparkline, node["ticker"]),
                timeout=_YF_CALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            sparkline = []
    return {"node_id": node_id, "ticker": node["ticker"], "sparkline": sparkline}


# ── AI Chat endpoint ─────────────────────────────────────────────────────────

class ChatIn(BaseModel):
    question: str
    graph_context: dict | None = None   # {nodes, edges, center_id, selected_id}


@router.post("/chat")
async def graph_chat(body: ChatIn):
    """AI conversation about the graph — powered by OpenRouter free tier."""
    from app.services.ai_service import _call_with_fallback  # noqa: PLC2701
    import json as _json

    system = (
        "You are a senior Indian market intelligence analyst. "
        "You are given a snapshot of a causal market-relationship graph "
        "and the user asks a question about it. "
        "Answer concisely (2–3 sentences) and always return valid JSON:\n"
        '{"answer":"...","highlight_nodes":["node_id_1"],"confidence":0-100}\n'
        "highlight_nodes should list at most 4 node IDs most relevant to the answer. "
        "Return ONLY the JSON object — no markdown, no extra text."
    )

    ctx = body.graph_context or {}
    nodes = ctx.get("nodes", [])
    center_id = ctx.get("center_id", "")
    selected_id = ctx.get("selected_id", "")
    center = next((n for n in nodes if n.get("id") == center_id), None)
    selected = next((n for n in nodes if n.get("id") == selected_id), center)

    node_lines = "\n".join(
        f'- [{n["node_type"].upper()}] {n["label"]} (id:{n["id"]})'
        for n in nodes[:20]
    )

    prompt = (
        f"Graph center node: {center['label'] if center else 'Unknown'}\n"
        f"Currently selected node: {selected['label'] if selected else 'None'}\n\n"
        f"Visible nodes ({len(nodes)}):\n{node_lines}\n\n"
        f"User question: {body.question.strip()[:400]}"
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=350)
    if not raw:
        return {"answer": "I couldn't generate a response right now. Please try again.", "highlight_nodes": [], "confidence": 0}

    try:
        text = raw.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        return _json.loads(text.strip())
    except Exception:
        return {"answer": raw.strip()[:500], "highlight_nodes": [], "confidence": 60}


# ── Write endpoints ───────────────────────────────────────────────────────────

class NodeIn(BaseModel):
    node_type: str
    label: str
    ticker: str | None = None
    description: str | None = None
    extra: dict = {}
    auto_added: bool = False


class EdgeIn(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 0.7
    confidence: float = 0.8
    lag_days: int = 0
    description: str | None = None
    source_event: str | None = None
    auto_added: bool = False


@router.post("/node", dependencies=[Depends(require_admin_key)])
async def upsert_node_endpoint(body: NodeIn):
    from app.services.intelligence_graph_service import upsert_node, NODE_TYPES
    if body.node_type not in NODE_TYPES:
        raise HTTPException(400, f"node_type must be one of: {sorted(NODE_TYPES)}")
    node_id = await upsert_node(
        body.node_type, body.label, body.ticker,
        body.description, body.extra, body.auto_added,
    )
    return {"id": node_id}


@router.post("/edge", dependencies=[Depends(require_admin_key)])
async def upsert_edge_endpoint(body: EdgeIn):
    from app.services.intelligence_graph_service import upsert_edge, EDGE_TYPES
    if body.edge_type not in EDGE_TYPES:
        raise HTTPException(400, f"edge_type must be one of: {sorted(EDGE_TYPES)}")
    edge_id = await upsert_edge(
        body.source_id, body.target_id, body.edge_type,
        body.weight, body.confidence, body.lag_days,
        body.description, body.source_event, body.auto_added,
    )
    return {"id": edge_id}

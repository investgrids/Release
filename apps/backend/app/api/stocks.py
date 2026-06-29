import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_events
from app.schemas.stock import StockDetail, StockEvent, StockNews
from app.services.market_data import get_stock_detail, get_stock_chart, get_top_movers
from app.services import finnhub

router = APIRouter()

_PEERS_MAP: dict = {
    "IT Services":             ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Software—Application":    ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Banks—Regional":          ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN"],
    "Banks—Diversified":       ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN"],
    "Banking":                 ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN"],
    "Pharmaceuticals":         ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA"],
    "Drug Manufacturers":      ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA"],
    "Oil & Gas E&P":           ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL"],
    "Energy":                  ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "TATAPOWER"],
    "Auto Manufacturers":      ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO"],
    "Automobiles":             ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO"],
    "Infrastructure":          ["LT", "RVNL", "IRCON", "BEML", "BHEL"],
    "Aerospace & Defence":     ["HAL", "BEL", "BHEL", "MTAR", "GRSE"],
    "Steel":                   ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL"],
    "Metals & Mining":         ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "COALINDIA"],
    "Consumer Defensive":      ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"],
    "FMCG":                    ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"],
    "Telecom Services":        ["AIRTEL", "TATACOMM", "MTNL"],
    "Real Estate":             ["DLF", "GODREJPROP", "OBEROIRLTY", "BRIGADE"],
    "Chemicals":               ["PIDILITIND", "ATUL", "ASIANPAINT", "DEEPAKNTR", "UPL"],
}
_DEFAULT_PEERS = ["TCS", "INFY", "WIPRO", "HDFCBANK", "RELIANCE"]

_FMT_PRICE_RE = lambda v: f"{float(v):,.2f}" if v else "—"


def _fmt_p(v) -> str:
    try:
        return f"{float(v):,.2f}" if v else "—"
    except Exception:
        return "—"


@router.get("/movers")
async def get_movers():
    """Top gainers, losers, and most active NSE stocks."""
    return await get_top_movers()


@router.get("/{symbol}/chart")
async def get_chart(symbol: str, period: str = Query("6M")):
    return await get_stock_chart(symbol, period)


@router.get("/{symbol}/news")
async def get_stock_news(symbol: str):
    """Company-specific news from Finnhub (last 7 days)."""
    articles = await finnhub.get_company_news(symbol, days=7)
    return articles


@router.get("/{symbol}", response_model=StockDetail)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
    sym_upper = symbol.upper()

    # Run yfinance detail + Finnhub calls concurrently
    yf_task    = get_stock_detail(symbol)
    q_task     = finnhub.get_quote(symbol)
    rec_task   = finnhub.get_recommendation(symbol)
    pt_task    = finnhub.get_price_target(symbol)
    peer_task  = finnhub.get_peers(symbol)
    news_task  = finnhub.get_company_news(symbol, days=7)

    yf_data, fh_quote, fh_rec, fh_pt, fh_peers, fh_news = await asyncio.gather(
        yf_task, q_task, rec_task, pt_task, peer_task, news_task,
        return_exceptions=True,
    )

    # Treat exceptions as None/empty
    if isinstance(yf_data,  Exception): yf_data  = None
    if isinstance(fh_quote, Exception): fh_quote = None
    if isinstance(fh_rec,   Exception): fh_rec   = None
    if isinstance(fh_pt,    Exception): fh_pt    = None
    if isinstance(fh_peers, Exception): fh_peers = []
    if isinstance(fh_news,  Exception): fh_news  = []

    if yf_data is None and fh_quote is None:
        raise HTTPException(status_code=404, detail=f"Symbol {sym_upper} not found on NSE")

    # ── Price: prefer Finnhub real-time, fallback to yfinance ───────────────
    if fh_quote and fh_quote.get("c"):
        price      = float(fh_quote["c"])
        prev_close = float(fh_quote.get("pc") or price)
        change_abs = float(fh_quote.get("d")  or 0.0)
        pct_change = float(fh_quote.get("dp") or 0.0)
        sign       = "+" if change_abs >= 0 else ""
        price_str  = _fmt_p(price)
        change_str = f"{sign}{pct_change:.2f}%"
        change_abs_str = f"{sign}{change_abs:.2f}"
        day_high   = _fmt_p(fh_quote.get("h") or price)
        day_low    = _fmt_p(fh_quote.get("l") or price)
        open_str   = _fmt_p(fh_quote.get("o") or prev_close)
        prev_str   = _fmt_p(prev_close)
    else:
        # Fall back to yfinance values
        price_str      = (yf_data or {}).get("price", "—")
        change_str     = (yf_data or {}).get("change", "—")
        change_abs_str = (yf_data or {}).get("change_abs", "—")
        pct_change     = (yf_data or {}).get("pct_change", 0.0)
        day_high       = (yf_data or {}).get("day_high", "—")
        day_low        = (yf_data or {}).get("day_low", "—")
        open_str       = (yf_data or {}).get("open", "—")
        prev_str       = (yf_data or {}).get("prev_close", "—")

    # ── Analyst data: prefer Finnhub ────────────────────────────────────────
    buy_count       = 0
    hold_count      = 0
    sell_count      = 0
    strong_buy      = 0
    strong_sell     = 0
    analyst_count   = 0
    recommendation  = "hold"
    target_mean     = "—"
    target_high     = "—"
    target_low      = "—"

    if fh_rec:
        rec_data = fh_rec[0] if isinstance(fh_rec, list) and fh_rec else (fh_rec if isinstance(fh_rec, dict) else {})
        buy_count    = int(rec_data.get("buy", 0) or 0)
        hold_count   = int(rec_data.get("hold", 0) or 0)
        sell_count   = int(rec_data.get("sell", 0) or 0)
        strong_buy   = int(rec_data.get("strongBuy", 0) or 0)
        strong_sell  = int(rec_data.get("strongSell", 0) or 0)
        analyst_count = buy_count + hold_count + sell_count + strong_buy + strong_sell
        total_bull   = strong_buy + buy_count
        total_bear   = sell_count + strong_sell
        if analyst_count:
            if strong_buy > analyst_count * 0.4:
                recommendation = "strong buy"
            elif total_bull > analyst_count * 0.6:
                recommendation = "buy"
            elif total_bear > analyst_count * 0.4:
                recommendation = "sell"
            else:
                recommendation = "hold"

    if fh_pt:
        target_mean = _fmt_p(fh_pt.get("targetMean"))
        target_high = _fmt_p(fh_pt.get("targetHigh"))
        target_low  = _fmt_p(fh_pt.get("targetLow"))
    elif yf_data:
        target_mean = yf_data.get("target_mean", "—")
        target_high = yf_data.get("target_high", "—")
        target_low  = yf_data.get("target_low",  "—")

    if not analyst_count and yf_data:
        analyst_count  = yf_data.get("analyst_count", 0)
        recommendation = (yf_data.get("recommendation") or "hold").replace("_", " ")

    # ── Peers: prefer Finnhub live list, fallback to industry map ───────────
    if fh_peers:
        peers = [p for p in fh_peers if p != sym_upper][:4]
    else:
        industry = (yf_data or {}).get("industry", "")
        sector   = (yf_data or {}).get("sector", "")
        raw = _PEERS_MAP.get(industry) or _PEERS_MAP.get(sector) or _DEFAULT_PEERS
        peers = [p for p in raw if p != sym_upper][:4]

    # ── Related events from DB ───────────────────────────────────────────────
    all_events = await get_events(db)
    def _matches(e) -> bool:
        for c in (e.companies or []):
            if isinstance(c, dict) and c.get("symbol", "") == sym_upper:
                return True
            if isinstance(c, str) and c.strip().upper() == sym_upper:
                return True
        return False

    related_events = [
        StockEvent(title=e.title, date=str(e.published_at.date()) if e.published_at else "")
        for e in all_events if _matches(e)
    ][:4]

    yf = yf_data or {}

    return StockDetail(
        symbol=sym_upper,
        name=yf.get("name", f"{sym_upper} Ltd."),
        price=price_str,
        prev_close=prev_str,
        open=open_str,
        day_high=day_high,
        day_low=day_low,
        change=change_str,
        change_abs=change_abs_str,
        pct_change=pct_change,
        week52_high=yf.get("week52_high", "—"),
        week52_low=yf.get("week52_low", "—"),
        volume=yf.get("volume", "—"),
        avg_volume=yf.get("avg_volume", "—"),
        market_cap=yf.get("market_cap", "—"),
        industry=yf.get("industry", "N/A"),
        sector=yf.get("sector", "N/A"),
        description=yf.get("description", ""),
        pe=yf.get("pe", "—"),
        forward_pe=yf.get("forward_pe", "—"),
        pb=yf.get("pb", "—"),
        eps=yf.get("eps", "—"),
        roe=yf.get("roe", "—"),
        roa=yf.get("roa", "—"),
        beta=yf.get("beta", "—"),
        dividend_yield=yf.get("dividend_yield", "—"),
        dividend_rate=yf.get("dividend_rate", "—"),
        gross_margins=yf.get("gross_margins", "—"),
        operating_margins=yf.get("operating_margins", "—"),
        net_margins=yf.get("net_margins", "—"),
        debt_to_equity=yf.get("debt_to_equity", "—"),
        current_ratio=yf.get("current_ratio", "—"),
        free_cashflow=yf.get("free_cashflow", "—"),
        recommendation=recommendation,
        target_mean=target_mean,
        target_high=target_high,
        target_low=target_low,
        analyst_count=analyst_count,
        buy_count=buy_count + strong_buy,
        hold_count=hold_count,
        sell_count=sell_count + strong_sell,
        held_institutions=yf.get("held_institutions", "—"),
        held_insiders=yf.get("held_insiders", "—"),
        quarterly_revenue=yf.get("quarterly_revenue", []),
        quarterly_net_income=yf.get("quarterly_net_income", []),
        enterprise_value=yf.get("enterprise_value", ""),
        roce=yf.get("roce", ""),
        annual_financials=yf.get("annual_financials", []),
        dna_scores=yf.get("dna_scores", {}),
        gov_score=yf.get("gov_score", 0),
        gov_level=yf.get("gov_level", ""),
        gov_breakdown=yf.get("gov_breakdown", []),
        gov_support_areas=yf.get("gov_support_areas", []),
        events=related_events,
        news=[
            StockNews(
                headline=a.get("headline", ""),
                published_at=a.get("published_at", ""),
            )
            for a in (fh_news or [])[:8]
            if a.get("headline")
        ],
        peers=peers,
        chart_data=[],
    )

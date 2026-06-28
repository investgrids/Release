from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_events
from app.schemas.stock import StockDetail, StockEvent, StockNews
from app.services.market_data import get_stock_detail, get_stock_chart

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


@router.get("/{symbol}/chart")
async def get_chart(symbol: str, period: str = Query("6M")):
    return await get_stock_chart(symbol, period)


@router.get("/{symbol}", response_model=StockDetail)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
    data = await get_stock_detail(symbol)

    if data is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol.upper()} not found on NSE")

    sym_upper = symbol.upper()

    # Related events from DB
    all_events = await get_events(db)
    related_events = [
        StockEvent(title=e.title, date=str(e.published_at.date()) if e.published_at else "")
        for e in all_events
        if any(c.get("symbol", "") == sym_upper for c in (e.companies or []))
    ][:4]

    # Peers by industry → sector fallback → default
    industry = data.get("industry", "")
    sector = data.get("sector", "")
    raw_peers = (
        _PEERS_MAP.get(industry)
        or _PEERS_MAP.get(sector)
        or _DEFAULT_PEERS
    )
    peers = [p for p in raw_peers if p != sym_upper][:4]

    return StockDetail(
        symbol=data["symbol"],
        name=data.get("name", ""),
        price=data["price"],
        prev_close=data.get("prev_close", ""),
        open=data.get("open", ""),
        day_high=data.get("day_high", ""),
        day_low=data.get("day_low", ""),
        change=data["change"],
        change_abs=data.get("change_abs", ""),
        pct_change=data.get("pct_change", 0.0),
        week52_high=data.get("week52_high", ""),
        week52_low=data.get("week52_low", ""),
        volume=data.get("volume", ""),
        avg_volume=data.get("avg_volume", ""),
        market_cap=data["market_cap"],
        industry=data["industry"],
        sector=data.get("sector", ""),
        description=data.get("description", ""),
        pe=data["pe"],
        forward_pe=data.get("forward_pe", ""),
        pb=data["pb"],
        eps=data.get("eps", ""),
        roe=data["roe"],
        roa=data.get("roa", ""),
        beta=data.get("beta", ""),
        dividend_yield=data.get("dividend_yield", ""),
        dividend_rate=data.get("dividend_rate", ""),
        gross_margins=data.get("gross_margins", ""),
        operating_margins=data.get("operating_margins", ""),
        net_margins=data.get("net_margins", ""),
        debt_to_equity=data.get("debt_to_equity", ""),
        current_ratio=data.get("current_ratio", ""),
        free_cashflow=data.get("free_cashflow", ""),
        recommendation=data.get("recommendation", "hold"),
        target_mean=data.get("target_mean", ""),
        target_high=data.get("target_high", ""),
        target_low=data.get("target_low", ""),
        analyst_count=data.get("analyst_count", 0),
        held_institutions=data.get("held_institutions", ""),
        held_insiders=data.get("held_insiders", ""),
        quarterly_revenue=data.get("quarterly_revenue", []),
        quarterly_net_income=data.get("quarterly_net_income", []),
        events=related_events,
        news=[],
        peers=peers,
        chart_data=[],  # fetched separately via /chart
    )

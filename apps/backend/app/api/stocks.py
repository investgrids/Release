from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_events
from app.schemas.stock import StockDetail, StockEvent, StockNews
from app.services.market_data import get_stock_detail

router = APIRouter()


@router.get("/{symbol}", response_model=StockDetail)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
    data = await get_stock_detail(symbol)

    if data is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol.upper()} not found on NSE")

    # Pull related events from DB for this symbol
    all_events = await get_events(db)
    sym_upper = symbol.upper()
    related_events = [
        StockEvent(title=e.title, date=str(e.published_at.date()) if e.published_at else "")
        for e in all_events
        if any(c.get("symbol", "") == sym_upper for c in (e.companies or []))
    ][:4]

    # Fallback peers by industry (simplified)
    peers_map = {
        "IT Services": ["TCS", "INFY", "WIPRO", "HCLTECH"],
        "Banking": ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK"],
        "Pharmaceuticals": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB"],
        "Energy": ["RELIANCE", "ONGC", "BPCL", "IOC"],
        "Automobiles": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO"],
    }
    industry = data.get("industry", "")
    peers = [p for p in peers_map.get(industry, ["TCS", "INFY", "WIPRO"]) if p != sym_upper][:3]

    return StockDetail(
        symbol=data["symbol"],
        price=data["price"],
        change=data["change"],
        industry=data["industry"],
        market_cap=data["market_cap"],
        pe=data["pe"],
        pb=data["pb"],
        roe=data["roe"],
        events=related_events,
        news=[
            StockNews(headline=f"{data['symbol']} latest market update", published_at="Today")
        ],
        peers=peers,
        chart_data=data["chart_data"],
    )

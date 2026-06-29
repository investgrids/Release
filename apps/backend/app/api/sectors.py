import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_sectors

router = APIRouter()

_SECTOR_STOCKS: dict[str, list[str]] = {
    "banking":      ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN", "INDUSINDBK", "BANDHANBNK"],
    "it":           ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "MPHASIS", "LTIM"],
    "pharma":       ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA", "TORNTPHARM", "ALKEM"],
    "energy":       ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "NTPC", "ADANIGREEN"],
    "auto":         ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR"],
    "fmcg":         ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "GODREJCP", "MARICO"],
    "metals":       ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "COALINDIA", "SAIL", "NMDC"],
    "infrastructure": ["LT", "RVNL", "IRCON", "BEML", "BHEL", "NBCC", "PFC"],
    "defence":      ["HAL", "BEL", "BHEL", "MTAR", "GRSE", "COCHINSHIP", "PARAS"],
    "realty":       ["DLF", "GODREJPROP", "OBEROIRLTY", "BRIGADE", "PRESTIGE", "SOBHA"],
    "chemicals":    ["PIDILITIND", "ATUL", "ASIANPAINT", "DEEPAKNTR", "UPL", "GNFC", "FINEORG"],
    "telecom":      ["AIRTEL", "TATACOMM", "VODAFONEIDEA", "MTNL"],
    "finance":      ["BAJFINANCE", "BAJAJFINSV", "MUTHOOTFIN", "CHOLAFIN", "MANAPPURAM"],
}

# Normalise incoming sector id to match our keys
def _norm(sid: str) -> str:
    s = sid.lower().replace("-", "").replace(" ", "")
    for key in _SECTOR_STOCKS:
        if s in key or key in s:
            return key
    return s


@router.get("/", response_model=list[dict])
async def list_sectors(db: AsyncSession = Depends(get_db)):
    rows = await get_sectors(db)
    return [
        {"id": r.id, "name": r.name, "value": r.value, "positive": r.positive}
        for r in rows
    ]


@router.get("/{sector_id}/stocks")
async def sector_stocks(sector_id: str):
    """Return constituent stocks for a sector with live prices."""
    key = _norm(sector_id)
    symbols = _SECTOR_STOCKS.get(key)
    if not symbols:
        raise HTTPException(status_code=404, detail=f"Sector '{sector_id}' not found")

    import yfinance as yf, math
    tickers = [f"{s}.NS" for s in symbols]

    def _fetch():
        try:
            raw = yf.download(
                tickers, period="2d", interval="1d",
                progress=False, auto_adjust=True, group_by="ticker",
            )
        except Exception:
            return []

        result = []
        for sym, ns in zip(symbols, tickers):
            try:
                df = raw[ns] if ns in raw.columns.get_level_values(0) else raw.get(ns)
                if df is None or df.empty or len(df) < 1:
                    result.append({"symbol": sym, "name": sym, "price": "—", "change": "—", "positive": True})
                    continue
                curr = float(df["Close"].iloc[-1])
                if math.isnan(curr):
                    result.append({"symbol": sym, "name": sym, "price": "—", "change": "—", "positive": True})
                    continue
                if len(df) >= 2:
                    prev = float(df["Close"].iloc[-2])
                    pct = (curr - prev) / prev * 100 if prev else 0.0
                else:
                    pct = 0.0
                sign = "+" if pct >= 0 else ""
                result.append({
                    "symbol":   sym,
                    "name":     sym,
                    "price":    f"₹{curr:,.2f}",
                    "change":   f"{sign}{pct:.2f}%",
                    "positive": pct >= 0,
                })
            except Exception:
                result.append({"symbol": sym, "name": sym, "price": "—", "change": "—", "positive": True})
        return result

    loop = asyncio.get_event_loop()
    stocks = await loop.run_in_executor(None, _fetch)
    return {"sector": sector_id, "stocks": stocks}

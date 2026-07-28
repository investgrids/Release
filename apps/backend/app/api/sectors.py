import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_sectors

router = APIRouter()

# Simple in-memory TTL cache for sector stock data (yfinance calls are slow)
_sector_stock_cache: dict[str, tuple[float, list]] = {}
_SECTOR_STOCK_TTL = 300  # 5 minutes

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
    if key not in _SECTOR_STOCKS:
        raise HTTPException(status_code=404, detail=f"Sector '{sector_id}' not found")
    stocks = await _get_sector_stocks_cached(key)
    return {"sector": sector_id, "stocks": stocks}


async def _get_sector_stocks_cached(key: str) -> list[dict]:
    """Same fetch-or-cache logic as the /stocks route above, extracted so
    the new /intelligence route (sector landing pages, SEO Phase 2) can
    call it directly instead of a self-HTTP round-trip."""
    symbols = _SECTOR_STOCKS.get(key)
    if not symbols:
        return []

    cached_entry = _sector_stock_cache.get(key)
    if cached_entry and time.time() - cached_entry[0] < _SECTOR_STOCK_TTL:
        return cached_entry[1]

    import yfinance as yf, math
    tickers = [f"{s}.NS" for s in symbols]

    def _fetch():
        try:
            raw = yf.download(
                tickers, period="2d", interval="1d",
                progress=False, auto_adjust=True, group_by="ticker", timeout=10,
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
                    pct = (curr - prev) / prev * 100 if prev and not math.isnan(prev) else 0.0
                else:
                    pct = 0.0
                if math.isnan(pct):
                    pct = 0.0
                sign = "+" if pct >= 0 else ""
                result.append({
                    "symbol": sym, "name": sym,
                    "price": f"₹{curr:,.2f}", "change": f"{sign}{pct:.2f}%", "positive": pct >= 0,
                })
            except Exception:
                result.append({"symbol": sym, "name": sym, "price": "—", "change": "—", "positive": True})
        return result

    loop = asyncio.get_event_loop()
    stocks = await loop.run_in_executor(None, _fetch)
    _sector_stock_cache[key] = (time.time(), stocks)
    return stocks


def _sector_words(name: str) -> set[str]:
    return {w.lower() for w in (name or "").replace("&", " ").split() if len(w) > 3}


# A few real sector-name variants share no substring at all (found live
# while sizing best-of pages: SectorData's fixed 12 rows use "IT", but
# Opportunity/Event rows tag "Technology" — no word is a substring of the
# other, unlike Auto/Automotive or Infra/Infrastructure, which
# _words_overlap's substring check below already catches on its own).
_SECTOR_ALIASES: dict[str, set[str]] = {"it": {"technology", "information"}}


def _words_overlap(a: set[str], b: set[str]) -> bool:
    """True if any word in `a` and any word in `b` share a real relationship
    — exact match, one contains the other (Auto/Automotive, Infra/
    Infrastructure, Metal/Metals — the common case for real sector-name
    variance), or a known alias pair. Same reasoning as this file's own
    _norm() substring check, generalized to two whole word-sets."""
    for wa in a:
        aliases = _SECTOR_ALIASES.get(wa, set())
        for wb in b:
            if wa == wb or wa in wb or wb in wa or wb in aliases:
                return True
    return False


@router.get("/{sector_id}/intelligence")
async def sector_intelligence(sector_id: str, db: AsyncSession = Depends(get_db)):
    """Real aggregation for sector landing pages (SEO Phase 2, §2.1) — the
    sector's live momentum + constituent stocks (existing /stocks logic)
    plus real opportunities and events whose own `sectors` field overlaps
    this sector's name. No new intelligence generated here: every field is
    a read of data that already exists elsewhere in the app, filtered by
    sector — same word-overlap matching pattern as context_pulse.py's
    _find_related_opportunity, reused rather than reinvented."""
    from sqlalchemy import select
    from app.db.models.event import Event
    from app.db.models.opportunity import Opportunity

    rows = await get_sectors(db)
    sector_row = next((r for r in rows if r.id.lower() == sector_id.lower()), None)
    key = _norm(sector_id)

    if not sector_row:
        # No live-momentum SectorData row, but real constituent stocks
        # exist for this key (_SECTOR_STOCKS has 13 sectors; SectorData
        # only tracks 12, and they're NOT the same 12 — Defence,
        # Chemicals, Telecom, and Finance have real stock lists and real
        # Opportunity/Event data but no momentum row). A page with real
        # opportunities/events/companies and no momentum badge is honest
        # and valuable; a 404 for "defence" when HAL/BEL opportunity and
        # event data is sitting right there is not.
        if key not in _SECTOR_STOCKS:
            raise HTTPException(status_code=404, detail=f"Sector '{sector_id}' not found")
        sector_name = key.replace("-", " ").title()
        sector_value, sector_positive = None, None
    else:
        sector_name = sector_row.name
        sector_value, sector_positive = sector_row.value, sector_row.positive

    stocks = await _get_sector_stocks_cached(key)
    target_words = _sector_words(sector_name) | _sector_words(sector_id.replace("-", " "))

    opp_rows = (await db.execute(
        select(Opportunity).order_by(Opportunity.opportunity_score.desc()).limit(60)
    )).scalars().all()
    opportunities = []
    for o in opp_rows:
        opp_words = {w.lower() for s in (o.sectors or []) for w in _sector_words(s)}
        if _words_overlap(target_words, opp_words):
            opportunities.append({
                "id": o.id, "slug": o.slug, "title": o.title,
                "opportunity_score": o.opportunity_score, "confidence": o.confidence,
            })
        if len(opportunities) >= 6:
            break

    event_rows = (await db.execute(
        select(Event).order_by(Event.published_at.desc()).limit(200)
    )).scalars().all()
    events = []
    for e in event_rows:
        ev_words = {w.lower() for s in (e.sectors or []) for w in _sector_words(s)}
        if _words_overlap(target_words, ev_words):
            events.append({
                "id": e.id, "title": e.title, "impact_score": e.impact_score,
                "date": (e.event_date or e.published_at).isoformat() if (e.event_date or e.published_at) else None,
            })
        if len(events) >= 6:
            break

    return {
        "id": sector_id.lower(), "name": sector_name,
        "value": sector_value, "positive": sector_positive,
        "stocks": stocks, "opportunities": opportunities, "events": events,
    }

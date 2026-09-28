import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

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

# Display names for each of the 13 real, stock-backed sector keys above —
# NOT derived from `.title()` (which would wrongly produce "It"/"Fmcg"
# instead of "IT"/"FMCG"). Content-integrity repair (2026-09-22): this
# replaces the fabricated `SectorData` table's `name` column as the
# source of truth for sector display names, since that table's only
# other column (`value`, a hand-typed percentage frozen since its
# 2026-07-22 seed insert — never updated by any job) is being removed
# from every public response below. See this module's own removed
# SectorData usage in list_sectors()/sector_intelligence() for the full
# rationale.
_SECTOR_NAMES: dict[str, str] = {
    "banking": "Banking", "it": "IT", "pharma": "Pharma", "energy": "Energy",
    "auto": "Auto", "fmcg": "FMCG", "metals": "Metals", "infrastructure": "Infrastructure",
    "defence": "Defence", "realty": "Realty", "chemicals": "Chemicals",
    "telecom": "Telecom", "finance": "Finance (NBFC)",
}

# Normalise incoming sector id to match our keys
def _norm(sid: str) -> str:
    s = sid.lower().replace("-", "").replace(" ", "")
    if s in _SECTOR_STOCKS:
        return s
    # 2026-08 fix — the fuzzy substring check below matched garbage input
    # to a real sector whenever the input merely CONTAINED a short key as a
    # substring (e.g. "it" is inside "definitely", "credit", "digital"...),
    # so almost any typo/garbage sector slug silently resolved to the real
    # IT sector at HTTP 200 instead of 404 — a duplicate-content generator
    # of exactly the kind flagged in GSC. Gated to keys/input of length >=4
    # (the exact-match check above already covers "it" itself) so the
    # legitimate fuzzy pairs (Auto/Automotive, Infra/Infrastructure,
    # Metal/Metals) still match.
    for key in _SECTOR_STOCKS:
        if len(key) >= 4 and len(s) >= 4 and (s in key or key in s):
            return key
    return s


# Real NSE sectoral indices (2026-09-28) — the official index itself, not
# a sector ETF proxy. Only indices whose sector already has a real page
# (a key in _SECTOR_STOCKS) are listed, so every card links somewhere real.
# NIFTY Financial Services is deliberately NOT mapped to "finance": that
# page is NBFC-only, while the index is bank-dominated — a different
# population under the same label would mislead.
_SECTOR_INDICES: dict[str, tuple[str, str]] = {
    "banking":        ("NIFTY Bank",           "^NSEBANK"),
    "it":             ("NIFTY IT",             "^CNXIT"),
    "pharma":         ("NIFTY Pharma",         "^CNXPHARMA"),
    "auto":           ("NIFTY Auto",           "^CNXAUTO"),
    "fmcg":           ("NIFTY FMCG",           "^CNXFMCG"),
    "metals":         ("NIFTY Metal",          "^CNXMETAL"),
    "realty":         ("NIFTY Realty",         "^CNXREALTY"),
    "energy":         ("NIFTY Energy",         "^CNXENERGY"),
    "infrastructure": ("NIFTY Infrastructure", "^CNXINFRA"),
}
_SECTOR_INDEX_TTL = 300
# A failed/empty fetch (e.g. Yahoo rate-limiting) waits this long before
# retrying, so page loads don't hit upstream on every request.
_SECTOR_INDEX_FAILURE_TTL = 60
# During an outage, the last real result is served only while it's this
# fresh — never presented as current day change indefinitely.
_SECTOR_INDEX_MAX_STALE = 1800
_sector_index_cache: dict = {"checked_at": 0.0, "success_at": 0.0, "data": None}


def _fetch_sector_indices_sync() -> list[dict]:
    """last_price/previous_close from yfinance fast_info. history() only
    returns a single row for most CNX indices, so a day change can't be
    derived from it; fast_info's previous_close is the exchange's real
    prior close (verified to match history() for ^NSEBANK/^CNXIT/
    ^CNXPHARMA, where both are available). An index with either value
    missing is omitted, never estimated."""
    import math
    from datetime import datetime, timedelta, timezone

    import yfinance as yf

    ist = timezone(timedelta(hours=5, minutes=30))
    rows: list[dict] = []
    for key, (index_name, ticker) in _SECTOR_INDICES.items():
        try:
            fi = yf.Ticker(ticker).fast_info
            last, prev = fi.last_price, fi.previous_close
        except Exception:
            continue
        if not last or not prev or any(math.isnan(v) or math.isinf(v) for v in (last, prev)):
            continue
        pct = (last / prev - 1) * 100
        rows.append({
            "id": key,
            "name": _SECTOR_NAMES[key],
            "value": f"{pct:.2f}%",
            "positive": pct >= 0,
            "index_name": index_name,
            "ticker": ticker,
            "last": round(float(last), 2),
            "previous_close": round(float(prev), 2),
            "fetched_at": datetime.now(ist).isoformat(),
        })
    rows.sort(key=lambda r: float(r["value"].rstrip("%")), reverse=True)
    return rows


@router.get("/", response_model=list[dict])
async def list_sectors():
    """Real day change for each NSE sectoral index (see _SECTOR_INDICES).
    Replaces the 2026-09-22 content-integrity repair's unconditional []
    (which removed the fabricated, never-updated `SectorData` percentages)
    now that a real, provenance-tracked feed exists — every row carries
    its index name, ticker, last value and previous close. Cached 5 min;
    returns [] if the upstream fetch fails, and the frontend's empty
    state still handles that honestly."""
    now = time.time()
    c = _sector_index_cache
    last_good = c["data"] if c["data"] and now - c["success_at"] < _SECTOR_INDEX_MAX_STALE else []
    if c["data"] and now - c["success_at"] < _SECTOR_INDEX_TTL:
        return c["data"]
    if now - c["checked_at"] < _SECTOR_INDEX_FAILURE_TTL:
        return last_good  # a fetch just failed; don't retry yet

    c["checked_at"] = now
    rows = await asyncio.get_event_loop().run_in_executor(None, _fetch_sector_indices_sync)
    if rows:
        c.update(success_at=now, data=rows)
        return rows
    return last_good


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
    """Real aggregation for sector landing pages (SEO Phase 2, §2.1) —
    constituent stocks (existing /stocks logic) plus real opportunities
    and events whose own `sectors` field overlaps this sector's name. No
    new intelligence generated here: every field is a read of data that
    already exists elsewhere in the app, filtered by sector — same
    word-overlap matching pattern as context_pulse.py's
    _find_related_opportunity, reused rather than reinvented.

    Content-integrity repair (2026-09-22): no longer reads the
    fabricated `SectorData` table at all — `value`/`positive` are now
    always None for every sector (the same honest state Defence/
    Chemicals/Telecom/Finance already returned before this repair, when
    they had real stock/opportunity/event data but no SectorData
    momentum row). No replacement momentum source is substituted; a real
    sector index feed is Data Foundation-phase work."""
    from sqlalchemy import select
    from app.core.config import settings
    from app.db.models.event import Event
    from app.db.models.opportunity import Opportunity

    key = _norm(sector_id)
    if key not in _SECTOR_STOCKS:
        # No real constituent-stock backing for this id at all — an
        # honest 404, not a page with nothing real to show. (Previously
        # some of these ids — e.g. "media", "psu-bank", "pvt-bank" —
        # rendered a page anyway, backed only by the fabricated
        # SectorData row; that row is exactly what this repair removes.)
        raise HTTPException(status_code=404, detail=f"Sector '{sector_id}' not found")
    sector_name = _SECTOR_NAMES.get(key, key.replace("-", " ").title())
    sector_value, sector_positive = None, None

    stocks = await _get_sector_stocks_cached(key)
    target_words = _sector_words(sector_name) | _sector_words(sector_id.replace("-", " "))

    # Batch E consumer migration, 2026-08-24 — dispatches on
    # settings.opportunity_v2_promoted. Both branches build `href`
    # server-side (never a raw id/slug pair the frontend has to guess how
    # to route — the exact class of bug already found and fixed on
    # CompanyIntelligenceSection.tsx) and a generic `score` field
    # (opportunity_score in V1, current_strength in V2 — same real
    # signal, real field per mode, no V1-shaped fake in V2 mode).
    opportunities = []
    if settings.opportunity_v2_promoted:
        from app.services.opportunity_v2.read_service import list_public_opportunities_v2
        page = await list_public_opportunities_v2(db, page=1, page_size=100)
        for o in page.items:
            opp_words = {w.lower() for s in (o.sectors_themes or []) for w in _sector_words(s)}
            if _words_overlap(target_words, opp_words):
                opportunities.append({"title": o.title, "href": f"/opportunity-radar/{o.slug}", "score": o.current_strength})
            if len(opportunities) >= 6:
                break
    else:
        opp_rows = (await db.execute(
            select(Opportunity).order_by(Opportunity.opportunity_score.desc()).limit(60)
        )).scalars().all()
        for o in opp_rows:
            opp_words = {w.lower() for s in (o.sectors or []) for w in _sector_words(s)}
            if _words_overlap(target_words, opp_words):
                opportunities.append({"title": o.title, "href": f"/opportunity-radar/{o.id}", "score": o.opportunity_score})
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
                "id": e.id, "slug": e.slug or "", "title": e.title, "impact_score": e.impact_score,
                "date": (e.event_date or e.published_at).isoformat() if (e.event_date or e.published_at) else None,
            })
        if len(events) >= 6:
            break

    return {
        "id": sector_id.lower(), "name": sector_name,
        "value": sector_value, "positive": sector_positive,
        "stocks": stocks, "opportunities": opportunities, "events": events,
    }

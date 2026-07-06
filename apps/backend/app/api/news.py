from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_news
from app.schemas.news import NewsArticle
from app.services.news_fetcher import get_live_news, get_cached_article

router = APIRouter()

_SECTOR_MAP: list[tuple[str, list[str]]] = [
    ("rbi",            ["Banking", "Monetary Policy"]),
    ("sebi",           ["Capital Markets", "Regulation"]),
    ("defence",        ["Defence", "Aerospace"]),
    ("crude",          ["Energy"]),
    ("oil",            ["Energy", "FMCG"]),
    ("nifty",          ["Equity", "Index"]),
    ("sensex",         ["Equity", "Index"]),
    ("inflation",      ["Macro", "FMCG"]),
    ("ipo",            ["Capital Markets"]),
    ("results",        ["Corporate Earnings"]),
    ("earnings",       ["Corporate Earnings"]),
    ("ebitda",         ["Corporate Earnings"]),
    ("profit",         ["Corporate Earnings"]),
    ("merger",         ["Corporate Action"]),
    ("acquisition",    ["Corporate Action"]),
    ("deal",           ["Corporate Action"]),
    ("contract",       ["Corporate Action", "Infrastructure"]),
    ("railway",        ["Infrastructure"]),
    ("infrastructure", ["Infrastructure"]),
    ("port",           ["Infrastructure"]),
    ("vizhinjam",      ["Infrastructure"]),
    ("shipping",       ["Infrastructure"]),
    ("airport",        ["Infrastructure"]),
    ("highway",        ["Infrastructure"]),
    ("pharma",         ["Pharmaceuticals"]),
    ("banking",        ["Banking"]),
    ("budget",         ["Macro", "Government"]),
    ("gdp",            ["Macro"]),
    ("rupee",          ["Currency"]),
    ("fii",            ["Institutional Flow"]),
    ("dividend",       ["Corporate Action"]),
    ("buyback",        ["Corporate Action"]),
    ("fmcg",           ["FMCG"]),
    ("auto",           ["Automotive"]),
    ("real estate",    ["Real Estate"]),
    ("it sector",      ["Technology"]),
    ("technology",     ["Technology"]),
    ("software",       ["Technology"]),
    ("power",          ["Energy", "Infrastructure"]),
    ("steel",          ["Metals"]),
    ("metal",          ["Metals"]),
    ("cement",         ["Infrastructure"]),
    ("telecom",        ["Telecommunications"]),
    ("adani",          ["Infrastructure"]),
    ("tata",           ["Corporate Action"]),
]

def _derive_sectors(headline: str) -> list[str]:
    h = headline.lower()
    seen: set[str] = set()
    result: list[str] = []
    for kw, secs in _SECTOR_MAP:
        if kw in h:
            for s in secs:
                if s not in seen:
                    seen.add(s)
                    result.append(s)
    return result[:4] or ["Indian Markets"]


def _norm(v) -> float:
    """Normalise news impact_score from 0-10 → 0-100."""
    return round(float(v or 0) * 10, 1)


def _row_to_schema(r) -> NewsArticle:
    return NewsArticle(
        id=r.id,
        headline=r.headline,
        summary=r.summary,
        source=r.source,
        published_at=r.published_at,
        companies=r.companies or [],
        impact_score=_norm(r.impact_score),
        url=None,
        sectors=_derive_sectors(r.headline),
    )


def _dict_to_schema(a: dict) -> NewsArticle:
    return NewsArticle(
        id=a["id"],
        headline=a["headline"],
        summary=a["summary"],
        source=a["source"],
        published_at=a["published_at"],
        companies=a.get("companies", []),
        impact_score=_norm(a.get("impact_score", 7.0)),
        url=a.get("url") or None,
        sectors=_derive_sectors(a["headline"]),
    )


@router.get("/{article_id}/market-data")
async def get_news_market_data(article_id: str, db: AsyncSession = Depends(get_db)):
    """Real-time market status + sector-relevant index quotes for this article."""
    from app.services.market_data import get_market_status, get_event_market_indices

    # Resolve headline to derive sectors
    headline = ""
    cached = get_cached_article(article_id)
    if cached:
        headline = cached.get("headline", "")
    else:
        await get_live_news(limit=20)
        cached = get_cached_article(article_id)
        if cached:
            headline = cached.get("headline", "")
        else:
            from sqlalchemy import select
            from app.db.models_legacy import NewsArticle as NewsArticleModel
            result = await db.execute(
                select(NewsArticleModel).where(NewsArticleModel.id == article_id)
            )
            row = result.scalar_one_or_none()
            if row:
                headline = row.headline or ""

    sectors = _derive_sectors(headline) if headline else ["Indian Markets"]
    market_status = get_market_status()
    indices = await get_event_market_indices(sectors)

    from app.services.market_data import _SECTOR_INDEX_MAP
    _ICON: dict[str, str] = {
        "Banking": "bank", "Monetary Policy": "policy", "Capital Markets": "markets",
        "Regulation": "law", "Defence": "defence", "Aerospace": "aerospace",
        "Energy": "energy", "FMCG": "fmcg", "Equity": "equity", "Index": "index",
        "Macro": "macro", "Government": "govt", "Corporate Earnings": "earnings",
        "Corporate Action": "action", "Infrastructure": "infra",
        "Pharmaceuticals": "pharma", "Automotive": "auto", "Real Estate": "realty",
        "Technology": "tech", "Currency": "currency", "Institutional Flow": "flow",
        "Metals": "metals", "Telecommunications": "telecom", "Indian Markets": "india",
    }

    sector_details = []
    for sector in sectors:
        key = sector.lower().strip()
        matched_ticker = "^NSEI"
        matched_iname = "Nifty 50"
        for kw, (iname, ticker) in _SECTOR_INDEX_MAP.items():
            if kw in key:
                matched_ticker = ticker
                matched_iname = iname
                break
        idx_data = (
            next((i for i in indices if i["ticker"] == matched_ticker), None)
            or next((i for i in indices if "50" in i["name"]), None)
            or (indices[0] if indices else None)
        )
        pct = idx_data["pct_change"] if idx_data else 0.0
        impact = "High" if abs(pct) >= 1.5 else "Medium" if abs(pct) >= 0.5 else "Low"
        sector_details.append({
            "sector": sector,
            "icon": _ICON.get(sector, "pin"),
            "indexName": matched_iname,
            "indexTicker": matched_ticker,
            "value": idx_data["value"] if idx_data else "—",
            "pct_change": pct,
            "positive": idx_data["positive"] if idx_data else True,
            "change_str": idx_data["change_str"] if idx_data else "—",
            "impactLevel": impact,
        })

    return {
        "marketStatus": market_status,
        "marketIndices": indices,
        "sectors": sectors,
        "sectorDetails": sector_details,
    }


@router.get("/", response_model=list[NewsArticle])
async def list_news(db: AsyncSession = Depends(get_db)):
    live = await get_live_news(limit=20)
    if live:
        return [_dict_to_schema(a) for a in live]
    rows = await get_news(db)
    return [_row_to_schema(r) for r in rows]


@router.get("/{article_id}", response_model=NewsArticle)
async def get_news_article(article_id: str, db: AsyncSession = Depends(get_db)):
    # Try live cache first
    cached = get_cached_article(article_id)
    if cached:
        return _dict_to_schema(cached)

    # Trigger a fetch to warm the cache, then retry
    await get_live_news(limit=20)
    cached = get_cached_article(article_id)
    if cached:
        return _dict_to_schema(cached)

    # Fall back to DB
    from sqlalchemy import select
    from app.db.models_legacy import NewsArticle as NewsArticleModel
    result = await db.execute(
        select(NewsArticleModel).where(NewsArticleModel.id == article_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _row_to_schema(row)

"""
DB search helpers and historical-precedent inference, shared by both AI
Search pipelines (V2: ai_search_service.py, V3: this package) — extracted
verbatim from ai_search_service.py during P5 Stage 1 (2026-08-06), zero
behavior change.
"""
from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import Event, GovernmentPolicy
from app.db.models_legacy import NewsArticle as NewsModel
from app.services.ai_search.regexes import _STOPWORDS
from app.services.news_fetcher import get_live_news


def _words(query: str) -> list[str]:
    return [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2 and w not in _STOPWORDS][:8]


def _event_row_to_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "summary": (e.summary or "")[:300],
        "category": e.category or "Market",
        "impact_score": round(float(e.impact_score or 0), 1),
        "confidence": round(float(e.confidence or 0), 1),
        "sectors": e.sectors or [],
        "companies": e.companies or [],
        "date": (
            e.event_date.strftime("%b %d, %Y") if e.event_date else
            e.published_at.strftime("%b %d, %Y") if e.published_at else ""
        ),
    }


async def _search_events(
    db: AsyncSession, query: str, limit: int = 10, entities: dict | None = None,
) -> list[dict]:
    ws = _words(query)
    symbols = [s for s in (entities or {}).get("companies", []) if s]

    # Entity-scoped filter first (P1 fix). Event.companies is a JSON list of
    # {"symbol": ..., "name": ..., "impact": ...} dicts — 93% coverage
    # (107/115 events) — NOT the relational EventCompany junction table,
    # which exists but is effectively unpopulated (1 row against 115 events)
    # and isn't what enrichment actually writes to today. ILIKE is anchored
    # on the `"symbol": "X"` key specifically, not a bare substring of the
    # whole JSON blob, so a different company's `name` field can't
    # accidentally satisfy this company's symbol match.
    if symbols:
        company_conds = [Event.companies.ilike(f'%"symbol": "{s}"%') for s in symbols]
        stmt = select(Event).where(or_(*company_conds)).order_by(Event.impact_score.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        if rows:
            return [_event_row_to_dict(e) for e in rows]
        # Resolved a company but nothing is tagged to it — fall through to
        # the word-match path below instead of returning nothing.

    conds = [Event.title.ilike(f"%{w}%") for w in ws] + [Event.summary.ilike(f"%{w}%") for w in ws]
    stmt = (
        select(Event).where(or_(*conds)).order_by(Event.impact_score.desc()).limit(limit)
        if conds else
        select(Event).order_by(Event.impact_score.desc()).limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_event_row_to_dict(e) for e in rows]


def _symbols_to_names(symbols: list[str]) -> list[str]:
    from app.api.companies import _NSE_UNIVERSE
    by_symbol = {co["symbol"]: co["name"] for co in _NSE_UNIVERSE}
    return [by_symbol[s] for s in symbols if s in by_symbol]


async def _search_news(
    db: AsyncSession, query: str, limit: int = 8, entities: dict | None = None,
) -> list[dict]:
    ws = _words(query)

    def _matches(text: str) -> bool:
        t = text.lower()
        return any(w in t for w in ws)

    results: list[dict] = []
    try:
        # get_live_news() carries no entity/company field at all — only
        # headline/summary text — so this primary path can only benefit
        # from P1's stopword filtering (via _words()/_matches() above), not
        # entity-scoped filtering. Tagging the live RSS/yfinance cache with
        # resolved entities is a real data-pipeline project, not a
        # retrieval-layer fix — flagged as backlog, not attempted here.
        live = await get_live_news(limit=20) or []
        for a in live:
            if _matches(a.get("headline", "") + " " + a.get("summary", "")):
                results.append({
                    "id": a["id"], "headline": a["headline"],
                    "summary": (a.get("summary") or "")[:200],
                    "source": a.get("source", ""), "published_at": a.get("published_at", ""),
                    "impact_score": float(a.get("impact_score", 5.0)),
                    "url": a.get("url"),
                })
    except Exception:
        pass

    if len(results) < limit:
        # DB fallback: NewsArticle.companies is a JSON list of plain NAME
        # strings (not {symbol,name} dicts like Event.companies), 7%
        # coverage (161/2,248 rows) — so entity-scoped filtering here
        # matches by company name, resolved from the entity symbol via the
        # same NSE universe lookup _match_companies uses.
        symbols = [s for s in (entities or {}).get("companies", []) if s]
        names = _symbols_to_names(symbols)
        db_rows = []
        if names:
            name_conds = [NewsModel.companies.ilike(f'%"{n}"%') for n in names]
            stmt = (
                select(NewsModel).where(or_(*name_conds))
                .order_by(NewsModel.impact_score.desc()).limit(limit)
            )
            db_rows = (await db.execute(stmt)).scalars().all()

        if not db_rows and ws:
            conds = [NewsModel.headline.ilike(f"%{w}%") for w in ws]
            # P1 fix: this query had no .order_by() at all before — rows
            # came back in whatever order SQLite happened to return them,
            # not by relevance or any other defined criterion.
            stmt = (
                select(NewsModel).where(or_(*conds))
                .order_by(NewsModel.impact_score.desc()).limit(limit)
            )
            db_rows = (await db.execute(stmt)).scalars().all()

        for r in db_rows:
            if not any(x["id"] == r.id for x in results):
                results.append({
                    "id": r.id, "headline": r.headline,
                    "summary": (r.summary or "")[:200],
                    "source": r.source, "published_at": r.published_at,
                    "impact_score": float(r.impact_score or 5.0) * 10,
                    "url": None,
                })

    return results[:limit]


async def _search_policies(
    db: AsyncSession, query: str, limit: int = 5, entities: dict | None = None,
) -> list[dict]:
    # entities accepted for call-site consistency with _search_events/
    # _search_news (P1) but not used to filter — GovernmentPolicy has no
    # company/sector column, only ministry/title text.
    ws = _words(query)
    conds = [GovernmentPolicy.title.ilike(f"%{w}%") for w in ws]
    stmt = (
        select(GovernmentPolicy).where(or_(*conds)).limit(limit)
        if conds else
        select(GovernmentPolicy).limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": p.id, "title": p.title,
            "ministry": p.ministry or "Ministry of Finance",
            "summary": (p.summary or "")[:200],
            "status": "Active", "impact_score": 75, "url": p.url,
        }
        for p in rows
    ]


# Canonical vocabulary used by historical_memory_service's seed table — live
# events only ever carry event_type="macro", which never matches this, so
# historical comparison must be inferred from the query text itself instead.
_HIST_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Monetary Policy":       ("rbi", "repo rate", "interest rate", "rate cut", "rate hike", "monetary policy"),
    "Union Budget":          ("union budget", "budget 20", "capex outlay", "fiscal budget", "finance bill", "budget capex", "the budget", "latest budget", "budget announcement", "budget spending"),
    "Infrastructure Policy": ("pli scheme", "production-linked incentive", "infrastructure policy", "production linked"),
    "Geopolitical":          ("war", "geopolitical", "sanctions", "conflict", "border tension", "pakistan", "ukraine", "military"),
    "Global Market Shock":   ("global market", "recession", "financial crisis", "bankruptcy", "fed taper", "contagion", "circuit breaker"),
    "Corporate Crisis":      ("fraud", "default", "scam", "corporate crisis", "insolvency", "moratorium"),
    "Commodity Shock":       ("crude", "oil price", "commodity shock", "gold price", "wti"),
    "Election":              ("election", "lok sabha", "poll result", "government formation"),
    "Regulatory":            ("gst", "regulation", "sebi", "compliance", "regulatory", "demonetization", "demonetisation"),
    "Trade Policy":          ("trade deal", "tariff", "import duty", "export ban"),
}
_HIST_SECTOR_NAMES = [
    "PSU Banks", "Housing Finance", "Capital Markets", "Capital Goods", "Specialty Chemicals",
    "Consumer Durables", "Real Estate", "Oil & Gas", "Banking", "NBFC", "Defence", "Infrastructure",
    "Metal", "Cement", "Auto", "Retail", "FMCG", "Aviation", "Railway", "PSU", "Pharma",
    "Electronics", "Textile", "Telecom", "Media", "Ports", "Utilities", "Jewellery", "Hotels",
    "Fertilizers", "Paints", "Tyres", "Financials", "Consumer", "Tourism", "Logistics", "Finance",
]


def _infer_historical_category(query_lower: str) -> str | None:
    for category, keywords in _HIST_CATEGORY_KEYWORDS.items():
        if any(k in query_lower for k in keywords):
            return category
    return None


def _infer_historical_sectors(query_lower: str) -> list[str]:
    return [s for s in _HIST_SECTOR_NAMES if s.lower() in query_lower]

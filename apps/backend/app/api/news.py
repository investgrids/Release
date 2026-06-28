from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_news
from app.schemas.news import NewsArticle
from app.services.news_fetcher import get_live_news, get_cached_article

router = APIRouter()


def _row_to_schema(r) -> NewsArticle:
    return NewsArticle(
        id=r.id,
        headline=r.headline,
        summary=r.summary,
        source=r.source,
        published_at=r.published_at,
        companies=r.companies or [],
        impact_score=r.impact_score,
        url=None,
    )


def _dict_to_schema(a: dict) -> NewsArticle:
    return NewsArticle(
        id=a["id"],
        headline=a["headline"],
        summary=a["summary"],
        source=a["source"],
        published_at=a["published_at"],
        companies=a.get("companies", []),
        impact_score=a.get("impact_score", 7.0),
        url=a.get("url") or None,
    )


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
    from app.db.models import NewsArticle as NewsArticleModel
    result = await db.execute(
        select(NewsArticleModel).where(NewsArticleModel.id == article_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _row_to_schema(row)

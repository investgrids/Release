"""Read-only data-quality check: does the news table persist RELATIVE published_at strings ("9m ago"), which the freshness filter then reads as brand-new forever? No writes, no provider calls."""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import func, select  # noqa: E402

from app.db.models_legacy import NewsArticle  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.ai_search.evidence_filter import age_days  # noqa: E402


async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(NewsArticle).where(NewsArticle.headline.ilike("%surprise exit%")))).scalars().all()
        for r in rows:
            print("CEO-exit row | created_at:", r.created_at, "| published_at:", repr(r.published_at), "| company tag:", r.companies, "| age the filter computes (days):", age_days(r.published_at), "|", r.headline[:80])
        tot = (await db.execute(select(func.count()).select_from(NewsArticle))).scalar()
        rel = (await db.execute(select(func.count()).select_from(NewsArticle).where(NewsArticle.published_at.like("%ago")))).scalar()
        print("news_articles total:", tot, "| rows whose published_at is relative ('... ago'):", rel)
        rel_rows = (await db.execute(select(NewsArticle).where(NewsArticle.published_at.like("%ago")).order_by(NewsArticle.created_at.asc()).limit(5))).scalars().all()
        for r in rel_rows:
            print("  oldest relative row | created_at:", r.created_at, "| published_at:", repr(r.published_at), "|", r.headline[:70])
        newest = (await db.execute(select(func.max(NewsArticle.created_at)))).scalar()
        print("newest created_at in news_articles:", newest)


asyncio.run(main())

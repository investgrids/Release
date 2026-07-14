from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db import models_legacy as models


async def get_events(db: AsyncSession, limit: int = 20, sort_by: str = "published_at"):
    if sort_by == "impact_score":
        order = models.Event.impact_score.desc()
    else:
        order = models.Event.published_at.desc()
    result = await db.execute(
        select(models.Event).order_by(order).limit(limit)
    )
    return result.scalars().all()


async def get_news(db: AsyncSession, limit: int = 20):
    result = await db.execute(
        select(models.NewsArticle).order_by(models.NewsArticle.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


async def get_calendar(db: AsyncSession):
    result = await db.execute(select(models.CalendarEvent))
    return result.scalars().all()


async def get_radar(db: AsyncSession):
    result = await db.execute(
        select(models.RadarOpportunity).order_by(models.RadarOpportunity.score.desc())
    )
    return result.scalars().all()


async def get_stories(db: AsyncSession):
    result = await db.execute(select(models.Story))
    return result.scalars().all()


async def get_sectors(db: AsyncSession):
    result = await db.execute(select(models.SectorData))
    return result.scalars().all()


async def get_trending_events(db: AsyncSession, limit: int = 5):
    result = await db.execute(
        select(models.Event)
        .order_by(models.Event.impact_score.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def count_rows(db: AsyncSession, model) -> int:
    result = await db.execute(select(func.count()).select_from(model))
    return result.scalar_one()


async def upsert_event(db: AsyncSession, data: dict):
    existing = await db.get(models.Event, data["id"])
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
    else:
        db.add(models.Event(**data))
    await db.commit()


async def bulk_insert(db: AsyncSession, records: list):
    """Insert a list of model instances, skipping duplicates by primary key."""
    for record in records:
        existing = await db.get(type(record), record.id)
        if not existing:
            db.add(record)
    await db.commit()

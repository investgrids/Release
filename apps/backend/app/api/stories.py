from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db import models_legacy as models
from app.db.crud import get_stories
from app.schemas.story import StoryCard, StoryDetail

router = APIRouter()


def _row_to_card(r) -> StoryCard:
    return StoryCard(
        id=r.id,
        title=r.title,
        description=r.description,
        theme=r.theme,
        image=r.image,
    )


def _row_to_detail(r) -> StoryDetail:
    return StoryDetail(
        id=r.id,
        slug=r.id,
        title=r.title,
        description=r.description,
        theme=r.theme,
        image=r.image,
    )


@router.get("/", response_model=list[StoryCard])
async def list_stories(db: AsyncSession = Depends(get_db)):
    rows = await get_stories(db)
    return [_row_to_card(r) for r in rows]


@router.get("/{slug}", response_model=StoryDetail)
async def get_story(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Story).where(models.Story.id == slug)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Story not found")
    return _row_to_detail(row)

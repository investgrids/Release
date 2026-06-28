from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_stories
from app.schemas.story import StoryCard

router = APIRouter()


@router.get("/", response_model=list[StoryCard])
async def list_stories(db: AsyncSession = Depends(get_db)):
    rows = await get_stories(db)
    return [
        StoryCard(
            id=r.id,
            title=r.title,
            description=r.description,
            theme=r.theme,
            image=r.image,
        )
        for r in rows
    ]

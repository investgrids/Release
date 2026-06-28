from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_calendar
from app.schemas.calendar import CalendarEvent

router = APIRouter()


@router.get("/", response_model=list[CalendarEvent])
async def list_calendar(db: AsyncSession = Depends(get_db)):
    rows = await get_calendar(db)
    return [
        CalendarEvent(
            id=r.id,
            category=r.category,
            title=r.title,
            date=r.date,
            description=r.description,
        )
        for r in rows
    ]

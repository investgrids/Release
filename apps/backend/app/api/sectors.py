from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_sectors

router = APIRouter()


@router.get("/", response_model=list[dict])
async def list_sectors(db: AsyncSession = Depends(get_db)):
    rows = await get_sectors(db)
    return [
        {"id": r.id, "name": r.name, "value": r.value, "positive": r.positive}
        for r in rows
    ]

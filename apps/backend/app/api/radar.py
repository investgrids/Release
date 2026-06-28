from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_radar
from app.schemas.radar import RadarOpportunity

router = APIRouter()


@router.get("/", response_model=list[RadarOpportunity])
async def list_radar(db: AsyncSession = Depends(get_db)):
    rows = await get_radar(db)
    return [
        RadarOpportunity(
            id=r.id,
            theme=r.theme,
            score=r.score,
            reason=r.reason,
            confidence=r.confidence,
            beneficiaries=r.beneficiaries or [],
        )
        for r in rows
    ]

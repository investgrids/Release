from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_events
from app.schemas.event import EventSummary, CompanyImpact

router = APIRouter()


@router.get("/", response_model=List[EventSummary])
async def list_events(db: AsyncSession = Depends(get_db)):
    rows = await get_events(db)
    result = []
    for e in rows:
        companies = [
            CompanyImpact(
                symbol=c.get("symbol", ""),
                name=c.get("name", ""),
                impact=c.get("impact", "Neutral"),
            )
            for c in (e.companies or [])
        ]
        result.append(
            EventSummary(
                id=e.id,
                title=e.title,
                summary=e.summary,
                impact_score=e.impact_score,
                confidence=e.confidence,
                sectors=e.sectors or [],
                companies=companies,
                date=e.published_at,
            )
        )
    return result

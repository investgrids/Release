from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import get_trending_events
from app.services.market_data import get_index_quotes

router = APIRouter()


@router.get("/", response_model=dict)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    index_quotes = await get_index_quotes()
    events = await get_trending_events(db, limit=5)

    trending = [
        {
            "id": e.id,
            "title": e.title,
            "summary": e.summary,
            "category": e.category or "Macro",
            "impact_score": e.impact_score,
            "confidence": e.confidence,
            "sectors": e.sectors,
            "companies": e.companies,
            "date": e.published_at.isoformat() if e.published_at else None,
        }
        for e in events
    ]

    market_snapshot = {}
    for q in index_quotes:
        key = q["title"].lower().replace(" ", "_")
        market_snapshot[key] = q["value"]

    return {
        "market_snapshot": market_snapshot,
        "index_quotes": index_quotes,
        "aiSummary": (
            "Markets opened positive across key indices. Defence and energy sectors lead gains "
            "following budget allocation revisions. IT sector under mild pressure from global "
            "demand concerns. RBI's rate hold supports banking sector sentiment."
        ),
        "trending_events": trending,
    }

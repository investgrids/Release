from fastapi import APIRouter, Query
from app.services.market_data import get_extended_indices, get_index_chart

router = APIRouter()


@router.get("/chart/{symbol}")
async def index_chart(symbol: str, period: str = Query("1M")):
    return await get_index_chart(symbol, period)


@router.get("/", response_model=list[dict])
async def list_indices():
    return await get_extended_indices()
